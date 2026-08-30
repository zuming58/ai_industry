from __future__ import annotations

from copy import deepcopy
from typing import Any

from .adapters import CAPABILITIES
from .audit import audit_bundle
from .generator import GeneratedBundle, GENERATOR_VERSION, content_hash, generate_bundle, stable_json
from .simulation import SimulationInputError, run_reference_simulation, run_test_spec


AUTOMATED_REVIEW_VERSION = "3"
DEFAULT_REPEAT_COUNT = 20
EXTERNAL_VALIDATION_GATES = (
    {
        "id": "golden_project_acceptance",
        "title": "黄金项目双向验收",
        "status": "pending_external",
        "required_evidence": "脱敏黄金项目原资料、锁定 MachineSpec、差异清单和工程师理解确认",
    },
    {
        "id": "gxworks3_compile",
        "title": "GX Works3 导入与 Rebuild All",
        "status": "pending_external",
        "required_evidence": "精确软件版本、工程副本、Program Commit、编译日志和诊断映射",
    },
    {
        "id": "gxsimulator3_validation",
        "title": "GX Simulator3 与 MX Component 对照",
        "status": "pending_external",
        "required_evidence": "模拟器版本、TestSpec、变量读写 Trace 和异常场景报告",
    },
    {
        "id": "fx5u_hardware_validation",
        "title": "FX5U 受控台架实测",
        "status": "pending_external",
        "required_evidence": "CPU/模块/接线清单、台架记录、断电断线恢复和原始证据",
    },
    {
        "id": "electrical_engineer_signoff",
        "title": "电气工程师集中确认",
        "status": "pending_external",
        "required_evidence": "互锁、复位、异常和失效状态签字记录",
    },
)


def _bundle_fingerprint(bundle: GeneratedBundle) -> str:
    return content_hash(
        stable_json(
            {
                "control_ir": bundle.control_ir,
                "files": bundle.files,
                "test_spec": bundle.test_spec,
                "trace_links": sorted(
                    bundle.trace_links,
                    key=lambda item: (
                        str(item.get("output_path") or ""),
                        int(item.get("output_line") or 0),
                        str(item.get("entity_type") or ""),
                        str(item.get("entity_id") or ""),
                    ),
                ),
                "warnings": bundle.warnings,
            }
        )
    )


def _baseline_fingerprint(bundle: GeneratedBundle) -> str:
    return content_hash(
        stable_json(
            {
                "control_ir": bundle.control_ir,
                "test_spec": bundle.test_spec,
                "warnings": bundle.warnings,
            }
        )
    )


def _check(
    check_id: str,
    title: str,
    passed: bool,
    detail: str,
    *,
    evidence: dict[str, Any] | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "status": "passed" if passed else "failed",
        "severity": "info" if passed else "blocker",
        "detail": detail,
        "evidence": evidence or {},
        "action": action,
    }


def _fold_identifier(value: Any) -> str:
    """Normalize IEC/ST identifiers without changing diagnostic spelling."""
    return str(value or "").strip().casefold()


def _source_coverage(spec: dict[str, Any], bundle: GeneratedBundle) -> tuple[bool, dict[str, Any]]:
    expected: set[tuple[str, str]] = set()
    for item in spec.get("components", []):
        expected.add(("component", _fold_identifier(item.get("component_id"))))
    for item in spec.get("signals", []):
        expected.add(("signal", _fold_identifier(item.get("signal_id"))))
    for item in spec.get("sequence", []):
        expected.add(("sequence_step", _fold_identifier(item.get("step_id"))))
    for item in spec.get("interlocks", []):
        expected.add(("interlock", _fold_identifier(item.get("interlock_id"))))
    for item in spec.get("exceptions", []):
        expected.add(("exception", _fold_identifier(item.get("exception_id"))))

    actual = {
        (str(item.get("entity_type")), _fold_identifier(item.get("entity_id")))
        for item in bundle.trace_links
        if item.get("source_sheet") and item.get("source_row")
    }
    missing = sorted(f"{kind}:{entity_id}" for kind, entity_id in expected - actual)

    tests = bundle.test_spec.get("tests", [])
    expected_tests = {
        *(_fold_identifier(f"TEST_{item.get('step_id')}") for item in spec.get("sequence", [])),
        *(_fold_identifier(f"TEST_{item.get('exception_id')}") for item in spec.get("exceptions", [])),
    }
    traced_tests = {
        _fold_identifier(item.get("entity_id"))
        for item in bundle.trace_links
        if item.get("entity_type") == "test_case" and item.get("source_sheet") and item.get("source_row")
    }
    actual_tests = {_fold_identifier(item.get("id")) for item in tests}
    missing_tests = sorted(expected_tests - actual_tests)
    missing_test_sources = sorted(expected_tests - traced_tests)
    return not missing and not missing_tests and not missing_test_sources, {
        "expected_object_count": len(expected),
        "traced_object_count": len(expected & actual),
        "missing_objects": missing,
        "expected_test_count": len(expected_tests),
        "generated_test_count": len(actual_tests),
        "missing_tests": missing_tests,
        "missing_test_sources": missing_test_sources,
    }


def _mutation_checks(spec: dict[str, Any], bundle: GeneratedBundle) -> tuple[bool, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    steps = bundle.control_ir.get("steps", [])
    if not steps:
        return False, [{"id": "no_steps", "caught": False, "detected_codes": []}]

    undefined = deepcopy(bundle)
    undefined.control_ir["steps"][0]["completion_condition"] = "KONGPU_MISSING_REFERENCE"
    undefined_codes = {item["code"] for item in audit_bundle(spec, undefined)["findings"]}
    results.append(
        {
            "id": "undefined_reference",
            "caught": "UNDEFINED_ST_REFERENCE" in undefined_codes,
            "detected_codes": sorted(undefined_codes),
        }
    )

    broken_next = deepcopy(bundle)
    broken_next.control_ir["steps"][0]["next_step_id"] = "KONGPU_MISSING_STEP"
    next_codes = {item["code"] for item in audit_bundle(spec, broken_next)["findings"]}
    results.append(
        {
            "id": "missing_next_step",
            "caught": "NEXT_STEP_MISSING" in next_codes,
            "detected_codes": sorted(next_codes),
        }
    )

    unsafe = deepcopy(bundle)
    unsafe.files["src/PRG_AutoCycle.st"] += "\nDOWNLOAD();\n"
    unsafe_codes = {item["code"] for item in audit_bundle(spec, unsafe)["findings"]}
    results.append(
        {
            "id": "forbidden_control_operation",
            "caught": "FORBIDDEN_CONTROL_OPERATION" in unsafe_codes,
            "detected_codes": sorted(unsafe_codes),
        }
    )

    no_interlock = deepcopy(bundle)
    no_interlock.control_ir["interlocks"] = []
    interlock_codes = {item["code"] for item in audit_bundle(spec, no_interlock)["findings"]}
    results.append(
        {
            "id": "removed_interlocks",
            "caught": "INTERLOCK_NOT_DEFINED" in interlock_codes,
            "detected_codes": sorted(interlock_codes),
        }
    )

    # A condition flip remains valid ST, so it needs behavioral detection in
    # addition to the static audit. Use the generated test's declared inputs.
    flip_step, flip_case = next(
        (
            (step, test)
            for step in steps
            for test in bundle.test_spec.get("tests", [])
            if _fold_identifier(test.get("source_step_id"))
            == _fold_identifier(step.get("id"))
        ),
        (None, None),
    )
    condition = str((flip_step or {}).get("completion_condition") or "TRUE").strip() or "TRUE"
    flip_caught = False
    flip_events: list[str] = []
    if flip_step is not None and flip_case is not None:
        try:
            inputs = dict(flip_case.get("inputs") or {})
            baseline_result = run_reference_simulation(bundle.control_ir, inputs, max_cycles=20)
            flipped = deepcopy(bundle.control_ir)
            flipped_step = next(
                item for item in flipped["steps"]
                if _fold_identifier(item.get("id")) == _fold_identifier(flip_step.get("id"))
            )
            flipped_step["completion_condition"] = f"NOT ({condition})"
            flipped_result = run_reference_simulation(flipped, inputs, max_cycles=20)
            flip_caught = (
                baseline_result.get("status") != flipped_result.get("status")
                or baseline_result.get("final_step_id") != flipped_result.get("final_step_id")
                or baseline_result.get("cycles") != flipped_result.get("cycles")
            )
            flip_events = [
                f"baseline:{baseline_result.get('status')}:{baseline_result.get('cycles')}",
                f"flipped:{flipped_result.get('status')}:{flipped_result.get('cycles')}",
            ]
        except (SimulationInputError, ValueError) as exc:
            flip_events = [f"error:{exc}"]
    results.append(
        {
            "id": "condition_flip_behavior",
            "caught": flip_caught,
            "detected_codes": flip_events,
        }
    )

    stuck_ir = deepcopy(bundle.control_ir)
    stuck_ir["steps"][0]["completion_condition"] = "FALSE"
    stuck = run_reference_simulation(stuck_ir, {}, max_cycles=3)
    results.append(
        {
            "id": "missing_feedback_timeout",
            "caught": stuck["status"] == "failed" and "MAX_CYCLES_OR_MISSING_FEEDBACK" in stuck["events"],
            "detected_codes": stuck["events"],
        }
    )

    malicious_spec = {"version": "1.0", "tests": [{"id": "MUTATION", "python": "__import__('os')"}]}
    rejected = False
    try:
        run_test_spec(bundle.control_ir, malicious_spec, {}, 3)
    except SimulationInputError:
        rejected = True
    results.append(
        {
            "id": "arbitrary_code_in_testspec",
            "caught": rejected,
            "detected_codes": ["SIMULATION_INPUT_INVALID"] if rejected else [],
        }
    )
    return all(item["caught"] for item in results), results


def run_automated_review(
    spec: dict[str, Any],
    baseline: GeneratedBundle,
    *,
    run_generator_version: str,
    program_commit_id: str,
    program_git_sha: str,
    repeat_count: int = DEFAULT_REPEAT_COUNT,
) -> dict[str, Any]:
    if repeat_count < 2 or repeat_count > 50:
        raise ValueError("repeat_count 必须在 2 到 50 之间")

    checks: list[dict[str, Any]] = []
    expected = generate_bundle(spec)
    baseline_match = _baseline_fingerprint(expected) == _baseline_fingerprint(baseline)
    checks.append(
        _check(
            "immutable_baseline",
            "不可变规格与生成元数据完整性",
            baseline_match,
            "Control IR、TestSpec 与锁定规格重新生成结果一致；当前 Commit 源码已独立审计。" if baseline_match else "Control IR、TestSpec 或生成元数据与锁定规格不一致。",
            evidence={
                "baseline_hash": _baseline_fingerprint(baseline),
                "regenerated_hash": _baseline_fingerprint(expected),
                "program_commit_id": program_commit_id,
                "git_sha": program_git_sha,
            },
            action=None if baseline_match else "停止使用该基线，检查生成器版本、Control IR、TestSpec 和工件库",
        )
    )

    fingerprints = [_bundle_fingerprint(generate_bundle(spec)) for _ in range(repeat_count)]
    repeatable = len(set(fingerprints)) == 1 and run_generator_version == GENERATOR_VERSION
    checks.append(
        _check(
            "deterministic_generation",
            "确定性重复生成",
            repeatable,
            f"同一锁定规格重复生成 {repeat_count} 次，结果哈希一致。" if repeatable else "重复生成结果或生成器版本不一致。",
            evidence={
                "repeat_count": repeat_count,
                "unique_hash_count": len(set(fingerprints)),
                "content_hash": fingerprints[0],
                "run_generator_version": run_generator_version,
                "current_generator_version": GENERATOR_VERSION,
            },
            action=None if repeatable else "固定生成器版本并检查非确定性输入",
        )
    )

    covered, coverage = _source_coverage(spec, baseline)
    checks.append(
        _check(
            "source_trace_coverage",
            "MachineSpec 与 Excel 来源追溯覆盖",
            covered,
            "组件、信号、工步、互锁、异常和 TestSpec 均可回溯来源。" if covered else "存在未建立来源追溯的对象或测试。",
            evidence=coverage,
            action=None if covered else "补齐生成器 TraceLink 后重新生成",
        )
    )

    audit_report = audit_bundle(spec, baseline)
    audit_passed = audit_report["status"] != "blocked"
    checks.append(
        _check(
            "generation_static_audit",
            "生成物确定性静态审计",
            audit_passed,
            "静态审计没有 blocker。" if audit_passed else "静态审计发现 blocker。",
            evidence={"input_hash": audit_report["input_hash"], **audit_report["summary"]},
            action=None if audit_passed else "按审计发现修复并创建新的生成基线",
        )
    )

    simulation_error: SimulationInputError | ValueError | None = None
    try:
        first_simulation = run_test_spec(baseline.control_ir, baseline.test_spec, {}, 100)
        second_simulation = run_test_spec(baseline.control_ir, baseline.test_spec, {}, 100)
    except (SimulationInputError, ValueError) as exc:
        simulation_error = exc
        first_simulation = {
            "engine_version": "unknown",
            "status": "failed",
            "test_summary": {"total": 0, "passed": 0, "failed": 0, "blocked": 0},
            "traces": [],
        }
        second_simulation = first_simulation
    simulation_repeatable = (
        simulation_error is None
        and stable_json(first_simulation) == stable_json(second_simulation)
        and first_simulation.get("status") == "passed"
    )
    checks.append(
        _check(
            "reference_executor_determinism",
            "受限参考执行器确定性",
            simulation_repeatable,
            "相同 Control IR、TestSpec 和输入产生相同且通过的 Trace 与用例结果。"
            if simulation_repeatable
            else f"参考执行器执行失败：{simulation_error}" if simulation_error else "参考执行器结果未通过，或重复结果不一致。",
            evidence={
                "engine_version": first_simulation.get("engine_version"),
                "result_status": first_simulation.get("status"),
                "test_summary": first_simulation.get("test_summary"),
                "trace_hash": content_hash(stable_json(first_simulation.get("traces", []))),
            },
            action=None
            if simulation_repeatable
            else "检查失败用例，并排除执行器的时间、随机数或共享状态",
        )
    )

    mutations_passed, mutations = _mutation_checks(spec, baseline)
    checks.append(
        _check(
            "mutation_detection",
            "审计与参考执行器变异检测",
            mutations_passed,
            "断引用、断流程、危险操作、互锁删除、条件翻转、缺反馈和任意代码注入均被检测。" if mutations_passed else "至少一个故意植入的缺陷未被检测。",
            evidence={"mutations": mutations},
            action=None if mutations_passed else "补充相应审计规则或模拟断言",
        )
    )

    forbidden_capabilities = sorted(
        value for value in CAPABILITIES if value in {"download", "run", "stop", "force_output", "write_plc"}
    )
    safety_passed = not forbidden_capabilities
    checks.append(
        _check(
            "product_safety_boundary",
            "产品控制安全边界",
            safety_passed,
            "Adapter 契约不包含 PLC 下载、RUN/STOP、强制输出或在线写入。" if safety_passed else "Adapter 契约暴露了禁止的控制能力。",
            evidence={"capabilities": list(CAPABILITIES), "forbidden_capabilities": forbidden_capabilities},
            action=None if safety_passed else "删除禁止能力并重新执行全部安全测试",
        )
    )

    input_hash = content_hash(
        stable_json(
            {
                "review_version": AUTOMATED_REVIEW_VERSION,
                "repeat_count": repeat_count,
                "baseline_hash": _bundle_fingerprint(baseline),
                "program_commit_id": program_commit_id,
                "git_sha": program_git_sha,
                "generator_version": run_generator_version,
            }
        )
    )
    failed = [item for item in checks if item["status"] == "failed"]
    return {
        "review_version": AUTOMATED_REVIEW_VERSION,
        "input_hash": input_hash,
        "status": "passed" if not failed else "blocked",
        "verification_level": "automatic",
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "external_pending": len(EXTERNAL_VALIDATION_GATES),
        },
        "external_validation_gates": list(EXTERNAL_VALIDATION_GATES),
        "claim_boundary": "自动审核只证明代码和确定性自动验证范围，不代表厂商工具、真实 PLC 或电气工程师确认。",
    }
