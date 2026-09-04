from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any, NoReturn

import h5py
import numpy as np
from pynwb import NWBHDF5IO, NWBFile, TimeSeries

from ..pynwb_utils import (
    _rename_pose_estimation_original_videos,
    _sanitize_nwb_version,
    nwb_has_external_links,
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


def test_rename_pose_estimation_original_videos() -> None:
    pose = SimpleNamespace(
        neurodata_type="PoseEstimation",
        original_videos=[b"camera\\raw.mp4", "https://example.com/remote.mp4", "other.mp4"],
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


def test_rename_pose_estimation_original_videos_persists_hdf5(
    tmp_path: Path,
) -> None:
    filepath = tmp_path / "pose-videos.h5"
    string_type = h5py.string_dtype(encoding="utf-8")
    with h5py.File(filepath, "w") as f:
        f.create_dataset(
            "original_videos",
            data=np.asarray(
                ["camera/raw.mp4", "camera/other.mp4"], dtype=string_type
            ),
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


def test_rename_nwb_external_files_updates_pose_references(
    tmp_path: Path, mocker
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
