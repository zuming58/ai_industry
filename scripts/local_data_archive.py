from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import unicodedata
import zipfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO, Iterable


DATABASE_NAME = "kongpu.sqlite3"
MANIFEST_NAME = "backup-manifest.json"
MANIFEST_SCHEMA = "kongpu-local-backup/v1"
ALLOWED_DIRECTORY_ROOTS = {"artifacts", "repositories"}
COPY_CHUNK_BYTES = 1024 * 1024
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class ArchiveLimits:
    max_entries: int = 50_000
    max_total_bytes: int = 20 * 1024 * 1024 * 1024
    max_file_bytes: int = 512 * 1024 * 1024
    max_archive_bytes: int = 20 * 1024 * 1024 * 1024
    max_manifest_bytes: int = 16 * 1024 * 1024
    max_path_chars: int = 512


DEFAULT_LIMITS = ArchiveLimits()


class ArchiveSafetyError(RuntimeError):
    pass


def lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def require_safe_data_root(path: Path, *, create: bool = False) -> Path:
    root = lexical_absolute(path)
    if root.exists():
        if root.is_symlink() or not root.is_dir():
            raise ArchiveSafetyError(f"Data directory must be a regular directory: {root}")
    elif create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_component(component: str) -> None:
    if (
        not component
        or component in {".", ".."}
        or component.endswith((" ", "."))
        or any(
            ord(character) < 32 or character in '<>:"|?*'
            for character in component
        )
        or len(component) > 255
    ):
        raise ArchiveSafetyError(f"Unsafe backup path component: {component!r}")
    stem = component.split(".", 1)[0].upper()
    if stem in WINDOWS_RESERVED_NAMES:
        raise ArchiveSafetyError(f"Reserved backup path component: {component!r}")


def normalize_member_name(name: str, limits: ArchiveLimits = DEFAULT_LIMITS) -> str:
    if not isinstance(name, str) or not name or len(name) > limits.max_path_chars:
        raise ArchiveSafetyError("Backup entry path is empty or too long")
    if name != unicodedata.normalize("NFC", name):
        raise ArchiveSafetyError(f"Backup entry path is not NFC-normalized: {name!r}")
    if "\\" in name or name.startswith("/") or name.endswith("/"):
        raise ArchiveSafetyError(f"Unsafe backup entry: {name}")
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    parts = name.split("/")
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ArchiveSafetyError(f"Unsafe backup entry: {name}")
    for part in parts:
        _validate_component(part)
    normalized = "/".join(parts)
    if normalized in {DATABASE_NAME, MANIFEST_NAME}:
        return normalized
    if len(parts) < 2 or parts[0] not in ALLOWED_DIRECTORY_ROOTS:
        raise ArchiveSafetyError(f"Unsupported backup entry: {name}")
    return normalized


def validate_zip_members(
    archive_path: Path,
    archive: zipfile.ZipFile,
    limits: ArchiveLimits = DEFAULT_LIMITS,
) -> dict[str, zipfile.ZipInfo]:
    if not archive_path.is_file() or archive_path.is_symlink():
        raise ArchiveSafetyError(f"Backup is not a regular file: {archive_path}")
    if archive_path.stat().st_size > limits.max_archive_bytes:
        raise ArchiveSafetyError("Backup archive exceeds the compressed-size limit")

    members: dict[str, zipfile.ZipInfo] = {}
    canonical_names: set[str] = set()
    total_size = 0
    for info in archive.infolist():
        if info.is_dir():
            raise ArchiveSafetyError(f"Explicit directory entries are not supported: {info.filename}")
        if info.flag_bits & 0x1:
            raise ArchiveSafetyError(f"Encrypted backup entry is not supported: {info.filename}")
        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_IFMT(unix_mode) == stat.S_IFLNK:
            raise ArchiveSafetyError(f"Symbolic-link backup entry is not supported: {info.filename}")
        name = normalize_member_name(info.filename, limits)
        canonical = unicodedata.normalize("NFC", name).casefold()
        if canonical in canonical_names:
            raise ArchiveSafetyError(f"Duplicate backup entry: {name}")
        canonical_names.add(canonical)
        if len(members) >= limits.max_entries:
            raise ArchiveSafetyError("Backup entry count exceeds the safety limit")
        file_limit = limits.max_manifest_bytes if name == MANIFEST_NAME else limits.max_file_bytes
        if info.file_size < 0 or info.file_size > file_limit:
            raise ArchiveSafetyError(f"Backup entry exceeds the per-file limit: {name}")
        total_size += info.file_size
        if total_size > limits.max_total_bytes:
            raise ArchiveSafetyError("Backup uncompressed size exceeds the safety limit")
        members[name] = info
    if DATABASE_NAME not in members:
        raise ArchiveSafetyError(f"Backup does not contain {DATABASE_NAME}")
    if MANIFEST_NAME not in members:
        raise ArchiveSafetyError(
            f"Backup does not contain {MANIFEST_NAME}; legacy unverified backups are rejected"
        )
    return members


def copy_and_hash(
    source: BinaryIO,
    target: BinaryIO,
    *,
    max_bytes: int,
    expected_size: int | None = None,
) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = source.read(COPY_CHUNK_BYTES)
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise ArchiveSafetyError("File content exceeds the safety limit while streaming")
        target.write(chunk)
        digest.update(chunk)
    if expected_size is not None and size != expected_size:
        raise ArchiveSafetyError("File size changed or does not match ZIP metadata")
    return size, digest.hexdigest()


def load_and_validate_manifest(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    limits: ArchiveLimits = DEFAULT_LIMITS,
) -> dict[str, dict[str, object]]:
    info = members[MANIFEST_NAME]
    with archive.open(info, "r") as source:
        raw = source.read(limits.max_manifest_bytes + 1)
        if len(raw) > limits.max_manifest_bytes:
            raise ArchiveSafetyError("Backup manifest exceeds the safety limit")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchiveSafetyError("Backup manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise ArchiveSafetyError("Backup manifest schema is unsupported")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ArchiveSafetyError("Backup manifest entries are invalid")

    expected: dict[str, dict[str, object]] = {}
    canonical_names: set[str] = set()
    for value in entries:
        if not isinstance(value, dict):
            raise ArchiveSafetyError("Backup manifest entry is invalid")
        path = normalize_member_name(value.get("path", ""), limits)
        if path == MANIFEST_NAME:
            raise ArchiveSafetyError("Backup manifest cannot list itself")
        canonical = path.casefold()
        if canonical in canonical_names:
            raise ArchiveSafetyError(f"Duplicate manifest entry: {path}")
        canonical_names.add(canonical)
        size = value.get("size_bytes")
        sha256 = value.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ArchiveSafetyError(f"Invalid manifest size for {path}")
        if not isinstance(sha256, str) or len(sha256) != 64 or any(
            character not in "0123456789abcdef" for character in sha256
        ):
            raise ArchiveSafetyError(f"Invalid manifest SHA-256 for {path}")
        expected[path] = {"size_bytes": size, "sha256": sha256}
    actual_paths = set(members) - {MANIFEST_NAME}
    if set(expected) != actual_paths:
        raise ArchiveSafetyError("Backup manifest and ZIP entry sets do not match")
    for path, value in expected.items():
        if members[path].file_size != value["size_bytes"]:
            raise ArchiveSafetyError(f"Backup manifest size does not match ZIP metadata: {path}")
    return expected


def assert_sqlite_integrity(path: Path) -> None:
    try:
        with closing(
            sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        ) as connection:
            rows = connection.execute("PRAGMA quick_check").fetchall()
    except sqlite3.DatabaseError as exc:
        raise ArchiveSafetyError("Backup SQLite database cannot be opened") from exc
    if rows != [("ok",)]:
        raise ArchiveSafetyError("Backup SQLite database failed PRAGMA quick_check")


def iter_regular_source_files(
    data_dir: Path,
    limits: ArchiveLimits = DEFAULT_LIMITS,
) -> Iterable[tuple[Path, str]]:
    count = 0
    total = 0
    for root_name in sorted(ALLOWED_DIRECTORY_ROOTS):
        root = data_dir / root_name
        if not root.exists():
            continue
        if root.is_symlink() or not root.is_dir():
            raise ArchiveSafetyError(f"Backup source is not a regular directory: {root}")
        for current, directory_names, file_names in os.walk(root, followlinks=False):
            current_path = Path(current)
            for directory_name in sorted(directory_names):
                directory = current_path / directory_name
                if directory.is_symlink():
                    raise ArchiveSafetyError(f"Backup source contains a symbolic link: {directory}")
            for file_name in sorted(file_names):
                source = current_path / file_name
                metadata = source.stat(follow_symlinks=False)
                if stat.S_IFMT(metadata.st_mode) != stat.S_IFREG:
                    raise ArchiveSafetyError(f"Backup source is not a regular file: {source}")
                if metadata.st_size > limits.max_file_bytes:
                    raise ArchiveSafetyError(f"Backup source file exceeds the safety limit: {source}")
                count += 1
                total += metadata.st_size
                if count + 2 > limits.max_entries:
                    raise ArchiveSafetyError("Backup source entry count exceeds the safety limit")
                if total > limits.max_total_bytes:
                    raise ArchiveSafetyError("Backup source total size exceeds the safety limit")
                relative = source.relative_to(data_dir).as_posix()
                normalize_member_name(relative, limits)
                yield source, relative


def ensure_destination_parent(data_dir: Path, member_name: str) -> Path:
    parts = normalize_member_name(member_name).split("/")
    current = data_dir
    if current.is_symlink() or not current.is_dir():
        raise ArchiveSafetyError(f"Restore data directory is unsafe: {current}")
    for part in parts[:-1]:
        current = current / part
        if current.exists():
            if current.is_symlink() or not current.is_dir():
                raise ArchiveSafetyError(f"Restore path parent is unsafe: {current}")
        else:
            current.mkdir()
    destination = current / parts[-1]
    if destination.exists() and (destination.is_symlink() or not destination.is_file()):
        raise ArchiveSafetyError(f"Restore destination is not a regular file: {destination}")
    return destination
