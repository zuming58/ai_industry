from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any


ENGINE_VERSION = "kongpu-reference-v2"
TEST_SPEC_DSL_VERSION = "1.0"
_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_CONDITION_WORDS = {"TRUE", "FALSE", "AND", "OR", "NOT"}
_EXTERNAL_INPUT_DIRECTIONS = {"DI", "AI", "COMM"}
_ACTION_TARGET_DIRECTIONS = {"DO", "AO", "INTERNAL", "COMM"}


class SimulationInputError(ValueError):
    pass


def _fold_identifier(value: Any) -> str:
    return str(value or "").strip().casefold()


def _canonical_names(names: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        folded = _fold_identifier(name)
        existing = result.get(folded)
        if existing is not None and existing != name:
            raise SimulationInputError(f"信号名称仅大小写不同，无法确定性解析: {existing}, {name}")
        result[folded] = name
    return result


def _validate_ir_identifiers(ir: dict[str, Any]) -> None:
    """Reject IR maps that would otherwise overwrite identifiers in dicts."""
    for items_key, field, label in (
        ("signals", "id", "信号 ID"),
        ("signals", "name", "信号名称"),
        ("steps", "id", "工步 ID"),
        ("exceptions", "exception_id", "异常 ID"),
    ):
        seen: dict[str, str] = {}
        for item in ir.get(items_key, []):
            value = str(item.get(field) or "").strip()
            if not value:
                continue
            folded = _fold_identifier(value)
            existing = seen.get(folded)
            if existing is not None:
                raise SimulationInputError(f"{label}重复或仅大小写不同: {existing}, {value}")
            seen[folded] = value


def _normalize_values(
    values: dict[str, Any],
    known: set[str],
    *,
    context: str,
) -> dict[str, Any]:
    canonical = _canonical_names(known)
    normalized: dict[str, Any] = {}
    seen: set[str] = set()
    for key, value in values.items():
        folded = _fold_identifier(key)
        name = canonical.get(folded)
        if name is None:
            raise SimulationInputError(f"{context}使用未知输入或不可作为外部输入的信号: {key}")
        if folded in seen:
            raise SimulationInputError(f"{context}包含仅大小写不同的重复信号: {key}")
        if not isinstance(value, (bool, int, float)):
            raise SimulationInputError(f"{context}输入 {key} 必须是布尔或数字")
        if isinstance(value, float) and not math.isfinite(value):
            raise SimulationInputError(f"{context}输入 {key} 必须是有限数值")
        seen.add(folded)
        normalized[name] = value
    return normalized


def _condition_identifiers(expression: Any) -> set[str]:
    return {
        token
        for token in _IDENTIFIER.findall(str(expression or ""))
        if token.upper() not in _CONDITION_WORDS
    }


def _interlock_internal_states(ir: dict[str, Any]) -> set[str]:
    """Return read-only state names used only by interlock conditions.

    Interlocks may refer to derived/internal states (for example AxisMoving)
    that are intentionally not PLC I/O signals. They are modelled as false in
    the reference executor until a deterministic state model is added. They
    never become user-injectable inputs.
    """
    known = {
        _fold_identifier(item.get(key))
        for item in ir.get("signals", [])
        for key in ("id", "name")
        if item.get(key)
    }
    internal: set[str] = set()
    for interlock in ir.get("interlocks", []):
        for key in ("allow_condition", "inhibit_condition"):
            for token in _condition_identifiers(interlock.get(key)):
                if _fold_identifier(token) not in known:
                    internal.add(token)
    return internal


def _safe_eval(expression: str | None, values: dict[str, Any]) -> bool:
    text = str(expression or "TRUE").replace(":=", "=")
    text = re.sub(r"\bTRUE\b", "True", text, flags=re.I)
    text = re.sub(r"\bFALSE\b", "False", text, flags=re.I)
    text = re.sub(r"\bAND\b", " and ", text, flags=re.I)
    text = re.sub(r"\bOR\b", " or ", text, flags=re.I)
    text = re.sub(r"\bNOT\b", " not ", text, flags=re.I)
    text = text.strip()
    if len(text) > 2_000:
        raise SimulationInputError("条件表达式超过 2000 字符限制")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise SimulationInputError("条件表达式语法无效；仅支持信号、TRUE/FALSE、AND/OR/NOT 和比较运算") from exc

    value_names = _canonical_names(set(values))

    def evaluate(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression): return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (bool, int, float)):
            if isinstance(node.value, float) and not math.isfinite(node.value):
                raise SimulationInputError("条件表达式不允许非有限数值")
            return node.value
        if isinstance(node, ast.Name):
            canonical = value_names.get(_fold_identifier(node.id))
            if canonical is None:
                raise SimulationInputError(f"条件表达式使用未知信号: {node.id}")
            return values[canonical]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not): return not bool(evaluate(node.operand))
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            result = bool(evaluate(node.values[0]))
            for child in node.values[1:]: result = (result and bool(evaluate(child))) if isinstance(node.op, ast.And) else (result or bool(evaluate(child)))
            return result
        if isinstance(node, ast.Compare):
            left = evaluate(node.left)
            for op, right_node in zip(node.ops, node.comparators):
                right = evaluate(right_node)
                fn = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Lt: operator.lt, ast.LtE: operator.le}.get(type(op))
                if fn is None or not fn(left, right): return False
                left = right
            return True
        raise SimulationInputError("表达式包含参考模拟器不支持的语法")

    return bool(evaluate(tree))


def _apply_actions(actions: str | None, values: dict[str, Any], allowed: set[str] | None = None) -> dict[str, Any]:
    text = str(actions or "")
    changed: dict[str, Any] = {}
    assignment_targets = set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=)", text))
    allowed_names = _canonical_names(allowed or set(values))
    for name, raw in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=)\s*(TRUE|FALSE|[-+]?\d+(?:\.\d+)?)", text, flags=re.I):
        value: Any = raw.upper() == "TRUE" if raw.upper() in {"TRUE", "FALSE"} else float(raw) if "." in raw else int(raw)
        canonical = allowed_names.get(_fold_identifier(name))
        if canonical is None:
            raise SimulationInputError(f"动作目标不是已定义信号: {name}")
        values[canonical] = value
        changed[canonical] = value
    changed_folded = {_fold_identifier(name) for name in changed}
    unsupported = sorted(name for name in assignment_targets if _fold_identifier(name) not in changed_folded)
    if unsupported:
        raise SimulationInputError(f"动作赋值仅支持布尔或数字常量: {', '.join(unsupported)}")
    return changed


def _signal_defaults(ir: dict[str, Any]) -> dict[str, Any]:
    return {
        str(item.get("name")): False
        for item in ir.get("signals", [])
        if item.get("name")
    }


def _signal_names_for_directions(ir: dict[str, Any], directions: set[str]) -> set[str]:
    return {
        str(item.get("name"))
        for item in ir.get("signals", [])
        if item.get("name") and str(item.get("direction") or "").upper() in directions
    }


def _action_targets(actions: str | None) -> set[str]:
    return set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=)", str(actions or "")))


def _cycle_schedule(
    schedule: dict[int | str, dict[str, Any]] | None,
    known: set[str],
    max_cycles: int,
) -> dict[int, dict[str, Any]]:
    normalized: dict[int, dict[str, Any]] = {}
    for raw_cycle, values in (schedule or {}).items():
        try:
            cycle = int(raw_cycle)
        except (TypeError, ValueError) as exc:
            raise SimulationInputError("输入注入周期必须是整数") from exc
        if cycle < 1 or cycle > max_cycles:
            raise SimulationInputError("输入注入周期必须位于 1 到 max_cycles 之间")
        if not isinstance(values, dict):
            raise SimulationInputError("输入注入帧必须是对象")
        values = _normalize_values(values, known, context="输入注入帧")
        if cycle in normalized:
            raise SimulationInputError(f"输入注入周期重复: {cycle}")
        normalized[cycle] = dict(values)
    return normalized


def _cycle_set(values: list[int] | set[int] | None, max_cycles: int, name: str) -> set[int]:
    normalized: set[int] = set()
    for value in values or []:
        if not isinstance(value, int) or isinstance(value, bool):
            raise SimulationInputError(f"{name} 必须只包含整数")
        if value < 1 or value > max_cycles:
            raise SimulationInputError(f"{name} 必须位于 1 到 max_cycles 之间")
        normalized.add(value)
    return normalized


def _timeout_cycles(step: dict[str, Any], cycle_time_ms: int) -> int | None:
    duration = step.get("duration")
    if duration in (None, ""):
        return None
    try:
        numeric = float(duration)
    except (TypeError, ValueError) as exc:
        raise SimulationInputError(f"工步 {step.get('id')} 的持续时间不是数字") from exc
    if numeric <= 0:
        raise SimulationInputError(f"工步 {step.get('id')} 的持续时间必须大于 0")
    unit = str(step.get("duration_unit") or "").strip().lower()
    multiplier = {"ms": 1, "s": 1000, "sec": 1000, "min": 60000}.get(unit)
    if multiplier is None:
        raise SimulationInputError(f"工步 {step.get('id')} 的持续时间单位不受支持")
    return max(1, int((numeric * multiplier + cycle_time_ms - 1) // cycle_time_ms))


def _translated_condition(expression: Any, ir: dict[str, Any]) -> str:
    text = str(expression or "TRUE")
    mapping = {
        str(item.get("id")): str(item.get("name"))
        for item in ir.get("signals", [])
        if item.get("id") and item.get("name")
    }
    for source, target in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(rf"\b{re.escape(source)}\b", target, text, flags=re.I)
    return text


def _blocked_by_interlocks(step: dict[str, Any], ir: dict[str, Any], values: dict[str, Any]) -> list[str]:
    action_names = {_fold_identifier(name) for name in _action_targets(step.get("actions"))}
    signal_names = {
        _fold_identifier(item.get("id")): _fold_identifier(item.get("name"))
        for item in ir.get("signals", [])
        if item.get("id") and item.get("name")
    }
    blocked: list[str] = []
    for interlock in ir.get("interlocks", []):
        action_id = _fold_identifier(interlock.get("action_id"))
        if action_id not in action_names and signal_names.get(action_id) not in action_names:
            continue
        allow = _safe_eval(_translated_condition(interlock.get("allow_condition"), ir), values)
        inhibit = _safe_eval(_translated_condition(interlock.get("inhibit_condition"), ir), values) if interlock.get("inhibit_condition") else False
        if not allow or inhibit:
            blocked.append(str(interlock.get("interlock_id") or action_id or "unknown"))
    return blocked


def run_reference_simulation(
    ir: dict[str, Any],
    input_overrides: dict[str, Any] | None = None,
    max_cycles: int = 100,
    *,
    input_schedule: dict[int | str, dict[str, Any]] | None = None,
    restart_cycles: list[int] | set[int] | None = None,
    disconnect_cycles: list[int] | set[int] | None = None,
    cycle_time_ms: int = 100,
) -> dict[str, Any]:
    if max_cycles < 1 or max_cycles > 10_000:
        raise SimulationInputError("max_cycles 必须在 1 到 10000 之间")
    if cycle_time_ms < 1 or cycle_time_ms > 60_000:
        raise SimulationInputError("cycle_time_ms 必须在 1 到 60000 之间")
    _validate_ir_identifiers(ir)
    internal_states = _interlock_internal_states(ir)
    values = _signal_defaults(ir)
    values.update({name: False for name in internal_states})
    external_inputs = _signal_names_for_directions(ir, _EXTERNAL_INPUT_DIRECTIONS)
    action_targets = _signal_names_for_directions(ir, _ACTION_TARGET_DIRECTIONS)
    normalized_overrides = _normalize_values(input_overrides or {}, external_inputs, context="模拟")
    values.update(normalized_overrides)
    schedule = _cycle_schedule(input_schedule, external_inputs, max_cycles)
    restarts = _cycle_set(restart_cycles, max_cycles, "restart_cycles")
    disconnects = _cycle_set(disconnect_cycles, max_cycles, "disconnect_cycles")
    if restarts & disconnects:
        raise SimulationInputError("同一周期不能同时重启和断开通信")
    signal_by_name = {str(item.get("name")): item for item in ir.get("signals", []) if item.get("name")}
    communication_values = {
        name: values.get(name, False)
        for name, signal in signal_by_name.items()
        if str(signal.get("direction") or "").upper() == "COMM"
    }
    reset_names = {name for name in external_inputs if "RESET" in name.upper()}
    reset_active = False
    steps = ir.get("steps", [])
    by_id = {_fold_identifier(item.get("id")): item for item in steps}
    current = _fold_identifier(steps[0].get("id")) if steps else None
    traces: list[dict[str, Any]] = []
    events: list[str] = []
    completed = False
    step_cycles = 0
    timeout_reported = False
    diagnostics: list[dict[str, Any]] = []
    if internal_states:
        diagnostics.append(
            {
                "code": "INTERLOCK_INTERNAL_STATE_DEFAULTED",
                "severity": "warning",
                "internal_states": sorted(internal_states),
                "action": "在确定性状态模型或厂商工具验证中补充内部状态来源；当前参考模拟按 false 处理",
            }
        )
    if not steps:
        return {
            "engine_version": ENGINE_VERSION,
            "status": "failed",
            "verification_level": "automatic_reference",
            "cycles": 0,
            "final_step_id": None,
            "events": ["NO_STEPS"],
            "diagnostics": [{"code": "NO_STEPS", "severity": "blocker", "action": "在 Sequence 至少定义一个工步"}],
            "traces": [],
        }
    for cycle in range(1, max_cycles + 1):
        restarted = False
        if cycle in restarts:
            persistent = {
                name: values.get(name, False)
                for name, signal in signal_by_name.items()
                if str(signal.get("direction") or "").upper() in {"DI", "AI", "COMM"}
            }
            values = _signal_defaults(ir)
            values.update({name: False for name in internal_states})
            values.update(persistent)
            current = _fold_identifier(steps[0].get("id"))
            step_cycles = 0
            timeout_reported = False
            reset_active = False
            restarted = True
            events.append(f"restart:{cycle}")
            diagnostics.append({"code": "RESTART_APPLIED", "severity": "info", "cycle": cycle, "action": "核对重启后的初始工步与持久输入"})
        if cycle in schedule:
            values.update(schedule[cycle])
            for name in communication_values:
                if name in schedule[cycle]:
                    communication_values[name] = schedule[cycle][name]
        communication_disconnected = cycle in disconnects
        if communication_disconnected:
            for name in communication_values:
                values[name] = False
        else:
            values.update(communication_values)
        if current is None:
            completed = True
            break
        step = by_id.get(current)
        if step is None:
            events.append(f"UNKNOWN_STEP:{current}")
            diagnostics.append({"code": "UNKNOWN_STEP", "severity": "blocker", "step_id": current, "cycle": cycle, "action": "修复 next_step_id 并重新生成"})
            break
        step_cycles += 1
        timeout = _timeout_cycles(step, cycle_time_ms)
        cycle_events: list[str] = []
        if restarted:
            cycle_events.append("RESTART_APPLIED")
        if communication_disconnected:
            cycle_events.append("COMMUNICATION_DISCONNECTED")
            events.append(f"communication_disconnected:{cycle}")
            if not any(item.get("code") == "COMMUNICATION_DISCONNECTED" for item in diagnostics):
                diagnostics.append({"code": "COMMUNICATION_DISCONNECTED", "severity": "warning", "cycle": cycle, "step_id": current, "action": "核对通信断开时的失效状态与恢复路径"})
        entry_condition = _translated_condition(step.get("entry_condition"), ir)
        if not _safe_eval(entry_condition, values):
            cycle_events.append("ENTRY_CONDITION_BLOCKED")
        blocked_interlocks = _blocked_by_interlocks(step, ir, values)
        cycle_events.extend(f"INTERLOCK_BLOCKED:{interlock_id}" for interlock_id in blocked_interlocks)
        inputs_snapshot = {name: values.get(name, False) for name in sorted(external_inputs)}
        outputs: dict[str, Any] = {}
        execution_blocked = any(
            event == "ENTRY_CONDITION_BLOCKED"
            or event == "COMMUNICATION_DISCONNECTED"
            or event.startswith("INTERLOCK_BLOCKED:")
            for event in cycle_events
        )
        if not execution_blocked:
            outputs = _apply_actions(step.get("actions"), values, action_targets)
        completion_condition = _translated_condition(step.get("completion_condition"), ir)
        done = not execution_blocked and _safe_eval(completion_condition, values)
        if done:
            cycle_events.append("step_complete")
        if timeout is not None and step_cycles >= timeout and not done and not timeout_reported:
            cycle_events.append("STEP_TIMEOUT")
            events.append(f"step_timeout:{current}")
            diagnostics.append({"code": "STEP_TIMEOUT", "severity": "blocker", "step_id": current, "cycle": cycle, "timeout_cycles": timeout, "action": "检查反馈、互锁和工步超时参数"})
            timeout_reported = True
        reset_now = any(bool(values.get(name)) for name in reset_names)
        reset_triggered = reset_now and not reset_active
        reset_active = reset_now
        if reset_triggered:
            cycle_events.append("RESET_TRIGGERED")
            events.append(f"reset_triggered:{cycle}")
            current = _fold_identifier(steps[0].get("id"))
            step_cycles = 0
            timeout_reported = False
        traces.append({"cycle": cycle, "step_id": step.get("id"), "inputs": inputs_snapshot, "outputs": outputs, "entry_condition": entry_condition, "completion_condition": completion_condition, "events": cycle_events, "source": step.get("source"), "communication": "disconnected" if communication_disconnected else "connected", "internal_state": {name: values.get(name, False) for name in sorted(internal_states)}})
        if done and "RESET_TRIGGERED" not in cycle_events:
            events.append(f"step_complete:{current}")
            next_step = _fold_identifier(step.get("next_step_id"))
            current = next_step if next_step and next_step != "end" else None
            step_cycles = 0
            timeout_reported = False
        if current is None:
            completed = True
            break
    status = "passed" if completed else "failed"
    if not completed:
        events.append("MAX_CYCLES_OR_MISSING_FEEDBACK")
        if not any(item.get("code") == "UNKNOWN_STEP" for item in diagnostics):
            diagnostics.append({"code": "MAX_CYCLES_OR_MISSING_FEEDBACK", "severity": "blocker", "cycle": len(traces), "step_id": current, "action": "检查入口条件、反馈、互锁、通信状态和最大扫描周期"})
    return {"engine_version": ENGINE_VERSION, "status": status, "verification_level": "automatic_reference", "cycles": len(traces), "final_step_id": current, "events": events, "diagnostics": diagnostics, "traces": traces}


def run_test_spec(
    ir: dict[str, Any],
    test_spec: dict[str, Any],
    input_overrides: dict[str, Any] | None = None,
    max_cycles: int = 100,
    *,
    input_schedule: dict[int | str, dict[str, Any]] | None = None,
    restart_cycles: list[int] | set[int] | None = None,
    disconnect_cycles: list[int] | set[int] | None = None,
    cycle_time_ms: int = 100,
) -> dict[str, Any]:
    if str(test_spec.get("version")) != TEST_SPEC_DSL_VERSION:
        raise SimulationInputError("TestSpec 版本不受支持")
    _validate_ir_identifiers(ir)
    tests = test_spec.get("tests")
    if not isinstance(tests, list) or not tests:
        raise SimulationInputError("TestSpec 必须包含至少一个测试用例")

    signals = _signal_defaults(ir)
    external_inputs = _signal_names_for_directions(ir, _EXTERNAL_INPUT_DIRECTIONS)
    action_targets = _signal_names_for_directions(ir, _ACTION_TARGET_DIRECTIONS)
    normalized_overrides = _normalize_values(input_overrides or {}, external_inputs, context="模拟")
    signals.update(normalized_overrides)

    steps = {_fold_identifier(item.get("id")): item for item in ir.get("steps", [])}
    exceptions = {_fold_identifier(item.get("exception_id")): item for item in ir.get("exceptions", [])}
    allowed = {"id", "source_step_id", "source_exception_id", "inputs", "given", "when", "expect"}
    seen: set[str] = set()
    case_results: list[dict[str, Any]] = []
    for raw_case in tests:
        if not isinstance(raw_case, dict) or set(raw_case) - allowed:
            raise SimulationInputError("TestSpec 用例包含不受支持的字段")
        case_id = str(raw_case.get("id") or "").strip()
        folded_case_id = _fold_identifier(case_id)
        if not case_id or folded_case_id in seen:
            raise SimulationInputError("TestSpec 用例 ID 缺失或重复")
        seen.add(folded_case_id)
        values = dict(signals)
        case_inputs = raw_case.get("inputs") or {}
        if not isinstance(case_inputs, dict):
            raise SimulationInputError("TestSpec inputs 必须是对象")
        normalized_case_inputs = _normalize_values(case_inputs, external_inputs, context="TestSpec")
        values.update(normalized_case_inputs)
        given = _safe_eval(str(raw_case.get("given") or "TRUE"), values)
        changes = _apply_actions(str(raw_case.get("when") or ""), values, action_targets)
        expected = _safe_eval(str(raw_case.get("expect") or "TRUE"), values)
        status = "passed" if given and expected else "blocked" if not given else "failed"
        source_step_id = raw_case.get("source_step_id")
        source_exception_id = raw_case.get("source_exception_id")
        if bool(source_step_id) == bool(source_exception_id):
            raise SimulationInputError("TestSpec 用例必须且只能引用一个工步或异常")
        if source_step_id and _fold_identifier(source_step_id) not in steps:
            raise SimulationInputError(f"TestSpec 引用不存在的工步: {source_step_id}")
        if source_exception_id and _fold_identifier(source_exception_id) not in exceptions:
            raise SimulationInputError(f"TestSpec 引用不存在的异常: {source_exception_id}")
        source_object = steps.get(_fold_identifier(source_step_id)) or exceptions.get(_fold_identifier(source_exception_id)) or {}
        case_results.append({
            "id": case_id,
            "status": status,
            "given_satisfied": given,
            "assertion_satisfied": expected,
            "changes": changes,
            "source_step_id": source_step_id,
            "source_exception_id": source_exception_id,
            "source": source_object.get("source"),
        })
    if input_schedule is not None and not isinstance(input_schedule, dict):
        raise SimulationInputError("input_schedule 必须是对象")
    if restart_cycles is not None and not isinstance(restart_cycles, (list, set, tuple)):
        raise SimulationInputError("restart_cycles 必须是整数数组")
    if disconnect_cycles is not None and not isinstance(disconnect_cycles, (list, set, tuple)):
        raise SimulationInputError("disconnect_cycles 必须是整数数组")
    if any(not isinstance(value, int) or isinstance(value, bool) for value in (restart_cycles or [])):
        raise SimulationInputError("restart_cycles 必须只包含整数")
    if any(not isinstance(value, int) or isinstance(value, bool) for value in (disconnect_cycles or [])):
        raise SimulationInputError("disconnect_cycles 必须只包含整数")
    if set((restart_cycles or [])) & set((disconnect_cycles or [])):
        raise SimulationInputError("同一周期不能同时重启和断开通信")

    sequence_inputs = dict(normalized_overrides)
    for raw_case in tests:
        for key, value in (raw_case.get("inputs") or {}).items():
            canonical = _canonical_names(external_inputs).get(_fold_identifier(key))
            if canonical is not None:
                sequence_inputs.setdefault(canonical, value)
    sequence_result = run_reference_simulation(
        ir,
        sequence_inputs,
        max_cycles,
        input_schedule=input_schedule,
        restart_cycles=restart_cycles,
        disconnect_cycles=disconnect_cycles,
        cycle_time_ms=cycle_time_ms,
    )
    passed_cases = sum(item["status"] == "passed" for item in case_results)
    failed_cases = sum(item["status"] == "failed" for item in case_results)
    blocked_cases = sum(item["status"] == "blocked" for item in case_results)
    sequence_result.update({
        "status": "passed" if sequence_result["status"] == "passed" and failed_cases == 0 and blocked_cases == 0 else "failed",
        "test_spec_version": TEST_SPEC_DSL_VERSION,
        "test_cases": case_results,
        "test_summary": {"total": len(case_results), "passed": passed_cases, "failed": failed_cases, "blocked": blocked_cases},
    })
    return sequence_result
