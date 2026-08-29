from __future__ import annotations

import re
from typing import Any

from .generator import GeneratedBundle, GENERATOR_VERSION, content_hash, stable_json


AUDIT_VERSION = "1"
_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_KNOWN_WORDS = {"TRUE", "FALSE", "AND", "OR", "NOT", "IF", "THEN", "END_IF", "END", "END_CASE", "CASE", "OF", "BOOL", "INT", "DINT", "REAL", "WORD", "DWORD", "STRING", "AT"}


def _line_for(entity_id: Any, bundle: GeneratedBundle) -> int | None:
    for link in bundle.trace_links:
        if link.get("entity_id") == entity_id:
            return link.get("output_line")
    return None


def _finding(code: str, severity: str, title: str, detail: str, *, file: str | None = None, line: int | None = None, entity_id: str | None = None, source: dict[str, Any] | None = None, action: str = "查看来源并在工作分支修订") -> dict[str, Any]:
    return {"code": code, "severity": severity, "title": title, "detail": detail, "file": file, "line": line, "entity_id": entity_id, "source": source, "action": action}


def _expression_identifiers(expression: Any) -> set[str]:
    return {item for item in _IDENTIFIER.findall(str(expression or "")) if item.upper() not in _KNOWN_WORDS}


def audit_bundle(spec: dict[str, Any], bundle: GeneratedBundle) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    signals = [item for item in bundle.control_ir.get("signals", []) if item.get("name")]
    signal_names = {str(item.get("name")) for item in signals}
    signal_by_address: dict[str, list[dict[str, Any]]] = {}
    for signal in signals:
        address = str(signal.get("address") or "").upper()
        if address:
            signal_by_address.setdefault(address, []).append(signal)
    for signal in bundle.control_ir.get("signals", []):
        if signal.get("name") in signal_names and sum(1 for item in bundle.control_ir["signals"] if item.get("name") == signal.get("name")) > 1:
            findings.append(_finding("DUPLICATE_ST_SYMBOL", "blocker", "ST 符号重复", f"变量 {signal.get('name')} 在生成变量表中重复。", file="src/GVL_IO.st", line=_line_for(signal.get("id"), bundle), entity_id=signal.get("id"), source=signal.get("source")))
        if signal.get("address") and not re.fullmatch(r"[XYM][0-9A-F]+", str(signal["address"]), re.IGNORECASE):
            findings.append(_finding("INVALID_IO_ADDRESS", "blocker", "I/O 地址格式异常", f"{signal.get('id')} 的地址 {signal.get('address')} 不符合 FX5U 基本地址格式。", file="src/GVL_IO.st", line=_line_for(signal.get("id"), bundle), entity_id=signal.get("id"), source=signal.get("source")))
        if signal.get("data_type") in {"INT", "DINT", "REAL", "WORD", "DWORD"} and not signal.get("unit"):
            findings.append(_finding("SIGNAL_UNIT_MISSING", "warning", "数值信号缺少单位", f"信号 {signal.get('id')} 是数值类型但没有单位，不能可靠解释量程或超时。", file="src/GVL_IO.st", line=_line_for(signal.get("id"), bundle), entity_id=signal.get("id"), source=signal.get("source"), action="在 Signals 填写 unit 后重新生成"))
    for address, addressed in signal_by_address.items():
        if len(addressed) > 1:
            for signal in addressed:
                findings.append(_finding("DUPLICATE_IO_ADDRESS", "blocker", "I/O 地址重复", f"地址 {address} 同时分配给多个信号。", file="src/GVL_IO.st", line=_line_for(signal.get("id"), bundle), entity_id=signal.get("id"), source=signal.get("source"), action="为每个信号分配唯一地址"))
    target = bundle.control_ir.get("target") or spec.get("plc_target") or {}
    target_model = str(target.get("model") or target.get("plc_model") or "")
    target_brand = str(target.get("brand") or "")
    if "FX5U" not in target_model.upper() or (target_brand and "三菱" not in target_brand and "MITSUBISHI" not in target_brand.upper()):
        findings.append(_finding("TARGET_UNSUPPORTED", "blocker", "目标 PLC 与 M3 范围不一致", f"当前 M3 只审计三菱 FX5U，收到目标 {target_brand} {target_model}。", file="generated/ControlIR.json", action="切换到 FX5U 目标或等待后续 Adapter"))
    for step in bundle.control_ir.get("steps", []):
        expression = " ".join((step.get("entry_condition"), step.get("actions"), step.get("completion_condition")))
        unknown = sorted(item for item in _expression_identifiers(expression) if item not in signal_names and not item.startswith("KP_") and item not in {"TRUE", "FALSE"})
        for token in unknown:
            findings.append(_finding("UNDEFINED_ST_REFERENCE", "blocker", "生成物包含未定义引用", f"工步 {step.get('id')} 使用了未定义符号 {token}。", file="src/PRG_AutoCycle.st", line=_line_for(step.get("id"), bundle), entity_id=step.get("id"), source=step.get("source")))
    steps = bundle.control_ir.get("steps", [])
    ids = {str(item.get("id")) for item in steps}
    reachable: set[str] = set()
    current = str(steps[0].get("id")) if steps else None
    while current and current not in reachable:
        reachable.add(current)
        step = next((item for item in steps if item.get("id") == current), None)
        current = str(step.get("next_step_id")) if step and step.get("next_step_id") in ids else None
    for step in steps:
        if step.get("id") not in reachable:
            findings.append(_finding("UNREACHABLE_STEP", "blocker", "工步不可达", f"工步 {step.get('id')} 不在主流程可达路径上。", file="src/PRG_AutoCycle.st", line=_line_for(step.get("id"), bundle), entity_id=step.get("id"), source=step.get("source")))
    for step in steps:
        if step.get("next_step_id") and step.get("next_step_id") not in ids and step.get("next_step_id") != "END":
            findings.append(_finding("NEXT_STEP_MISSING", "blocker", "下一工步不存在", f"工步 {step.get('id')} 指向 {step.get('next_step_id')}。", file="src/PRG_AutoCycle.st", line=_line_for(step.get("id"), bundle), entity_id=step.get("id"), source=step.get("source")))
        if not step.get("duration") or not step.get("duration_unit"):
            findings.append(_finding("STEP_TIMEOUT_MISSING", "warning", "工步缺少完整超时参数", f"工步 {step.get('id')} 没有持续时间或单位，模拟无法判断超时。", file="src/PRG_AutoCycle.st", entity_id=step.get("id"), source=step.get("source"), action="在 Sequence 填写 expected_duration 与 duration_unit"))
    for start in ids:
        path: set[str] = set()
        current = start
        terminated = False
        while current in ids and current not in path:
            path.add(current)
            step = next(item for item in steps if str(item.get("id")) == current)
            next_id = str(step.get("next_step_id") or "END")
            if next_id == "END":
                terminated = True
                break
            current = next_id
        if not terminated and current in path:
            step = next(item for item in steps if str(item.get("id")) == current)
            findings.append(_finding("LOOP_NO_EXIT", "blocker", "流程循环没有退出条件", f"从工步 {start} 出发在 {current} 形成无退出循环。", file="src/PRG_AutoCycle.st", line=_line_for(current, bundle), entity_id=current, source=step.get("source"), action="增加可达 END 分支或明确受控退出条件"))
            break
    if not bundle.control_ir.get("interlocks"):
        findings.append(_finding("INTERLOCK_NOT_DEFINED", "warning", "未定义互锁", "当前规格没有 Interlocks 数据，普通控制骨架不会自动推断安全互锁。", action="补充互锁资料并重新生成"))
    else:
        interlock_actions = {str(item.get("action_id")) for item in bundle.control_ir.get("interlocks", []) if item.get("action_id")}
        for signal in signals:
            if str(signal.get("direction")) == "DO" and str(signal.get("id")) not in interlock_actions:
                findings.append(_finding("INTERLOCK_COVERAGE_MISSING", "warning", "输出未关联互锁", f"DO 信号 {signal.get('id')} 没有对应 Interlocks.action_id。", file="src/GVL_IO.st", line=_line_for(signal.get("id"), bundle), entity_id=signal.get("id"), source=signal.get("source"), action="补充该输出的互锁条件并重新生成"))
    signal_ids = {str(item.get("id")) for item in signals}
    if not any(token in signal_ids or token in {str(item.get("name")) for item in signals} for token in {"SIG_MODE_AUTO", "MODE_AUTO", "KP_ModeAuto"}):
        findings.append(_finding("MODE_PATH_MISSING", "warning", "自动/手动模式路径未显式建模", "Control IR 没有可追溯的模式信号；生成骨架不能推断现场模式切换。", file="generated/ControlIR.json", action="在 Signals 增加自动/手动模式信号"))
    if not any("RESET" in value.upper() or "STOP" in value.upper() for value in signal_ids):
        findings.append(_finding("RESET_PATH_MISSING", "warning", "复位/停止路径未显式建模", "Control IR 没有名称包含 RESET 或 STOP 的信号；复位行为需由工程师补充。", file="generated/ControlIR.json", action="在 Signals 或 Exceptions 增加复位/停止信号"))
    for component in bundle.control_ir.get("components", []):
        template = str(component.get("control_template") or "").lower()
        if any(token in template for token in {"servo", "motion", "axis", "inverter"}) and template not in {"axis_handshake", "vfd_handshake"}:
            findings.append(_finding("UNSUPPORTED_MOTION_TEMPLATE", "warning", "运动控制模板未支持", f"组件 {component.get('component_id')} 使用未支持的控制模板 {template}。", file="generated/ControlIR.json", entity_id=component.get("component_id"), source=component.get("source"), action="改用已支持握手模板或等待 M3/M4 厂商验证"))
    for exception in bundle.control_ir.get("exceptions", []):
        if exception.get("timeout_value") and not exception.get("timeout_unit"):
            findings.append(_finding("EXCEPTION_TIMEOUT_UNIT_MISSING", "warning", "异常超时缺少单位", f"异常 {exception.get('exception_id')} 有超时数值但没有单位。", file="tests/TestSpec.json", entity_id=exception.get("exception_id"), source=exception.get("source"), action="补充 timeout_unit 后重新生成"))
    for exception in bundle.control_ir.get("exceptions", []):
        if not exception.get("operator_message"):
            findings.append(_finding("OPERATOR_MESSAGE_TODO", "warning", "报警文本待补充", f"{exception.get('exception_id')} 未填写操作员消息。", file="tests/TestSpec.json", entity_id=exception.get("exception_id"), source=exception.get("source"), action="补充 operator_message 后重新生成"))
    program = bundle.files.get("src/PRG_AutoCycle.st", "")
    if not program.startswith("PROGRAM") or "END_PROGRAM" not in program:
        findings.append(_finding("ST_PROGRAM_BOUNDARY", "blocker", "ST 程序边界异常", "未找到完整 PROGRAM/END_PROGRAM 边界。", file="src/PRG_AutoCycle.st"))
    # Ignore comments when checking prohibited runtime operations. The generated
    # safety banner intentionally mentions download/forced output as excluded.
    executable_st = "\n".join(line.split("//", 1)[0] for line in program.splitlines())
    if "FORCED_OUTPUT" in executable_st.upper() or re.search(r"\bDOWNLOAD\s*\(", executable_st, re.IGNORECASE):
        findings.append(_finding("FORBIDDEN_CONTROL_OPERATION", "blocker", "发现禁止的控制操作", "生成物包含下载或强制输出关键字，已阻断。", file="src/PRG_AutoCycle.st", action="删除危险操作并重新生成"))
    input_hash = content_hash(stable_json({"generator_version": GENERATOR_VERSION, "files": bundle.files}))
    status = "blocked" if any(item["severity"] == "blocker" for item in findings) else "review_ready"
    return {"audit_version": AUDIT_VERSION, "input_hash": input_hash, "status": status, "findings": findings, "summary": {"total": len(findings), "blocker": sum(item["severity"] == "blocker" for item in findings), "warning": sum(item["severity"] == "warning" for item in findings)}}
