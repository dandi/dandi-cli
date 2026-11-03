from __future__ import annotations

from pathlib import Path
import subprocess
import time

import pytest

from . import gitrepos
from .gitrepos import (
    CLONE_RETRY_DELAYS,
    GitRepoCloneError,
    GitRepoSpec,
    extract_tarball,
    get_tarball,
)
from .skip import skipif


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Tester", "-c", "user.email=tester@example.com", *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.DEVNULL,
    )


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    """A repository with three top-level directories and a top-level file"""
    skipif.no_git()
    repo = tmp_path / "source"
    for d in ("ds1", "ds2", "ds3"):
        (repo / d / "sub").mkdir(parents=True)
        (repo / d / "sub" / "data.txt").write_text(f"content of {d}\n")
    (repo / "README").write_text("top level\n")
    _git("init", "-q", cwd=repo)
    # so that the partial clone (--filter=blob:none) is honored over file://
    _git("config", "uploadpack.allowFilter", "true", cwd=repo)
    _git("add", ".", cwd=repo)
    _git("commit", "-q", "-m", "initial", cwd=repo)
    return repo


@pytest.mark.ai_generated
def test_get_tarball_sparse(source_repo: Path, tmp_path: Path) -> None:
    spec = GitRepoSpec(url=source_repo.as_uri(), sparse=("ds1", "ds3"))
    tarball = get_tarball(spec, tmp_path / "cache")
    assert tarball == tmp_path / "cache" / spec.tarball_name
    assert [p.name for p in (tmp_path / "cache").iterdir()] == [tarball.name]
    extract_tarball(tarball, dest := tmp_path / "copy")
    assert (dest / "ds1" / "sub" / "data.txt").read_text() == "content of ds1\n"
    assert (dest / "ds3" / "sub" / "data.txt").exists()
    assert not (dest / "ds2").exists()
    assert (dest / "README").exists()
    assert (dest / ".git").is_dir()


@pytest.mark.ai_generated
def test_get_tarball_full(source_repo: Path, tmp_path: Path) -> None:
    tarball = get_tarball(GitRepoSpec(url=source_repo.as_uri()), tmp_path / "cache")
    extract_tarball(tarball, dest := tmp_path / "copy")
    for d in ("ds1", "ds2", "ds3"):
        assert (dest / d / "sub" / "data.txt").read_text() == f"content of {d}\n"


@pytest.mark.ai_generated
def test_get_tarball_reuses_cache(
    source_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = GitRepoSpec(url=source_repo.as_uri(), sparse=("ds1",))
    tarball = get_tarball(spec, tmp_path / "cache")

    def no_clone(*_args: object) -> None:
        raise AssertionError("must not clone again")

    monkeypatch.setattr(gitrepos, "clone", no_clone)
    assert get_tarball(spec, tmp_path / "cache") == tarball


@pytest.mark.ai_generated
def test_extracted_copies_are_independent(source_repo: Path, tmp_path: Path) -> None:
    tarball = get_tarball(GitRepoSpec(url=source_repo.as_uri()), tmp_path / "cache")
    extract_tarball(tarball, copy1 := tmp_path / "copy1")
    extract_tarball(tarball, copy2 := tmp_path / "copy2")
    (copy1 / "ds1" / "sub" / "data.txt").write_text("modified\n")
    (copy1 / "new.txt").write_text("new\n")
    assert (copy2 / "ds1" / "sub" / "data.txt").read_text() == "content of ds1\n"
    assert not (copy2 / "new.txt").exists()


@pytest.mark.ai_generated
def test_tarball_name() -> None:
    url = "https://github.com/bids-standard/bids-examples"
    names = {
        GitRepoSpec(url=url).tarball_name,
        GitRepoSpec(url=url, sparse=("asl003",)).tarball_name,
        GitRepoSpec(url=url, sparse=("asl003", "pet003")).tarball_name,
        GitRepoSpec(url=url + "-other").tarball_name,
    }
    assert len(names) == 4
    assert all(n.startswith("bids-examples") and n.endswith(".tar") for n in names)
    assert GitRepoSpec(url=url + ".git").tarball_name.startswith("bids-examples-")


def _fail_with(stderr: str) -> subprocess.CalledProcessError:
    return subprocess.CalledProcessError(128, ["git", "clone"], stderr=stderr)


@pytest.mark.ai_generated
def test_clone_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    sleeps: list[float] = []

    def flaky_git(*args: str, cwd: Path | None = None) -> None:
        calls.append(args)
        # a failed attempt may leave a partial clone behind
        (path / ".git").mkdir(parents=True)
        (path / ".git" / "packed").write_text("partial")
        (path / ".git" / "packed").chmod(0o444)
        if len(calls) <= len(CLONE_RETRY_DELAYS):
            raise _fail_with("fatal: Could not resolve host: github.com")

    path = tmp_path / "clone"
    monkeypatch.setattr(gitrepos, "_git", flaky_git)
    monkeypatch.setattr(time, "sleep", sleeps.append)
    gitrepos.clone(GitRepoSpec(url="https://example.com/repo"), path)
    assert len(calls) == len(CLONE_RETRY_DELAYS) + 1
    assert sleeps == list(CLONE_RETRY_DELAYS)


@pytest.mark.ai_generated
def test_clone_retries_sparse_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lazy fetch by ``sparse-checkout set`` is retried too"""
    calls: list[str] = []

    def flaky_git(*args: str, cwd: Path | None = None) -> None:
        calls.append(args[0])
        if args[0] == "clone":
            path.mkdir()
        elif calls.count("sparse-checkout") == 1:
            raise _fail_with("error: RPC failed; curl 56 Recv failure")

    path = tmp_path / "clone"
    monkeypatch.setattr(gitrepos, "_git", flaky_git)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    gitrepos.clone(GitRepoSpec(url="https://example.com/repo", sparse=("a",)), path)
    assert calls == ["clone", "sparse-checkout", "clone", "sparse-checkout"]


@pytest.mark.ai_generated
def test_get_tarball_gives_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def failing_git(*_args: str, cwd: Path | None = None) -> None:
        nonlocal calls
        calls += 1
        raise _fail_with("fatal: unable to access: Could not resolve host: github.com")

    monkeypatch.setattr(gitrepos, "_git", failing_git)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    cache_dir = tmp_path / "cache"
    with pytest.raises(GitRepoCloneError, match="Could not resolve host: github.com"):
        get_tarball(GitRepoSpec(url="https://example.com/repo"), cache_dir)
    assert calls == len(CLONE_RETRY_DELAYS) + 1
    # nothing, in particular no partial tarball, is left in the cache
    assert list(cache_dir.iterdir()) == []


@pytest.mark.ai_generated
def test_git_error_includes_stderr(tmp_path: Path) -> None:
    skipif.no_git()
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        gitrepos._git("clone", str(tmp_path / "nonexistent"), str(tmp_path / "x"))
    assert "nonexistent" in excinfo.value.stderr
