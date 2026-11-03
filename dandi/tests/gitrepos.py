"""Git repositories used as test data: clone once, then unpack copies from a tarball

Cloning is the only step that needs the network, so it is done once per
repository (with retries), and the result is kept as a tarball.  Every
consumer then gets its own copy by unpacking that tarball, which takes
milliseconds and cannot fail on the network.  The tarballs can be kept across
test sessions (and CI jobs) in a cache directory, in which case no clone is
needed at all.

This module deliberately does not depend on the rest of ``dandi`` (or on
pytest), so that it could be lifted into a shared package for other projects
cloning the same repositories (e.g. ``bids-examples``) in their tests.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time

lgr = logging.getLogger(__name__)

#: Seconds to wait before each retry of a failed clone; one more attempt is
#: made than there are entries.  Kept short, as the fixture setup counts toward
#: the timeout of the first test using it.
CLONE_RETRY_DELAYS: tuple[float, ...] = (5, 10)

#: Abort a transfer that stalls below 1 KiB/s for 60 s, so that it can be
#: retried, instead of hanging until the test times out.
GIT_HTTP_OPTIONS = ("-c", "http.lowSpeedLimit=1024", "-c", "http.lowSpeedTime=60")

#: Bump to invalidate cached tarballs whenever their layout changes.
TARBALL_FORMAT = 1


class GitRepoCloneError(RuntimeError):
    """Cloning a git repository failed on every attempt"""


@dataclass(frozen=True)
class GitRepoSpec:
    """A git repository to clone, possibly only partially"""

    #: URL of the repository
    url: str
    #: Top-level directories to check out (sparse checkout, cone mode), with
    #: no blobs fetched for the rest; ``None`` checks out everything
    sparse: tuple[str, ...] | None = None

    @property
    def tarball_name(self) -> str:
        """Name of the cached tarball, unique to the URL and selection"""
        name = self.url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        digest = hashlib.sha256(
            json.dumps([TARBALL_FORMAT, self.url, self.sparse]).encode("utf-8")
        ).hexdigest()[:16]
        return f"{name}-{digest}.tar"


def _git(*args: str, cwd: Path | None = None) -> None:
    r = subprocess.run(
        ["git", *GIT_HTTP_OPTIONS, *args],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
    )
    if r.returncode:
        raise subprocess.CalledProcessError(
            r.returncode, ["git", *args], stderr=r.stderr
        )


def _rmtree(path: Path) -> None:
    # git makes its object files read-only, which blocks removal on Windows
    for root, _, files in os.walk(path):
        for f in files:
            os.chmod(os.path.join(root, f), stat.S_IREAD | stat.S_IWRITE)
    shutil.rmtree(path)


def clone(spec: GitRepoSpec, path: Path) -> None:
    """Shallow-clone ``spec`` into the (not yet existing) ``path``

    The whole sequence is retried, since a sparse checkout fetches the blobs
    it needs lazily, i.e. over the network as well.
    """
    for attempt, delay in enumerate((*CLONE_RETRY_DELAYS, None), start=1):
        lgr.debug("Cloning %s into %s (attempt %d)", spec.url, path, attempt)
        try:
            if spec.sparse is None:
                _git("clone", "--depth=1", spec.url, str(path))
            else:
                _git(
                    "clone",
                    "--depth=1",
                    "--filter=blob:none",
                    "--sparse",
                    spec.url,
                    str(path),
                )
                # cwd is VERY important, not only to achieve the correct
                # effects, but also to avoid changing the checkout of the
                # repository the tests are run from.
                _git("sparse-checkout", "set", "--cone", *spec.sparse, cwd=path)
            return
        except subprocess.CalledProcessError as e:
            error = (e.stderr or "").strip()
            if delay is None:
                raise GitRepoCloneError(
                    f"Failed to clone {spec.url} after {attempt} attempts;"
                    f" last error from {' '.join(e.cmd[:2])!r}:\n{error}"
                ) from e
            lgr.warning(
                "Attempt %d to clone %s failed, retrying in %s s: %s",
                attempt,
                spec.url,
                delay,
                error,
            )
            if path.exists():
                _rmtree(path)
            time.sleep(delay)


def get_tarball(spec: GitRepoSpec, cache_dir: Path) -> Path:
    """Return the tarball of a fresh clone of ``spec`` in ``cache_dir``

    The clone is made only if no such tarball is there yet.  The tarball is
    put in place atomically, so concurrent sessions sharing ``cache_dir`` can
    at worst both clone, and never see a partial tarball.
    """
    tarball = cache_dir / spec.tarball_name
    if tarball.exists():
        lgr.debug("Using cached clone of %s from %s", spec.url, tarball)
        return tarball
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache_dir, prefix=".tmp-") as tmpdir:
        clone(spec, Path(tmpdir, "repo"))
        tmptar = Path(tmpdir, "repo.tar")
        with tarfile.open(tmptar, "w") as tf:
            tf.add(Path(tmpdir, "repo"), arcname=".")
        os.replace(tmptar, tarball)
    return tarball


def extract_tarball(tarball: Path, path: Path) -> None:
    """Unpack a tarball made by `get_tarball()` into the directory ``path``"""
    path.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball) as tf:
        if hasattr(tarfile, "data_filter"):
            tf.extractall(path, filter="data")
        else:
            # The `filter` argument is only available from Python 3.11.4 on;
            # the tarball is one we made ourselves, so this is equivalent.
            tf.extractall(path)
