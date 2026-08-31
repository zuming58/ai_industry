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
    assert pending["prerequisites"]["software"] == ["GX Works3", "GX Simulator3", "MX Component"]
    assert "FX5U CPU" in pending["prerequisites"]["hardware"]
    assert "FX5U I/O 与断电/断线恢复" in pending["prerequisites"]["validation_scope"]

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
    assert "GX Simulator3" in checklist
    assert "MX Component" in checklist
    assert "FX5U CPU" in checklist
    assert "FX5U I/O 与断电/断线恢复" in checklist
    assert f"Program Commit ID：{candidate['program_commit_id']}" in checklist
    assert "每项只能填写 `通过`、`失败` 或 `未执行`" in checklist
    assert "电气工程师结论与签名" in checklist

    validation_json = client.get(
        f"/api/v1/release-candidates/{candidate['id']}/validation-material",
        params={"kind": "json"},
    )
    assert validation_json.status_code == 200, validation_json.text
    assert validation_json.json() == validation_package
    assert validation_json.headers["content-disposition"].endswith(
        f'Kongpu-{candidate["version"]}-validation.json"'
    )
    assert validation_json.headers["etag"] == (
        f'"{hashlib.sha256(validation_json.content).hexdigest()}"'
    )

    validation_checklist = client.get(
        f"/api/v1/release-candidates/{candidate['id']}/validation-material",
        params={"kind": "checklist"},
    )
    assert validation_checklist.status_code == 200, validation_checklist.text
    assert validation_checklist.content.decode("utf-8") == checklist
    assert validation_checklist.headers["content-type"].startswith("text/markdown")
    invalid_kind = client.get(
        f"/api/v1/release-candidates/{candidate['id']}/validation-material",
        params={"kind": "unknown"},
    )
    assert invalid_kind.status_code == 422

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


def test_release_candidate_evidence_is_immutable_scoped_and_unverified(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generated_run(
        client, project, locked_example, "generated/release-evidence"
    )
    simulation = client.post(
        f"/api/v1/projects/{project['id']}/simulation-runs",
        json={
            "generation_run_id": run["id"],
            "expected_generation_revision": run["revision"],
        },
    )
    assert simulation.status_code == 201, simulation.text
    candidate_response = client.post(
        f"/api/v1/projects/{project['id']}/release-candidates",
        json={
            "generation_run_id": run["id"],
            "expected_generation_revision": run["revision"],
        },
    )
    assert candidate_response.status_code == 201, candidate_response.text
    candidate = candidate_response.json()
    assert candidate["evidence_count"] == 0

    content = b"GX Works3 Rebuild All manual evidence\n"
    uploaded = client.post(
        f"/api/v1/release-candidates/{candidate['id']}/evidence",
        headers={"If-Match": str(candidate["revision"])},
        data={
            "evidence_kind": "vendor_compile",
            "expected_candidate_revision": candidate["revision"],
            "note": "GX Works3 版本与诊断日志，尚未签字确认",
        },
        files={"file": ("rebuild.log", content, "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    evidence = uploaded.json()
    candidate = evidence["candidate"]
    assert evidence["reused"] is False
    assert evidence["verification_level"] == "manual_unverified"
    assert evidence["sha256"] == hashlib.sha256(content).hexdigest()
    assert evidence["original_name"] == "rebuild.log"
    assert evidence["size_bytes"] == len(content)
    assert candidate["revision"] == 2
    assert candidate["evidence_count"] == 1
    assert candidate["status"] == "external_validation_required"
    assert candidate["verification_level"] == "automatic_package"

    downloaded = client.get(
        f"/api/v1/artifacts/{evidence['source_artifact_id']}"
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == content
    assert hashlib.sha256(downloaded.content).hexdigest() == evidence["sha256"]

    listed = client.get(
        f"/api/v1/release-candidates/{candidate['id']}/evidence"
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == evidence["id"]
    assert listed.json()[0]["verification_level"] == "manual_unverified"

    duplicate = client.post(
        f"/api/v1/release-candidates/{candidate['id']}/evidence",
        headers={"If-Match": str(candidate["revision"])},
        data={
            "evidence_kind": "vendor_compile",
            "expected_candidate_revision": candidate["revision"],
            "note": "重复上传不创建新记录",
        },
        files={"file": ("rebuild-copy.log", content, "text/plain")},
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["id"] == evidence["id"]
    assert duplicate.json()["reused"] is True
    assert duplicate.json()["candidate"]["revision"] == candidate["revision"]
    assert duplicate.json()["candidate"]["evidence_count"] == 1

    stale = client.post(
        f"/api/v1/release-candidates/{candidate['id']}/evidence",
        data={
            "evidence_kind": "environment",
            "expected_candidate_revision": candidate["revision"] - 1,
        },
        files={"file": ("environment.txt", b"versions", "text/plain")},
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "REVISION_CONFLICT"

    invalid_kind = client.post(
        f"/api/v1/release-candidates/{candidate['id']}/evidence",
        data={
            "evidence_kind": "plc_download_success",
            "expected_candidate_revision": candidate["revision"],
        },
        files={"file": ("invalid.txt", b"invalid", "text/plain")},
    )
    assert invalid_kind.status_code == 422, invalid_kind.text
    assert invalid_kind.json()["code"] == "RELEASE_EVIDENCE_KIND_INVALID"
    assert "vendor_compile" in invalid_kind.json()["location"]["allowed"]

    too_large = client.post(
        f"/api/v1/release-candidates/{candidate['id']}/evidence",
        data={
            "evidence_kind": "other",
            "expected_candidate_revision": candidate["revision"],
        },
        files={
            "file": (
                "too-large.bin",
                b"x" * (20 * 1024 * 1024 + 1),
                "application/octet-stream",
            )
        },
    )
    assert too_large.status_code == 413, too_large.text
    assert too_large.json()["code"] == "FILE_TOO_LARGE"

    current = client.get(
        f"/api/v1/release-candidates/{candidate['id']}"
    ).json()
    assert current["status"] == "external_validation_required"
    assert current["verification_level"] == "automatic_package"
    assert current["revision"] == candidate["revision"]
    assert current["evidence_count"] == 1

    timeline = client.get(f"/api/v1/projects/{project['id']}/timeline")
    assert timeline.status_code == 200, timeline.text
    ledger_events = [
        item
        for item in timeline.json()["events"]
        if item["entity_type"] == "ReleaseCandidateEvidence"
    ]
    assert ledger_events
    assert any(item["source"].get("page") == "release" for item in ledger_events)
    assert all(item["verification_level"] == "manual_unverified" for item in ledger_events)


def test_release_candidate_evidence_ledger_exports_bindings_and_hashes(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generated_run(client, project, locked_example, "generated/evidence-ledger")
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
    evidence_response = client.post(
        f"/api/v1/release-candidates/{candidate['id']}/evidence",
        headers={"If-Match": str(candidate["revision"])},
        data={
            "evidence_kind": "vendor_compile",
            "expected_candidate_revision": candidate["revision"],
            "note": "外部验证前导入的日志原件",
        },
        files={"file": ("compile.log", b"manual compile evidence", "text/plain")},
    )
    assert evidence_response.status_code == 201, evidence_response.text

    ledger_response = client.get(
        f"/api/v1/release-candidates/{candidate['id']}/evidence-ledger",
        params={"kind": "json"},
    )
    assert ledger_response.status_code == 200, ledger_response.text
    ledger = ledger_response.json()
    assert ledger["schema"] == "kongpu-release-evidence-ledger/v1"
    assert ledger["candidate"]["id"] == candidate["id"]
    assert ledger["candidate"]["manifest_hash"] == candidate["manifest_hash"]
    assert ledger["candidate"]["package_sha256"] == candidate["package_sha256"]
    assert ledger["baseline"]["program_commit_id"] == candidate["program_commit_id"]
    assert ledger["baseline"]["machine_spec_hash"]
    assert ledger["evidence"][0]["evidence_kind"] == "vendor_compile"
    assert ledger["evidence"][0]["verification_level"] == "manual_unverified"
    assert ledger["evidence"][0]["sha256"] == hashlib.sha256(b"manual compile evidence").hexdigest()
    assert ledger_response.headers["etag"] == f'"{hashlib.sha256(ledger_response.content).hexdigest()}"'
    assert ledger_response.headers["content-disposition"].endswith(
        f'Kongpu-{candidate["version"]}-evidence-ledger.json"'
    )

    markdown_response = client.get(
        f"/api/v1/release-candidates/{candidate['id']}/evidence-ledger",
        params={"kind": "markdown"},
    )
    assert markdown_response.status_code == 200, markdown_response.text
    markdown = markdown_response.content.decode("utf-8")
    assert "控谱候选包外部证据台账" in markdown
    assert candidate["manifest_hash"] in markdown
    assert "compile.log" in markdown
    assert "manual_unverified" in markdown
    assert markdown_response.headers["content-type"].startswith("text/markdown")

    invalid = client.get(
        f"/api/v1/release-candidates/{candidate['id']}/evidence-ledger",
        params={"kind": "yaml"},
    )
    assert invalid.status_code == 422


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
