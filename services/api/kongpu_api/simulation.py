from __future__ import annotations

import ast
import operator
import re
from typing import Any


ENGINE_VERSION = "kongpu-reference-v1"
TEST_SPEC_DSL_VERSION = "1.0"


class SimulationInputError(ValueError):
    pass


def _safe_eval(expression: str | None, values: dict[str, Any]) -> bool:
    text = str(expression or "TRUE").replace(":=", "=")
    text = re.sub(r"\bTRUE\b", "True", text, flags=re.I)
    text = re.sub(r"\bFALSE\b", "False", text, flags=re.I)
    text = re.sub(r"\bAND\b", " and ", text, flags=re.I)
    text = re.sub(r"\bOR\b", " or ", text, flags=re.I)
    text = re.sub(r"\bNOT\b", " not ", text, flags=re.I)
    text = text.strip()
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return False

    def evaluate(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression): return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (bool, int, float, str)): return node.value
        if isinstance(node, ast.Name): return values.get(node.id, False)
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


def _apply_actions(actions: str | None, values: dict[str, Any]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for name, raw in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=)\s*(TRUE|FALSE|[-+]?\d+(?:\.\d+)?)", str(actions or ""), flags=re.I):
        value: Any = raw.upper() == "TRUE" if raw.upper() in {"TRUE", "FALSE"} else float(raw) if "." in raw else int(raw)
        values[name] = value
        changed[name] = value
    return changed


def run_reference_simulation(ir: dict[str, Any], input_overrides: dict[str, Any] | None = None, max_cycles: int = 100) -> dict[str, Any]:
    if max_cycles < 1 or max_cycles > 10_000:
        raise SimulationInputError("max_cycles 必须在 1 到 10000 之间")
    values = {str(item.get("name")): False for item in ir.get("signals", []) if item.get("name")}
    for key, value in (input_overrides or {}).items():
        if key not in values:
            raise SimulationInputError(f"未知模拟输入: {key}")
        if not isinstance(value, (bool, int, float)):
            raise SimulationInputError(f"模拟输入 {key} 必须是布尔或数字")
        values[key] = value
    steps = ir.get("steps", [])
    by_id = {str(item.get("id")): item for item in steps}
    current = str(steps[0].get("id")) if steps else None
    traces: list[dict[str, Any]] = []
    events: list[str] = []
    completed = False
    for cycle in range(1, max_cycles + 1):
        if current is None:
            completed = True
            break
        step = by_id.get(current)
        if step is None:
            events.append(f"unknown_step:{current}")
            break
        outputs = _apply_actions(step.get("actions"), values)
        done = _safe_eval(step.get("completion_condition"), values)
        traces.append({"cycle": cycle, "step_id": current, "inputs": dict(values), "outputs": outputs, "events": ["step_complete"] if done else []})
        if done:
            events.append(f"step_complete:{current}")
            current = str(step.get("next_step_id")) if step.get("next_step_id") and step.get("next_step_id") != "END" else None
        if current is None:
            completed = True
            break
    status = "passed" if completed else "failed"
    if not completed:
        events.append("MAX_CYCLES_OR_MISSING_FEEDBACK")
    return {"engine_version": ENGINE_VERSION, "status": status, "verification_level": "automatic_reference", "cycles": len(traces), "final_step_id": current, "events": events, "traces": traces}


def run_test_spec(
    ir: dict[str, Any],
    test_spec: dict[str, Any],
    input_overrides: dict[str, Any] | None = None,
    max_cycles: int = 100,
) -> dict[str, Any]:
    if str(test_spec.get("version")) != TEST_SPEC_DSL_VERSION:
        raise SimulationInputError("TestSpec 版本不受支持")
    tests = test_spec.get("tests")
    if not isinstance(tests, list) or not tests:
        raise SimulationInputError("TestSpec 必须包含至少一个测试用例")

    signals = {str(item.get("name")): False for item in ir.get("signals", []) if item.get("name")}
    for key, value in (input_overrides or {}).items():
        if key not in signals:
            raise SimulationInputError(f"未知模拟输入: {key}")
        if not isinstance(value, (bool, int, float)):
            raise SimulationInputError(f"模拟输入 {key} 必须是布尔或数字")
        signals[key] = value

    steps = {str(item.get("id")): item for item in ir.get("steps", [])}
    exceptions = {str(item.get("exception_id")): item for item in ir.get("exceptions", [])}
    allowed = {"id", "source_step_id", "source_exception_id", "inputs", "given", "when", "expect"}
    seen: set[str] = set()
    case_results: list[dict[str, Any]] = []
    for raw_case in tests:
        if not isinstance(raw_case, dict) or set(raw_case) - allowed:
            raise SimulationInputError("TestSpec 用例包含不受支持的字段")
        case_id = str(raw_case.get("id") or "").strip()
        if not case_id or case_id in seen:
            raise SimulationInputError("TestSpec 用例 ID 缺失或重复")
        seen.add(case_id)
        values = dict(signals)
        case_inputs = raw_case.get("inputs") or {}
        if not isinstance(case_inputs, dict):
            raise SimulationInputError("TestSpec inputs 必须是对象")
        for key, value in case_inputs.items():
            if key not in values:
                raise SimulationInputError(f"TestSpec 使用未知输入: {key}")
            if not isinstance(value, (bool, int, float)):
                raise SimulationInputError(f"TestSpec 输入 {key} 必须是布尔或数字")
            values[key] = value
        given = _safe_eval(str(raw_case.get("given") or "TRUE"), values)
        changes = _apply_actions(str(raw_case.get("when") or ""), values)
        expected = _safe_eval(str(raw_case.get("expect") or "TRUE"), values)
        status = "passed" if given and expected else "blocked" if not given else "failed"
        source_step_id = raw_case.get("source_step_id")
        source_exception_id = raw_case.get("source_exception_id")
        source_object = steps.get(str(source_step_id)) or exceptions.get(str(source_exception_id)) or {}
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

    sequence_inputs = dict(input_overrides or {})
    for raw_case in tests:
        for key, value in (raw_case.get("inputs") or {}).items():
            sequence_inputs.setdefault(key, value)
    sequence_result = run_reference_simulation(ir, sequence_inputs, max_cycles)
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
