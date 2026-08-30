from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any


MONITORING_SCHEMA_VERSION = "1"


class MonitoringInputError(ValueError):
    pass


def _fold_identifier(value: Any) -> str:
    return str(value or "").strip().casefold()


def _canonical_names(names: list[str] | set[str]) -> dict[str, str]:
    canonical: dict[str, str] = {}
    for raw in names:
        name = str(raw or "").strip()
        if not name:
            continue
        folded = _fold_identifier(name)
        existing = canonical.get(folded)
        if existing is not None and existing != name:
            raise MonitoringInputError(f"变量名称仅大小写不同，无法确定性解析: {existing}, {name}")
        canonical[folded] = name
    return canonical


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_variable_map(control_ir: dict[str, Any]) -> list[dict[str, Any]]:
    variables = []
    seen: dict[str, str] = {}
    for signal in sorted(
        control_ir.get("signals", []), key=lambda item: str(item.get("id") or "")
    ):
        name = str(signal.get("name") or "").strip()
        if not name:
            continue
        folded = _fold_identifier(name)
        existing = seen.get(folded)
        if existing is not None:
            if existing != name:
                raise MonitoringInputError(f"变量名称仅大小写不同，无法建立只读映射: {existing}, {name}")
            raise MonitoringInputError(f"变量名称重复: {name}")
        seen[folded] = name
        source = signal.get("source") or {}
        variables.append(
            {
                "name": name,
                "signal_id": str(signal.get("id") or signal.get("signal_id") or ""),
                "address": signal.get("address"),
                "data_type": signal.get("data_type"),
                "direction": signal.get("direction"),
                "source": {"sheet": source.get("sheet"), "row": source.get("row")},
                "access": "read_only",
            }
        )
    return variables


def variable_map_hash(variables: list[dict[str, Any]]) -> str:
    return _stable_hash(variables)


def target_fingerprint(
    *,
    project_id: str,
    plc_brand: str,
    plc_series: str,
    plc_model: str,
    candidate_manifest_hash: str,
    variables: list[dict[str, Any]],
) -> str:
    return _stable_hash(
        {
            "schema": f"kongpu-monitor-plan/v{MONITORING_SCHEMA_VERSION}",
            "project_id": project_id,
            "plc_brand": plc_brand,
            "plc_series": plc_series,
            "plc_model": plc_model,
            "candidate_manifest_hash": candidate_manifest_hash,
            "variable_map_hash": variable_map_hash(variables),
            "access": "read_only",
        }
    )


def analyze_snapshot(
    control_ir: dict[str, Any],
    variables: list[dict[str, Any]],
    values: dict[str, bool | int | float],
    current_step_id: str | None,
) -> dict[str, Any]:
    allowed = _canonical_names([str(item.get("name") or "") for item in variables])
    normalized_values: dict[str, bool | int | float] = {}
    duplicate_values: list[str] = []
    for raw_name, value in values.items():
        folded = _fold_identifier(raw_name)
        name = allowed.get(folded)
        if name is None:
            continue
        if name in normalized_values:
            duplicate_values.append(str(raw_name))
            continue
        if not isinstance(value, (bool, int, float)):
            raise MonitoringInputError(f"快照变量 {raw_name} 必须是布尔或数字")
        if isinstance(value, float) and not math.isfinite(value):
            raise MonitoringInputError(f"快照变量 {raw_name} 必须是有限数值")
        normalized_values[name] = value
    unknown = sorted(str(key) for key in values if _fold_identifier(key) not in allowed)
    if unknown:
        raise MonitoringInputError(
            "快照包含变量映射之外的名称: " + ", ".join(unknown)
        )
    if duplicate_values:
        raise MonitoringInputError(
            "快照包含仅大小写不同的重复变量: " + ", ".join(sorted(duplicate_values))
        )

    steps = {
        _fold_identifier(item.get("id")): item for item in control_ir.get("steps", []) if item.get("id")
    }
    if current_step_id and _fold_identifier(current_step_id) not in steps:
        raise MonitoringInputError(f"当前工步不存在: {current_step_id}")
    step = steps.get(_fold_identifier(current_step_id))
    condition = str((step or {}).get("completion_condition") or "")
    referenced = sorted(
        {
            token
            for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", condition)
            if token.upper() not in {"TRUE", "FALSE", "AND", "OR", "NOT"}
        }
    )
    value_names = _canonical_names(set(normalized_values))
    missing = sorted(name for name in referenced if _fold_identifier(name) not in value_names)
    relevant = {
        value_names[_fold_identifier(name)]: normalized_values[value_names[_fold_identifier(name)]]
        for name in referenced
        if _fold_identifier(name) in value_names
    }
    return {
        "schema": f"kongpu-monitor-evidence/v{MONITORING_SCHEMA_VERSION}",
        "status": "data_incomplete" if missing else "recorded_unverified",
        "verification_level": "manual_unverified",
        "current_step_id": step.get("id") if step else current_step_id,
        "waiting_condition": condition or None,
        "condition_values": relevant,
        "missing_condition_values": missing,
        "captured_variable_count": len(normalized_values),
        "claim_boundary": "离线快照只用于证据整理，不代表已连接 PLC，也不执行写入、RUN/STOP 或强制输出。",
    }
