from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from .config import Settings


BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{1,119}$")


class RepositoryError(RuntimeError):
    pass


def _run(repo: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and completed.returncode != 0:
        raise RepositoryError((completed.stderr or completed.stdout).strip() or "Git command failed")
    return completed.stdout.strip()


def repository_path(settings: Settings, project_id: str) -> Path:
    root = settings.repository_dir.resolve()
    path = (root / project_id).resolve()
    if root not in path.parents:
        raise RepositoryError("Repository path escaped data directory")
    return path


def ensure_repository(settings: Settings, project_id: str) -> Path:
    path = repository_path(settings, project_id)
    path.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").is_dir():
        _run(path, "init", "-b", "main")
        _run(path, "config", "user.name", "Kongpu Local")
        _run(path, "config", "user.email", "local@kongpu.invalid")
    return path


def validate_branch_name(name: str) -> str:
    if not BRANCH_PATTERN.fullmatch(name) or ".." in name or name.endswith("/"):
        raise RepositoryError("Invalid branch name")
    return name


def checkout_branch(repo: Path, name: str, base_commit: str | None = None) -> None:
    name = validate_branch_name(name)
    exists = _run(repo, "show-ref", "--verify", f"refs/heads/{name}", check=False)
    if exists:
        _run(repo, "switch", name)
        return
    args = ["switch", "-c", name]
    if base_commit:
        args.append(base_commit)
    _run(repo, *args)


def safe_file(repo: Path, relative: str) -> Path:
    normalized = relative.replace("\\", "/").lstrip("/")
    path = (repo / normalized).resolve()
    if not normalized or normalized.startswith(".git/") or repo.resolve() not in path.parents:
        raise RepositoryError("Invalid repository file path")
    return path


def write_files(repo: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = safe_file(repo, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def read_file(repo: Path, relative: str) -> str:
    path = safe_file(repo, relative)
    if not path.is_file():
        raise RepositoryError("Repository file not found")
    return path.read_text(encoding="utf-8")


def list_files(repo: Path) -> list[dict[str, object]]:
    result = []
    for path in sorted(item for item in repo.rglob("*") if item.is_file() and ".git" not in item.parts):
        relative = path.relative_to(repo).as_posix()
        content = path.read_bytes()
        result.append({"path": relative, "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return result


def commit_all(repo: Path, message: str, author: str = "本机工程师") -> str:
    _run(repo, "add", "--all")
    if not _run(repo, "status", "--porcelain"):
        return _run(repo, "rev-parse", "HEAD")
    env_name = author.replace("\n", " ").strip() or "本机工程师"
    _run(repo, "-c", f"user.name={env_name}", "-c", "user.email=local@kongpu.invalid", "commit", "-m", message)
    return _run(repo, "rev-parse", "HEAD")


def commit_diff(repo: Path, sha: str) -> str:
    return _run(repo, "show", "--format=fuller", "--stat", "--patch", sha)


def parent_of(repo: Path, sha: str) -> str | None:
    value = _run(repo, "rev-parse", f"{sha}^", check=False)
    return value or None
