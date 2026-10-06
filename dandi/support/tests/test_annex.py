from __future__ import annotations

from collections.abc import Iterator
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import shutil
from subprocess import run
import threading
from typing import Any

from fscacher import PersistentCache
import h5py
import pytest

from ..annex import (
    AnnexKey,
    AnnexReadableFile,
    AnnexRepo,
    get_annex_key,
    get_annex_readable,
    parse_url_log,
)
from ...pynwb_utils import get_neurodata_types, readable_fingerprint
from ...tests.fixtures import (
    annex_key_for_file,
    create_git_annex_branch,
    make_annexed_dandiset,
)
from ...tests.skip import skipif

# The key of an actual asset of https://github.com/dandisets/000003
REAL_KEY = (
    "SHA256E-s61510864725--"
    "e063aec023141b5a11fb95a7605fb31057aab05944a81f37c5c6211739ed7f62.nwb"
)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "key,backend,size,name",
    [
        (
            REAL_KEY,
            "SHA256E",
            61510864725,
            "e063aec023141b5a11fb95a7605fb31057aab05944a81f37c5c6211739ed7f62.nwb",
        ),
        (
            "MD5E-s123--0123456789abcdef0123456789abcdef.nwb",
            "MD5E",
            123,
            "0123456789abcdef0123456789abcdef.nwb",
        ),
        ("WORM-s512-m1700000000--foo.txt", "WORM", 512, "foo.txt"),
        ("URL--http&c%%example.com%file", "URL", None, "http&c%%example.com%file"),
    ],
)
def test_annex_key_parse(key: str, backend: str, size: int | None, name: str) -> None:
    k = AnnexKey.parse(key)
    assert (k.backend, k.size, k.name) == (backend, size, name)
    assert str(k) == key


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "key", ["", "SHA256E-s123", "--abc", "SHA256E-s1--", "-s1--abc"]
)
def test_annex_key_parse_invalid(key: str) -> None:
    with pytest.raises(ValueError):
        AnnexKey.parse(key)


@pytest.mark.ai_generated
def test_annex_key_hashdir_lower() -> None:
    # This is where the key's log files are located in the git-annex branch of
    # https://github.com/dandisets/000003
    assert AnnexKey.parse(REAL_KEY).hashdir_lower == "595/864"


@pytest.mark.ai_generated
def test_get_annex_key(tmp_path: Path) -> None:
    (tmp_path / "regular.nwb").write_bytes(b"data")
    assert get_annex_key(tmp_path / "regular.nwb") is None
    assert get_annex_key(tmp_path / "nonexistent.nwb") is None
    (tmp_path / "other.nwb").symlink_to("somewhere/else.nwb")
    assert get_annex_key(tmp_path / "other.nwb") is None
    (tmp_path / "notakey.nwb").symlink_to(".git/annex/objects/Xx/Yy/notakey/notakey")
    assert get_annex_key(tmp_path / "notakey.nwb") is None
    (tmp_path / "annexed.nwb").symlink_to(
        f"../.git/annex/objects/Xx/Yy/{REAL_KEY}/{REAL_KEY}"
    )
    key = get_annex_key(tmp_path / "annexed.nwb")
    assert key is not None
    assert key.key == REAL_KEY
    assert key.size == 61510864725
    # Keys that do not pin the content cannot be used to fingerprint it
    for i, other_key in enumerate(
        ["WORM-s4-m1700000000--file.nwb", "URL-s4--https&c%%example.com%file.nwb"]
    ):
        (tmp_path / f"unpinned{i}.nwb").symlink_to(
            f"../.git/annex/objects/Xx/Yy/{other_key}/{other_key}"
        )
        assert get_annex_key(tmp_path / f"unpinned{i}.nwb") is None


@pytest.mark.ai_generated
def test_parse_url_log() -> None:
    s3_url = "https://dandiarchive.s3.amazonaws.com/blobs/9d7/5f6/uuid?versionId=abc"
    api_url = "https://api.dandiarchive.org/api/assets/25564f6b/download/"
    old_api_url = (
        "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
        "/assets/25564f6b/download/"
    )
    log = (
        f"1620050417.649816s 1 {s3_url}\n"
        f"1630339841.045183s 1 {api_url}\n"
        f"1630339840.983847s 0 {old_api_url}\n"
        "1620050418.205986s 0 https://dandiarchive.s3.amazonaws.com/girder/71/54/old\n"
        # A URL that was present and then removed, with the lines out of order
        "1700000002s 0 https://example.com/removed\n"
        "1700000001s 1 https://example.com/removed\n"
        # A URL that was removed and then restored
        "1700000001s 0 https://example.com/restored\n"
        "1700000002s 1 https://example.com/restored\n"
        "garbage line\n"
    )
    assert parse_url_log(log) == [
        s3_url,
        "https://example.com/restored",
        # DANDI API download URLs come last
        api_url,
    ]
    assert parse_url_log("") == []


def _git(repo: Path, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "DANDI tests",
        "GIT_AUTHOR_EMAIL": "tests@dandiarchive.org",
        "GIT_COMMITTER_NAME": "DANDI tests",
        "GIT_COMMITTER_EMAIL": "tests@dandiarchive.org",
    }
    run(["git", "-C", str(repo), *args], check=True, env=env)


@pytest.mark.ai_generated
def test_annex_repo_get_urls(tmp_path: Path) -> None:
    skipif.no_git()
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "Initial commit")
    key = AnnexKey.parse(REAL_KEY)

    found = AnnexRepo.find(repo / "sub-01" / "sub-01.nwb")
    assert found is not None
    assert found.root == repo
    assert AnnexRepo.find(repo) is found
    assert AnnexRepo.find(tmp_path / "norepo" / "file.nwb") is None

    # Without a git-annex branch there are no URLs
    annex_repo = AnnexRepo(repo)
    assert annex_repo.annex_ref is None
    assert annex_repo.get_urls(key) == []

    create_git_annex_branch(
        repo,
        {
            f"{key.hashdir_lower}/{REAL_KEY}.log.web": (
                "1s 1 https://api.dandiarchive.org/api/assets/x/download/\n"
                "2s 1 https://example.com/direct\n"
            )
        },
    )
    annex_repo = AnnexRepo(repo)
    assert annex_repo.annex_ref == "refs/heads/git-annex"
    urls = [
        "https://example.com/direct",
        "https://api.dandiarchive.org/api/assets/x/download/",
    ]
    assert annex_repo.get_urls(key) == urls
    assert annex_repo.get_urls(REAL_KEY) == urls
    assert annex_repo.get_urls("MD5E-s1--00000000000000000000000000000000.nwb") == []

    # A plain `git clone` only has the remote-tracking git-annex branch
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(repo), str(clone))
    cloned = AnnexRepo(clone)
    assert cloned.annex_ref == "refs/remotes/origin/git-annex"
    assert cloned.get_urls(key) == urls


@pytest.mark.ai_generated
def test_get_annex_readable(tmp_path: Path, simple2_nwb: Path) -> None:
    skipif.no_git()
    ds = tmp_path / "ds"
    key = annex_key_for_file(simple2_nwb)
    make_annexed_dandiset(
        ds,
        {
            "sub-01/sub-01.nwb": (key, [simple2_nwb.as_uri()]),
            "sub-02/sub-02.nwb": ("SHA256E-s42--" + "0" * 64 + ".nwb", []),
            "sub-03/sub-03.nwb": ("URL--http&c%%example.com%sub-03.nwb", ["x"]),
        },
    )
    r = get_annex_readable(ds / "sub-01" / "sub-01.nwb")
    assert r is not None
    assert r.key.key == key
    assert r.urls == [simple2_nwb.as_uri()]
    assert r.get_size() == simple2_nwb.stat().st_size
    assert r.get_filename() == "sub-01.nwb"
    assert r.get_fingerprint() == r.key.key
    assert str(r) == str(ds / "sub-01" / "sub-01.nwb")
    # No URLs registered
    r = get_annex_readable(ds / "sub-02" / "sub-02.nwb")
    assert r is not None
    assert r.urls == []
    # Key without a size
    assert get_annex_readable(ds / "sub-03" / "sub-03.nwb") is None
    # Not an annexed file
    assert get_annex_readable(ds / "dandiset.yaml") is None


@pytest.mark.ai_generated
def test_annex_readable_file_open_file_url(tmp_path: Path) -> None:
    pytest.importorskip("fsspec")
    content = tmp_path / "content.bin"
    content.write_bytes(b"0123456789" * 100)
    key = AnnexKey.parse(annex_key_for_file(content))
    assert key.size == 1000
    filepath = tmp_path / "ds" / "content.bin"
    missing = (tmp_path / "missing.bin").as_uri()
    r = AnnexReadableFile(filepath=filepath, key=key, urls=[missing, content.as_uri()])
    assert r.get_size() == 1000
    assert r.get_mtime() is None
    assert r.get_filename() == "content.bin"
    assert r.get_fingerprint() == key.key
    # The first URL cannot be opened, so the second one is used
    fp = r.open()
    try:
        assert fp.read(10) == b"0123456789"
        fp.seek(995)
        assert fp.read() == b"56789"
    finally:
        fp.close()
    with pytest.raises(FileNotFoundError):
        AnnexReadableFile(filepath=filepath, key=key, urls=[missing]).open()
    with pytest.raises(RuntimeError):
        AnnexReadableFile(filepath=filepath, key=key, urls=[]).open()
    with pytest.raises(ValueError):
        AnnexReadableFile(
            filepath=filepath, key=AnnexKey.parse("URL--x"), urls=[]
        ).get_size()


class RangeHTTPServer(ThreadingHTTPServer):
    """An HTTP server counting the range requests it served"""

    ranged_requests: int = 0


class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """
    A handler serving files with support for ``HEAD`` and single-range ``GET``
    requests, like S3 does
    """

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _send_headers(
        self, status: HTTPStatus, length: int, content_range: str | None = None
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if content_range is not None:
            self.send_header("Content-Range", content_range)
        self.end_headers()

    def do_HEAD(self) -> None:
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_headers(HTTPStatus.OK, os.path.getsize(path))

    def do_GET(self) -> None:
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        size = os.path.getsize(path)
        start, end = 0, size - 1
        if m := re.fullmatch(r"bytes=(\d+)-(\d*)", self.headers.get("Range", "")):
            start = int(m[1])
            end = min(int(m[2]) if m[2] else size - 1, size - 1)
            assert isinstance(self.server, RangeHTTPServer)
            self.server.ranged_requests += 1
            self._send_headers(
                HTTPStatus.PARTIAL_CONTENT,
                end - start + 1,
                f"bytes {start}-{end}/{size}",
            )
        else:
            self._send_headers(HTTPStatus.OK, size)
        with open(path, "rb") as fp:
            fp.seek(start)
            self.wfile.write(fp.read(end - start + 1))


@pytest.fixture()
def range_http_server(tmp_path: Path) -> Iterator[tuple[RangeHTTPServer, str]]:
    """Serve the files in ``tmp_path`` over HTTP with support for range requests"""
    server = RangeHTTPServer(
        ("127.0.0.1", 0), partial(RangeHTTPRequestHandler, directory=str(tmp_path))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.ai_generated
def test_annex_readable_file_cached_by_key(tmp_path: Path, simple2_nwb: Path) -> None:
    pytest.importorskip("fsspec")
    cache = PersistentCache(path=tmp_path / "cache")
    neurodata_types = cache.memoize_path(custom_fingerprint=readable_fingerprint)(
        get_neurodata_types.__wrapped__
    )
    content = tmp_path / "content.nwb"
    shutil.copy(simple2_nwb, content)
    key = AnnexKey.parse(annex_key_for_file(content))
    expected = get_neurodata_types.__wrapped__(content)
    streamed = AnnexReadableFile(
        filepath=tmp_path / "ds" / "sub-01.nwb", key=key, urls=[content.as_uri()]
    )
    assert neurodata_types(streamed) == expected
    # A file with the same key and name elsewhere (e.g., in another clone) is
    # served from the cache, without its content being read (it could not be)
    twin = AnnexReadableFile(
        filepath=tmp_path / "clone" / "sub-01.nwb", key=key, urls=[]
    )
    with pytest.raises(RuntimeError):
        twin.open()
    assert neurodata_types(twin) == expected


@pytest.mark.ai_generated
def test_annex_readable_file_open_http(
    range_http_server: tuple[RangeHTTPServer, str], simple2_nwb: Path, tmp_path: Path
) -> None:
    pytest.importorskip("fsspec")
    pytest.importorskip("aiohttp")
    server, base_url = range_http_server
    shutil.copy(simple2_nwb, tmp_path / "content.nwb")
    key = AnnexKey.parse(annex_key_for_file(tmp_path / "content.nwb"))
    r = AnnexReadableFile(
        filepath=tmp_path / "ds" / "sub-01" / "sub-01.nwb",
        key=key,
        # The first URL does not exist, so the second one is used
        urls=[f"{base_url}/missing.nwb", f"{base_url}/content.nwb"],
    )
    fp = r.open()
    try:
        # Random access over HTTP is enough for h5py to read the file
        with h5py.File(fp, "r") as h5:
            assert h5.attrs["nwb_version"]
            assert "session_description" in h5
    finally:
        fp.close()
    assert server.ranged_requests > 0
