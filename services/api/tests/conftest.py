from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kongpu_api.config import Settings
from kongpu_api.database import DatabaseRuntime
from kongpu_api.main import create_app


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    settings = Settings(
        data_dir=tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}",
    )
    settings.ensure_directories()
    database = DatabaseRuntime(settings)
    app = create_app(settings_override=settings, database_override=database)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def project(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={"name": "FX5U 装配线", "customer_code": "CUST-001"},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def imported_example(client: TestClient, project: dict) -> dict:
    template = client.post(f"/api/v1/projects/{project['id']}/templates?kind=example")
    assert template.status_code == 200, template.text
    response = client.post(
        f"/api/v1/projects/{project['id']}/imports",
        files={
            "file": (
                "MachineSpec.xlsx",
                template.content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def locked_example(client: TestClient, imported_example: dict) -> dict:
    revision = imported_example["revision"]
    for issue in revision["issues"]:
        if issue["severity"] == "warning":
            accepted = client.post(
                f"/api/v1/spec-revisions/{revision['id']}/warnings/{issue['id']}/accept",
                json={"reason": "工程师已复核并接受", "expected_revision": revision["revision"]},
            )
            assert accepted.status_code == 200, accepted.text
            revision = accepted.json()
    for view in revision["required_views"]:
        confirmed = client.put(
            f"/api/v1/spec-revisions/{revision['id']}/confirmations/{view}",
            json={"confirmed_by": "测试工程师", "expected_revision": revision["revision"]},
        )
        assert confirmed.status_code == 200, confirmed.text
        revision = confirmed.json()
    locked = client.post(
        f"/api/v1/spec-revisions/{revision['id']}/lock",
        json={"confirmed_by": "测试工程师", "expected_revision": revision["revision"]},
    )
    assert locked.status_code == 200, locked.text
    return locked.json()
