from __future__ import annotations

from pathlib import Path
import threading
import time

import pytest

from kongpu_api import adapters, repository


def test_adapter_detection_rejects_relative_and_outside_paths(monkeypatch, tmp_path: Path) -> None:
    allowed = tmp_path / "vendor"
    allowed.mkdir()
    tool = allowed / "GXWorks3.exe"
    tool.write_bytes(b"placeholder")
    monkeypatch.setenv("KONGPU_ADAPTER_ALLOWED_ROOTS", str(allowed))

    monkeypatch.setenv("KONGPU_GXWORKS3_PATH", "relative/tool.exe")
    relative = adapters.detect("gxworks3")
    assert relative["status"] == "unavailable"
    assert relative["details"]["path_status"] == "relative_path_rejected"

    outside = tmp_path / "outside.exe"
    outside.write_bytes(b"placeholder")
    monkeypatch.setenv("KONGPU_GXWORKS3_PATH", str(outside))
    rejected = adapters.detect("gxworks3")
    assert rejected["status"] == "unavailable"
    assert rejected["details"]["path_status"] == "outside_allowlist"

    monkeypatch.setenv("KONGPU_GXWORKS3_PATH", str(tool))
    accepted = adapters.detect("gxworks3")
    assert accepted["status"] == "manual_required"
    assert accepted["details"]["path_status"] == "accepted"
    assert accepted["details"]["detected_path"].endswith("GXWorks3.exe")


def test_adapter_detection_redacts_home_and_user_from_snapshot(monkeypatch) -> None:
    home_tool = Path.home() / "vendor" / "GXWorks3.exe"
    monkeypatch.setenv("KONGPU_GXWORKS3_PATH", str(home_tool))
    monkeypatch.delenv("KONGPU_ADAPTER_ALLOWED_ROOTS", raising=False)
    result = adapters.detect("gxworks3")
    serialized = str(result["details"])
    assert str(Path.home()) not in serialized
    assert "\\" not in result["details"]["checked_paths"][0]


def test_git_commands_are_noninteractive_bounded_and_timeout(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    class Stream:
        def __init__(self, value: str = ""):
            self.value = value
            self.reads = 0

        def read(self, _size: int):
            if self.reads:
                return ""
            self.reads += 1
            return self.value

        def close(self):
            return None

    class Process:
        returncode = 0
        stdout = Stream("ok")
        stderr = Stream()

        def wait(self, timeout=None):
            calls.append({"wait_timeout": timeout})
            return self.returncode

        def kill(self):
            return None

    def fake_popen(*args, **kwargs):
        calls.append(kwargs)
        return Process()

    monkeypatch.setattr(repository.subprocess, "Popen", fake_popen)
    assert repository._run(tmp_path, "status", "--porcelain") == "ok"
    assert calls[0]["stdin"] is repository.subprocess.DEVNULL
    assert calls[0]["stdout"] is repository.subprocess.PIPE
    assert calls[0]["stderr"] is repository.subprocess.PIPE
    assert calls[1]["wait_timeout"] == repository.GIT_TIMEOUT_SECONDS
    assert calls[0]["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert calls[0]["env"]["GIT_CONFIG_NOSYSTEM"] == "1"

    class TimeoutProcess(Process):
        def __init__(self):
            self.wait_calls = 0

        def wait(self, timeout=None):
            self.wait_calls += 1
            if self.wait_calls == 1:
                raise repository.subprocess.TimeoutExpired(cmd="git", timeout=timeout)
            return 0

    timeout_process = TimeoutProcess()
    monkeypatch.setattr(repository.subprocess, "Popen", lambda *args, **kwargs: timeout_process)

    with pytest.raises(repository.RepositoryError, match="超时"):
        repository._run(tmp_path, "status")
    assert timeout_process.wait_calls == 2


def test_git_combined_stdout_and_stderr_share_one_output_budget(
    monkeypatch, tmp_path: Path
) -> None:
    class Stream:
        def __init__(self, value: str):
            self.value = value
            self.reads = 0

        def read(self, _size: int) -> str:
            if self.reads:
                return ""
            self.reads += 1
            return self.value

        def close(self) -> None:
            return None

    class Process:
        returncode = 0

        def __init__(self) -> None:
            self.stdout = Stream("a" * 6)
            self.stderr = Stream("b" * 6)

        def wait(self, timeout=None):
            return self.returncode

        def kill(self) -> None:
            return None

    monkeypatch.setattr(repository, "GIT_OUTPUT_LIMIT_BYTES", 10)
    monkeypatch.setattr(repository.subprocess, "Popen", lambda *args, **kwargs: Process())
    with pytest.raises(repository.RepositoryError, match="输出超过"):
        repository._run(tmp_path, "status")


def test_git_output_and_repository_file_guards(monkeypatch, tmp_path: Path) -> None:
    with pytest.raises(repository.RepositoryError, match="输出超过"):
        repository._check_output_size("x" * (repository.GIT_OUTPUT_LIMIT_BYTES + 1), tmp_path)

    repo = tmp_path / "repo"
    repo.mkdir()
    for value in (
        "",
        ".",
        "../escape",
        "/absolute",
        "C:/absolute",
        ".git/config",
        "a//b",
        "CON.txt",
        "trailing./file.st",
        "bad?/file.st",
        "a\x00b.st",
    ):
        with pytest.raises(repository.RepositoryError):
            repository.safe_file(repo, value)

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    link = repo / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable in this test environment")
    with pytest.raises(repository.RepositoryError):
        repository.safe_file(repo, "linked/secret.txt")


def test_repository_size_and_tree_metadata_guards(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    oversized = repo / "oversized.txt"
    oversized.write_bytes(b"x" * (repository.REPOSITORY_FILE_LIMIT_BYTES + 1))
    with pytest.raises(repository.RepositoryError, match="文件超过"):
        repository.read_file(repo, "oversized.txt")
    with pytest.raises(repository.RepositoryError, match="文件超过"):
        repository.list_files(repo)

    monkeypatch.setattr(repository, "_verified_commit", lambda _repo, _sha: "a" * 40)
    oversized_tree = (
        b"100644 blob " + b"b" * 40 + b" "
        + str(repository.REPOSITORY_FILE_LIMIT_BYTES + 1).encode("ascii")
        + b"\tlarge.st\0"
    )
    monkeypatch.setattr(repository, "_run_bytes", lambda *_args: oversized_tree)
    with pytest.raises(repository.RepositoryError, match="文件超过"):
        repository.list_files_at_commit(repo, "a" * 40)

    valid_tree = b"100644 blob " + b"b" * 40 + b" 4\tmain.st\0"
    monkeypatch.setattr(repository, "_run_bytes", lambda *_args: valid_tree)
    assert repository.list_files_at_commit(repo, "a" * 40) == ["main.st"]

    symlink_tree = b"120000 blob " + b"b" * 40 + b" 10\tlinked.st\0"
    monkeypatch.setattr(repository, "_run_bytes", lambda *_args: symlink_tree)
    with pytest.raises(repository.RepositoryError, match="unsupported"):
        repository.list_files_at_commit(repo, "a" * 40)

    backslash_tree = b"100644 blob " + b"b" * 40 + b" 4\tdir\\main.st\0"
    monkeypatch.setattr(repository, "_run_bytes", lambda *_args: backslash_tree)
    with pytest.raises(repository.RepositoryError, match="backslash"):
        repository.list_files_at_commit(repo, "a" * 40)


def test_write_files_enforces_projected_repository_budget_and_duplicate_paths(
    monkeypatch, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "first.st").write_text("1234", encoding="utf-8")
    (repo / "second.st").write_text("5678", encoding="utf-8")
    monkeypatch.setattr(repository, "REPOSITORY_FILE_LIMIT", 2)
    monkeypatch.setattr(repository, "REPOSITORY_TOTAL_LIMIT_BYTES", 10)

    repository.write_files(repo, {"first.st": "12"})
    assert (repo / "first.st").read_text(encoding="utf-8") == "12"

    with pytest.raises(repository.RepositoryError, match="数量超过"):
        repository.write_files(repo, {"third.st": "1"})
    assert not (repo / "third.st").exists()

    with pytest.raises(repository.RepositoryError, match="总体积超过"):
        repository.write_files(repo, {"first.st": "1234567"})
    assert (repo / "first.st").read_text(encoding="utf-8") == "12"

    with pytest.raises(repository.RepositoryError, match="Duplicate"):
        repository.write_files(repo, {"nested/main.st": "a", "nested\\main.st": "b"})


def test_checkout_branch_refuses_to_switch_a_dirty_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    repository._run(repo, "init", "-b", "main")
    repository._run(repo, "config", "user.name", "Kongpu Test")
    repository._run(repo, "config", "user.email", "test@kongpu.invalid")
    (repo / "main.st").write_text("initial", encoding="utf-8")
    repository._run(repo, "add", "main.st")
    repository._run(repo, "commit", "-m", "initial")
    (repo / "main.st").write_text("modified", encoding="utf-8")

    with pytest.raises(repository.RepositoryError, match="uncommitted"):
        repository.checkout_branch(repo, "feature/safe")
    assert repository._run(repo, "branch", "--show-current") == "main"
    assert (repo / "main.st").read_text(encoding="utf-8") == "modified"


def test_repository_guard_serializes_same_repo_but_not_other_repo(tmp_path: Path) -> None:
    first_repo = tmp_path / "first"
    second_repo = tmp_path / "second"
    first_repo.mkdir()
    second_repo.mkdir()
    entered = threading.Event()
    release = threading.Event()
    second_entered = threading.Event()

    def hold_first() -> None:
        with repository.repository_guard(first_repo):
            entered.set()
            release.wait(timeout=2)

    def enter_first_again() -> None:
        entered.wait(timeout=2)
        with repository.repository_guard(first_repo):
            second_entered.set()

    holder = threading.Thread(target=hold_first)
    waiter = threading.Thread(target=enter_first_again)
    holder.start()
    waiter.start()
    assert entered.wait(timeout=1)
    time.sleep(0.05)
    assert not second_entered.is_set()
    with repository.repository_guard(second_repo):
        pass
    release.set()
    holder.join(timeout=2)
    waiter.join(timeout=2)
    assert second_entered.is_set()
