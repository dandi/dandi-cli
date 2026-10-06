from __future__ import annotations

from pathlib import Path
import shutil

import h5py
import pytest

from .test_annex import RangeHTTPServer, range_http_server  # noqa: F401
from ..annex import AnnexKey
from ..datalad_fuse import DataladFuseReadableFile, get_datalad_fuse_readable
from ...pynwb_utils import get_neurodata_types
from ...tests.fixtures import (
    annex_key_for_file,
    make_annexed_dandiset,
    make_git_annex_dandiset,
)
from ...tests.skip import mark

pytestmark = mark.skipif_no_git_annex


@pytest.fixture(autouse=True)
def _no_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    # The test HTTP server is local
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")


@pytest.mark.ai_generated
def test_datalad_fuse_readable(
    range_http_server: tuple[RangeHTTPServer, str],  # noqa: F811
    simple2_nwb: Path,
    tmp_path: Path,
) -> None:
    pytest.importorskip("datalad_fuse.adapter")
    server, base_url = range_http_server
    shutil.copy(simple2_nwb, tmp_path / "content.nwb")
    ds = tmp_path / "ds"
    make_git_annex_dandiset(
        ds, {"sub-01/sub-01.nwb": (simple2_nwb, f"{base_url}/content.nwb")}
    )
    nwb = ds / "sub-01" / "sub-01.nwb"
    assert not nwb.exists()

    r = get_datalad_fuse_readable(nwb)
    assert isinstance(r, DataladFuseReadableFile)
    assert r.key == AnnexKey.parse(annex_key_for_file(simple2_nwb))
    assert r.url == f"{base_url}/content.nwb"
    assert r.get_size() == simple2_nwb.stat().st_size
    assert r.get_filename() == "sub-01.nwb"
    assert r.get_fingerprint() == r.key.key
    fp = r.open()
    try:
        # Random access over HTTP is enough for h5py to read the file
        with h5py.File(fp, "r") as h5:
            assert h5.attrs["nwb_version"]
    finally:
        fp.close()
    assert server.ranged_requests > 0
    assert get_neurodata_types.__wrapped__(r) == get_neurodata_types.__wrapped__(
        simple2_nwb
    )


@pytest.mark.ai_generated
def test_datalad_fuse_readable_none(tmp_path: Path, simple2_nwb: Path) -> None:
    pytest.importorskip("datalad_fuse.adapter")
    ds = tmp_path / "ds"
    make_git_annex_dandiset(
        ds, {"sub-01/sub-01.nwb": (simple2_nwb, "http://127.0.0.1:1/content.nwb")}
    )
    # The content is present: no need to stream it
    (ds / "regular.nwb").write_bytes(b"content")
    assert get_datalad_fuse_readable(ds / "regular.nwb") is None
    # Not in a Git repository
    assert get_datalad_fuse_readable(simple2_nwb) is None
    # git-annex not initialized: left to `dandi.support.annex`
    fake = tmp_path / "fake"
    make_annexed_dandiset(
        fake,
        {"sub-01/sub-01.nwb": (annex_key_for_file(simple2_nwb), ["http://x/y.nwb"])},
    )
    assert get_datalad_fuse_readable(fake / "sub-01" / "sub-01.nwb") is None
