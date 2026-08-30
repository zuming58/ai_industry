from __future__ import annotations

import json
import re
from typing import Any

from .generator import GeneratedBundle, GENERATOR_VERSION, content_hash, stable_json
from .plc_profiles import TargetProfileError, profile_for_target


AUDIT_VERSION = "2"
_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_KNOWN_WORDS = {"TRUE", "FALSE", "AND", "OR", "NOT", "IF", "THEN", "END_IF", "END", "END_CASE", "CASE", "OF", "BOOL", "INT", "DINT", "REAL", "WORD", "DWORD", "STRING", "AT"}
_REQUIRED_FILES = {
    "src/GVL_IO.st",
    "src/PRG_AutoCycle.st",
    "generated/ControlIR.json",
    "tests/TestSpec.json",
    "README.md",
}


def _line_for(entity_id: Any, bundle: GeneratedBundle) -> int | None:
    folded = _fold_identifier(entity_id)
    for link in bundle.trace_links:
        if _fold_identifier(link.get("entity_id")) == folded:
            return link.get("output_line")
    return None


def _finding(code: str, severity: str, title: str, detail: str, *, file: str | None = None, line: int | None = None, entity_id: str | None = None, source: dict[str, Any] | None = None, action: str = "查看来源并在工作分支修订") -> dict[str, Any]:
    return {"code": code, "severity": severity, "title": title, "detail": detail, "file": file, "line": line, "entity_id": entity_id, "source": source, "action": action}


def _expression_identifiers(expression: Any) -> set[str]:
    return {item for item in _IDENTIFIER.findall(str(expression or "")) if item.upper() not in _KNOWN_WORDS}


def _fold_identifier(value: Any) -> str:
    """Return the IEC/ST identifier comparison form.

    IEC 61131-3 identifiers are case-insensitive. Keep the original spelling
    in diagnostics, but use case-folded values for all reference and duplicate
    checks so a vendor-style spelling cannot bypass the audit.
    """
    return str(value or "").strip().casefold()


def _strip_st_non_executable(text: str) -> str:
    """Remove ST comments and string contents while preserving line positions."""
    output: list[str] = []
    index = 0
    state = "code"
    block_end = ""
    while index < len(text):
        current = text[index]
        following = text[index : index + 2]
        if state == "code":
            if following == "//":
                state = "line_comment"
                output.extend("  ")
                index += 2
                continue
            if following in {"(*", "/*"}:
                state = "block_comment"
                block_end = "*)" if following == "(*" else "*/"
                output.extend("  ")
                index += 2
                continue
            if current in {"'", '"'}:
                state = f"string:{current}"
                output.append(" ")
                index += 1
                continue
            output.append(current)
            index += 1
            continue
        if state == "line_comment":
            if current == "\n":
                state = "code"
                output.append(current)
            else:
                output.append(" ")
            index += 1
            continue
        if state == "block_comment":
            if following == block_end:
                state = "code"
                output.extend("  ")
                index += 2
            else:
                output.append("\n" if current == "\n" else " ")
                index += 1
            continue
        quote = state[-1]
        if current == quote:
            if text[index : index + 2] == quote * 2:
                output.extend("  ")
                index += 2
            else:
                state = "code"
                output.append(" ")
                index += 1
        else:
            output.append("\n" if current == "\n" else " ")
            index += 1
    return "".join(output)


def audit_bundle(spec: dict[str, Any], bundle: GeneratedBundle) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    target = bundle.control_ir.get("target") or spec.get("plc_target") or {}
    target_profile = None
    try:
        target_profile = profile_for_target(target)
    except TargetProfileError as exc:
        findings.append(_finding("TARGET_UNSUPPORTED", "blocker", "目标 PLC 不受生成器支持", str(exc), file="generated/ControlIR.json", action="选择兼容矩阵中列出的目标并重新生成"))
    for path in sorted(_REQUIRED_FILES):
        if path not in bundle.files:
            findings.append(_finding("GENERATED_FILE_MISSING", "blocker", "生成文件缺失", f"生成物缺少必需文件 {path}。", file=path, action="重新运行确定性生成并核对工件清单"))
        elif not str(bundle.files[path]).strip():
            findings.append(_finding("GENERATED_FILE_EMPTY", "blocker", "生成文件为空", f"生成文件 {path} 没有内容。", file=path, action="重新运行确定性生成并检查生成器错误"))

    parsed_ir: dict[str, Any] | None = None
    parsed_test_spec: dict[str, Any] | None = None
    for path, expected, code in (
        ("generated/ControlIR.json", bundle.control_ir, "CONTROL_IR_JSON_INVALID"),
        ("tests/TestSpec.json", bundle.test_spec, "TEST_SPEC_JSON_INVALID"),
    ):
        raw = bundle.files.get(path)
        if raw is None:
            continue
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            findings.append(_finding(code, "blocker", "生成 JSON 无法解析", f"{path} 不是有效 JSON。", file=path, action="重新生成并保留失败输入用于回归"))
            continue
        if not isinstance(parsed, dict):
            findings.append(_finding(code, "blocker", "生成 JSON 顶层类型错误", f"{path} 顶层必须是对象。", file=path, action="修复生成器 JSON 契约"))
            continue
        if stable_json(parsed) != stable_json(expected):
            findings.append(_finding("CONTROL_IR_CONTENT_MISMATCH" if path.startswith("generated/") else "TEST_SPEC_CONTENT_MISMATCH", "blocker", "内存模型与工件不一致", f"{path} 与本次审计使用的内存模型不一致。", file=path, action="禁止复用该工件并重新运行确定性生成"))
        if path.startswith("generated/"):
            parsed_ir = parsed
        else:
            parsed_test_spec = parsed

    if str(bundle.control_ir.get("ir_version")) != "1.0":
        findings.append(_finding("CONTROL_IR_VERSION_UNSUPPORTED", "blocker", "Control IR 版本不受支持", f"收到 {bundle.control_ir.get('ir_version')}，当前只支持 1.0。", file="generated/ControlIR.json", action="使用受支持的生成器重新生成"))
    if str(bundle.control_ir.get("generator_version")) != GENERATOR_VERSION:
        findings.append(_finding("GENERATOR_VERSION_MISMATCH", "blocker", "生成器版本不一致", f"Control IR 记录 {bundle.control_ir.get('generator_version')}，当前生成器为 {GENERATOR_VERSION}。", file="generated/ControlIR.json", action="使用当前生成器重新生成并创建新 Commit"))
    if str(bundle.test_spec.get("version")) != "1.0":
        findings.append(_finding("TEST_SPEC_VERSION_UNSUPPORTED", "blocker", "TestSpec 版本不受支持", f"收到 {bundle.test_spec.get('version')}，当前只支持 1.0。", file="tests/TestSpec.json", action="使用受支持的 TestSpec 生成器重新生成"))
    if stable_json(bundle.control_ir.get("target") or {}) != stable_json(bundle.test_spec.get("target") or {}):
        findings.append(_finding("TEST_SPEC_TARGET_MISMATCH", "blocker", "TestSpec 目标不一致", "TestSpec 与 Control IR 的 PLC 目标不同。", file="tests/TestSpec.json", action="从同一个锁定 MachineSpec 重新生成 Control IR 和 TestSpec"))
    if parsed_ir is not None and parsed_test_spec is not None and stable_json(parsed_ir.get("target") or {}) != stable_json(parsed_test_spec.get("target") or {}):
        findings.append(_finding("GENERATED_TARGET_MISMATCH", "blocker", "生成工件目标不一致", "已保存的 Control IR 与 TestSpec 目标不同。", file="tests/TestSpec.json", action="拒绝该工件并重新生成"))

    entity_groups = (
        ("component", "component_id", bundle.control_ir.get("components", [])),
        ("signal", "id", bundle.control_ir.get("signals", [])),
        ("sequence_step", "id", bundle.control_ir.get("steps", [])),
        ("interlock", "interlock_id", bundle.control_ir.get("interlocks", [])),
        ("exception", "exception_id", bundle.control_ir.get("exceptions", [])),
        ("test_case", "id", bundle.test_spec.get("tests", [])),
    )
    expected_entities: dict[tuple[str, str], str] = {}
    for entity_type, id_key, items in entity_groups:
        seen_ids: set[str] = set()
        for item in items:
            entity_id = str(item.get(id_key) or "").strip()
            file = "tests/TestSpec.json" if entity_type == "test_case" else "generated/ControlIR.json"
            if not entity_id:
                findings.append(_finding("STABLE_ID_MISSING", "blocker", "稳定 ID 缺失", f"{entity_type} 对象缺少 {id_key}。", file=file, source=item.get("source"), action="在源资料补充稳定 ID 后重新生成"))
                continue
            folded_id = _fold_identifier(entity_id)
            if folded_id in seen_ids:
                findings.append(_finding("STABLE_ID_DUPLICATE", "blocker", "稳定 ID 重复", f"{entity_type} 的稳定 ID {entity_id} 重复。", file=file, entity_id=entity_id, source=item.get("source"), action="修复重复 ID 后重新生成"))
            seen_ids.add(folded_id)
            expected_entities[(entity_type, folded_id)] = entity_id

    step_ids = {_fold_identifier(item.get("id")) for item in bundle.control_ir.get("steps", []) if item.get("id")}
    exception_ids = {_fold_identifier(item.get("exception_id")) for item in bundle.control_ir.get("exceptions", []) if item.get("exception_id")}
    signal_names_for_tests = {_fold_identifier(item.get("name")) for item in bundle.control_ir.get("signals", []) if item.get("name")}
    external_input_names = {
        _fold_identifier(item.get("name"))
        for item in bundle.control_ir.get("signals", [])
        if item.get("name") and str(item.get("direction") or "").upper() in {"DI", "AI", "COMM"}
    }
    for test in bundle.test_spec.get("tests", []):
        test_id = str(test.get("id") or "")
        source_step = test.get("source_step_id")
        source_exception = test.get("source_exception_id")
        if bool(source_step) == bool(source_exception):
            findings.append(_finding("TEST_SOURCE_INVALID", "blocker", "测试来源引用无效", f"测试 {test_id} 必须且只能引用一个工步或异常。", file="tests/TestSpec.json", entity_id=test_id, action="修复 TestSpec 来源引用并重新生成"))
        elif source_step and _fold_identifier(source_step) not in step_ids:
            findings.append(_finding("TEST_SOURCE_MISSING", "blocker", "测试引用工步不存在", f"测试 {test_id} 引用不存在的工步 {source_step}。", file="tests/TestSpec.json", entity_id=test_id, action="修复 source_step_id 后重新生成"))
        elif source_exception and _fold_identifier(source_exception) not in exception_ids:
            findings.append(_finding("TEST_SOURCE_MISSING", "blocker", "测试引用异常不存在", f"测试 {test_id} 引用不存在的异常 {source_exception}。", file="tests/TestSpec.json", entity_id=test_id, action="修复 source_exception_id 后重新生成"))
        expression = " ".join(str(test.get(key) or "") for key in ("given", "when", "expect"))
        unknown = sorted(item for item in _expression_identifiers(expression) if _fold_identifier(item) not in signal_names_for_tests)
        for token in unknown:
            findings.append(_finding("TEST_SIGNAL_UNKNOWN", "blocker", "测试使用未知信号", f"测试 {test_id} 使用了未知信号 {token}。", file="tests/TestSpec.json", entity_id=test_id, action="修复 TestSpec 信号引用后重新生成"))
        invalid_inputs = sorted(key for key in (test.get("inputs") or {}) if _fold_identifier(key) not in external_input_names)
        for token in invalid_inputs:
            findings.append(_finding("TEST_INPUT_DIRECTION_INVALID", "blocker", "测试输入方向无效", f"测试 {test_id} 将 {token} 作为外部输入，但只允许 DI、AI 或 COMM。", file="tests/TestSpec.json", entity_id=test_id, action="从 TestSpec 输入中移除输出或内部信号后重新生成"))

    trace_entities: set[tuple[str, str]] = set()
    for link in bundle.trace_links:
        entity_type = str(link.get("entity_type") or "")
        entity_id = str(link.get("entity_id") or "")
        trace_entities.add((entity_type, _fold_identifier(entity_id)))
        output_path = str(link.get("output_path") or "")
        output_line = link.get("output_line")
        if output_path not in bundle.files:
            findings.append(_finding("TRACE_OUTPUT_FILE_MISSING", "blocker", "追溯输出文件不存在", f"{entity_type} {entity_id} 指向不存在的文件 {output_path}。", file=output_path or None, entity_id=entity_id, action="重新生成追溯链接"))
        elif not isinstance(output_line, int) or output_line < 1 or output_line > len(bundle.files[output_path].splitlines()):
            findings.append(_finding("TRACE_OUTPUT_LINE_INVALID", "blocker", "追溯输出行号无效", f"{entity_type} {entity_id} 的输出行号 {output_line} 无效。", file=output_path, entity_id=entity_id, action="重新生成并校验输出行号"))
        if not link.get("source_sheet") or not isinstance(link.get("source_row"), int) or link.get("source_row") < 1:
            findings.append(_finding("TRACE_SOURCE_MISSING", "blocker", "Excel 来源追溯缺失", f"{entity_type} {entity_id} 缺少有效的工作表或行号。", file=output_path or None, line=output_line if isinstance(output_line, int) else None, entity_id=entity_id, action="补充源 Excel 定位后重新生成"))
    missing_trace_entities = sorted(set(expected_entities) - trace_entities)
    for entity_type, folded_id in missing_trace_entities:
        entity_id = expected_entities[(entity_type, folded_id)]
        findings.append(_finding("TRACE_LINK_MISSING", "blocker", "对象追溯链接缺失", f"{entity_type} {entity_id} 没有输出与 Excel 来源追溯。", entity_id=entity_id, action="重新生成 TraceLink 并阻止交付"))
    signals = [item for item in bundle.control_ir.get("signals", []) if item.get("name")]
    signal_names = {_fold_identifier(item.get("name")) for item in signals}
    signal_ids = {_fold_identifier(item.get("id")) for item in signals if item.get("id")}
    known_interlock_symbols = signal_names | signal_ids
    for interlock in bundle.control_ir.get("interlocks", []):
        internal_symbols = sorted(
            token
            for key in ("allow_condition", "inhibit_condition")
            for token in _expression_identifiers(interlock.get(key))
            if _fold_identifier(token) not in known_interlock_symbols
        )
        for token in internal_symbols:
            findings.append(_finding(
                "INTERLOCK_INTERNAL_STATE_UNDECLARED",
                "warning",
                "互锁内部状态未显式建模",
                f"互锁 {interlock.get('interlock_id')} 使用内部状态 {token}；参考模拟按只读 false 处理。",
                file="generated/ControlIR.json",
                entity_id=interlock.get("interlock_id"),
                source=interlock.get("source"),
                action="在 Signals 或确定性状态模型中声明该状态并重新生成",
            ))
    signal_by_address: dict[str, list[dict[str, Any]]] = {}
    for signal in signals:
        address = str(signal.get("address") or "").upper()
        if address:
            signal_by_address.setdefault(address, []).append(signal)
    for signal in bundle.control_ir.get("signals", []):
        if _fold_identifier(signal.get("name")) in signal_names and sum(1 for item in bundle.control_ir["signals"] if _fold_identifier(item.get("name")) == _fold_identifier(signal.get("name"))) > 1:
            findings.append(_finding("DUPLICATE_ST_SYMBOL", "blocker", "ST 符号重复", f"变量 {signal.get('name')} 在生成变量表中重复。", file="src/GVL_IO.st", line=_line_for(signal.get("id"), bundle), entity_id=signal.get("id"), source=signal.get("source")))
        if signal.get("address") and target_profile and not target_profile.address_pattern.fullmatch(str(signal["address"])):
            findings.append(_finding("INVALID_IO_ADDRESS", "blocker", "I/O 地址格式异常", f"{signal.get('id')} 的地址 {signal.get('address')} 不符合 {target_profile.profile_id} 的首批 X/Y/M 逻辑地址子集。", file="src/GVL_IO.st", line=_line_for(signal.get("id"), bundle), entity_id=signal.get("id"), source=signal.get("source")))
        if signal.get("data_type") in {"INT", "DINT", "REAL", "WORD", "DWORD"} and not signal.get("unit"):
            findings.append(_finding("SIGNAL_UNIT_MISSING", "warning", "数值信号缺少单位", f"信号 {signal.get('id')} 是数值类型但没有单位，不能可靠解释量程或超时。", file="src/GVL_IO.st", line=_line_for(signal.get("id"), bundle), entity_id=signal.get("id"), source=signal.get("source"), action="在 Signals 填写 unit 后重新生成"))
    for address, addressed in signal_by_address.items():
        if len(addressed) > 1:
            for signal in addressed:
                findings.append(_finding("DUPLICATE_IO_ADDRESS", "blocker", "I/O 地址重复", f"地址 {address} 同时分配给多个信号。", file="src/GVL_IO.st", line=_line_for(signal.get("id"), bundle), entity_id=signal.get("id"), source=signal.get("source"), action="为每个信号分配唯一地址"))
    if target_profile:
        recorded_profile = str(target.get("generator_profile") or "")
        if recorded_profile != target_profile.profile_id:
            findings.append(_finding("TARGET_PROFILE_MISMATCH", "blocker", "目标 Profile 与生成记录不一致", f"目标应使用 {target_profile.profile_id}，生成记录为 {recorded_profile or '空'}。", file="generated/ControlIR.json", action="使用当前生成器从锁定规格重新生成"))
    for step in bundle.control_ir.get("steps", []):
        expression = " ".join((step.get("entry_condition"), step.get("actions"), step.get("completion_condition")))
        unknown = sorted(item for item in _expression_identifiers(expression) if _fold_identifier(item) not in signal_names and not item.upper().startswith("KP_") and item.upper() not in {"TRUE", "FALSE"})
        for token in unknown:
            findings.append(_finding("UNDEFINED_ST_REFERENCE", "blocker", "生成物包含未定义引用", f"工步 {step.get('id')} 使用了未定义符号 {token}。", file="src/PRG_AutoCycle.st", line=_line_for(step.get("id"), bundle), entity_id=step.get("id"), source=step.get("source")))
        signal_directions = {_fold_identifier(item.get("name")): str(item.get("direction") or "").upper() for item in signals}
        for target in sorted(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=)", str(step.get("actions") or ""))):
            if signal_directions.get(_fold_identifier(target)) not in {"DO", "AO", "INTERNAL", "COMM"}:
                findings.append(_finding("ACTION_TARGET_DIRECTION_INVALID", "blocker", "动作目标方向无效", f"工步 {step.get('id')} 尝试写入 {target}；动作只能写 DO、AO、INTERNAL 或 COMM。", file="src/PRG_AutoCycle.st", line=_line_for(step.get("id"), bundle), entity_id=step.get("id"), source=step.get("source"), action="修正 Signals 方向或 Sequence 动作后重新生成"))
    steps = bundle.control_ir.get("steps", [])
    ids = {_fold_identifier(item.get("id")) for item in steps}
    steps_by_id = {_fold_identifier(item.get("id")): item for item in steps}
    reachable: set[str] = set()
    current = _fold_identifier(steps[0].get("id")) if steps else None
    while current and current not in reachable:
        reachable.add(current)
        step = steps_by_id.get(current)
        next_id = _fold_identifier(step.get("next_step_id")) if step else ""
        current = next_id if next_id in ids else None
    for step in steps:
        if _fold_identifier(step.get("id")) not in reachable:
            findings.append(_finding("UNREACHABLE_STEP", "blocker", "工步不可达", f"工步 {step.get('id')} 不在主流程可达路径上。", file="src/PRG_AutoCycle.st", line=_line_for(step.get("id"), bundle), entity_id=step.get("id"), source=step.get("source")))
    for step in steps:
        next_id = _fold_identifier(step.get("next_step_id"))
        if step.get("next_step_id") and next_id not in ids and next_id != "end":
            findings.append(_finding("NEXT_STEP_MISSING", "blocker", "下一工步不存在", f"工步 {step.get('id')} 指向 {step.get('next_step_id')}。", file="src/PRG_AutoCycle.st", line=_line_for(step.get("id"), bundle), entity_id=step.get("id"), source=step.get("source")))
        if not step.get("duration") or not step.get("duration_unit"):
            findings.append(_finding("STEP_TIMEOUT_MISSING", "warning", "工步缺少完整超时参数", f"工步 {step.get('id')} 没有持续时间或单位，模拟无法判断超时。", file="src/PRG_AutoCycle.st", entity_id=step.get("id"), source=step.get("source"), action="在 Sequence 填写 expected_duration 与 duration_unit"))
    for start in ids:
        path: set[str] = set()
        current = start
        terminated = False
        while current in ids and current not in path:
            path.add(current)
            step = steps_by_id[current]
            next_id = _fold_identifier(step.get("next_step_id") or "END")
            if next_id == "end":
                terminated = True
                break
            current = next_id
        if not terminated and current in path:
            step = steps_by_id[current]
            findings.append(_finding("LOOP_NO_EXIT", "blocker", "流程循环没有退出条件", f"从工步 {start} 出发在 {current} 形成无退出循环。", file="src/PRG_AutoCycle.st", line=_line_for(current, bundle), entity_id=current, source=step.get("source"), action="增加可达 END 分支或明确受控退出条件"))
            break
    if not bundle.control_ir.get("interlocks"):
        findings.append(_finding("INTERLOCK_NOT_DEFINED", "warning", "未定义互锁", "当前规格没有 Interlocks 数据，普通控制骨架不会自动推断安全互锁。", action="补充互锁资料并重新生成"))
    else:
        interlock_actions = {_fold_identifier(item.get("action_id")) for item in bundle.control_ir.get("interlocks", []) if item.get("action_id")}
        for signal in signals:
            if str(signal.get("direction")).upper() == "DO" and _fold_identifier(signal.get("id")) not in interlock_actions:
                findings.append(_finding("INTERLOCK_COVERAGE_MISSING", "warning", "输出未关联互锁", f"DO 信号 {signal.get('id')} 没有对应 Interlocks.action_id。", file="src/GVL_IO.st", line=_line_for(signal.get("id"), bundle), entity_id=signal.get("id"), source=signal.get("source"), action="补充该输出的互锁条件并重新生成"))
    if not any(_fold_identifier(token) in signal_ids or _fold_identifier(token) in signal_names for token in {"SIG_MODE_AUTO", "MODE_AUTO", "KP_ModeAuto"}):
        findings.append(_finding("MODE_PATH_MISSING", "warning", "自动/手动模式路径未显式建模", "Control IR 没有可追溯的模式信号；生成骨架不能推断现场模式切换。", file="generated/ControlIR.json", action="在 Signals 增加自动/手动模式信号"))
    if not any("reset" in value or "stop" in value for value in signal_ids):
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
    # The generated safety banner intentionally names excluded operations. Only
    # executable ST may trigger the prohibited-operation gate.
    executable_st = _strip_st_non_executable(program)
    if "FORCED_OUTPUT" in executable_st.upper() or re.search(r"\bDOWNLOAD\s*\(", executable_st, re.IGNORECASE):
        findings.append(_finding("FORBIDDEN_CONTROL_OPERATION", "blocker", "发现禁止的控制操作", "生成物包含下载或强制输出关键字，已阻断。", file="src/PRG_AutoCycle.st", action="删除危险操作并重新生成"))
    input_hash = content_hash(stable_json({"audit_version": AUDIT_VERSION, "generator_version": GENERATOR_VERSION, "files": bundle.files, "control_ir": bundle.control_ir, "test_spec": bundle.test_spec, "trace_links": bundle.trace_links}))
    status = "blocked" if any(item["severity"] == "blocker" for item in findings) else "review_ready"
    return {"audit_version": AUDIT_VERSION, "input_hash": input_hash, "status": status, "findings": findings, "summary": {"total": len(findings), "blocker": sum(item["severity"] == "blocker" for item in findings), "warning": sum(item["severity"] == "warning" for item in findings)}}
