from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_backup_and_restore_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source"
    restored = tmp_path / "restored"
    source.mkdir()
    database = source / "kongpu.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("create table verification (value text not null)")
        connection.execute("insert into verification values ('round-trip-ok')")

    artifact = source / "artifacts" / "sha256" / "sample.bin"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"immutable-artifact")
    backup = tmp_path / "kongpu-backup.zip"

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "backup-local.py"), str(backup), "--data-dir", str(source)],
        check=True,
        cwd=ROOT,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "restore-local.py"),
            str(backup),
            "--data-dir",
            str(restored),
            "--confirm-overwrite",
        ],
        check=True,
        cwd=ROOT,
    )

    with sqlite3.connect(restored / "kongpu.sqlite3") as connection:
        assert connection.execute("select value from verification").fetchone() == ("round-trip-ok",)
    assert (restored / "artifacts" / "sha256" / "sample.bin").read_bytes() == b"immutable-artifact"
