from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from kongpu_api.artifacts import (
    ArtifactIntegrityError, artifact_path, read_stored_bytes, store_bytes,
)
from kongpu_api.models import SourceArtifact


def test_download_blocks_tampered_content_and_metadata(
    client: TestClient, locked_example: dict
) -> None:
    artifact_id = locked_example["snapshot_artifact_id"]
    database = client.app.state.database
    settings = client.app.state.settings
    with database.session_factory() as session:
        record = session.get(SourceArtifact, artifact_id)
        assert record is not None
        path = artifact_path(settings, record)
        original = path.read_bytes()
        path.write_bytes(b"tampered")

    tampered = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert tampered.status_code == 409
    assert tampered.json()["code"] == "ARTIFACT_SIZE_MISMATCH"

    path.write_bytes(original)
    with database.session_factory() as session:
        record = session.get(SourceArtifact, artifact_id)
        assert record is not None
        record.size_bytes += 1
        session.commit()
    metadata = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert metadata.status_code == 409
    assert metadata.json()["code"] == "ARTIFACT_SIZE_MISMATCH"


def test_store_refuses_to_overwrite_corrupted_content_addressed_file(client: TestClient) -> None:
    database = client.app.state.database
    settings = client.app.state.settings
    content = b"immutable-content"
    with database.session_factory() as session:
        stored = store_bytes(session, settings, content, "source.bin", "application/octet-stream")
        session.commit()
        path = stored.path
    path.write_bytes(b"corrupted-content")

    with database.session_factory() as session:
        try:
            store_bytes(session, settings, content, "same.bin", "application/octet-stream")
        except ArtifactIntegrityError as exc:
            assert exc.code == "ARTIFACT_HASH_MISMATCH"
        else:
            raise AssertionError("corrupted content-addressed artifact must be blocked")
    assert path.read_bytes() == b"corrupted-content"


def test_artifact_path_rejects_database_path_escape(client: TestClient, tmp_path: Path) -> None:
    database = client.app.state.database
    settings = client.app.state.settings
    with database.session_factory() as session:
        record = SourceArtifact(
            sha256="f" * 64,
            size_bytes=1,
            media_type="application/octet-stream",
            original_name="escape.bin",
            relative_path="../../escape.bin",
        )
        session.add(record)
        session.commit()
        artifact_id = record.id
    response = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert response.status_code == 409
    assert response.json()["code"] == "ARTIFACT_PATH_INVALID"


def test_artifact_read_checks_size_limit_before_loading(client: TestClient) -> None:
    database = client.app.state.database
    settings = client.app.state.settings
    settings.max_artifact_bytes = 8
    content = b"12345678"
    with database.session_factory() as session:
        stored = store_bytes(
            session, settings, content, "bounded.bin", "application/octet-stream"
        )
        session.commit()
        record = session.get(SourceArtifact, stored.record.id)
        assert record is not None
        stored.path.write_bytes(b"x" * 9)
        try:
            read_stored_bytes(settings, record)
        except ArtifactIntegrityError as exc:
            assert exc.code == "ARTIFACT_TOO_LARGE"
        else:
            raise AssertionError("oversized artifact must be rejected before loading")
