from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from local_data_archive import (
    ArchiveSafetyError, DATABASE_NAME, DEFAULT_LIMITS, MANIFEST_NAME,
    MANIFEST_SCHEMA, assert_sqlite_integrity, copy_and_hash,
    iter_regular_source_files, lexical_absolute, normalize_member_name,
    require_safe_data_root,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent Kongpu local-data backup.")
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".local-data")
    args = parser.parse_args()
    data_dir = require_safe_data_root(args.data_dir)
    output = lexical_absolute(
        args.output
        or ROOT / "backups" / f"kongpu-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.zip"
    )
    if output == data_dir or data_dir in output.parents:
        raise SystemExit("Backup output must be outside the source data directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    database = data_dir / DATABASE_NAME
    if not database.is_file() or database.is_symlink():
        raise SystemExit(f"Database not found: {database}")

    handle = tempfile.NamedTemporaryFile(prefix="kongpu-backup-", suffix=".sqlite3", delete=False)
    temp_database = Path(handle.name)
    handle.close()
    temporary_output = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    try:
        with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(temp_database)) as target:
            source.backup(target)
        assert_sqlite_integrity(temp_database)
        sources = [(temp_database, DATABASE_NAME), *iter_regular_source_files(data_dir)]
        manifest_entries: list[dict[str, object]] = []
        total_size = 0
        with zipfile.ZipFile(
            temporary_output, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
        ) as archive:
            for source_path, member_name in sources:
                normalize_member_name(member_name)
                before = source_path.stat(follow_symlinks=False)
                if before.st_size > DEFAULT_LIMITS.max_file_bytes:
                    raise ArchiveSafetyError(f"Backup source file exceeds the safety limit: {source_path}")
                with source_path.open("rb") as source_handle, archive.open(
                    member_name, "w", force_zip64=True
                ) as target_handle:
                    size, digest = copy_and_hash(
                        source_handle, target_handle, max_bytes=DEFAULT_LIMITS.max_file_bytes
                    )
                after = source_path.stat(follow_symlinks=False)
                if source_path.is_symlink() or before.st_size != size or after.st_size != size:
                    raise ArchiveSafetyError(f"Backup source changed while being read: {source_path}")
                total_size += size
                if total_size > DEFAULT_LIMITS.max_total_bytes:
                    raise ArchiveSafetyError("Backup source total size exceeds the safety limit")
                manifest_entries.append(
                    {"path": member_name, "size_bytes": size, "sha256": digest}
                )
            manifest = json.dumps(
                {
                    "schema": MANIFEST_SCHEMA,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "entries": manifest_entries,
                },
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(manifest) > DEFAULT_LIMITS.max_manifest_bytes:
                raise ArchiveSafetyError("Backup manifest exceeds the safety limit")
            archive.writestr(MANIFEST_NAME, manifest)
        if temporary_output.stat().st_size > DEFAULT_LIMITS.max_archive_bytes:
            raise ArchiveSafetyError("Backup archive exceeds the compressed-size limit")
        os.replace(temporary_output, output)
        print(output)
    except ArchiveSafetyError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        if temp_database.is_file():
            temp_database.unlink()
        if temporary_output.is_file():
            temporary_output.unlink()


if __name__ == "__main__":
    main()
