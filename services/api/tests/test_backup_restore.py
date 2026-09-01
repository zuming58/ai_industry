from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from local_data_archive import (  # noqa: E402
    ArchiveLimits,
    ArchiveSafetyError,
    MANIFEST_NAME,
    normalize_member_name,
    validate_zip_members,
)

restore_spec = importlib.util.spec_from_file_location(
    "kongpu_restore_local", SCRIPTS / "restore-local.py"
)
assert restore_spec and restore_spec.loader
restore_local = importlib.util.module_from_spec(restore_spec)
restore_spec.loader.exec_module(restore_local)


def run_backup(source: Path, backup: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "backup-local.py"),
            str(backup),
            "--data-dir",
            str(source),
        ],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def run_restore(backup: Path, restored: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "restore-local.py"),
            str(backup),
            "--data-dir",
            str(restored),
            "--confirm-overwrite",
        ],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def create_source(root: Path) -> Path:
    source = root / "source"
    source.mkdir()
    database = source / "kongpu.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("create table verification (value text not null)")
        connection.execute("insert into verification values ('round-trip-ok')")
    artifact = source / "artifacts" / "sha256" / "sample.bin"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"immutable-artifact")
    return source


def test_backup_and_restore_round_trip(tmp_path: Path) -> None:
    source = create_source(tmp_path)
    restored = tmp_path / "restored"
    backup = tmp_path / "kongpu-backup.zip"

    backup_result = run_backup(source, backup)
    assert backup_result.returncode == 0, backup_result.stderr
    with zipfile.ZipFile(backup) as archive:
        manifest = json.loads(archive.read(MANIFEST_NAME))
        assert manifest["schema"] == "kongpu-local-backup/v1"
        assert {entry["path"] for entry in manifest["entries"]} == {
            "kongpu.sqlite3",
            "artifacts/sha256/sample.bin",
        }
    restore_result = run_restore(backup, restored)
    assert restore_result.returncode == 0, restore_result.stderr

    with sqlite3.connect(restored / "kongpu.sqlite3") as connection:
        assert connection.execute("select value from verification").fetchone() == ("round-trip-ok",)
    assert (restored / "artifacts" / "sha256" / "sample.bin").read_bytes() == b"immutable-artifact"


@pytest.mark.parametrize(
    "name",
    [
        "C:/outside.txt",
        "artifacts\\outside.txt",
        "artifacts/../outside.txt",
        "artifacts//outside.txt",
        "artifacts/./outside.txt",
        "artifacts/CON.txt",
        "repositories/trailing./file.st",
    ],
)
def test_backup_member_name_rejects_windows_and_ambiguous_paths(name: str) -> None:
    with pytest.raises(ArchiveSafetyError):
        normalize_member_name(name)


def test_restore_rejects_tampered_content_without_overwriting_existing_data(
    tmp_path: Path,
) -> None:
    source = create_source(tmp_path)
    backup = tmp_path / "valid.zip"
    assert run_backup(source, backup).returncode == 0

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(backup) as original, zipfile.ZipFile(
        tampered, "w", compression=zipfile.ZIP_DEFLATED
    ) as modified:
        for info in original.infolist():
            content = original.read(info.filename)
            if info.filename == "artifacts/sha256/sample.bin":
                content = b"tampered--artifact"
            modified.writestr(info.filename, content)

    restored = tmp_path / "restored"
    restored.mkdir()
    existing_database = restored / "kongpu.sqlite3"
    existing_database.write_bytes(b"existing-database-must-survive")
    result = run_restore(tampered, restored)
    assert result.returncode != 0
    assert "does not match the manifest" in result.stderr
    assert existing_database.read_bytes() == b"existing-database-must-survive"
    assert not (restored / "artifacts" / "sha256" / "sample.bin").exists()


def test_zip_validation_rejects_duplicate_entries_and_size_limits(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.zip"
    with pytest.warns(UserWarning), zipfile.ZipFile(duplicate, "w") as archive:
        archive.writestr("kongpu.sqlite3", b"first")
        archive.writestr("kongpu.sqlite3", b"second")
        archive.writestr(MANIFEST_NAME, b"{}")
    with zipfile.ZipFile(duplicate) as archive:
        with pytest.raises(ArchiveSafetyError, match="Duplicate"):
            validate_zip_members(duplicate, archive)

    oversized = tmp_path / "oversized.zip"
    with zipfile.ZipFile(oversized, "w") as archive:
        archive.writestr("kongpu.sqlite3", b"1234")
        archive.writestr(MANIFEST_NAME, b"{}")
    limits = ArchiveLimits(
        max_entries=10,
        max_total_bytes=100,
        max_file_bytes=3,
        max_archive_bytes=1024,
        max_manifest_bytes=10,
    )
    with zipfile.ZipFile(oversized) as archive:
        with pytest.raises(ArchiveSafetyError, match="per-file"):
            validate_zip_members(oversized, archive, limits)


def test_backup_rejects_source_symbolic_links_when_supported(tmp_path: Path) -> None:
    source = create_source(tmp_path)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    link = source / "artifacts" / "linked.bin"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable in this test environment")
    result = run_backup(source, tmp_path / "backup.zip")
    assert result.returncode != 0
    assert "symbolic link" in result.stderr


def test_restore_rejects_destination_parent_symbolic_links_when_supported(
    tmp_path: Path,
) -> None:
    source = create_source(tmp_path)
    backup = tmp_path / "backup.zip"
    assert run_backup(source, backup).returncode == 0
    restored = tmp_path / "restored"
    restored.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = restored / "artifacts"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable in this test environment")
    result = run_restore(backup, restored)
    assert result.returncode != 0
    assert "unsafe" in result.stderr
    assert list(outside.iterdir()) == []


def test_restore_rejects_corrupt_sqlite_before_replacing_existing_database(
    tmp_path: Path,
) -> None:
    source = create_source(tmp_path)
    backup = tmp_path / "backup.zip"
    assert run_backup(source, backup).returncode == 0

    corrupt = tmp_path / "corrupt.zip"
    with zipfile.ZipFile(backup) as original, zipfile.ZipFile(
        corrupt, "w", compression=zipfile.ZIP_DEFLATED
    ) as modified:
        manifest = json.loads(original.read(MANIFEST_NAME))
        database_info = original.getinfo("kongpu.sqlite3")
        corrupt_database = b"x" * database_info.file_size
        for entry in manifest["entries"]:
            if entry["path"] == "kongpu.sqlite3":
                entry["sha256"] = hashlib.sha256(corrupt_database).hexdigest()
        for info in original.infolist():
            content = original.read(info.filename)
            if info.filename == "kongpu.sqlite3":
                content = corrupt_database
            elif info.filename == MANIFEST_NAME:
                content = json.dumps(
                    manifest,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            modified.writestr(info.filename, content)

    restored = tmp_path / "restored"
    restored.mkdir()
    existing_database = restored / "kongpu.sqlite3"
    existing_database.write_bytes(b"existing-database-must-survive")
    result = run_restore(corrupt, restored)
    assert result.returncode != 0
    assert "SQLite" in result.stderr
    assert existing_database.read_bytes() == b"existing-database-must-survive"
    assert not (restored / "artifacts" / "sha256" / "sample.bin").exists()


def test_restore_rolls_back_all_replacements_after_mid_commit_failure(
    monkeypatch, tmp_path: Path
) -> None:
    restored = tmp_path / "restored"
    restored.mkdir()
    first = restored / "artifacts" / "first.bin"
    second = restored / "kongpu.sqlite3"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"old-first")
    second.write_bytes(b"old-database")

    staged_first = restored / ".first.restore"
    staged_second = restored / ".database.restore"
    staged_first.write_bytes(b"new-first")
    staged_second.write_bytes(b"new-database")
    real_replace = restore_local.os.replace
    calls = 0

    def fail_once(source, destination):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError("injected replacement failure")
        return real_replace(source, destination)

    monkeypatch.setattr(restore_local.os, "replace", fail_once)
    with pytest.raises(OSError, match="injected"):
        restore_local.replace_prepared_files(
            restored,
            {
                "artifacts/first.bin": staged_first,
                "kongpu.sqlite3": staged_second,
            },
        )
    assert first.read_bytes() == b"old-first"
    assert second.read_bytes() == b"old-database"
