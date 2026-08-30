from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from kongpu_api.models import AppSetting, SettingsAuditEvent


def test_settings_defaults_are_private_and_persistent(client: TestClient) -> None:
    first = client.get("/api/v1/settings")
    assert first.status_code == 200
    body = first.json()
    assert body["schema"] == "kongpu-settings/v1"
    assert body["settings"] == {
        "model_endpoint": None,
        "model_name": None,
        "model_status": "not_configured",
        "allow_project_context": False,
        "send_raw_excel": False,
        "send_generated_artifacts": False,
    }
    assert body["secret_policy"]["secret_storage"] == "not_supported"

    updated = client.patch(
        "/api/v1/settings",
        json={
            "model_endpoint": "https://models.example.test/v1",
            "model_name": "explain-only",
            "allow_project_context": True,
            "expected_revision": body["revision"],
        },
    )
    assert updated.status_code == 200, updated.text
    saved = client.get("/api/v1/settings").json()
    assert saved == updated.json()
    assert saved["settings"]["model_status"] == "configured_unverified"

    database = client.app.state.database
    with database.session_factory() as session:
        row = session.scalar(select(AppSetting).where(AppSetting.key == "local"))
        assert row is not None
        stored = json.loads(row.value_json)
        assert "api_key" not in stored
        assert stored["model_endpoint"] == "https://models.example.test/v1"


def test_settings_revision_conflict_and_noop_do_not_overwrite(client: TestClient) -> None:
    current = client.get("/api/v1/settings").json()
    changed = client.patch(
        "/api/v1/settings",
        json={"model_name": "local-explainer", "expected_revision": current["revision"]},
    )
    assert changed.status_code == 200

    stale = client.patch(
        "/api/v1/settings",
        json={"send_raw_excel": True, "expected_revision": current["revision"]},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "SETTINGS_REVISION_CONFLICT"
    assert client.get("/api/v1/settings").json()["settings"]["send_raw_excel"] is False

    latest = changed.json()
    noop = client.patch(
        "/api/v1/settings",
        json={"model_name": "local-explainer", "expected_revision": latest["revision"]},
    )
    assert noop.status_code == 200
    assert noop.json()["revision"] == latest["revision"]
    assert len(client.get("/api/v1/settings/audit").json()) == 1


def test_settings_endpoint_validation_and_secret_rejection(client: TestClient) -> None:
    revision = client.get("/api/v1/settings").json()["revision"]
    for endpoint in (
        "ftp://models.example.test",
        "https:///v1",
        "https://user:secret@models.example.test/v1",
        "https://models.example.test/v1?api_key=secret",
        "https://bad host.example/v1",
        "http://localhost:invalid/v1",
    ):
        response = client.patch(
            "/api/v1/settings",
            json={"model_endpoint": endpoint, "expected_revision": revision},
        )
        assert response.status_code == 422, endpoint
        assert response.json()["code"] == "INVALID_MODEL_ENDPOINT"

    secret = client.patch(
        "/api/v1/settings",
        json={"api_key": "must-not-persist", "expected_revision": revision},
    )
    assert secret.status_code == 422
    assert secret.json()["code"] == "REQUEST_VALIDATION_FAILED"


def test_settings_audit_records_only_changed_keys(client: TestClient) -> None:
    current = client.get("/api/v1/settings").json()
    response = client.patch(
        "/api/v1/settings",
        json={
            "model_endpoint": "http://127.0.0.1:11434/v1",
            "model_name": "local-model",
            "send_generated_artifacts": True,
            "expected_revision": current["revision"],
        },
    )
    assert response.status_code == 200, response.text
    audit = client.get("/api/v1/settings/audit").json()
    assert audit[0]["changed_keys"] == [
        "model_endpoint",
        "model_name",
        "send_generated_artifacts",
    ]

    database = client.app.state.database
    with database.session_factory() as session:
        event = session.scalar(select(SettingsAuditEvent))
        assert event is not None
        assert "local-model" not in event.payload_json
        assert "11434" not in event.payload_json


def test_template_history_and_compatibility_matrix_are_explicit(client: TestClient) -> None:
    versions = client.get("/api/v1/template-versions")
    assert versions.status_code == 200
    assert versions.json()[0]["version"] == "1.0"
    assert versions.json()[0]["schema_version"] == "1.0"

    matrix = client.get("/api/v1/compatibility-matrix")
    assert matrix.status_code == 200
    body = matrix.json()
    assert body["schema"] == "kongpu-compatibility-matrix/v1"
    assert len(body["entries"]) == 6
    assert {entry["target"]["series"] for entry in body["entries"]} == {"MELSEC iQ-F", "H5U"}
    assert {entry["vendor_compile"] for entry in body["entries"]} == {"unverified"}
    assert {entry["vendor_simulation"] for entry in body["entries"]} == {"unverified"}
    assert {entry["hardware"] for entry in body["entries"]} == {"pending_external"}
    assert {entry["safety_plc"] for entry in body["entries"]} == {"excluded"}
