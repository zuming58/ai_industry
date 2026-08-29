from __future__ import annotations

import hashlib
import re
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
    digest = hashlib.sha256(content).hexdigest()
    existing = session.scalar(select(SourceArtifact).where(SourceArtifact.sha256 == digest))
    relative = Path(digest[:2]) / digest[2:4] / digest
    destination = settings.artifact_dir / relative
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
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
    return StoredArtifact(record=existing, path=destination)


def artifact_path(settings: Settings, artifact: SourceArtifact) -> Path:
    path = (settings.artifact_dir / artifact.relative_path).resolve()
    root = settings.artifact_dir.resolve()
    if root not in path.parents:
        raise ValueError("Artifact path escaped the data directory")
    return path

