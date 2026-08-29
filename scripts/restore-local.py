from __future__ import annotations

import argparse
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOTS = {"kongpu.sqlite3", "artifacts", "repositories"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore Kongpu local data without deleting unrelated files.")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".local-data")
    parser.add_argument("--confirm-overwrite", action="store_true")
    args = parser.parse_args()
    if not args.confirm_overwrite:
        raise SystemExit("Restore overwrites matching local files. Re-run with --confirm-overwrite after stopping the services.")

    backup = args.backup.resolve()
    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(backup) as archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        for entry in entries:
            relative = PurePosixPath(entry.filename)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] not in ALLOWED_ROOTS:
                raise SystemExit(f"Unsafe backup entry: {entry.filename}")
        if "kongpu.sqlite3" not in {entry.filename for entry in entries}:
            raise SystemExit("Backup does not contain kongpu.sqlite3")
        for entry in entries:
            destination = (data_dir / Path(*PurePosixPath(entry.filename).parts)).resolve()
            if data_dir not in destination.parents and destination != data_dir:
                raise SystemExit(f"Restore path escaped data directory: {entry.filename}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(entry))
    print(f"Restored {len(entries)} files into {data_dir}. Existing unrelated files were not deleted.")


if __name__ == "__main__":
    main()
