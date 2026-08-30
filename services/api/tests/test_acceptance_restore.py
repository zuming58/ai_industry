from __future__ import annotations

from fastapi.testclient import TestClient


def _generate(
    client: TestClient, project: dict, locked: dict, branch_name: str
) -> dict:
    response = client.post(
        f"/api/v1/projects/{project['id']}/generation-runs",
        json={
            "spec_revision_id": locked["revision"]["id"],
            "branch_name": branch_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _simulate(client: TestClient, project: dict, run: dict) -> dict:
    current = client.get(f"/api/v1/generation-runs/{run['id']}").json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/simulation-runs",
        json={
            "generation_run_id": run["id"],
            "expected_generation_revision": current["revision"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _candidate(client: TestClient, project: dict, run: dict) -> dict:
    current = client.get(f"/api/v1/generation-runs/{run['id']}").json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/release-candidates",
        json={
            "generation_run_id": run["id"],
            "expected_generation_revision": current["revision"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_locked_project(client: TestClient, name: str) -> tuple[dict, dict]:
    created = client.post(
        "/api/v1/projects",
        json={"name": name, "customer_code": "CROSS-PROJECT"},
    )
    assert created.status_code == 201, created.text
    project = created.json()
    template = client.post(
        f"/api/v1/projects/{project['id']}/templates?kind=example"
    )
    assert template.status_code == 200, template.text
    imported = client.post(
        f"/api/v1/projects/{project['id']}/imports",
        files={
            "file": (
                "MachineSpec.xlsx",
                template.content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert imported.status_code == 201, imported.text
    revision = imported.json()["revision"]
    for issue in revision["issues"]:
        if issue["severity"] == "warning":
            accepted = client.post(
                f"/api/v1/spec-revisions/{revision['id']}/warnings/{issue['id']}/accept",
                json={
                    "reason": "跨项目隔离测试已复核",
                    "expected_revision": revision["revision"],
                },
            )
            assert accepted.status_code == 200, accepted.text
            revision = accepted.json()
    for view in revision["required_views"]:
        confirmed = client.put(
            f"/api/v1/spec-revisions/{revision['id']}/confirmations/{view}",
            json={
                "confirmed_by": "自动测试",
                "expected_revision": revision["revision"],
            },
        )
        assert confirmed.status_code == 200, confirmed.text
        revision = confirmed.json()
    locked = client.post(
        f"/api/v1/spec-revisions/{revision['id']}/lock",
        json={
            "confirmed_by": "自动测试",
            "expected_revision": revision["revision"],
        },
    )
    assert locked.status_code == 200, locked.text
    return project, locked.json()


def test_candidate_verification_and_project_acceptance_are_immutable(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generate(
        client, project, locked_example, "generated/acceptance-report"
    )
    _simulate(client, project, run)
    candidate = _candidate(client, project, run)

    verified = client.post(
        f"/api/v1/release-candidates/{candidate['id']}/verify",
        json={"expected_candidate_revision": candidate["revision"]},
    )
    assert verified.status_code == 200, verified.text
    verification = verified.json()
    assert verification["status"] == "passed"
    assert verification["verification_level"] == "automatic_integrity"
    assert verification["summary"] == {"total": 4, "passed": 4, "failed": 0}
    assert verification["reused"] is False

    repeated_verification = client.post(
        f"/api/v1/release-candidates/{candidate['id']}/verify",
        json={"expected_candidate_revision": candidate["revision"]},
    )
    assert repeated_verification.status_code == 200
    assert repeated_verification.json()["id"] == verification["id"]
    assert repeated_verification.json()["reused"] is True

    current = client.get(f"/api/v1/generation-runs/{run['id']}").json()
    accepted = client.post(
        f"/api/v1/projects/{project['id']}/acceptance-runs",
        json={
            "generation_run_id": run["id"],
            "release_candidate_id": candidate["id"],
            "expected_generation_revision": current["revision"],
        },
    )
    assert accepted.status_code == 201, accepted.text
    acceptance = accepted.json()
    assert acceptance["status"] == "automatic_passed_external_pending"
    assert acceptance["verification_level"] == "automatic"
    assert acceptance["summary"]["passed"] == 5
    assert acceptance["summary"]["external_pending"] > 0
    assert acceptance["candidate_verification_id"] == verification["id"]
    assert "真实 FX5U" in acceptance["claim_boundary"]
    assert acceptance["reused"] is False

    repeated = client.post(
        f"/api/v1/projects/{project['id']}/acceptance-runs",
        json={
            "generation_run_id": run["id"],
            "release_candidate_id": candidate["id"],
            "expected_generation_revision": current["revision"],
        },
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == acceptance["id"]
    assert repeated.json()["reused"] is True
    listed = client.get(
        f"/api/v1/projects/{project['id']}/acceptance-runs"
    ).json()
    assert [item["id"] for item in listed] == [acceptance["id"]]


def test_commit_compare_and_restore_preserve_history_and_reset_results(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    run = _generate(client, project, locked_example, "generated/restore-source")
    branch_id = run["branch_id"]
    initial_commits = client.get(
        f"/api/v1/projects/{project['id']}/commits"
    ).json()
    initial = initial_commits[0]
    original_head = initial["git_sha"]

    listing = client.get(f"/api/v1/branches/{branch_id}/files").json()
    source = client.get(
        f"/api/v1/branches/{branch_id}/files/src/PRG_AutoCycle.st"
    ).json()["content"]
    changed = client.patch(
        f"/api/v1/branches/{branch_id}/files/src/PRG_AutoCycle.st",
        json={
            "content": source + "\n// Compare and restore evidence.\n",
            "reason": "验证版本比较与恢复",
            "expected_revision": listing["branch"]["revision"],
        },
    )
    assert changed.status_code == 200, changed.text
    committed = client.post(
        f"/api/v1/branches/{branch_id}/commits",
        json={
            "message": "Add compare and restore evidence",
            "author": "自动测试",
            "expected_revision": changed.json()["branch"]["revision"],
        },
    )
    assert committed.status_code == 201, committed.text
    latest = committed.json()
    assert latest["git_sha"] != original_head

    comparison = client.get(
        f"/api/v1/commits/{initial['id']}/diff/{latest['id']}"
    )
    assert comparison.status_code == 200, comparison.text
    comparison_payload = comparison.json()
    assert comparison_payload["schema"] == "kongpu-version-comparison/v1"
    assert comparison_payload["same_commit"] is False
    assert "Compare and restore evidence" in comparison_payload["source_diff"]
    assert comparison_payload["diff"] == comparison_payload["source_diff"]
    sections = {item["id"]: item for item in comparison_payload["sections"]}
    assert sections["source"]["status"] == "changed"
    assert sections["source"]["summary"]["changed"] == 1
    for unchanged in ("machine_spec", "io", "parameters", "control_ir", "test_spec", "generation"):
        assert sections[unchanged]["status"] == "unchanged"
    assert sections["verification"]["status"] == "changed"
    assert sections["vendor_configuration"]["verification_level"] == "unverified"
    assert "GX Works3" in sections["vendor_configuration"]["note"]

    repeated = client.get(
        f"/api/v1/commits/{initial['id']}/diff/{latest['id']}"
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["comparison_hash"] == comparison_payload["comparison_hash"]

    current_listing = client.get(f"/api/v1/branches/{branch_id}/files").json()
    uncommitted = client.patch(
        f"/api/v1/branches/{branch_id}/files/src/PRG_AutoCycle.st",
        json={
            "content": source + "\n// This must not leak into an explicit Commit comparison.\n",
            "reason": "验证明确 SHA 与工作区隔离",
            "expected_revision": current_listing["branch"]["revision"],
        },
    )
    assert uncommitted.status_code == 200, uncommitted.text
    while_dirty = client.get(
        f"/api/v1/commits/{initial['id']}/diff/{latest['id']}"
    )
    assert while_dirty.status_code == 200, while_dirty.text
    assert while_dirty.json()["comparison_hash"] == comparison_payload["comparison_hash"]
    assert "must not leak" not in while_dirty.json()["source_diff"]
    cleaned_by_commit = client.post(
        f"/api/v1/branches/{branch_id}/commits",
        json={
            "message": "Commit isolated worktree evidence",
            "author": "自动测试",
            "expected_revision": uncommitted.json()["branch"]["revision"],
        },
    )
    assert cleaned_by_commit.status_code == 201, cleaned_by_commit.text
    current_head = cleaned_by_commit.json()
    after_new_head = client.get(
        f"/api/v1/commits/{initial['id']}/diff/{latest['id']}"
    )
    assert after_new_head.status_code == 200, after_new_head.text
    assert after_new_head.json()["comparison_hash"] == comparison_payload["comparison_hash"]

    _simulate(client, project, run)
    historical_candidate = _candidate(client, project, run)
    source_branch_before = next(
        item
        for item in client.get(
            f"/api/v1/projects/{project['id']}/branches"
        ).json()
        if item["id"] == branch_id
    )
    restored = client.post(
        f"/api/v1/commits/{initial['id']}/restore-branches",
        json={
            "name": "restore/initial-baseline",
            "expected_source_branch_revision": source_branch_before["revision"],
        },
    )
    assert restored.status_code == 201, restored.text
    payload = restored.json()
    assert payload["branch"]["name"] == "restore/initial-baseline"
    assert payload["branch"]["base_commit"] == original_head
    assert payload["branch"]["head_commit"] == original_head
    assert payload["commit"]["git_sha"] == original_head
    assert payload["inherited_results"] == []
    assert "不继承" in payload["verification_boundary"]

    source_branch_after = next(
        item
        for item in client.get(
            f"/api/v1/projects/{project['id']}/branches"
        ).json()
        if item["id"] == branch_id
    )
    assert source_branch_after["head_commit"] == current_head["git_sha"]
    restored_run = payload["generation_run"]
    restored_reviews = client.get(
        f"/api/v1/projects/{project['id']}/automated-reviews"
    ).json()
    assert any(
        item["generation_run_id"] == restored_run["id"]
        and item["program_commit_id"] == payload["commit"]["id"]
        and item["status"] == "passed"
        for item in restored_reviews
    )
    simulations = client.get(
        f"/api/v1/projects/{project['id']}/simulation-runs"
    ).json()
    assert not any(
        item["generation_run_id"] == restored_run["id"]
        for item in simulations
    )
    candidates = client.get(
        f"/api/v1/projects/{project['id']}/release-candidates"
    ).json()
    assert [item["id"] for item in candidates] == [historical_candidate["id"]]

    missing_new_simulation = client.post(
        f"/api/v1/projects/{project['id']}/acceptance-runs",
        json={
            "generation_run_id": restored_run["id"],
            "expected_generation_revision": restored_run["revision"],
        },
    )
    assert missing_new_simulation.status_code == 409
    assert missing_new_simulation.json()["code"] == "REFERENCE_SIMULATION_REQUIRED"


def test_commit_comparison_rejects_cross_project_access(
    client: TestClient, project: dict, locked_example: dict
) -> None:
    first_run = _generate(
        client, project, locked_example, "generated/first-project"
    )
    first_commit = next(
        item
        for item in client.get(
            f"/api/v1/projects/{project['id']}/commits"
        ).json()
        if item["branch_id"] == first_run["branch_id"]
    )

    second_project, second_locked = _create_locked_project(
        client, "FX5U 跨项目隔离"
    )
    second_run = _generate(
        client,
        second_project,
        second_locked,
        "generated/second-project",
    )
    second_commit = next(
        item
        for item in client.get(
            f"/api/v1/projects/{second_project['id']}/commits"
        ).json()
        if item["branch_id"] == second_run["branch_id"]
    )

    response = client.get(
        f"/api/v1/commits/{first_commit['id']}/diff/{second_commit['id']}"
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "COMMIT_PROJECT_MISMATCH"
