from __future__ import annotations

import argparse
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent Kongpu local-data backup.")
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".local-data")
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    output = (args.output or ROOT / "backups" / f"kongpu-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.zip").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    database = data_dir / "kongpu.sqlite3"
    if not database.is_file():
        raise SystemExit(f"Database not found: {database}")

    handle = tempfile.NamedTemporaryFile(prefix="kongpu-backup-", suffix=".sqlite3", delete=False)
    temp_database = Path(handle.name)
    handle.close()
    try:
        with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(temp_database)) as target:
            source.backup(target)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(temp_database, "kongpu.sqlite3")
            for folder_name in ("artifacts", "repositories"):
                folder = data_dir / folder_name
                if folder.is_dir():
                    for file_path in sorted(path for path in folder.rglob("*") if path.is_file()):
                        archive.write(file_path, file_path.relative_to(data_dir).as_posix())
        print(output)
    finally:
        if temp_database.is_file():
            temp_database.unlink()


if __name__ == "__main__":
    main()
