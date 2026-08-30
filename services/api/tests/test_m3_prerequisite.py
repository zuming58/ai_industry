from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from kongpu_api.audit import audit_bundle
from kongpu_api.adapters import CAPABILITIES, adapter
from kongpu_api.automated_review import run_automated_review
from kongpu_api.generator import generate_bundle
from kongpu_api.models import GenerationRun
from kongpu_api.simulation import run_reference_simulation, run_test_spec, SimulationInputError


def _generated_run(client: TestClient, project: dict, locked: dict) -> dict:
    response = client.post(
        f"/api/v1/projects/{project['id']}/generation-runs",
        json={"spec_revision_id": locked["revision"]["id"], "branch_name": "generated/m3-acceptance"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_adapter_registry_and_missing_vendor_detection(client: TestClient, project: dict) -> None:
    listed = client.get("/api/v1/adapters")
    assert listed.status_code == 200
    adapters = {item["adapter_id"]: item for item in listed.json()}
    assert {"reference", "gxworks3", "autoshop", "codesys"} <= adapters.keys()
    assert "compile" in adapters["gxworks3"]["capabilities"]
    assert "download" not in adapters["gxworks3"]["capabilities"]

    detected = client.post("/api/v1/adapters/detect", json={"adapter_id": "gxworks3", "project_id": project["id"]})
    assert detected.status_code == 200, detected.text
    body = detected.json()
    assert body["status"] in {"unavailable", "manual_required"}
    assert body["verification_level"] == "unverified"
    environments = client.get(f"/api/v1/projects/{project['id']}/adapter-environments")
    assert environments.status_code == 200
    assert environments.json()[0]["adapter_id"] == "gxworks3"


def test_adapter_contract_is_bounded_and_manual_by_default() -> None:
    manual = adapter("gxworks3")
    assert set(manual.get_capabilities()) == set(CAPABILITIES)
    assert "download" not in manual.get_capabilities()
    result = manual.compile("C:/isolated/workspace")
    assert result["status"] == "manual_required"
    assert result["verification_level"] == "unverified"
    reference = adapter("reference")
    assert reference.start_simulation("ignored") ["verification_level"] == "automatic_reference"


def test_generation_audit_is_stable_and_compile_uses_automatic_review(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generated_run(client, project, locked_example)
    automatic = client.get(
        f"/api/v1/projects/{project['id']}/automated-reviews"
    )
    assert automatic.status_code == 200
    assert automatic.json()[0]["generation_run_id"] == run["id"]
    assert automatic.json()[0]["status"] == "passed"

    first = client.post(f"/api/v1/generation-runs/{run['id']}/audit")
    second = client.post(f"/api/v1/generation-runs/{run['id']}/audit")
    assert first.status_code == second.status_code == 200
    assert first.json()["input_hash"] == second.json()["input_hash"]
    assert first.json()["findings"] == second.json()["findings"]

    compile_run = client.post(f"/api/v1/projects/{project['id']}/compile-runs", json={"generation_run_id": run["id"], "adapter_id": "gxworks3", "expected_generation_revision": run["revision"]})
    assert compile_run.status_code == 201, compile_run.text
    assert compile_run.json()["status"] == "manual_required"
    assert compile_run.json()["verification_level"] == "unverified"


def test_automated_review_is_persisted_reused_and_downloadable(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generated_run(client, project, locked_example)
    listed = client.get(f"/api/v1/projects/{project['id']}/automated-reviews")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    automatic = listed.json()[0]
    assert automatic["status"] == "passed"
    assert automatic["review_version"] == "3"
    assert automatic["verification_level"] == "automatic"
    assert automatic["repeat_count"] == 20
    assert automatic["summary"] == {
        "total": 7,
        "passed": 7,
        "failed": 0,
        "external_pending": 5,
    }
    assert {
        gate["status"] for gate in automatic["external_validation_gates"]
    } == {"pending_external"}
    deterministic = next(
        check
        for check in automatic["checks"]
        if check["id"] == "deterministic_generation"
    )
    assert deterministic["evidence"]["repeat_count"] == 20
    assert deterministic["evidence"]["unique_hash_count"] == 1
    mutations = next(
        check
        for check in automatic["checks"]
        if check["id"] == "mutation_detection"
    )
    assert all(item["caught"] for item in mutations["evidence"]["mutations"])
    assert any(item["id"] == "condition_flip_behavior" for item in mutations["evidence"]["mutations"])

    downloaded = client.get(f"/api/v1/artifacts/{automatic['report_artifact_id']}")
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == automatic["report_sha256"]
    by_id = client.get(f"/api/v1/automated-reviews/{automatic['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["input_hash"] == automatic["input_hash"]

    repeated = client.post(
        f"/api/v1/projects/{project['id']}/automated-reviews",
        json={
            "generation_run_id": run["id"],
            "repeat_count": 20,
            "expected_generation_revision": run["revision"],
        },
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == automatic["id"]
    assert repeated.json()["reused"] is True
    assert repeated.json()["report_sha256"] == automatic["report_sha256"]


def test_automated_review_source_coverage_uses_iec_identifier_semantics(locked_example: dict) -> None:
    spec = locked_example["revision"]["data"]
    bundle = generate_bundle(spec)
    for link in bundle.trace_links:
        link["entity_id"] = str(link["entity_id"]).swapcase()
    report = run_automated_review(
        spec,
        bundle,
        run_generator_version=bundle.control_ir["generator_version"],
        program_commit_id="commit-id",
        program_git_sha="0" * 40,
        repeat_count=2,
    )
    coverage = next(item for item in report["checks"] if item["id"] == "source_trace_coverage")
    assert coverage["status"] == "passed"


def test_automated_review_validates_limits_revision_and_generator_version(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generated_run(client, project, locked_example)
    for repeat_count in (1, 51):
        invalid = client.post(
            f"/api/v1/projects/{project['id']}/automated-reviews",
            json={
                "generation_run_id": run["id"],
                "repeat_count": repeat_count,
                "expected_generation_revision": run["revision"],
            },
        )
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "REQUEST_VALIDATION_FAILED"

    stale = client.post(
        f"/api/v1/projects/{project['id']}/automated-reviews",
        json={
            "generation_run_id": run["id"],
            "repeat_count": 2,
            "expected_generation_revision": run["revision"] + 1,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "REVISION_CONFLICT"

    database = client.app.state.database
    with database.session_factory() as session:
        row = session.scalar(select(GenerationRun).where(GenerationRun.id == run["id"]))
        assert row is not None
        row.generator_version = "fx5u-st-v1"
        session.commit()

    blocked = client.post(
        f"/api/v1/projects/{project['id']}/automated-reviews",
        json={
            "generation_run_id": run["id"],
            "repeat_count": 2,
            "expected_generation_revision": run["revision"],
        },
    )
    assert blocked.status_code == 201, blocked.text
    assert blocked.json()["status"] == "blocked"
    deterministic = next(
        check
        for check in blocked.json()["checks"]
        if check["id"] == "deterministic_generation"
    )
    assert deterministic["status"] == "failed"
    assert deterministic["evidence"]["run_generator_version"] == "fx5u-st-v1"


def test_audit_detects_undefined_reference_and_forbidden_operation(locked_example: dict) -> None:
    spec = locked_example["revision"]["data"]
    bundle = generate_bundle(spec)
    program = bundle.files["src/PRG_AutoCycle.st"] + "\nDOWNLOAD();\n"
    broken = type(bundle)(bundle.control_ir, {**bundle.files, "src/PRG_AutoCycle.st": program}, bundle.test_spec, bundle.trace_links, bundle.warnings)
    broken.control_ir["steps"][0]["completion_condition"] = "MISSING_INPUT"
    report = audit_bundle(spec, broken)
    codes = {finding["code"] for finding in report["findings"]}
    assert "UNDEFINED_ST_REFERENCE" in codes
    assert "FORBIDDEN_CONTROL_OPERATION" in codes
    assert report["status"] == "blocked"


def test_audit_ignores_prohibited_words_in_st_comments_and_strings(locked_example: dict) -> None:
    spec = locked_example["revision"]["data"]
    bundle = generate_bundle(spec)
    program = bundle.files["src/PRG_AutoCycle.st"] + (
        "\n// DOWNLOAD(); FORCED_OUTPUT\n"
        "(* DOWNLOAD();\nFORCED_OUTPUT *)\n"
        "/* DOWNLOAD(); */\n"
        "KP_Note := 'DOWNLOAD(); FORCED_OUTPUT';\n"
    )
    commented = type(bundle)(
        bundle.control_ir,
        {**bundle.files, "src/PRG_AutoCycle.st": program},
        bundle.test_spec,
        bundle.trace_links,
        bundle.warnings,
    )
    codes = {item["code"] for item in audit_bundle(spec, commented)["findings"]}
    assert "FORBIDDEN_CONTROL_OPERATION" not in codes

    executable = type(bundle)(
        bundle.control_ir,
        {**bundle.files, "src/PRG_AutoCycle.st": program + "\nDOWNLOAD();\n"},
        bundle.test_spec,
        bundle.trace_links,
        bundle.warnings,
    )
    executable_codes = {
        item["code"] for item in audit_bundle(spec, executable)["findings"]
    }
    assert "FORBIDDEN_CONTROL_OPERATION" in executable_codes


def test_audit_detects_loop_target_and_missing_interlock_coverage(locked_example: dict) -> None:
    spec = locked_example["revision"]["data"]
    bundle = generate_bundle(spec)
    bundle.control_ir["steps"][0]["next_step_id"] = bundle.control_ir["steps"][0]["id"]
    bundle.control_ir["steps"][0]["next_step_number"] = bundle.control_ir["steps"][0]["number"]
    bundle.control_ir["interlocks"] = []
    report = audit_bundle(spec, bundle)
    codes = {finding["code"] for finding in report["findings"]}
    assert "LOOP_NO_EXIT" in codes
    assert "INTERLOCK_NOT_DEFINED" in codes
    assert "RESET_PATH_MISSING" in codes


def test_reference_simulation_success_timeout_and_unknown_input() -> None:
    ir = {
        "signals": [{"name": "Start", "direction": "DI"}],
        "steps": [
            {"id": "S1", "completion_condition": "Start", "actions": "", "next_step_id": "S2"},
            {"id": "S2", "completion_condition": "TRUE", "actions": "", "next_step_id": "END"},
        ],
    }
    passed = run_reference_simulation(ir, {"Start": True}, 5)
    assert passed["status"] == "passed"
    failed = run_reference_simulation(ir, {"Start": False}, 2)
    assert failed["status"] == "failed"
    try:
        run_reference_simulation(ir, {"Unknown": True}, 2)
    except SimulationInputError:
        pass
    else:
        raise AssertionError("unknown inputs must be rejected")


def test_reference_simulation_is_case_insensitive_like_iec_st() -> None:
    ir = {
        "signals": [
            {"id": "SIG_START", "name": "Start", "direction": "DI"},
            {"id": "SIG_DONE", "name": "Done", "direction": "DO"},
        ],
        "steps": [{
            "id": "S1",
            "entry_condition": "start",
            "completion_condition": "DONE",
            "actions": "done := TRUE",
            "next_step_id": "end",
        }],
    }
    result = run_reference_simulation(ir, {"START": True}, 2)
    assert result["status"] == "passed"
    assert result["traces"][0]["outputs"] == {"Done": True}


def test_reference_simulation_rejects_ambiguous_ir_identifiers() -> None:
    base = {
        "signals": [{"id": "SIG_READY", "name": "Ready", "direction": "DI"}],
        "steps": [{"id": "S1", "entry_condition": "TRUE", "completion_condition": "Ready", "actions": "", "next_step_id": "END"}],
        "exceptions": [{"exception_id": "EX_TIMEOUT"}],
    }
    variants = [
        {**base, "signals": [*base["signals"], {"id": "sig_ready", "name": "Other", "direction": "DI"}]},
        {**base, "signals": [*base["signals"], {"id": "SIG_OTHER", "name": "ready", "direction": "DI"}]},
        {**base, "steps": [*base["steps"], {**base["steps"][0], "id": "s1"}]},
        {**base, "exceptions": [*base["exceptions"], {"exception_id": "ex_timeout"}]},
    ]
    for ir in variants:
        with pytest.raises(SimulationInputError, match="重复"):
            run_reference_simulation(ir, {}, 2)


def test_restricted_test_spec_reports_cases_and_rejects_unknown_fields() -> None:
    ir = {
        "signals": [{"name": "Start", "direction": "DI"}, {"name": "Done", "direction": "DO"}],
        "steps": [{"id": "S1", "completion_condition": "Start", "actions": "Done := TRUE", "next_step_id": "END", "source": {"sheet": "Sequence", "row": 2}}],
        "exceptions": [],
    }
    test_spec = {"version": "1.0", "tests": [{"id": "T1", "source_step_id": "S1", "given": "Start", "when": "Done := TRUE", "expect": "Done"}]}
    result = run_test_spec(ir, test_spec, {"Start": True}, 3)
    assert result["test_summary"] == {"total": 1, "passed": 1, "failed": 0, "blocked": 0}
    assert result["test_cases"][0]["source"] == {"sheet": "Sequence", "row": 2}
    broken = {"version": "1.0", "tests": [{"id": "T1", "python": "__import__('os')"}]}
    try:
        run_test_spec(ir, broken, {"Start": True}, 3)
    except SimulationInputError:
        pass
    else:
        raise AssertionError("TestSpec must reject arbitrary fields")


def test_generated_testspec_uses_deterministic_inputs(locked_example: dict) -> None:
    bundle = generate_bundle(locked_example["revision"]["data"])
    result = run_test_spec(bundle.control_ir, bundle.test_spec, {}, 20)
    assert result["status"] == "passed"
    assert result["test_summary"]["failed"] == 0
    assert result["test_summary"]["blocked"] == 0


def test_reference_simulation_scheduled_inputs_timeout_and_trace_boundaries() -> None:
    ir = {
        "signals": [
            {"id": "SIG_START", "name": "Start", "direction": "DI"},
            {"id": "SIG_FEEDBACK", "name": "Feedback", "direction": "DI"},
            {"id": "SIG_COMMAND", "name": "Command", "direction": "DO"},
        ],
        "steps": [{
            "id": "S1",
            "entry_condition": "Start",
            "completion_condition": "Feedback",
            "actions": "Command := TRUE",
            "next_step_id": "END",
            "duration": 200,
            "duration_unit": "ms",
            "source": {"sheet": "Sequence", "row": 2},
        }],
        "interlocks": [],
    }
    completed = run_reference_simulation(
        ir,
        {"Start": True},
        3,
        input_schedule={2: {"Feedback": True}},
        cycle_time_ms=100,
    )
    assert completed["status"] == "passed"
    assert completed["cycles"] == 2
    assert completed["traces"][0]["inputs"] == {"Feedback": False, "Start": True}
    assert completed["traces"][0]["outputs"] == {"Command": True}
    assert completed["traces"][0]["source"] == {"sheet": "Sequence", "row": 2}

    timed_out = run_reference_simulation(
        ir, {"Start": True}, 2, cycle_time_ms=100
    )
    timeout = next(item for item in timed_out["diagnostics"] if item["code"] == "STEP_TIMEOUT")
    assert timeout["cycle"] == 2
    assert timeout["timeout_cycles"] == 2
    assert timeout["severity"] == "blocker"


def test_reference_simulation_interlocks_restart_disconnect_and_reset_edges() -> None:
    interlocked_ir = {
        "signals": [
            {"id": "SIG_PERMIT", "name": "Permit", "direction": "DI"},
            {"id": "SIG_COMMAND", "name": "Command", "direction": "DO"},
        ],
        "steps": [{"id": "S1", "entry_condition": "TRUE", "completion_condition": "Command", "actions": "Command := TRUE", "next_step_id": "END"}],
        "interlocks": [{"interlock_id": "ILK1", "action_id": "SIG_COMMAND", "allow_condition": "SIG_PERMIT", "inhibit_condition": "AxisMoving"}],
    }
    blocked = run_reference_simulation(interlocked_ir, {"Permit": False}, 1)
    assert "INTERLOCK_BLOCKED:ILK1" in blocked["traces"][0]["events"]
    assert blocked["traces"][0]["inputs"] == {"Permit": False}
    assert blocked["traces"][0]["internal_state"] == {"AxisMoving": False}
    assert any(item["code"] == "INTERLOCK_INTERNAL_STATE_DEFAULTED" for item in blocked["diagnostics"])
    with pytest.raises(SimulationInputError, match="未知输入"):
        run_reference_simulation(interlocked_ir, {"AxisMoving": True}, 1)

    communication_ir = {
        "signals": [
            {"id": "SIG_READY", "name": "Ready", "direction": "COMM"},
            {"id": "SIG_RESET", "name": "Reset", "direction": "DI"},
        ],
        "steps": [
            {"id": "S1", "entry_condition": "TRUE", "completion_condition": "Ready", "actions": "", "next_step_id": "S2"},
            {"id": "S2", "entry_condition": "TRUE", "completion_condition": "TRUE", "actions": "", "next_step_id": "END"},
        ],
        "interlocks": [],
    }
    recovered = run_reference_simulation(communication_ir, {"Ready": True}, 3, disconnect_cycles=[1])
    assert recovered["status"] == "passed"
    assert recovered["traces"][0]["communication"] == "disconnected"
    assert recovered["traces"][1]["communication"] == "connected"
    restarted = run_reference_simulation(communication_ir, {"Ready": True}, 4, restart_cycles=[2])
    assert restarted["status"] == "passed"
    assert "RESTART_APPLIED" in restarted["traces"][1]["events"]
    reset_once = run_reference_simulation(communication_ir, {"Ready": True}, 4, input_schedule={1: {"Reset": True}})
    assert sum("RESET_TRIGGERED" in trace["events"] for trace in reset_once["traces"]) == 1
    with pytest.raises(SimulationInputError, match="同时重启和断开通信"):
        run_reference_simulation(communication_ir, {"Ready": True}, 3, restart_cycles=[2], disconnect_cycles=[2])


def test_reference_simulation_rejects_malformed_dsl_and_non_finite_values() -> None:
    ir = {
        "signals": [{"name": "Known", "direction": "DI"}],
        "steps": [{"id": "S1", "entry_condition": "TRUE", "completion_condition": "Known", "actions": "", "next_step_id": "END"}],
        "interlocks": [],
    }
    with pytest.raises(SimulationInputError, match="有限数值"):
        run_reference_simulation(ir, {"Known": math.nan}, 1)
    with pytest.raises(SimulationInputError, match="未知输入"):
        run_reference_simulation(ir, {}, 2, input_schedule={1: {"Missing": True}})

    direction_ir = {
        "signals": [
            {"name": "Input", "direction": "DI"},
            {"name": "Output", "direction": "DO"},
        ],
        "steps": [{"id": "S1", "entry_condition": "TRUE", "completion_condition": "TRUE", "actions": "Output := TRUE", "next_step_id": "END"}],
        "interlocks": [],
    }
    with pytest.raises(SimulationInputError, match="不可作为外部输入"):
        run_reference_simulation(direction_ir, {"Output": True}, 1)
    invalid_action = deepcopy(direction_ir)
    invalid_action["steps"][0]["actions"] = "Input := TRUE"
    with pytest.raises(SimulationInputError, match="动作目标"):
        run_reference_simulation(invalid_action, {"Input": True}, 1)
    with pytest.raises(SimulationInputError, match="周期重复"):
        run_reference_simulation(ir, {}, 2, input_schedule={"1": {"Known": True}, "01": {"Known": False}})

    unknown_action = deepcopy(ir)
    unknown_action["steps"][0]["actions"] = "Missing := TRUE"
    with pytest.raises(SimulationInputError, match="动作目标"):
        run_reference_simulation(unknown_action, {"Known": True}, 1)
    malicious = deepcopy(ir)
    malicious["steps"][0]["completion_condition"] = "__import__('os')"
    with pytest.raises(SimulationInputError, match="不支持的语法"):
        run_reference_simulation(malicious, {}, 1)


def test_generation_audit_checks_artifact_integrity_trace_and_internal_state(locked_example: dict) -> None:
    spec = locked_example["revision"]["data"]
    bundle = generate_bundle(spec)
    baseline = audit_bundle(spec, bundle)
    baseline_codes = {item["code"] for item in baseline["findings"]}
    assert baseline["status"] == "review_ready"
    assert "INTERLOCK_INTERNAL_STATE_UNDECLARED" in baseline_codes

    missing_file = deepcopy(bundle)
    del missing_file.files["README.md"]
    assert "GENERATED_FILE_MISSING" in {item["code"] for item in audit_bundle(spec, missing_file)["findings"]}

    invalid_json = deepcopy(bundle)
    invalid_json.files["generated/ControlIR.json"] = "{not-json"
    assert "CONTROL_IR_JSON_INVALID" in {item["code"] for item in audit_bundle(spec, invalid_json)["findings"]}

    missing_trace = deepcopy(bundle)
    removed = missing_trace.trace_links.pop(0)
    report = audit_bundle(spec, missing_trace)
    assert any(item["code"] == "TRACE_LINK_MISSING" and item["entity_id"] == removed["entity_id"] for item in report["findings"])

    missing_source = deepcopy(bundle)
    missing_source.trace_links[0]["source_sheet"] = None
    assert "TRACE_SOURCE_MISSING" in {item["code"] for item in audit_bundle(spec, missing_source)["findings"]}

    invalid_test_input = deepcopy(bundle)
    output_name = next(item["name"] for item in invalid_test_input.control_ir["signals"] if item.get("direction") == "DO")
    invalid_test_input.test_spec["tests"][0]["inputs"][output_name] = True
    invalid_test_input.files["tests/TestSpec.json"] = json.dumps(invalid_test_input.test_spec, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    assert "TEST_INPUT_DIRECTION_INVALID" in {item["code"] for item in audit_bundle(spec, invalid_test_input)["findings"]}

    invalid_action_direction = deepcopy(bundle)
    input_name = next(item["name"] for item in invalid_action_direction.control_ir["signals"] if item.get("direction") == "DI")
    invalid_action_direction.control_ir["steps"][0]["actions"] = f"{input_name} := TRUE"
    assert "ACTION_TARGET_DIRECTION_INVALID" in {item["code"] for item in audit_bundle(spec, invalid_action_direction)["findings"]}


def test_generation_audit_treats_st_identifiers_case_insensitively(locked_example: dict) -> None:
    spec = locked_example["revision"]["data"]
    bundle = generate_bundle(spec)
    signal = bundle.control_ir["signals"][0]
    original_name = signal["name"]
    signal["name"] = original_name.swapcase()
    bundle.control_ir["steps"][0]["completion_condition"] = original_name.lower()
    report = audit_bundle(spec, bundle)
    codes = {item["code"] for item in report["findings"]}
    assert "UNDEFINED_ST_REFERENCE" not in codes

    duplicate = deepcopy(bundle)
    duplicate.control_ir["signals"].append(dict(signal, id="SIG_CASE_DUP", name=original_name.lower()))
    duplicate_codes = {item["code"] for item in audit_bundle(spec, duplicate)["findings"]}
    assert "DUPLICATE_ST_SYMBOL" in duplicate_codes


def test_automated_review_keeps_all_checks_when_reference_executor_fails(locked_example: dict) -> None:
    spec = locked_example["revision"]["data"]
    bundle = generate_bundle(spec)
    bundle.test_spec["tests"][0]["given"] = "UNKNOWN_TEST_SIGNAL"
    bundle.files["tests/TestSpec.json"] = json.dumps(bundle.test_spec, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    report = run_automated_review(
        spec,
        bundle,
        run_generator_version=bundle.control_ir["generator_version"],
        program_commit_id="commit-id",
        program_git_sha="0" * 40,
        repeat_count=2,
    )
    assert report["status"] == "blocked"
    assert len(report["checks"]) == 7
    checks = {item["id"]: item for item in report["checks"]}
    assert checks["deterministic_generation"]["status"] == "passed"
    assert checks["reference_executor_determinism"]["status"] == "failed"


def test_reference_simulation_api_trace_and_evidence_immutability(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generated_run(client, project, locked_example)
    audited = client.post(f"/api/v1/generation-runs/{run['id']}/audit")
    assert audited.status_code == 200
    invalid = client.post(
        f"/api/v1/projects/{project['id']}/simulation-runs",
        json={"generation_run_id": run["id"], "input_overrides": {}, "max_cycles": 10, "expected_generation_revision": run["revision"], "unknown_field": True},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "REQUEST_VALIDATION_FAILED"

    conflict = client.post(
        f"/api/v1/projects/{project['id']}/simulation-runs",
        json={"generation_run_id": run["id"], "input_overrides": {}, "max_cycles": 10, "restart_cycles": [2], "disconnect_cycles": [2], "expected_generation_revision": run["revision"]},
    )
    assert conflict.status_code == 422
    assert conflict.json()["code"] == "SIMULATION_INPUT_INVALID"

    simulation = client.post(
        f"/api/v1/projects/{project['id']}/simulation-runs",
        json={"generation_run_id": run["id"], "input_overrides": {}, "input_schedule": {"1": {"SIG_TRAY_PRESENT": True}}, "restart_cycles": [], "disconnect_cycles": [], "max_cycles": 10, "cycle_time_ms": 100, "expected_generation_revision": run["revision"]},
    )
    assert simulation.status_code == 201, simulation.text
    body = simulation.json()
    assert body["verification_level"] == "automatic_reference"
    assert body["program_commit_id"]
    assert body["test_spec_revision_id"]
    trace = client.get(f"/api/v1/simulation-runs/{body['id']}/trace")
    assert trace.status_code == 200
    assert trace.json()["simulation_run_id"] == body["id"]
    assert trace.json()["traces"][0]["entry_condition"]
    assert trace.json()["traces"][0]["source"]["sheet"] == "Sequence"
    assert trace.json()["traces"][0]["internal_state"] == {"AxisMoving": False}

    evidence = client.post(
        f"/api/v1/projects/{project['id']}/compile-runs",
        json={"generation_run_id": run["id"], "adapter_id": "gxworks3", "expected_generation_revision": run["revision"]},
    )
    assert evidence.status_code == 201
    compile_id = evidence.json()["id"]
    upload = client.post(
        f"/api/v1/compile-runs/{compile_id}/evidence",
        files={"file": ("vendor.log", b"manual evidence", "text/plain")},
        data={"expected_revision": evidence.json()["revision"]},
    )
    assert upload.status_code == 201, upload.text
    evidence_body = upload.json()
    assert evidence_body["verification_level"] == "manual_unverified"
    assert evidence_body["sha256"] == hashlib.sha256(b"manual evidence").hexdigest()
    stale = client.post(
        f"/api/v1/compile-runs/{compile_id}/evidence",
        files={"file": ("vendor-2.log", b"stale", "text/plain")},
        data={"expected_revision": evidence.json()["revision"]},
    )
    assert stale.status_code == 409
    compile_list = client.get(f"/api/v1/projects/{project['id']}/compile-runs")
    simulation_list = client.get(f"/api/v1/projects/{project['id']}/simulation-runs")
    assert compile_list.status_code == simulation_list.status_code == 200
    assert compile_list.json()[0]["evidence_count"] == 1
    assert simulation_list.json()[0]["id"] == body["id"]
