from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import select

from kongpu_api.audit import audit_bundle
from kongpu_api.adapters import CAPABILITIES, adapter
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
        "signals": [{"name": "Start"}],
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


def test_restricted_test_spec_reports_cases_and_rejects_unknown_fields() -> None:
    ir = {
        "signals": [{"name": "Start"}, {"name": "Done"}],
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


def test_reference_simulation_api_trace_and_evidence_immutability(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generated_run(client, project, locked_example)
    audited = client.post(f"/api/v1/generation-runs/{run['id']}/audit")
    assert audited.status_code == 200
    simulation = client.post(
        f"/api/v1/projects/{project['id']}/simulation-runs",
        json={"generation_run_id": run["id"], "input_overrides": {}, "max_cycles": 10, "expected_generation_revision": run["revision"]},
    )
    assert simulation.status_code == 201, simulation.text
    body = simulation.json()
    assert body["verification_level"] == "automatic_reference"
    assert body["program_commit_id"]
    assert body["test_spec_revision_id"]
    trace = client.get(f"/api/v1/simulation-runs/{body['id']}/trace")
    assert trace.status_code == 200
    assert trace.json()["simulation_run_id"] == body["id"]

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
