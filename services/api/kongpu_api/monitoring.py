from __future__ import annotations

import hashlib
import json
import re
from typing import Any


MONITORING_SCHEMA_VERSION = "1"


class MonitoringInputError(ValueError):
    pass


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_variable_map(control_ir: dict[str, Any]) -> list[dict[str, Any]]:
    variables = []
    seen: set[str] = set()
    for signal in sorted(
        control_ir.get("signals", []), key=lambda item: str(item.get("id") or "")
    ):
        name = str(signal.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
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
    allowed = {item["name"] for item in variables}
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise MonitoringInputError(
            "快照包含变量映射之外的名称: " + ", ".join(unknown)
        )

    steps = {
        str(item.get("id")): item for item in control_ir.get("steps", []) if item.get("id")
    }
    if current_step_id and current_step_id not in steps:
        raise MonitoringInputError(f"当前工步不存在: {current_step_id}")
    step = steps.get(current_step_id or "")
    condition = str((step or {}).get("completion_condition") or "")
    referenced = sorted(
        {
            token
            for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", condition)
            if token.upper() not in {"TRUE", "FALSE", "AND", "OR", "NOT"}
        }
    )
    missing = sorted(name for name in referenced if name not in values)
    relevant = {name: values[name] for name in referenced if name in values}
    return {
        "schema": f"kongpu-monitor-evidence/v{MONITORING_SCHEMA_VERSION}",
        "status": "data_incomplete" if missing else "recorded_unverified",
        "verification_level": "manual_unverified",
        "current_step_id": current_step_id,
        "waiting_condition": condition or None,
        "condition_values": relevant,
        "missing_condition_values": missing,
        "captured_variable_count": len(values),
        "claim_boundary": "离线快照只用于证据整理，不代表已连接 PLC，也不执行写入、RUN/STOP 或强制输出。",
    }
