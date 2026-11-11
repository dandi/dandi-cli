from __future__ import annotations

import gc
from pathlib import Path
import re
from typing import Any

import h5py
from h5py._objects import phil
import pytest
from pytest_mock import MockerFixture
import requests
import responses

from ..misctypes import RemoteReadableAsset
from ..pynwb_utils import get_nwb_version

remfile = pytest.importorskip("remfile")

URL = "https://example.com/blobs/abc/def/abcdef"


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "name,uses_remfile",
    [
        ("foo.nwb", True),
        ("foo.NWB", True),
        ("foo.h5", True),
        ("foo.hdf5", True),
        ("foo.txt", False),
    ],
)
def test_remote_readable_asset_open(
    mocker: MockerFixture, name: str, uses_remfile: bool
) -> None:
    """HDF5-based files are opened with remfile, other files with fsspec.

    Unlike ``test_asset_as_readable_open`` (``test_dandiapi.py``), this needs no
    archive instance, and covers every HDF5 extension, in any case.
    """
    remfile_file = mocker.patch.object(remfile, "File")
    open_fsspec = mocker.patch.object(RemoteReadableAsset, "_open_fsspec")
    r = RemoteReadableAsset(url=URL, size=10, mtime=None, name=name)
    fp = r.open()
    if uses_remfile:
        remfile_file.assert_called_once_with(URL, _size=10)
        assert fp is remfile_file.return_value
        open_fsspec.assert_not_called()
    else:
        open_fsspec.assert_called_once_with()
        assert fp is open_fsspec.return_value
        remfile_file.assert_not_called()


@pytest.mark.ai_generated
@pytest.mark.timeout(60)
@responses.activate
def test_remote_readable_asset_gc_while_reading_hdf5(tmp_path: Path) -> None:
    """A garbage collection freeing h5py objects during a read doesn't deadlock.

    Regression test for https://github.com/dandi/dandi-cli/issues/1450.  Unlike
    the archive-backed tests (e.g. ``test_nwb2asset_remote_asset``), which could
    only hit the deadlock by chance, this checks that each HTTP request is made
    in the thread holding h5py's lock, and forces a collection there, with an
    h5py object in the garbage.
    """
    p = tmp_path / "foo.nwb"
    with h5py.File(p, "w") as f:
        f.attrs["nwb_version"] = "2.8.0"
        f["x"] = [1, 2, 3]
    data = p.read_bytes()
    requests_made: list[tuple[bool, int]] = []

    def serve_range(request: requests.PreparedRequest) -> tuple[int, dict, bytes]:
        # Runs in the thread making the request.  Collect only if it holds
        # h5py's lock, so that a regression fails the test instead of hanging.
        locked = bool(phil._is_owned())
        requests_made.append((locked, gc.collect() if locked else 0))
        m = re.fullmatch(r"bytes=(\d+)-(\d+)", request.headers["Range"])
        assert m
        return (206, {}, data[int(m[1]) : int(m[2]) + 1])

    responses.add_callback(responses.GET, URL, callback=serve_range)
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        gc.collect()
        # Garbage holding an h5py object: a reference cycle with a dataset
        f = h5py.File(p, "r")
        cycle: list[Any] = [f["x"]]
        cycle.append(cycle)
        f.close()
        del f, cycle
        r = RemoteReadableAsset(url=URL, size=len(data), mtime=None, name=p.name)
        assert get_nwb_version(r) == "2.8.0"
    finally:
        if gc_was_enabled:
            gc.enable()
    assert requests_made
    assert all(locked for locked, _ in requests_made)
    assert requests_made[0][1] > 0
