from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .models import SourceArtifact


SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._()-]+")


@dataclass(frozen=True)
class StoredArtifact:
    record: SourceArtifact
    path: Path


class ArtifactIntegrityError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _artifact_destination(settings: Settings, relative: str) -> Path:
    """Resolve only the generated two-level SHA-256 layout, rejecting links."""
    if not re.fullmatch(r"[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{64}", relative):
        raise ArtifactIntegrityError("ARTIFACT_PATH_INVALID", "文件工件相对路径格式无效")
    root = settings.artifact_dir.resolve()
    lexical = root / Path(relative)
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ArtifactIntegrityError("ARTIFACT_PATH_INVALID", "文件工件路径包含符号链接")
    destination = lexical.resolve(strict=False)
    if root not in destination.parents:
        raise ArtifactIntegrityError("ARTIFACT_PATH_INVALID", "文件工件路径逃逸数据目录")
    return destination


def sanitize_filename(name: str) -> str:
    basename = Path(name.replace("\\", "/")).name
    cleaned = SAFE_FILENAME.sub("_", basename).strip("._")
    return cleaned[:180] or "artifact.bin"


def store_bytes(
    session: Session,
    settings: Settings,
    content: bytes,
    original_name: str,
    media_type: str,
) -> StoredArtifact:
    if len(content) > settings.max_artifact_bytes:
        raise ArtifactIntegrityError(
            "ARTIFACT_TOO_LARGE", "文件工件超过本机安全大小限制"
        )
    digest = hashlib.sha256(content).hexdigest()
    existing = session.scalar(select(SourceArtifact).where(SourceArtifact.sha256 == digest))
    relative = Path(digest[:2]) / digest[2:4] / digest
    destination = _artifact_destination(settings, relative.as_posix())
    if destination.exists():
        if not destination.is_file() or destination.is_symlink():
            raise ArtifactIntegrityError("ARTIFACT_PATH_INVALID", "文件工件路径不是普通文件")
        disk_size = destination.stat().st_size
        if disk_size > settings.max_artifact_bytes:
            raise ArtifactIntegrityError(
                "ARTIFACT_TOO_LARGE", "已有内容寻址工件超过本机安全大小限制"
            )
        if disk_size != len(content):
            raise ArtifactIntegrityError(
                "ARTIFACT_SIZE_MISMATCH", "已有内容寻址工件大小与输入不一致"
            )
        stored = destination.read_bytes()
        if len(stored) != disk_size or hashlib.sha256(stored).hexdigest() != digest:
            raise ArtifactIntegrityError("ARTIFACT_HASH_MISMATCH", "已有内容寻址工件与哈希不一致")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
    if existing is None:
        existing = SourceArtifact(
            sha256=digest,
            size_bytes=len(content),
            media_type=media_type,
            original_name=sanitize_filename(original_name),
            relative_path=relative.as_posix(),
        )
        session.add(existing)
        session.flush()
    elif existing.size_bytes != len(content):
        raise ArtifactIntegrityError("ARTIFACT_SIZE_MISMATCH", "文件工件元数据大小与内容不一致")
    return StoredArtifact(record=existing, path=destination)


def artifact_path(settings: Settings, artifact: SourceArtifact) -> Path:
    return _artifact_destination(settings, artifact.relative_path)


def read_stored_bytes(settings: Settings, artifact: SourceArtifact) -> bytes:
    """Read one immutable artifact only after validating its metadata and disk size."""
    try:
        path = _artifact_destination(settings, artifact.relative_path)
    except ArtifactIntegrityError:
        raise
    if not path.is_file() or path.is_symlink():
        raise ArtifactIntegrityError("ARTIFACT_MISSING", "文件工件已丢失")
    disk_size = path.stat().st_size
    if artifact.size_bytes < 0 or artifact.size_bytes > settings.max_artifact_bytes:
        raise ArtifactIntegrityError(
            "ARTIFACT_TOO_LARGE", "文件工件元数据超过本机安全大小限制"
        )
    if disk_size > settings.max_artifact_bytes:
        raise ArtifactIntegrityError(
            "ARTIFACT_TOO_LARGE", "文件工件磁盘大小超过本机安全限制"
        )
    if disk_size != artifact.size_bytes:
        raise ArtifactIntegrityError(
            "ARTIFACT_SIZE_MISMATCH", "文件工件大小与元数据不匹配"
        )
    content = path.read_bytes()
    if len(content) != disk_size:
        raise ArtifactIntegrityError(
            "ARTIFACT_SIZE_MISMATCH", "文件工件读取期间发生变化"
        )
    if hashlib.sha256(content).hexdigest() != artifact.sha256:
        raise ArtifactIntegrityError(
            "ARTIFACT_HASH_MISMATCH", "文件工件哈希不匹配"
        )
    return content
