from __future__ import annotations

import gc
import importlib
import io
from pathlib import Path
import re
import threading
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


def serve(data: bytes) -> None:
    """Serve ``data`` at `URL`, with support for HTTP range requests"""

    def callback(request: requests.PreparedRequest) -> tuple[int, dict, bytes]:
        m = re.fullmatch(r"bytes=(\d+)-(\d+)", request.headers["Range"])
        assert m
        start, end = int(m[1]), int(m[2])
        assert 0 <= start <= end < len(data)
        return (206, {}, data[start : end + 1])

    responses.add_callback(responses.GET, URL, callback=callback)


def no_fsspec(*_args: Any, **_kwargs: Any) -> None:
    raise AssertionError("fsspec must not be used for HDF5-based files")


@pytest.fixture
def h5_data(tmp_path: Path) -> bytes:
    p = tmp_path / "data.h5"
    with h5py.File(p, "w") as f:
        f.attrs["nwb_version"] = "2.8.0"
        f["x"] = list(range(100))
    return p.read_bytes()


@pytest.mark.ai_generated
@pytest.mark.parametrize("name", ["foo.nwb", "foo.NWB", "foo.h5", "foo.hdf5"])
@responses.activate
def test_remote_readable_asset_hdf5_uses_remfile(
    h5_data: bytes, mocker: MockerFixture, name: str
) -> None:
    serve(h5_data)
    fsspec = pytest.importorskip("fsspec")
    mocker.patch.object(fsspec, "open", no_fsspec)
    r = RemoteReadableAsset(url=URL, size=len(h5_data), mtime=None, name=name)
    fp: Any = r.open()
    assert isinstance(fp, remfile.File)
    with fp:
        with h5py.File(fp, "r") as f:
            assert f.attrs["nwb_version"] == "2.8.0"
            assert list(f["x"][:]) == list(range(100))
    # Only range requests (no request for the size), all with a timeout
    assert responses.calls
    for c in responses.calls:
        assert "Range" in c.request.headers
        assert c.request.req_kwargs["timeout"] is not None  # type: ignore[attr-defined]
    assert get_nwb_version(r) == "2.8.0"


@pytest.mark.ai_generated
@responses.activate
def test_remote_readable_asset_read() -> None:
    data = bytes(range(256)) * 10
    serve(data)
    r = RemoteReadableAsset(url=URL, size=len(data), mtime=None, name="foo.nwb")
    with r.open() as fp:
        assert fp.read(10) == data[:10]
        fp.seek(100)
        assert fp.tell() == 100
        assert fp.read(len(data) - 100) == data[100:]


@pytest.mark.ai_generated
@responses.activate
def test_remote_readable_asset_non_hdf5_uses_fsspec(mocker: MockerFixture) -> None:
    fsspec = pytest.importorskip("fsspec")
    sentinel = io.BytesIO(b"text")
    m = mocker.patch.object(fsspec, "open")
    m.return_value.open.return_value = sentinel
    r = RemoteReadableAsset(url=URL, size=4, mtime=None, name="foo.txt")
    fp = r.open()
    assert fp is sentinel
    m.assert_called_once()
    assert m.call_args.args == (URL,)
    assert len(responses.calls) == 0


@pytest.mark.ai_generated
@pytest.mark.timeout(60)
@responses.activate
def test_remote_readable_asset_gc_while_reading_hdf5(
    h5_data: bytes, mocker: MockerFixture, tmp_path: Path
) -> None:
    # <https://github.com/dandi/dandi-cli/issues/1450>: h5py holds its global
    # lock while it reads from a file object; the finalizers of h5py objects
    # freed by a garbage collection wait for that lock.  If the reads were made
    # in another thread (as fsspec does), a garbage collection there would
    # deadlock.  remfile reads in the calling thread, in which a garbage
    # collection can take the (reentrant) lock: force a garbage collection,
    # freeing h5py objects, in each of its fetches.
    serve(h5_data)
    remfile_module = importlib.import_module("remfile.RemFile")
    get_bytes = remfile_module._get_bytes
    fetches: list[tuple[bool, bool, int]] = []

    def get_bytes_with_gc(*args: Any, **kwargs: Any) -> Any:
        before = len(h5py_objects())
        gc.collect()
        fetches.append(
            (
                threading.current_thread() is threading.main_thread(),
                bool(phil._is_owned()),
                before - len(h5py_objects()),
            )
        )
        return get_bytes(*args, **kwargs)

    mocker.patch.object(remfile_module, "_get_bytes", get_bytes_with_gc)
    # Garbage holding h5py objects: a reference cycle with a dataset of a
    # closed file
    p = tmp_path / "garbage.h5"
    with h5py.File(p, "w") as f:
        f["y"] = [1, 2, 3]
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        f = h5py.File(p, "r")
        cycle: list[Any] = [f["y"]]
        cycle.append(cycle)
        f.close()
        del f, cycle
        r = RemoteReadableAsset(url=URL, size=len(h5_data), mtime=None, name="a.nwb")
        assert get_nwb_version(r) == "2.8.0"
    finally:
        if gc_was_enabled:
            gc.enable()
    assert fetches
    # All fetches were made in the calling thread, while h5py held its lock
    assert all(in_main and locked for in_main, locked, _ in fetches)
    # ... and the first collection freed h5py objects
    assert fetches[0][2] > 0


def h5py_objects() -> list[Any]:
    return [
        o
        for o in gc.get_objects()
        if str(getattr(type(o), "__module__", "")).startswith("h5py")
    ]
