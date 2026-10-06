from __future__ import annotations

from pathlib import Path
import shutil

from fscacher import PersistentCache
import h5py
import pytest

from ..datalad_fuse import AnnexedReadableFile, get_annexed_readable
from ...pynwb_utils import annex_fingerprint, get_neurodata_types
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
    pytest.importorskip("datalad_fuse.fsspec")
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
