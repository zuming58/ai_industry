from __future__ import annotations

import hashlib
import os
import re
import subprocess
import getpass
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath

from .config import Settings


BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{1,119}$")
GIT_TIMEOUT_SECONDS = 15
GIT_OUTPUT_LIMIT_BYTES = 8 * 1024 * 1024
REPOSITORY_FILE_LIMIT = 2_000
REPOSITORY_TOTAL_LIMIT_BYTES = 100 * 1024 * 1024
REPOSITORY_FILE_LIMIT_BYTES = 8 * 1024 * 1024
_REPOSITORY_LOCKS_GUARD = threading.Lock()
_REPOSITORY_LOCKS: dict[str, threading.RLock] = {}


class RepositoryError(RuntimeError):
    pass


@contextmanager
def repository_guard(repo: Path):
    """Serialize work-tree operations for one local project repository."""
    key = os.path.normcase(str(repo.resolve(strict=False)))
    with _REPOSITORY_LOCKS_GUARD:
        lock = _REPOSITORY_LOCKS.setdefault(key, threading.RLock())
    with lock:
        yield


def _redact_text(value: str, repo: Path | None = None) -> str:
    text = value
    for needle in (str(repo) if repo else "", str(Path.home()), os.environ.get("USERNAME", ""), os.environ.get("USER", ""), getpass.getuser()):
        if needle:
            text = text.replace(needle, "<redacted>")
    return text


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"})
    return env


def _check_output_size(output: bytes | str, repo: Path) -> None:
    size = len(output.encode("utf-8", errors="replace")) if isinstance(output, str) else len(output)
    if size > GIT_OUTPUT_LIMIT_BYTES:
        raise RepositoryError("Git 输出超过安全限制")


def _run_bounded(repo: Path, args: tuple[str, ...], *, text_mode: bool) -> tuple[int, str | bytes, str | bytes]:
    """Run Git with a hard wall-clock and streaming stdout/stderr bounds."""
    try:
        process = subprocess.Popen(
            ["git", *args],
            cwd=repo,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text_mode,
            encoding="utf-8" if text_mode else None,
            errors="replace" if text_mode else None,
            env=_git_env(),
        )
    except OSError as exc:
        raise RepositoryError(_redact_text(str(exc), repo)) from exc

    stdout_parts: list[str | bytes] = []
    stderr_parts: list[str | bytes] = []
    overflow = threading.Event()

    def drain(stream, parts: list[str | bytes]) -> None:
        total = 0
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                size = len(chunk.encode("utf-8", errors="replace")) if isinstance(chunk, str) else len(chunk)
                total += size
                if total > GIT_OUTPUT_LIMIT_BYTES:
                    overflow.set()
                    try:
                        process.kill()
                    except OSError:
                        pass
                    return
                parts.append(chunk)
        finally:
            stream.close()

    threads = [
        threading.Thread(target=drain, args=(process.stdout, stdout_parts), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, stderr_parts), daemon=True),
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + GIT_TIMEOUT_SECONDS
    try:
        process.wait(timeout=GIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        try:
            process.kill()
        except OSError:
            pass
        process.wait()
        for thread in threads:
            thread.join()
        raise RepositoryError("Git 命令超时") from exc
    for thread in threads:
        thread.join(max(0.1, deadline - time.monotonic()))
    if overflow.is_set():
        raise RepositoryError("Git 输出超过安全限制")
    stdout = ("" if text_mode else b"").join(stdout_parts)
    stderr = ("" if text_mode else b"").join(stderr_parts)
    return process.returncode, stdout, stderr


def _run(repo: Path, *args: str, check: bool = True) -> str:
    returncode, stdout, stderr = _run_bounded(repo, tuple(args), text_mode=True)
    if check and returncode != 0:
        message = (stderr or stdout).strip() or "Git command failed"
        raise RepositoryError(_redact_text(message, repo))
    return stdout.strip()


def _run_bytes(repo: Path, *args: str) -> bytes:
    returncode, stdout, stderr = _run_bounded(repo, tuple(args), text_mode=False)
    if returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RepositoryError(_redact_text(message or "Git command failed", repo))
    return stdout


def repository_path(settings: Settings, project_id: str) -> Path:
    root = settings.repository_dir.resolve()
    path = (root / project_id).resolve()
    if root not in path.parents:
        raise RepositoryError("Repository path escaped data directory")
    return path


def ensure_repository(settings: Settings, project_id: str) -> Path:
    path = repository_path(settings, project_id)
    with repository_guard(path):
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
    with repository_guard(repo):
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
    if not isinstance(relative, str):
        raise RepositoryError("Invalid repository file path")
    normalized = relative.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(normalized)
    parts = normalized.split("/")
    if (
        not normalized
        or normalized.startswith("/")
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or any(part in {"", ".", ".."} for part in parts)
        or any(part.lower() == ".git" for part in parts)
    ):
        raise RepositoryError("Invalid repository file path")
    root = repo.resolve()
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise RepositoryError("Repository file path contains a symbolic link")
    path = (root / normalized).resolve(strict=False)
    if path == root or root not in path.parents:
        raise RepositoryError("Invalid repository file path")
    return path


def write_files(repo: Path, files: dict[str, str]) -> None:
    if len(files) > REPOSITORY_FILE_LIMIT:
        raise RepositoryError("仓库写入文件数量超过安全限制")
    total_size = 0
    prepared: list[tuple[Path, bytes]] = []
    for relative, content in files.items():
        encoded = content.encode("utf-8")
        size = len(encoded)
        if size > REPOSITORY_FILE_LIMIT_BYTES:
            raise RepositoryError("仓库文件超过安全限制")
        total_size += size
        if total_size > REPOSITORY_TOTAL_LIMIT_BYTES:
            raise RepositoryError("仓库写入总体积超过安全限制")
        prepared.append((safe_file(repo, relative), encoded))
    with repository_guard(repo):
        temporary_files: list[Path] = []
        try:
            for path, encoded in prepared:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
                temporary.write_bytes(encoded)
                temporary_files.append(temporary)
            for (path, _encoded), temporary in zip(prepared, temporary_files, strict=True):
                os.replace(temporary, path)
        finally:
            for temporary in temporary_files:
                if temporary.exists():
                    temporary.unlink()


def read_file(repo: Path, relative: str) -> str:
    with repository_guard(repo):
        path = safe_file(repo, relative)
        if not path.is_file():
            raise RepositoryError("Repository file not found")
        if path.stat().st_size > REPOSITORY_FILE_LIMIT_BYTES:
            raise RepositoryError("仓库文件超过安全限制")
        return path.read_text(encoding="utf-8")


def _verified_commit(repo: Path, sha: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", sha):
        raise RepositoryError("Invalid Git commit id")
    resolved = _run(repo, "rev-parse", "--verify", f"{sha}^{{commit}}")
    if not re.fullmatch(r"[0-9a-f]{40,64}", resolved):
        raise RepositoryError("Git commit could not be resolved")
    return resolved


def list_files_at_commit(repo: Path, sha: str) -> list[str]:
    resolved = _verified_commit(repo, sha)
    output = _run_bytes(repo, "ls-tree", "-r", "-l", "-z", resolved)
    paths: list[str] = []
    total_size = 0
    for value in (entry for entry in output.split(b"\0") if entry):
        metadata, separator, raw_path = value.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 4 or fields[1] != b"blob":
            raise RepositoryError("Git tree contains an unsupported entry")
        try:
            size = int(fields[3])
            path = raw_path.decode("utf-8", errors="strict")
        except (ValueError, UnicodeDecodeError) as exc:
            raise RepositoryError("Git tree metadata is invalid") from exc
        if size > REPOSITORY_FILE_LIMIT_BYTES:
            raise RepositoryError("仓库文件超过安全限制")
        paths.append(path)
        total_size += size
        if len(paths) > REPOSITORY_FILE_LIMIT:
            raise RepositoryError("仓库文件数量超过安全限制")
        if total_size > REPOSITORY_TOTAL_LIMIT_BYTES:
            raise RepositoryError("仓库总体积超过安全限制")
    for path in paths:
        safe_file(repo, path)
    return sorted(paths)


def read_file_at_commit(repo: Path, sha: str, relative: str) -> str:
    resolved = _verified_commit(repo, sha)
    normalized = safe_file(repo, relative).relative_to(repo.resolve()).as_posix()
    raw_size = _run(repo, "cat-file", "-s", f"{resolved}:{normalized}")
    try:
        size = int(raw_size)
    except ValueError as exc:
        raise RepositoryError("Git blob size is invalid") from exc
    if size > REPOSITORY_FILE_LIMIT_BYTES:
        raise RepositoryError("仓库文件超过安全限制")
    return _run_bytes(repo, "show", f"{resolved}:{normalized}").decode(
        "utf-8", errors="strict"
    )


def list_files(repo: Path) -> list[dict[str, object]]:
    with repository_guard(repo):
        result = []
        total_size = 0
        root = repo.resolve()
        for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink() and ".git" not in item.parts):
            if len(result) >= REPOSITORY_FILE_LIMIT:
                raise RepositoryError("仓库文件数量超过安全限制")
            relative = path.relative_to(root).as_posix()
            safe_file(root, relative)
            disk_size = path.stat().st_size
            if disk_size > REPOSITORY_FILE_LIMIT_BYTES:
                raise RepositoryError("仓库文件超过安全限制")
            total_size += disk_size
            if total_size > REPOSITORY_TOTAL_LIMIT_BYTES:
                raise RepositoryError("仓库总体积超过安全限制")
            content = path.read_bytes()
            if len(content) != disk_size:
                raise RepositoryError("仓库文件读取期间发生变化")
            result.append({"path": relative, "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
        return result


def commit_all(repo: Path, message: str, author: str = "本机工程师") -> str:
    with repository_guard(repo):
        _run(repo, "add", "--all")
        if not _run(repo, "status", "--porcelain"):
            return _run(repo, "rev-parse", "HEAD")
        env_name = author.replace("\n", " ").strip() or "本机工程师"
        _run(repo, "-c", f"user.name={env_name}", "-c", "user.email=local@kongpu.invalid", "commit", "-m", message)
        return _run(repo, "rev-parse", "HEAD")


def create_generated_commit(
    repo: Path, branch_name: str, files: dict[str, str], message: str
) -> tuple[str, str | None]:
    with repository_guard(repo):
        checkout_branch(repo, branch_name)
        write_files(repo, files)
        sha = commit_all(repo, message)
        return sha, parent_of(repo, sha)


def commit_diff(repo: Path, sha: str) -> str:
    return _run(repo, "show", "--format=fuller", "--stat", "--patch", sha)


def compare_commits(repo: Path, base_sha: str, target_sha: str) -> str:
    base = _verified_commit(repo, base_sha)
    target = _verified_commit(repo, target_sha)
    return _run(
        repo,
        "diff",
        "--stat",
        "--patch",
        "--find-renames",
        base,
        target,
    )


def parent_of(repo: Path, sha: str) -> str | None:
    value = _run(repo, "rev-parse", f"{sha}^", check=False)
    return value or None


def is_working_tree_clean(repo: Path) -> bool:
    return not bool(_run(repo, "status", "--porcelain"))
