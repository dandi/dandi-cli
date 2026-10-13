from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil

from fscacher import PersistentCache
import h5py
from hdmf.backends.hdf5 import H5DataIO
import numpy as np
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
import pytest

from ..datalad_fuse import AnnexedReadableFile, annex_fingerprint, get_annexed_readable
from ...pynwb_utils import get_neurodata_types
from ...tests.fixtures import RangeHTTPServer, make_git_annex_dandiset
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
    pytest.importorskip("datalad_fuse.caching")
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
    fp = r.open()
    try:
        # Random access over HTTP is enough for h5py to read the file
        with h5py.File(fp, "r") as h5:
            assert h5.attrs["nwb_version"]
    finally:
        fp.close()
    assert server.ranged_requests > 0


@pytest.mark.ai_generated
def test_annexed_readable_reads_little(
    range_http_server: tuple[RangeHTTPServer, str], tmp_path: Path
) -> None:
    """Reading an NWB file's structure downloads only a small part of it"""
    pytest.importorskip("datalad_fuse.caching")
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
    with NWBHDF5IO(local, "w") as io:
        io.write(nwbfile)
    size = local.stat().st_size
    assert size > 15_000_000
    shutil.copy(local, tmp_path / "served" / "content.nwb")
    make_git_annex_dandiset(
        tmp_path / "ds", {"sub-01/sub-01.nwb": (local, f"{base_url}/content.nwb")}
    )
    r = get_annexed_readable(tmp_path / "ds" / "sub-01" / "sub-01.nwb")
    assert r is not None
    assert get_neurodata_types.__wrapped__(r) == get_neurodata_types.__wrapped__(local)
    assert server.bytes_served > 0
    with r.open() as fp:
        remfile_used = type(fp).__name__ == "RemfileWrapper"
    if not remfile_used:
        # With fsspec's default 5 MiB read-ahead, most of the file was
        # downloaded.  (remfile, used for HDF5 files by
        # datalad/datalad-fuse#131 when installed, reads ahead by itself, in
        # chunks growing up to 100 MiB that datalad-fuse does not configure.)
        assert server.bytes_served < size / 10


@pytest.mark.ai_generated
def test_annexed_readable_large_read(
    range_http_server: tuple[RangeHTTPServer, str], tmp_path: Path
) -> None:
    """A large read of streamed content is fetched with one request"""
    pytest.importorskip("datalad_fuse.caching")
    server, base_url = range_http_server
    local = tmp_path / "local.bin"
    content = np.random.default_rng(0).bytes(10_000_000)
    local.write_bytes(content)
    shutil.copy(local, tmp_path / "served" / "content.bin")
    make_git_annex_dandiset(
        tmp_path / "ds", {"sub-01/data.bin": (local, f"{base_url}/content.bin")}
    )
    r = get_annexed_readable(tmp_path / "ds" / "sub-01" / "data.bin")
    assert r is not None
    with r.open() as fp:
        fp.seek(123)
        assert fp.read(9_000_000) == content[123:9_000_123]
        assert server.ranged_requests == 1
        fp.seek(5_000_000)
        assert fp.read(100) == content[5_000_000:5_000_100]
        assert server.ranged_requests == 1


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
    # A broken symbolic link in a repository without git-annex initialized
    plain = tmp_path / "plain"
    plain.mkdir()
    shutil.copytree(nwb.parent, plain / "sub-01", symlinks=True)
    shutil.copytree(nwb.parent.parent / ".git", plain / ".git")
    (plain / ".git" / "config").write_text("[core]\n\tbare = false\n")
    assert get_annexed_readable(plain / "sub-01" / "sub-01.nwb") is None


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


@pytest.mark.ai_generated
def test_annexed_readable_remfile(
    streamed_nwb: tuple[Path, RangeHTTPServer], simple2_nwb: Path
) -> None:
    """With datalad/datalad-fuse#131 and remfile, NWB files are read with remfile"""
    pytest.importorskip("datalad_fuse.caching")
    pytest.importorskip("remfile")
    from datalad_fuse.remfile import RemfileWrapper

    nwb, server = streamed_nwb
    r = get_annexed_readable(nwb)
    assert r is not None
    fp = r.open()
    try:
        assert isinstance(fp, RemfileWrapper)
        with h5py.File(fp, "r") as h5:
            assert h5.attrs["nwb_version"]
    finally:
        fp.close()
    assert server.ranged_requests > 0
    assert get_neurodata_types.__wrapped__(r) == get_neurodata_types.__wrapped__(
        simple2_nwb
    )
