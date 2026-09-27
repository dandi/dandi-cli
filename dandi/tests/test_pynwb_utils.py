from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import time
from types import SimpleNamespace
from typing import Any, NoReturn

from fscacher import PersistentCache
import h5py
import numpy as np
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
import pytest
from pytest_mock import MockerFixture

from .fixtures import FingerprintedReadable
from ..misctypes import Readable
from ..pynwb_utils import (
    _rename_pose_estimation_original_videos,
    _sanitize_nwb_version,
    memoize_source,
    nwb_has_external_links,
    open_readable,
    rename_nwb_external_files,
)


def test_pynwb_io(simple1_nwb: Path) -> None:
    # To verify that our dependencies spec is sufficient to avoid
    # stepping into known pynwb/hdmf issues
    with NWBHDF5IO(simple1_nwb, "r", load_namespaces=True) as reader:
        nwbfile = reader.read()
    assert repr(nwbfile)
    assert str(nwbfile)


def test_sanitize_nwb_version() -> None:
    def _nocall(*args: Any) -> NoReturn:
        raise AssertionError(f"Should have not been called. Was called with {args}")

    def assert_regex(regex: str) -> Callable[[str], None]:
        def search(v: str) -> None:
            assert re.search(regex, v)

        return search

    assert _sanitize_nwb_version("1.0.0", log=_nocall) == "1.0.0"
    assert _sanitize_nwb_version("NWB-1.0.0", log=_nocall) == "1.0.0"
    assert _sanitize_nwb_version("NWB-2.0.0", log=_nocall) == "2.0.0"
    assert (
        _sanitize_nwb_version(
            "NWB-2.1.0",
            log=assert_regex("^nwb_version 'NWB-2.1.0' starts with NWB- prefix,"),
        )
        == "2.1.0"
    )
    assert (
        _sanitize_nwb_version(
            "NWB-2.1.0",
            filename="/bu",
            log=assert_regex(
                "^File /bu: nwb_version 'NWB-2.1.0' starts with NWB- prefix,"
            ),
        )
        == "2.1.0"
    )


@pytest.mark.ai_generated
def test_rename_pose_estimation_original_videos() -> None:
    pose = SimpleNamespace(
        neurodata_type="PoseEstimation",
        original_videos=[
            b"camera\\raw.mp4",
            "https://example.com/remote.mp4",
            "other.mp4",
        ],
    )
    unrelated = SimpleNamespace(
        neurodata_type="OtherContainer", original_videos=["camera/raw.mp4"]
    )
    nwb = SimpleNamespace(objects={"pose": pose, "unrelated": unrelated})

    _rename_pose_estimation_original_videos(
        nwb,
        {"camera/raw.mp4": "sub-01/session-01/source.mp4"},
    )

    assert pose.original_videos == [
        "sub-01/session-01/source.mp4",
        "https://example.com/remote.mp4",
        "other.mp4",
    ]
    assert unrelated.original_videos == ["camera/raw.mp4"]


@pytest.mark.ai_generated
def test_rename_pose_estimation_original_videos_ignores_missing_values() -> None:
    missing = SimpleNamespace(neurodata_type="PoseEstimation")
    scalar = SimpleNamespace(
        neurodata_type="PoseEstimation", original_videos="camera/raw.mp4"
    )
    scalar_bytes = SimpleNamespace(
        neurodata_type="PoseEstimation", original_videos=b"camera/raw.mp4"
    )
    nwb = SimpleNamespace(objects={"missing": missing, "scalar": scalar})

    _rename_pose_estimation_original_videos(nwb, {})
    nwb.objects["scalar_bytes"] = scalar_bytes
    _rename_pose_estimation_original_videos(
        nwb, {"camera/raw.mp4": "sub-01/source.mp4"}
    )

    assert scalar.original_videos == "camera/raw.mp4"
    assert scalar_bytes.original_videos == b"camera/raw.mp4"


@pytest.mark.ai_generated
def test_rename_pose_estimation_original_videos_persists_hdf5(
    tmp_path: Path,
) -> None:
    filepath = tmp_path / "pose-videos.h5"
    string_type = h5py.string_dtype(encoding="utf-8")
    with h5py.File(filepath, "w") as f:
        f.create_dataset(
            "original_videos",
            data=np.asarray(["camera/raw.mp4", "camera/other.mp4"], dtype=string_type),
        )

    with h5py.File(filepath, "r+") as f:
        pose = SimpleNamespace(
            neurodata_type="PoseEstimation",
            original_videos=f["original_videos"],
        )
        nwb = SimpleNamespace(objects={"pose": pose})
        _rename_pose_estimation_original_videos(
            nwb,
            {"camera/raw.mp4": "sub-01/session-01/a-much-longer-source-name.mp4"},
        )

    with h5py.File(filepath) as f:
        assert f["original_videos"].asstr()[...].tolist() == [
            "sub-01/session-01/a-much-longer-source-name.mp4",
            "camera/other.mp4",
        ]


@pytest.mark.ai_generated
def test_rename_nwb_external_files_updates_pose_references(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    image_series = SimpleNamespace(
        object_id="image-series-id", external_file=["camera/raw.mp4"]
    )
    pose = SimpleNamespace(
        neurodata_type="PoseEstimation", original_videos=["camera/raw.mp4"]
    )
    nwb = SimpleNamespace(
        children=[image_series], objects={"image-series": image_series, "pose": pose}
    )
    io = mocker.MagicMock()
    io.__enter__.return_value.read.return_value = nwb
    nwb_io = mocker.patch("dandi.pynwb_utils.NWBHDF5IO", return_value=io)
    metadata = [
        {
            "path": "original.nwb",
            "dandi_path": "sub-01/sub-01.nwb",
            "external_file_objects": [
                {
                    "id": "image-series-id",
                    "external_files": ["camera/raw.mp4"],
                    "external_files_renamed": ["sub-01/camera-renamed.mp4"],
                }
            ],
        }
    ]

    rename_nwb_external_files(metadata, str(tmp_path))

    assert image_series.external_file == ["sub-01/camera-renamed.mp4"]
    assert pose.original_videos == ["sub-01/camera-renamed.mp4"]
    nwb_io.assert_called_once()
    assert Path(nwb_io.call_args.args[0]) == tmp_path / "sub-01" / "sub-01.nwb"
    assert nwb_io.call_args.kwargs == {"mode": "r+", "load_namespaces": True}


def test_nwb_has_external_links(tmp_path):
    # Create the base data
    start_time = datetime(2017, 4, 3, 11, tzinfo=timezone.utc)
    create_date = datetime(2017, 4, 15, 12, tzinfo=timezone.utc)
    data = np.arange(1000).reshape((100, 10))
    timestamps = np.arange(100)
    filename1 = tmp_path / "external1_example.nwb"
    filename4 = tmp_path / "external_linkdataset_example.nwb"

    # Create the first file
    nwbfile1 = NWBFile(
        session_description="demonstrate external files",
        identifier="NWBE1",
        session_start_time=start_time,
        file_create_date=create_date,
    )
    test_ts1 = TimeSeries(
        name="test_timeseries1", data=data, unit="SIunit", timestamps=timestamps
    )
    nwbfile1.add_acquisition(test_ts1)
    # Write the first file
    with NWBHDF5IO(filename1, "w") as io:
        io.write(nwbfile1)

    nwbfile4 = NWBFile(
        session_description="demonstrate external files",
        identifier="NWBE4",
        session_start_time=start_time,
        file_create_date=create_date,
    )

    # Get the first timeseries
    with NWBHDF5IO(filename1, "r") as io1:
        nwbfile1 = io1.read()
        timeseries_1_data = nwbfile1.get_acquisition("test_timeseries1").data

        # Create a new timeseries that links to our data
        test_ts4 = TimeSeries(
            name="test_timeseries4",
            data=timeseries_1_data,  # <-------
            unit="SIunit",
            timestamps=timestamps,
        )
        nwbfile4.add_acquisition(test_ts4)

        with NWBHDF5IO(filename4, "w") as io4:
            io4.write(nwbfile4, link_data=True)

    assert not nwb_has_external_links(filename1)
    assert nwb_has_external_links(filename4)


@pytest.mark.ai_generated
def test_memoize_source(tmp_path: Path, simple1_nwb: Path) -> None:
    cache = PersistentCache(path=tmp_path / "cache", tokens=["t1"])
    calls: list[Any] = []

    def size(source: str | Path | Readable, flag: bool = False) -> str:
        calls.append(source)
        with open_readable(source) as fp:
            return f"{len(fp.read())}:{flag}"

    cached = memoize_source(cache, ["t1"])(size)
    nbytes = simple1_nwb.stat().st_size
    expected = f"{nbytes}:False"

    # A path is cached the memoize_path way (which skips a file modified "just
    # now", as the session-wide fixture may well have been: age a copy)
    nwb = tmp_path / simple1_nwb.name
    shutil.copyfile(simple1_nwb, nwb)
    hour_ago = time.time() - 3600
    os.utime(nwb, (hour_ago, hour_ago))
    assert cached(nwb) == expected
    assert cached(nwb) == expected
    assert len(calls) == 1

    # A Readable without a fingerprint is never cached
    assert cached(FingerprintedReadable(simple1_nwb, None)) == expected
    assert cached(FingerprintedReadable(simple1_nwb, None)) == expected
    assert len(calls) == 3

    # A Readable with a fingerprint is cached by it: its twin is served from
    # the cache without being read (it could not be)
    first = FingerprintedReadable(simple1_nwb, "A")
    assert cached(first) == expected
    assert first.opened == 1
    twin = FingerprintedReadable(tmp_path / "gone" / simple1_nwb.name, "A")
    assert cached(twin) == expected
    assert twin.opened == 0
    assert len(calls) == 4

    # The file name, the other arguments, and the tokens are part of the key
    with pytest.raises(FileNotFoundError):
        cached(FingerprintedReadable(tmp_path / "gone" / "other.nwb", "A"))
    assert cached(FingerprintedReadable(simple1_nwb, "B")) == expected
    assert (
        cached(FingerprintedReadable(simple1_nwb, "A"), flag=True) == f"{nbytes}:True"
    )
    assert len(calls) == 7
    # ... however those other arguments are passed
    assert cached(FingerprintedReadable(simple1_nwb, "A"), True) == f"{nbytes}:True"
    assert len(calls) == 7
    other_tokens = memoize_source(cache, ["t2"])(size)
    assert other_tokens(FingerprintedReadable(simple1_nwb, "A")) == expected
    assert len(calls) == 8

    # Different functions of the same cache do not share entries
    def name(source: str | Path | Readable, flag: bool = False) -> str:
        return source.get_filename() if isinstance(source, Readable) else str(source)

    cached_name = memoize_source(cache, ["t1"])(name)
    assert cached_name(FingerprintedReadable(simple1_nwb, "A")) == simple1_nwb.name
    assert cached(FingerprintedReadable(simple1_nwb, "A")) == expected
    assert len(calls) == 8

    # The other arguments are keyed by name, so `f` must not take *args
    def varargs(source: str | Path | Readable, *args: Any) -> None:
        pass

    with pytest.raises(TypeError, match="must not take"):
        memoize_source(cache, ["t1"])(varargs)


@pytest.mark.ai_generated
def test_memoize_source_ignored_cache(
    tmp_path: Path, simple1_nwb: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DANDI_TEST_CACHE", "ignore")
    cache = PersistentCache(
        path=tmp_path / "cache", tokens=["t1"], envvar="DANDI_TEST_CACHE"
    )
    calls = 0

    def count(source: str | Path | Readable) -> int:
        nonlocal calls
        calls += 1
        return calls

    cached = memoize_source(cache, ["t1"])(count)
    assert cached(FingerprintedReadable(simple1_nwb, "A")) == 1
    assert cached(FingerprintedReadable(simple1_nwb, "A")) == 2
    assert cached(simple1_nwb) == 3
    assert cached(simple1_nwb) == 4
