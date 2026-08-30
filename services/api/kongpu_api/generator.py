from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .plc_profiles import profile_for_target

GENERATOR_VERSION = "kongpu-st-v4"


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
        result = re.sub(rf"\b{re.escape(signal_id)}\b", signals[signal_id], result, flags=re.IGNORECASE)
    return result.replace(":=", "=")


def _satisfying_inputs(expression: str | None) -> dict[str, bool | int | float]:
    """Create a deterministic, conservative fixture for simple generated conditions."""
    text = str(expression or "TRUE")
    values: dict[str, bool | int | float] = {}
    comparisons = re.findall(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|>|<|=)\s*([-+]?\d+(?:\.\d+)?)",
        text,
    )
    for name, operator, raw in comparisons:
        number: int | float = float(raw) if "." in raw else int(raw)
        if operator == ">":
            number = number + 1
        elif operator == "<":
            number = number - 1
        values[name] = number
    excluded = {name for name, _operator, _raw in comparisons}
    for name in re.findall(r"\bNOT\s+([A-Za-z_][A-Za-z0-9_]*)\b", text, flags=re.I):
        if name.upper() not in {"TRUE", "FALSE"}:
            values[name] = False
            excluded.add(name)
    for name in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text):
        if name.upper() in {"TRUE", "FALSE", "AND", "OR", "NOT"} or name in excluded:
            continue
        values.setdefault(name, True)
    return values


@dataclass(frozen=True)
class GeneratedBundle:
    control_ir: dict[str, Any]
    files: dict[str, str]
    test_spec: dict[str, Any]
    trace_links: list[dict[str, Any]]
    warnings: list[dict[str, str]]


def build_control_ir(spec: dict[str, Any]) -> dict[str, Any]:
    profile = profile_for_target(spec.get("plc_target", {}))
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
    step_numbers = {str(item["id"]).casefold(): item["number"] for item in steps}
    for item in steps:
        item["next_step_number"] = step_numbers.get(str(item.get("next_step_id") or "").casefold(), 0)
    target = dict(spec.get("plc_target", {}))
    target.update(
        {
            "generator_profile": profile.profile_id,
            "adapter_id": profile.adapter_id,
            "vendor_tool": profile.vendor_tool,
            "vendor_compile_verified": False,
            "hardware_verified": False,
        }
    )
    return {
        "ir_version": "1.0",
        "generator_version": GENERATOR_VERSION,
        "target": target,
        "project": spec.get("project", {}),
        "components": sorted(spec.get("components", []), key=lambda row: row.get("component_id", "")),
        "signals": signals,
        "steps": steps,
        "interlocks": sorted(spec.get("interlocks", []), key=lambda row: row.get("interlock_id", "")),
        "exceptions": sorted(spec.get("exceptions", []), key=lambda row: row.get("exception_id", "")),
    }


def _render_gvl(ir: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    profile = profile_for_target(ir.get("target", {}))
    lines = [
        "VAR_GLOBAL",
        f"    // Generated from locked MachineSpec for {profile.brand} {profile.series}.",
        f"    // Vendor compile is unverified; review in {profile.vendor_tool} before use.",
    ]
    traces: list[dict[str, Any]] = []
    for signal in ir["signals"]:
        address = f" AT %{signal['address']}" if signal.get("address") and profile.direct_address_binding else ""
        logical_address = f" | logical address {signal['address']}" if signal.get("address") and not profile.direct_address_binding else ""
        lines.append(f"    {signal['name']}{address} : {signal['data_type']}; // {signal['display_name']}{logical_address}")
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
    profile = profile_for_target(ir.get("target", {}))
    lines = [
        "PROGRAM PRG_AutoCycle",
        f"// Deterministic Structured Text skeleton for profile {profile.profile_id}.",
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
    external_inputs = {
        str(signal.get("name"))
        for signal in ir.get("signals", [])
        if signal.get("name") and str(signal.get("direction") or "").upper() in {"DI", "AI", "COMM"}
    }

    def inputs_for(*expressions: str | None) -> dict[str, bool | int | float]:
        values: dict[str, bool | int | float] = {}
        for expression in expressions:
            values.update(_satisfying_inputs(expression))
        return {name: value for name, value in values.items() if name in external_inputs}

    tests = []
    for step in ir["steps"]:
        tests.append(
            {
                "id": f"TEST_{step['id']}",
                "source_step_id": step["id"],
                "inputs": inputs_for(step["entry_condition"], step["completion_condition"]),
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
                "inputs": inputs_for(exception.get("condition")),
                "given": exception.get("condition"),
                "when": "",
                "expect": exception.get("condition"),
            }
        )
    return {"version": "1.0", "target": ir["target"], "tests": tests}


def generate_bundle(spec: dict[str, Any]) -> GeneratedBundle:
    ir = build_control_ir(spec)
    profile = profile_for_target(ir.get("target", {}))
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
    control_ir_text = json.dumps(ir, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    test_spec_text = json.dumps(test_spec, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    files = {
        "src/GVL_IO.st": gvl,
        "src/PRG_AutoCycle.st": program,
        "generated/ControlIR.json": control_ir_text,
        "tests/TestSpec.json": test_spec_text,
        "README.md": (
            "# 控谱生成工作区\n\n"
            f"目标：{profile.brand} {profile.series} / {ir['target'].get('model')} / Structured Text。\n\n"
            f"生成 Profile：`{profile.profile_id}`；厂商 Adapter：`{profile.adapter_id}`。\n\n"
            f"本目录未经过 {profile.vendor_tool} 编译、厂商模拟或硬件验证，禁止直接用于真实 PLC 下载或生产。\n"
        ),
    }
    json_lines = control_ir_text.splitlines()
    test_lines = test_spec_text.splitlines()

    def line_of(lines: list[str], value: str) -> int | None:
        token = json.dumps(value, ensure_ascii=False)
        return next((index for index, line in enumerate(lines, start=1) if token in line), None)

    object_traces: list[dict[str, Any]] = []
    for entity_type, id_key, values in (
        ("component", "component_id", ir["components"]),
        ("interlock", "interlock_id", ir["interlocks"]),
        ("exception", "exception_id", ir["exceptions"]),
    ):
        for item in values:
            entity_id = str(item.get(id_key))
            source = item.get("source") or {}
            object_traces.append(
                {
                    "output_path": "generated/ControlIR.json",
                    "output_symbol": entity_id,
                    "output_line": line_of(json_lines, entity_id),
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "source_sheet": source.get("sheet"),
                    "source_row": source.get("row"),
                }
            )
    step_sources = {str(item.get("id")): item.get("source") or {} for item in ir["steps"]}
    exception_sources = {str(item.get("exception_id")): item.get("source") or {} for item in ir["exceptions"]}
    test_traces: list[dict[str, Any]] = []
    for test in test_spec["tests"]:
        source = step_sources.get(str(test.get("source_step_id"))) or exception_sources.get(str(test.get("source_exception_id"))) or {}
        test_id = str(test["id"])
        test_traces.append(
            {
                "output_path": "tests/TestSpec.json",
                "output_symbol": test_id,
                "output_line": line_of(test_lines, test_id),
                "entity_type": "test_case",
                "entity_id": test_id,
                "source_sheet": source.get("sheet"),
                "source_row": source.get("row"),
            }
        )
    return GeneratedBundle(
        ir,
        files,
        test_spec,
        signal_traces + step_traces + object_traces + test_traces,
        warnings,
    )
