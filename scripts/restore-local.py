from __future__ import annotations

import argparse
import os
import uuid
import zipfile
from pathlib import Path

from local_data_archive import (
    ArchiveSafetyError, DATABASE_NAME, DEFAULT_LIMITS,
    assert_sqlite_integrity, copy_and_hash, ensure_destination_parent,
    lexical_absolute, load_and_validate_manifest, require_safe_data_root,
    validate_zip_members,
)


ROOT = Path(__file__).resolve().parents[1]


def replace_prepared_files(data_dir: Path, temporary_files: dict[str, Path]) -> None:
    """Replace all manifest files with in-process rollback on partial failure."""
    replacement_order = sorted(
        temporary_files, key=lambda value: (value == DATABASE_NAME, value)
    )
    changed: list[tuple[Path, Path | None]] = []
    try:
        for member_name in replacement_order:
            destination = ensure_destination_parent(data_dir, member_name)
            temporary = temporary_files[member_name]
            if temporary.is_symlink() or not temporary.is_file():
                raise ArchiveSafetyError(f"Restore temporary file is unsafe: {temporary}")
            rollback = None
            if destination.exists():
                if destination.is_symlink() or not destination.is_file():
                    raise ArchiveSafetyError(f"Restore destination is unsafe: {destination}")
                rollback = destination.with_name(
                    f".{destination.name}.{uuid.uuid4().hex}.rollback"
                )
                os.replace(destination, rollback)
            changed.append((destination, rollback))
            os.replace(temporary, destination)
    except Exception:
        rollback_failures: list[str] = []
        for destination, rollback in reversed(changed):
            try:
                if rollback is not None and rollback.is_file() and not rollback.is_symlink():
                    os.replace(rollback, destination)
                elif rollback is None and destination.is_file() and not destination.is_symlink():
                    destination.unlink()
            except OSError as rollback_error:
                rollback_failures.append(f"{destination}: {rollback_error}")
        if rollback_failures:
            raise ArchiveSafetyError(
                "Restore failed and rollback was incomplete: " + "; ".join(rollback_failures)
            )
        raise
    else:
        for _destination, rollback in changed:
            if rollback is not None and rollback.is_file() and not rollback.is_symlink():
                rollback.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore Kongpu local data without deleting unrelated files.")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".local-data")
    parser.add_argument("--confirm-overwrite", action="store_true")
    args = parser.parse_args()
    if not args.confirm_overwrite:
        raise SystemExit("Restore overwrites matching local files. Re-run with --confirm-overwrite after stopping the services.")

    backup = lexical_absolute(args.backup)
    data_dir = require_safe_data_root(args.data_dir, create=True)
    temporary_files: dict[str, Path] = {}
    try:
        with zipfile.ZipFile(backup) as archive:
            members = validate_zip_members(backup, archive)
            manifest = load_and_validate_manifest(archive, members)
            for member_name in sorted(manifest):
                destination = ensure_destination_parent(data_dir, member_name)
                temporary = destination.with_name(
                    f".{destination.name}.{uuid.uuid4().hex}.restore"
                )
                info = members[member_name]
                with archive.open(info, "r") as source, temporary.open("xb") as target:
                    size, digest = copy_and_hash(
                        source,
                        target,
                        max_bytes=DEFAULT_LIMITS.max_file_bytes,
                        expected_size=info.file_size,
                    )
                expected = manifest[member_name]
                if size != expected["size_bytes"] or digest != expected["sha256"]:
                    raise ArchiveSafetyError(
                        f"Backup content does not match the manifest: {member_name}"
                    )
                temporary_files[member_name] = temporary

        assert_sqlite_integrity(temporary_files[DATABASE_NAME])
        replace_prepared_files(data_dir, temporary_files)
        print(
            f"Restored {len(temporary_files)} files into {data_dir}. "
            "Existing unrelated files were not deleted."
        )
    except (ArchiveSafetyError, zipfile.BadZipFile, OSError) as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        for temporary in temporary_files.values():
            if temporary.is_file() and not temporary.is_symlink():
                temporary.unlink()


if __name__ == "__main__":
    main()
