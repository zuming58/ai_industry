from __future__ import annotations

from fastapi.testclient import TestClient

from kongpu_api.generator import generate_bundle
from kongpu_api.repository import RepositoryError, safe_file


def test_generation_requires_locked_spec(client: TestClient, project: dict) -> None:
    response = client.post(f"/api/v1/projects/{project['id']}/generation-runs", json={})
    assert response.status_code == 409
    assert response.json()["code"] == "LOCKED_SPEC_REQUIRED"


def test_deterministic_generator(locked_example: dict) -> None:
    spec = locked_example["revision"]["data"]
    first = generate_bundle(spec)
    second = generate_bundle(spec)
    assert first.files == second.files
    assert first.control_ir == second.control_ir
    assert first.test_spec == second.test_spec


def test_generation_edit_commit_and_diff(
    client: TestClient,
    project: dict,
    locked_example: dict,
) -> None:
    generated = client.post(
        f"/api/v1/projects/{project['id']}/generation-runs",
        json={
            "spec_revision_id": locked_example["revision"]["id"],
            "branch_name": "generated/m1-acceptance",
        },
    )
    assert generated.status_code == 201, generated.text
    run = generated.json()
    assert run["status"] == "review_ready"
    assert {item["path"] for item in run["artifacts"]} >= {
        "src/GVL_IO.st",
        "src/PRG_AutoCycle.st",
        "generated/ControlIR.json",
        "tests/TestSpec.json",
    }
    assert run["trace_links"]

    branch_id = run["branch_id"]
    listing = client.get(f"/api/v1/branches/{branch_id}/files")
    assert listing.status_code == 200, listing.text
    branch = listing.json()["branch"]
    source = client.get(f"/api/v1/branches/{branch_id}/files/src/PRG_AutoCycle.st")
    assert source.status_code == 200
    changed_content = source.json()["content"] + chr(10) + "// Reviewed locally." + chr(10)
    changed = client.patch(
        f"/api/v1/branches/{branch_id}/files/src/PRG_AutoCycle.st",
        json={
            "content": changed_content,
            "reason": "工程师审阅标记",
            "expected_revision": branch["revision"],
        },
    )
    assert changed.status_code == 200, changed.text
    changed_branch = changed.json()["branch"]

    conflict = client.patch(
        f"/api/v1/branches/{branch_id}/files/src/PRG_AutoCycle.st",
        json={
            "content": changed_content,
            "reason": "过期写入",
            "expected_revision": branch["revision"],
        },
    )
    assert conflict.status_code == 409

    committed = client.post(
        f"/api/v1/branches/{branch_id}/commits",
        json={
            "message": "Review generated auto cycle",
            "author": "测试工程师",
            "expected_revision": changed_branch["revision"],
        },
    )
    assert committed.status_code == 201, committed.text
    commit = committed.json()
    diff = client.get(f"/api/v1/commits/{commit['id']}/diff")
    assert diff.status_code == 200, diff.text
    assert "Reviewed locally" in diff.json()["diff"]
    commits = client.get(f"/api/v1/projects/{project['id']}/commits")
    assert len(commits.json()) == 2

    traversal = client.get(f"/api/v1/branches/{branch_id}/files/../secret.txt")
    assert traversal.status_code in {404, 422}


def test_repository_path_guard(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    try:
        safe_file(repo, "../escape.txt")
    except RepositoryError:
        pass
    else:
        raise AssertionError("path traversal should be rejected")
