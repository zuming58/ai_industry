from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


GENERATOR_VERSION = "fx5u-st-v1"


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def _st_name(identifier: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", identifier)
    if not value or value[0].isdigit():
        value = f"V_{value}"
    return value


def _st_type(data_type: str) -> str:
    allowed = {"BOOL", "INT", "DINT", "REAL", "WORD", "DWORD", "STRING"}
    normalized = str(data_type or "BOOL").upper()
    return normalized if normalized in allowed else "BOOL"


def _translate_expression(expression: str | None, signals: dict[str, str]) -> str:
    if not expression:
        return "TRUE"
    result = str(expression)
    for signal_id in sorted(signals, key=len, reverse=True):
        result = re.sub(rf"\b{re.escape(signal_id)}\b", signals[signal_id], result)
    return result.replace(":=", "=")


@dataclass(frozen=True)
class GeneratedBundle:
    control_ir: dict[str, Any]
    files: dict[str, str]
    test_spec: dict[str, Any]
    trace_links: list[dict[str, Any]]
    warnings: list[dict[str, str]]


def build_control_ir(spec: dict[str, Any]) -> dict[str, Any]:
    signals = [
        {
            "id": item["signal_id"],
            "name": _st_name(item["signal_id"]),
            "display_name": item.get("display_name") or item["signal_id"],
            "direction": item.get("direction"),
            "address": item.get("address"),
            "data_type": _st_type(item.get("data_type")),
            "unit": item.get("unit"),
            "component_id": item.get("component_id"),
            "source": item.get("source"),
        }
        for item in sorted(spec.get("signals", []), key=lambda row: row.get("signal_id", ""))
    ]
    signal_names = {item["id"]: item["name"] for item in signals}
    steps = []
    for index, item in enumerate(spec.get("sequence", []), start=1):
        steps.append(
            {
                "id": item["step_id"],
                "number": index * 10,
                "display_name": item.get("display_name") or item["step_id"],
                "entry_condition": _translate_expression(item.get("entry_condition"), signal_names),
                "actions": _translate_expression(item.get("actions"), signal_names),
                "completion_condition": _translate_expression(item.get("completion_condition"), signal_names),
                "next_step_id": item.get("next_step_id"),
                "duration": item.get("expected_duration"),
                "duration_unit": item.get("duration_unit"),
                "source": item.get("source"),
            }
        )
    step_numbers = {item["id"]: item["number"] for item in steps}
    for item in steps:
        item["next_step_number"] = step_numbers.get(item.get("next_step_id"), 0)
    return {
        "ir_version": "1.0",
        "generator_version": GENERATOR_VERSION,
        "target": spec.get("plc_target", {}),
        "project": spec.get("project", {}),
        "components": sorted(spec.get("components", []), key=lambda row: row.get("component_id", "")),
        "signals": signals,
        "steps": steps,
        "interlocks": sorted(spec.get("interlocks", []), key=lambda row: row.get("interlock_id", "")),
        "exceptions": sorted(spec.get("exceptions", []), key=lambda row: row.get("exception_id", "")),
    }


def _render_gvl(ir: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    lines = ["VAR_GLOBAL", "    // Generated from locked MachineSpec. Review in GX Works3 before use."]
    traces: list[dict[str, Any]] = []
    for signal in ir["signals"]:
        address = f" AT %{signal['address']}" if signal.get("address") else ""
        lines.append(f"    {signal['name']}{address} : {signal['data_type']}; // {signal['display_name']}")
        traces.append(
            {
                "output_path": "src/GVL_IO.st",
                "output_symbol": signal["name"],
                "output_line": len(lines),
                "entity_type": "signal",
                "entity_id": signal["id"],
                "source_sheet": (signal.get("source") or {}).get("sheet"),
                "source_row": (signal.get("source") or {}).get("row"),
            }
        )
    lines.extend(["    KP_ModeAuto : BOOL;", "    KP_CurrentStep : INT := 10;", "END_VAR", ""])
    return "\n".join(lines), traces


def _render_program(ir: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    lines = [
        "PROGRAM PRG_AutoCycle",
        "// Deterministic FX5U Structured Text skeleton.",
        "// Safety functions, PLC download, RUN/STOP and forced output are intentionally absent.",
        "CASE KP_CurrentStep OF",
    ]
    traces: list[dict[str, Any]] = []
    for step in ir["steps"]:
        lines.append(f"    {step['number']}: // {step['id']} - {step['display_name']}")
        trace_line = len(lines)
        lines.append(f"        // Entry: {step['entry_condition']}")
        lines.append(f"        // Actions: {step['actions']}")
        lines.append(f"        IF {step['completion_condition']} THEN")
        if step["next_step_number"]:
            lines.append(f"            KP_CurrentStep := {step['next_step_number']};")
        else:
            lines.append("            KP_CurrentStep := 0; // END")
        lines.extend(["        END_IF;", ""])
        source = step.get("source") or {}
        traces.append(
            {
                "output_path": "src/PRG_AutoCycle.st",
                "output_symbol": step["id"],
                "output_line": trace_line,
                "entity_type": "sequence_step",
                "entity_id": step["id"],
                "source_sheet": source.get("sheet"),
                "source_row": source.get("row"),
            }
        )
    lines.extend(["END_CASE;", "END_PROGRAM", ""])
    return "\n".join(lines), traces


def _build_test_spec(ir: dict[str, Any]) -> dict[str, Any]:
    tests = []
    for step in ir["steps"]:
        tests.append(
            {
                "id": f"TEST_{step['id']}",
                "source_step_id": step["id"],
                "given": step["entry_condition"],
                "when": step["actions"],
                "expect": step["completion_condition"],
            }
        )
    for exception in ir["exceptions"]:
        tests.append(
            {
                "id": f"TEST_{exception['exception_id']}",
                "source_exception_id": exception["exception_id"],
                "given": exception.get("condition"),
                "expect": exception.get("response"),
            }
        )
    return {"version": "1.0", "target": ir["target"], "tests": tests}


def generate_bundle(spec: dict[str, Any]) -> GeneratedBundle:
    ir = build_control_ir(spec)
    gvl, signal_traces = _render_gvl(ir)
    program, step_traces = _render_program(ir)
    test_spec = _build_test_spec(ir)
    warnings = []
    for exception in ir["exceptions"]:
        if not exception.get("operator_message"):
            warnings.append(
                {
                    "code": "OPERATOR_MESSAGE_TODO",
                    "message": f"{exception['exception_id']} 未填写操作员消息，已保留 TODO。",
                }
            )
    files = {
        "src/GVL_IO.st": gvl,
        "src/PRG_AutoCycle.st": program,
        "generated/ControlIR.json": json.dumps(ir, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        "tests/TestSpec.json": json.dumps(test_spec, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        "README.md": "# 控谱生成工作区\n\n目标：三菱 FX5U / Structured Text。\n\n本目录未经过 GX Works3 编译验证，禁止直接用于真实 PLC 下载。\n",
    }
    return GeneratedBundle(ir, files, test_spec, signal_traces + step_traces, warnings)
