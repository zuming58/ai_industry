from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from kongpu_api.delivery import (
    DeliveryInputError,
    build_delivery_candidate,
    safe_package_path,
    verify_delivery_candidate,
)
from kongpu_api.monitoring import MonitoringInputError, analyze_snapshot, build_variable_map


def _generated_run(
    client: TestClient, project: dict, locked: dict, branch: str
) -> dict:
    response = client.post(
        f"/api/v1/projects/{project['id']}/generation-runs",
        json={
            "spec_revision_id": locked["revision"]["id"],
            "branch_name": branch,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_delivery_zip_is_deterministic_and_rejects_tampering() -> None:
    entries = {
        "program/src/PRG_Main.st": b"PROGRAM PRG_Main\nEND_PROGRAM\n",
        "spec/MachineSpec.locked.json": b"{\"schema_version\":\"1.0\"}\n",
    }
    seed = {
        "candidate_version": "RC-0001",
        "status": "external_validation_required",
    }
    first, manifest = build_delivery_candidate(seed, entries)
    second, second_manifest = build_delivery_candidate(seed, entries)
    assert first == second
    assert manifest == second_manifest == verify_delivery_candidate(first)

    for invalid in ("../escape", "/absolute", "C:/drive", "a/../b"):
        with pytest.raises(DeliveryInputError):
            safe_package_path(invalid)

    source = zipfile.ZipFile(io.BytesIO(first), mode="r")
    tampered_buffer = io.BytesIO()
    with zipfile.ZipFile(tampered_buffer, mode="w") as tampered:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "program/src/PRG_Main.st":
                content += b"DOWNLOAD();\n"
            tampered.writestr(item, content)
    source.close()
    with pytest.raises(DeliveryInputError, match="哈希"):
        verify_delivery_candidate(tampered_buffer.getvalue())


def test_readiness_reports_automatic_work_without_upgrading_external_gates(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generated_run(client, project, locked_example, "generated/readiness")
    before = client.get(
        f"/api/v1/projects/{project['id']}/readiness",
        params={"generation_run_id": run["id"]},
    )
    assert before.status_code == 200, before.text
    pending = before.json()
    assert pending["schema"] == "kongpu-readiness/v1"
    assert pending["status"] == "automatic_work_remaining"
    states = {item["id"]: item["status"] for item in pending["checks"]}
    assert states["locked_spec"] == "ready"
    assert states["automated_review"] == "ready"
    assert states["reference_simulation"] == "remaining"
    assert states["candidate"] == "remaining"
    assert {item["status"] for item in pending["external_validation_gates"]} == {"pending_external"}

    simulation = client.post(
        f"/api/v1/projects/{project['id']}/simulation-runs",
        json={"generation_run_id": run["id"], "expected_generation_revision": run["revision"]},
    )
    assert simulation.status_code == 201, simulation.text
    candidate_response = client.post(
        f"/api/v1/projects/{project['id']}/release-candidates",
        json={"generation_run_id": run["id"], "expected_generation_revision": run["revision"]},
    )
    assert candidate_response.status_code == 201, candidate_response.text
    candidate = candidate_response.json()
    after_candidate = client.get(
        f"/api/v1/projects/{project['id']}/readiness",
        params={"generation_run_id": run["id"]},
    )
    states = {item["id"]: item["status"] for item in after_candidate.json()["checks"]}
    assert states["candidate"] == "ready"
    assert states["candidate_integrity"] == "remaining"

    verified = client.post(
        f"/api/v1/release-candidates/{candidate['id']}/verify",
        json={"expected_candidate_revision": candidate["revision"]},
    )
    assert verified.status_code == 200, verified.text
    complete = client.get(
        f"/api/v1/projects/{project['id']}/readiness",
        params={"generation_run_id": run["id"]},
    )
    ready = complete.json()
    assert ready["status"] == "ready_for_external_validation"
    assert ready["verification_level"] == "automatic"
    assert ready["summary"] == {"total": 8, "ready": 8, "remaining": 0, "external_pending": 5}
    assert "pending_external" in ready["claim_boundary"]


def test_monitoring_identifier_semantics_and_snapshot_validation() -> None:
    ir = {
        "signals": [
            {"id": "SIG_READY", "name": "Ready", "direction": "DI", "source": {"sheet": "Signals", "row": 2}},
            {"id": "SIG_DONE", "name": "Done", "direction": "DO", "source": {"sheet": "Signals", "row": 3}},
        ],
        "steps": [{"id": "STEP_1", "completion_condition": "READY", "source": {"sheet": "Sequence", "row": 2}}],
    }
    variables = build_variable_map(ir)
    analysis = analyze_snapshot(ir, variables, {"ready": True}, "step_1")
    assert analysis["status"] == "recorded_unverified"
    assert analysis["current_step_id"] == "STEP_1"
    assert analysis["condition_values"] == {"Ready": True}

    with pytest.raises(MonitoringInputError, match="重复"):
        analyze_snapshot(ir, variables, {"Ready": True, "READY": False}, None)
    with pytest.raises(MonitoringInputError, match="有限"):
        analyze_snapshot(ir, variables, {"Ready": float("nan")}, None)
    with pytest.raises(MonitoringInputError, match="不存在"):
        analyze_snapshot(ir, variables, {}, "step_missing")
    ambiguous = {**ir, "signals": [*ir["signals"], {"id": "SIG_READY_2", "name": "ready", "direction": "DI"}]}
    with pytest.raises(MonitoringInputError, match="大小写"):
        build_variable_map(ambiguous)


def test_release_candidate_and_read_only_monitoring_flow(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generated_run(
        client, project, locked_example, "generated/release-monitoring"
    )

    missing_simulation = client.post(
        f"/api/v1/projects/{project['id']}/release-candidates",
        json={
            "generation_run_id": run["id"],
            "expected_generation_revision": run["revision"],
        },
    )
    assert missing_simulation.status_code == 409
    assert missing_simulation.json()["code"] == "REFERENCE_SIMULATION_REQUIRED"

    simulation = client.post(
        f"/api/v1/projects/{project['id']}/simulation-runs",
        json={
            "generation_run_id": run["id"],
            "expected_generation_revision": run["revision"],
        },
    )
    assert simulation.status_code == 201, simulation.text
    assert simulation.json()["status"] == "review_ready"

    candidate_response = client.post(
        f"/api/v1/projects/{project['id']}/release-candidates",
        json={
            "generation_run_id": run["id"],
            "expected_generation_revision": run["revision"],
        },
    )
    assert candidate_response.status_code == 201, candidate_response.text
    candidate = candidate_response.json()
    assert candidate["status"] == "external_validation_required"
    assert candidate["verification_level"] == "automatic_package"
    assert candidate["reused"] is False
    assert candidate["manifest"]["claim_boundary"]
    assert {
        item["status"]
        for item in candidate["manifest"]["external_validation_gates"]
    } == {"pending_external"}

    package = client.get(
        f"/api/v1/artifacts/{candidate['package_artifact_id']}"
    )
    assert package.status_code == 200
    assert hashlib.sha256(package.content).hexdigest() == candidate["package_sha256"]
    manifest = verify_delivery_candidate(package.content)
    assert manifest == candidate["manifest"]
    entry_paths = {item["path"] for item in manifest["entries"]}
    assert {
        "source/original.xlsx",
        "spec/MachineSpec.locked.json",
        "program/generated/ControlIR.json",
        "program/tests/TestSpec.json",
        "evidence/automated-review.json",
        "evidence/static-audit.json",
        "evidence/reference-simulation.json",
        "validation/EXTERNAL_VALIDATION_PACKAGE.json",
        "validation/EXTERNAL_VALIDATION_CHECKLIST.md",
    } <= entry_paths
    validation_package = json.loads(
        zipfile.ZipFile(io.BytesIO(package.content)).read(
            "validation/EXTERNAL_VALIDATION_PACKAGE.json"
        )
    )
    assert validation_package["schema"] == "kongpu-validation-package/v1"
    assert validation_package["status"] == "pending_external"
    assert validation_package["verification_level"] == "manual_unverified"
    assert validation_package["target"]["profile_id"] == "mitsubishi-fx5u-st-v1"
    assert validation_package["prerequisites"]["software"] == ["GX Works3", "GX Simulator3", "MX Component"]
    assert "FX5U CPU" in validation_package["prerequisites"]["hardware"]
    assert validation_package["baseline"]["machine_spec_hash"] == candidate["manifest"]["baseline"]["machine_spec_hash"]
    assert validation_package["baseline"]["git_sha"] == candidate["manifest"]["baseline"]["git_sha"]
    checklist = zipfile.ZipFile(io.BytesIO(package.content)).read(
        "validation/EXTERNAL_VALIDATION_CHECKLIST.md"
    ).decode("utf-8")
    assert "集中外部验证执行清单" in checklist
    assert "GX Works3" in checklist

    repeated = client.post(
        f"/api/v1/projects/{project['id']}/release-candidates",
        json={
            "generation_run_id": run["id"],
            "expected_generation_revision": run["revision"],
        },
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == candidate["id"]
    assert repeated.json()["reused"] is True
    assert repeated.json()["package_sha256"] == candidate["package_sha256"]
    assert len(
        client.get(
            f"/api/v1/projects/{project['id']}/release-candidates"
        ).json()
    ) == 1

    plan_response = client.post(
        f"/api/v1/projects/{project['id']}/monitoring-plans",
        json={
            "release_candidate_id": candidate["id"],
            "expected_candidate_revision": candidate["revision"],
        },
    )
    assert plan_response.status_code == 201, plan_response.text
    plan = plan_response.json()
    assert plan["access"] == "read_only"
    assert plan["verification_level"] == "unverified"
    assert all(item["access"] == "read_only" for item in plan["variable_map"])

    mismatch = client.post(
        f"/api/v1/monitoring-plans/{plan['id']}/snapshots",
        json={
            "observed_target_fingerprint": "0" * 64,
            "values": {},
            "expected_plan_revision": plan["revision"],
        },
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "MONITORING_TARGET_MISMATCH"

    unknown = client.post(
        f"/api/v1/monitoring-plans/{plan['id']}/snapshots",
        json={
            "observed_target_fingerprint": plan["target_fingerprint"],
            "values": {"UNKNOWN_WRITE_TARGET": True},
            "expected_plan_revision": plan["revision"],
        },
    )
    assert unknown.status_code == 422
    assert unknown.json()["code"] == "MONITORING_SNAPSHOT_INVALID"

    snapshot = client.post(
        f"/api/v1/monitoring-plans/{plan['id']}/snapshots",
        json={
            "observed_target_fingerprint": plan["target_fingerprint"],
            "values": {},
            "note": "离线导入的只读变量快照",
            "expected_plan_revision": plan["revision"],
        },
    )
    assert snapshot.status_code == 201, snapshot.text
    evidence = snapshot.json()
    assert evidence["verification_level"] == "manual_unverified"
    assert evidence["analysis"]["claim_boundary"]
    downloaded = client.get(f"/api/v1/artifacts/{evidence['source_artifact_id']}")
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == evidence["artifact_sha256"]
    assert json.loads(downloaded.content)["observed_target_fingerprint"] == plan["target_fingerprint"]

    current_plan = client.get(f"/api/v1/monitoring-plans/{plan['id']}").json()
    task = client.post(
        f"/api/v1/monitoring-evidence/{evidence['id']}/commissioning-tasks",
        json={
            "description": "根据离线证据检查等待条件，不连接或写入 PLC",
            "expected_plan_revision": current_plan["revision"],
        },
    )
    assert task.status_code == 201, task.text
    task_body = task.json()
    assert task_body["status"] == "open"
    assert task_body["generation_run_id"]
    branches = client.get(f"/api/v1/projects/{project['id']}/branches").json()
    derived = next(item for item in branches if item["id"] == task_body["branch_id"])
    assert derived["name"].startswith("engineer/commissioning-")
    assert derived["base_commit"] == candidate["manifest"]["baseline"]["git_sha"]
    assert derived["head_commit"] == derived["base_commit"]
    derived_files = client.get(
        f"/api/v1/branches/{task_body['branch_id']}/files"
    )
    assert derived_files.status_code == 200, derived_files.text
    derived_source = client.get(
        f"/api/v1/branches/{task_body['branch_id']}/files/src/PRG_AutoCycle.st"
    )
    assert derived_source.status_code == 200, derived_source.text
    changed = client.patch(
        f"/api/v1/branches/{task_body['branch_id']}/files/src/PRG_AutoCycle.st",
        json={
            "content": derived_source.json()["content"] + "\n// commissioning note\n",
            "reason": "离线调试分支记录",
            "expected_revision": derived_files.json()["branch"]["revision"],
        },
    )
    assert changed.status_code == 200, changed.text
    committed = client.post(
        f"/api/v1/branches/{task_body['branch_id']}/commits",
        json={
            "message": "Record offline commissioning analysis",
            "author": "自动测试",
            "expected_revision": changed.json()["branch"]["revision"],
        },
    )
    assert committed.status_code == 201, committed.text
    derived_reviews = client.get(
        f"/api/v1/projects/{project['id']}/automated-reviews"
    ).json()
    assert any(
        item["program_commit_id"] == committed.json()["id"]
        and item["status"] == "passed"
        for item in derived_reviews
    )


def test_release_candidate_rejects_uncommitted_branch(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generated_run(
        client, project, locked_example, "generated/dirty-release-guard"
    )
    simulation = client.post(
        f"/api/v1/projects/{project['id']}/simulation-runs",
        json={
            "generation_run_id": run["id"],
            "expected_generation_revision": run["revision"],
        },
    )
    assert simulation.status_code == 201, simulation.text
    branch_id = run["branch_id"]
    branch = client.get(f"/api/v1/branches/{branch_id}/files").json()["branch"]
    source = client.get(
        f"/api/v1/branches/{branch_id}/files/src/PRG_AutoCycle.st"
    ).json()["content"]
    modified = client.patch(
        f"/api/v1/branches/{branch_id}/files/src/PRG_AutoCycle.st",
        json={
            "content": source + "\n// pending local change\n",
            "reason": "验证未提交门禁",
            "expected_revision": branch["revision"],
        },
    )
    assert modified.status_code == 200, modified.text
    rejected = client.post(
        f"/api/v1/projects/{project['id']}/release-candidates",
        json={
            "generation_run_id": run["id"],
            "expected_generation_revision": run["revision"],
        },
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "PROGRAM_BRANCH_DIRTY"
