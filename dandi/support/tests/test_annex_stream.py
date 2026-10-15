from __future__ import annotations

from datetime import datetime, timezone
import io
from pathlib import Path
import shutil
import subprocess
import sys

from fscacher import PersistentCache
import h5py
from hdmf.backends.hdf5 import H5DataIO
import numpy as np
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
import pytest

from ..annex_stream import (
    AnnexedReadableFile,
    annex_fingerprint,
    annex_initialized,
    can_stream,
    get_annexed_readable,
)
from ...pynwb_utils import get_neurodata_types
from ...tests.fixtures import make_git_annex_dandiset
from ...tests.range_http_server import RangeHTTPServer
from ...tests.skip import mark

pytestmark = mark.skipif_no_git_annex


@pytest.fixture(autouse=True)
def require_streaming() -> None:
    pytest.importorskip("datalad_fuse.adapter")


@pytest.fixture
def streamed_nwb(
    range_http_server: tuple[RangeHTTPServer, str], simple2_nwb: Path, tmp_path: Path
) -> tuple[Path, RangeHTTPServer]:
    """
    An annexed copy of ``simple2_nwb`` in a git-annex repository, whose content
    is not present but registered at a URL of the HTTP server
    """
    server, base_url = range_http_server
    shutil.copy(simple2_nwb, tmp_path / "served" / "content.nwb")
    make_git_annex_dandiset(
        tmp_path / "ds",
        {"sub-01/sub-01.nwb": (simple2_nwb, f"{base_url}/content.nwb")},
    )
    nwb = tmp_path / "ds" / "sub-01" / "sub-01.nwb"
    assert not nwb.exists()
    return nwb, server


@pytest.mark.ai_generated
def test_annexed_readable(
    streamed_nwb: tuple[Path, RangeHTTPServer], simple2_nwb: Path
) -> None:
    nwb, server = streamed_nwb
    r = get_annexed_readable(nwb)
    assert isinstance(r, AnnexedReadableFile)
    assert r.key.startswith(f"SHA256E-s{simple2_nwb.stat().st_size}--")
    assert r.url.endswith("/content.nwb")
    assert r.get_size() == simple2_nwb.stat().st_size
    assert r.get_filename() == "sub-01.nwb"
    assert r.get_mtime() is None
    assert str(r) == str(nwb)
    with r.open() as fp:
        # Random access over HTTP is enough for h5py to read the file
        with h5py.File(fp, "r") as h5:
            assert h5.attrs["nwb_version"]
    assert server.ranged_requests > 0


@pytest.mark.ai_generated
def test_annexed_readable_file_object(
    range_http_server: tuple[RangeHTTPServer, str], tmp_path: Path
) -> None:
    _, base_url = range_http_server
    content = bytes(range(256)) * 1000
    local = tmp_path / "local.h5"
    local.write_bytes(content)
    shutil.copy(local, tmp_path / "served" / "content.h5")
    make_git_annex_dandiset(
        tmp_path / "ds", {"data.h5": (local, f"{base_url}/content.h5")}
    )
    r = get_annexed_readable(tmp_path / "ds" / "data.h5")
    assert r is not None
    with r.open() as fp:
        assert fp.readable() and fp.seekable()
        assert fp.read(8) == content[:8]
        assert fp.seek(1000) == 1000
        assert fp.read(3) == content[1000:1003]
        assert fp.tell() == 1003
        assert fp.seek(-5, io.SEEK_END) == len(content) - 5
        # Reads stop at the end of the content
        assert fp.read(100) == content[-5:]
        assert fp.read(100) == b""
        fp.seek(0)
        assert fp.read() == content
    assert fp.closed


@pytest.mark.ai_generated
def test_annexed_readable_url_fallback(
    range_http_server: tuple[RangeHTTPServer, str], simple2_nwb: Path, tmp_path: Path
) -> None:
    """The content is read from the first of its URLs that can be read"""
    _, base_url = range_http_server
    shutil.copy(simple2_nwb, tmp_path / "served" / "content.nwb")
    make_git_annex_dandiset(
        tmp_path / "ds",
        {
            "sub-01.nwb": (
                simple2_nwb,
                [f"{base_url}/missing.nwb", f"{base_url}/content.nwb"],
            )
        },
    )
    r = get_annexed_readable(tmp_path / "ds" / "sub-01.nwb")
    assert r is not None
    # Whichever of the URLs git-annex lists first, the content is read
    assert r.url in (f"{base_url}/missing.nwb", f"{base_url}/content.nwb")
    with r.open() as fp, h5py.File(fp, "r") as h5:
        assert h5.attrs["nwb_version"]


@pytest.mark.ai_generated
def test_annexed_readable_no_url_readable(
    range_http_server: tuple[RangeHTTPServer, str], simple2_nwb: Path, tmp_path: Path
) -> None:
    _, base_url = range_http_server
    make_git_annex_dandiset(
        tmp_path / "ds", {"sub-01.nwb": (simple2_nwb, f"{base_url}/missing.nwb")}
    )
    r = get_annexed_readable(tmp_path / "ds" / "sub-01.nwb")
    assert r is not None
    with pytest.raises(OSError, match="Could not open"):
        r.open()


@pytest.mark.ai_generated
def test_annexed_readable_reads_little(
    range_http_server: tuple[RangeHTTPServer, str], tmp_path: Path
) -> None:
    """Reading an NWB file's structure downloads only a small part of it"""
    server, base_url = range_http_server
    nwbfile = NWBFile("streamed", "id", datetime(2026, 1, 1, tzinfo=timezone.utc))
    for i in range(4):
        nwbfile.add_acquisition(
            TimeSeries(
                name=f"ts{i}",
                data=H5DataIO(np.arange(1_000_000, dtype="f4"), chunks=(10_000,)),
                unit="V",
                rate=1.0,
            )
        )
    local = tmp_path / "local.nwb"
    with NWBHDF5IO(local, "w") as io_:
        io_.write(nwbfile)
    size = local.stat().st_size
    assert size > 15_000_000
    shutil.copy(local, tmp_path / "served" / "content.nwb")
    make_git_annex_dandiset(
        tmp_path / "ds", {"sub-01/sub-01.nwb": (local, f"{base_url}/content.nwb")}
    )
    r = get_annexed_readable(tmp_path / "ds" / "sub-01" / "sub-01.nwb")
    assert r is not None
    assert get_neurodata_types.__wrapped__(r) == get_neurodata_types.__wrapped__(local)
    assert 0 < server.bytes_served < size / 10


def annex_uuid(repo: Path) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "annex.uuid"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


@pytest.mark.ai_generated
def test_annexed_readable_none(
    streamed_nwb: tuple[Path, RangeHTTPServer], simple2_nwb: Path, tmp_path: Path
) -> None:
    nwb, _ = streamed_nwb
    # The content is present
    (nwb.parent / "regular.nwb").write_bytes(b"content")
    assert get_annexed_readable(nwb.parent / "regular.nwb") is None
    # Not in a Git repository
    assert get_annexed_readable(simple2_nwb) is None
    # A broken symbolic link in a clone in which git-annex is not initialized,
    # which is not initialized by trying
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "-q", str(nwb.parent.parent), str(clone)], check=True
    )
    assert annex_uuid(clone) == ""
    assert get_annexed_readable(clone / "sub-01" / "sub-01.nwb") is None
    assert annex_uuid(clone) == ""


@pytest.mark.ai_generated
def test_annexed_readable_none_not_streamable(
    streamed_nwb: tuple[Path, RangeHTTPServer], monkeypatch: pytest.MonkeyPatch
) -> None:
    nwb, _ = streamed_nwb
    ds = nwb.parent.parent
    objects = Path(".git", "annex", "objects", "Xx", "Yy")
    # A broken symbolic link which is not to annexed content
    (ds / "other.nwb").symlink_to("missing.nwb")
    assert get_annexed_readable(ds / "other.nwb") is None
    # The key does not record the size of the content
    key = "URL--https&c%%example.org%x.nwb"
    (ds / "nosize.nwb").symlink_to(objects / key / key)
    assert get_annexed_readable(ds / "nosize.nwb") is None
    # git-annex knows no URL for the key
    key = "SHA256E-s5--" + "0" * 64 + ".nwb"
    (ds / "nourl.nwb").symlink_to(objects / key / key)
    assert get_annexed_readable(ds / "nourl.nwb") is None
    # A repository without any commit, which datalad-fuse cannot handle
    empty = ds.parent / "empty"
    subprocess.run(["git", "init", "-q", str(empty)], check=True)
    subprocess.run(["git", "-C", str(empty), "annex", "init", "-q"], check=True)
    (empty / "sub-01.nwb").symlink_to(objects / key / key)
    assert get_annexed_readable(empty / "sub-01.nwb") is None
    # datalad-fuse, or remfile, is not installed
    for module in ["datalad_fuse.adapter", "remfile"]:
        with monkeypatch.context() as m:
            m.setitem(sys.modules, module, None)
            assert not can_stream()
            assert get_annexed_readable(nwb) is None


@pytest.mark.ai_generated
def test_annex_initialized_no_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "nonexistent"))
    assert not annex_initialized(tmp_path)


@pytest.mark.ai_generated
def test_annexed_readable_cached_by_key(
    streamed_nwb: tuple[Path, RangeHTTPServer], simple2_nwb: Path, tmp_path: Path
) -> None:
    nwb, server = streamed_nwb
    cache = PersistentCache(path=tmp_path / "cache")
    neurodata_types = cache.memoize_path(custom_fingerprint=annex_fingerprint)(
        get_neurodata_types.__wrapped__
    )
    r = get_annexed_readable(nwb)
    assert r is not None
    expected = get_neurodata_types.__wrapped__(simple2_nwb)
    assert neurodata_types(r) == expected
    requests = server.ranged_requests
    assert requests > 0
    # Served from the cache, without the content being read again: by the
    # readable, and by the path of the (broken) link itself
    assert neurodata_types(get_annexed_readable(nwb)) == expected
    assert neurodata_types(nwb) == expected
    assert server.ranged_requests == requests
