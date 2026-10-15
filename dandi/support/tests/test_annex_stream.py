from __future__ import annotations

from datetime import datetime, timezone
import io
from pathlib import Path
import shutil
import subprocess

from fscacher import PersistentCache
import h5py
from hdmf.backends.hdf5 import H5DataIO
import numpy as np
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
import pytest

from ..annex_stream import (
    AnnexedReadableFile,
    annex_fingerprint,
    annex_key_size,
    get_annexed_readable,
)
from ...pynwb_utils import get_neurodata_types
from ...tests.fixtures import make_git_annex_dandiset
from ...tests.range_http_server import RangeHTTPServer
from ...tests.skip import mark

pytestmark = mark.skipif_no_git_annex


@pytest.fixture
def streamed_nwb(
    range_http_server: tuple[RangeHTTPServer, str], simple2_nwb: Path, tmp_path: Path
) -> tuple[Path, RangeHTTPServer]:
    """
    An annexed copy of ``simple2_nwb`` in a git-annex repository, whose content
    is not present but registered at a URL of the HTTP server
    """
    pytest.importorskip("remfile")
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
@pytest.mark.parametrize(
    "key,size",
    [
        ("SHA256E-s1234--abc.nwb", 1234),
        ("MD5E-s0--d41d8cd98f00b204e9800998ecf8427e", 0),
        ("SHA256E-s99-S10-C2--abc.nwb", 99),
        ("URL--https&c%%example.org%x.nwb", None),
    ],
)
def test_annex_key_size(key: str, size: int | None) -> None:
    assert annex_key_size(key) == size


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
    with r.open() as fp:
        # Random access over HTTP is enough for h5py to read the file
        with h5py.File(fp, "r") as h5:
            assert h5.attrs["nwb_version"]
    assert server.ranged_requests > 0


@pytest.mark.ai_generated
def test_annexed_readable_file_object(
    range_http_server: tuple[RangeHTTPServer, str], tmp_path: Path
) -> None:
    pytest.importorskip("remfile")
    _, base_url = range_http_server
    content = bytes(range(256)) * 1000
    local = tmp_path / "local.bin"
    local.write_bytes(content)
    shutil.copy(local, tmp_path / "served" / "content.bin")
    make_git_annex_dandiset(
        tmp_path / "ds", {"data.bin": (local, f"{base_url}/content.bin")}
    )
    r = get_annexed_readable(tmp_path / "ds" / "data.bin")
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
    pytest.importorskip("remfile")
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
    found = get_annexed_readable(tmp_path / "ds" / "sub-01.nwb")
    assert found is not None
    # (in the order in which git-annex lists them, which is not the order in
    # which they were registered)
    assert sorted(found.urls) == [f"{base_url}/content.nwb", f"{base_url}/missing.nwb"]
    r = AnnexedReadableFile(
        filepath=found.filepath,
        key=found.key,
        size=found.size,
        urls=[f"{base_url}/missing.nwb", f"{base_url}/content.nwb"],
    )
    assert r.url == f"{base_url}/missing.nwb"
    with r.open() as fp, h5py.File(fp, "r") as h5:
        assert h5.attrs["nwb_version"]
    assert r.url == f"{base_url}/content.nwb"


@pytest.mark.ai_generated
def test_annexed_readable_no_url_readable(
    range_http_server: tuple[RangeHTTPServer, str], simple2_nwb: Path, tmp_path: Path
) -> None:
    pytest.importorskip("remfile")
    _, base_url = range_http_server
    make_git_annex_dandiset(
        tmp_path / "ds", {"sub-01.nwb": (simple2_nwb, f"{base_url}/missing.nwb")}
    )
    r = get_annexed_readable(tmp_path / "ds" / "sub-01.nwb")
    assert r is not None
    with pytest.raises(OSError, match="None of the URLs"):
        r.open()


@pytest.mark.ai_generated
def test_annexed_readable_reads_little(
    range_http_server: tuple[RangeHTTPServer, str], tmp_path: Path
) -> None:
    """Reading an NWB file's structure downloads only a small part of it"""
    pytest.importorskip("remfile")
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
