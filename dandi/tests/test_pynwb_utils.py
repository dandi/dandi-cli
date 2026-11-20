from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from typing import Any, NoReturn

import h5py
import numcodecs.pickles
import numpy as np
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
import pytest
from pytest_mock import MockerFixture

from .test_helpers import mkzarrnode
from ..exceptions import NWBZarrReadError
from ..pynwb_utils import (
    NWB_ZARR_INSTALL_HINT,
    _get_pynwb_metadata,
    _rename_pose_estimation_original_videos,
    _sanitize_nwb_version,
    get_neurodata_types,
    get_nwb_extensions,
    get_nwb_version,
    get_nwb_zarr_reading_problem,
    get_object_id,
    get_pickled_zarr_arrays,
    is_nwb_zarr,
    nwb_has_external_links,
    pickle_decoding_allowed,
    rename_nwb_external_files,
)
from ..pynwb_utils import validate as pynwb_validate


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
def test_get_nwb_extensions(tmp_path: Path) -> None:
    """Test extraction of NWB extensions from HDF5 specifications group."""
    h5path = tmp_path / "test.nwb"
    with h5py.File(h5path, "w") as f:
        specs = f.create_group("specifications")
        # Core namespaces should be excluded
        specs.create_group("core/2.7.0")
        specs.create_group("hdmf-common/1.8.0")
        specs.create_group("hdmf-experimental/0.5.0")
        # Latest version is taken, compared as versions and not as strings
        specs.create_group("ndx-ecog/0.9.0")
        specs.create_group("ndx-ecog/0.10.0")
        specs.create_group("ndx-events/0.3.0")
        # Unparsable versions are compared as strings
        specs.create_group("ndx-odd/beta")
        specs.create_group("ndx-odd/alpha")
        # Namespace without versions is ignored
        specs.create_group("ndx-empty")

    assert get_nwb_extensions(h5path) == {
        "ndx-ecog": "0.10.0",
        "ndx-events": "0.3.0",
        "ndx-odd": "beta",
    }


@pytest.mark.ai_generated
def test_get_nwb_extensions_no_specs(tmp_path: Path) -> None:
    """No specifications group returns empty dict."""
    h5path = tmp_path / "test.nwb"
    with h5py.File(h5path, "w") as f:
        f.attrs["nwb_version"] = "2.7.0"

    assert get_nwb_extensions(h5path) == {}


@pytest.mark.ai_generated
@pytest.mark.parametrize("zarr_format", [2, 3])
def test_nwb_helpers_zarr_metadata(tmp_path: Path, zarr_format: int) -> None:
    """The light-weight NWB helpers read the Zarr metadata of an NWB file
    stored as Zarr (v2 or v3) without hdmf-zarr"""
    root = tmp_path / "test.nwb.zarr"
    mkzarrnode(
        root,
        attrs={
            "nwb_version": "2.8.0",
            "object_id": "4d5e2a3c-0000-4000-8000-000000000000",
            "neurodata_type": "NWBFile",
        },
        zarr_format=zarr_format,
    )
    mkzarrnode(root / "acquisition", zarr_format=zarr_format)
    for name in ("ts1", "ts2"):
        mkzarrnode(
            root / "acquisition" / name,
            attrs={"neurodata_type": "TimeSeries", "description": "a series"},
            zarr_format=zarr_format,
        )
        # Arrays (and their chunks) are not descended into
        mkzarrnode(
            root / "acquisition" / name / "data",
            node_type="array",
            attrs={"neurodata_type": "NotAGroup"},
            zarr_format=zarr_format,
        )
    mkzarrnode(
        root / "general" / "subject",
        attrs={"neurodata_type": "Subject"},
        zarr_format=zarr_format,
    )
    mkzarrnode(root / "general", zarr_format=zarr_format)
    specs = root / "specifications"
    for ns_version in (
        "core/2.8.0",
        "hdmf-common/1.8.0",
        "ndx-ecog/0.9.0",
        "ndx-ecog/0.10.0",
        "ndx-events/0.3.0",
    ):
        mkzarrnode(specs / ns_version, zarr_format=zarr_format)
    for p in (specs, specs / "core", specs / "hdmf-common", specs / "ndx-ecog"):
        mkzarrnode(p, zarr_format=zarr_format)
    mkzarrnode(specs / "ndx-events", zarr_format=zarr_format)

    assert is_nwb_zarr(root)
    assert get_nwb_version(root) == "2.8.0"
    assert get_object_id(root) == "4d5e2a3c-0000-4000-8000-000000000000"
    assert get_nwb_extensions(root) == {"ndx-ecog": "0.10.0", "ndx-events": "0.3.0"}
    assert get_neurodata_types(root) == ["Subject", "TimeSeries (2)"]
    assert not nwb_has_external_links(root)


@pytest.mark.ai_generated
@pytest.mark.parametrize("zarr_format,links_attr", [(2, "zarr_link"), (3, "_LINKS")])
@pytest.mark.parametrize(
    "source,external",
    [(".", False), ("./", False), ("../other.nwb.zarr", True)],
)
def test_nwb_has_external_links_zarr(
    tmp_path: Path, zarr_format: int, links_attr: str, source: str, external: bool
) -> None:
    root = tmp_path / "test.nwb.zarr"
    mkzarrnode(root, attrs={"nwb_version": "2.8.0"}, zarr_format=zarr_format)
    mkzarrnode(
        root / "acquisition" / "ts",
        attrs={
            links_attr: [
                {"source": source, "path": "/acquisition/other/data", "name": "data"}
            ]
        },
        zarr_format=zarr_format,
    )
    mkzarrnode(root / "acquisition", zarr_format=zarr_format)
    assert nwb_has_external_links(root) is external


@pytest.mark.ai_generated
def test_nwb_zarr_without_hdmf_zarr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without hdmf-zarr, reading an NWB file stored as Zarr says how to
    install it"""
    monkeypatch.setitem(sys.modules, "hdmf_zarr", None)
    root = tmp_path / "test.nwb.zarr"
    mkzarrnode(root, attrs={"nwb_version": "2.8.0"})
    problem = get_nwb_zarr_reading_problem(root)
    assert problem is not None
    assert "hdmf-zarr is not installed" in problem
    assert NWB_ZARR_INSTALL_HINT in problem
    # Reading metadata of the Zarr does not need hdmf-zarr
    assert get_nwb_version(root) == "2.8.0"
    with pytest.raises(NWBZarrReadError, match="hdmf-zarr is not installed"):
        _get_pynwb_metadata(root)


@pytest.mark.ai_generated
@pytest.mark.parametrize("zarr_format", [2, 3])
def test_nwb_zarr_with_old_hdmf_zarr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zarr_format: int
) -> None:
    """NWB files stored as Zarr, v2 or v3, are not read with hdmf-zarr < 0.14
    (without NWBZarrV2IO), which requires zarr-python 2"""
    monkeypatch.setitem(sys.modules, "hdmf_zarr", SimpleNamespace(__version__="0.13.0"))
    root = tmp_path / "test.nwb.zarr"
    mkzarrnode(root, attrs={"nwb_version": "2.8.0"}, zarr_format=zarr_format)
    problem = get_nwb_zarr_reading_problem(root)
    assert problem is not None
    assert "hdmf-zarr 0.13.0 is too old" in problem
    assert NWB_ZARR_INSTALL_HINT in problem


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "value,allowed", [("1", True), (" Yes ", True), ("true", True), ("0", False)]
)
def test_pickle_decoding_allowed(
    monkeypatch: pytest.MonkeyPatch,
    disallow_pickle_decoding: None,
    value: str,
    allowed: bool,
) -> None:
    assert not pickle_decoding_allowed()
    # numcodecs' own setting, which it reads from the environment variable
    # when imported, is what it enforces
    monkeypatch.setenv("NUMCODECS_ALLOW_UNSAFE_PICKLE_DECODE", value)
    assert not pickle_decoding_allowed()
    monkeypatch.setattr(numcodecs.pickles, "ALLOW_UNSAFE_PICKLE_DECODE", True)
    assert pickle_decoding_allowed()
    # The environment variable, for numcodecs releases without that setting
    monkeypatch.delattr(numcodecs.pickles, "ALLOW_UNSAFE_PICKLE_DECODE")
    assert pickle_decoding_allowed() is allowed
    monkeypatch.delenv("NUMCODECS_ALLOW_UNSAFE_PICKLE_DECODE")
    assert not pickle_decoding_allowed()


@pytest.mark.ai_generated
@pytest.mark.parametrize("zarr_format", [2, 3])
def test_get_pickled_zarr_arrays(tmp_path: Path, zarr_format: int) -> None:
    root = tmp_path / "test.nwb.zarr"
    mkzarrnode(root, zarr_format=zarr_format)
    mkzarrnode(root / "table", zarr_format=zarr_format)
    pickle: dict[str, Any]
    other: dict[str, Any]
    if zarr_format == 2:
        pickle = {"filters": [{"id": "pickle", "protocol": 5}]}
        other = {"compressor": {"id": "blosc"}, "filters": None}
    else:
        pickle = {"codecs": [{"name": "numcodecs.pickle"}]}
        other = {"codecs": [{"name": "bytes"}, {"name": "zstd"}]}
    for name, metadata in (("col1", other), ("col2", pickle)):
        mkzarrnode(
            root / "table" / name,
            node_type="array",
            zarr_format=zarr_format,
            metadata=metadata,
        )
    # Not looked for within arrays
    mkzarrnode(
        root / "table" / "col1" / "c",
        node_type="array",
        zarr_format=zarr_format,
        metadata=pickle,
    )
    assert get_pickled_zarr_arrays(root) == ["table/col2"]
    assert get_pickled_zarr_arrays(root / "table") == ["col2"]
    if zarr_format == 3:
        # Within the codecs of the sharding codec
        sharding = {"name": "sharding_indexed", "configuration": pickle}
        mkzarrnode(
            root / "table" / "col3",
            node_type="array",
            metadata={"codecs": [sharding]},
        )
        assert get_pickled_zarr_arrays(root) == ["table/col2", "table/col3"]


@pytest.mark.ai_generated
def test_get_pickled_zarr_arrays_consolidated(tmp_path: Path) -> None:
    """Arrays are pickled per the consolidated metadata too, by which zarr may
    open them"""
    pickle_v2 = {"compressor": None, "filters": [{"id": "pickle"}]}
    v2 = tmp_path / "v2.nwb.zarr"
    mkzarrnode(v2, zarr_format=2)
    mkzarrnode(v2 / "table", zarr_format=2)
    mkzarrnode(v2 / "table" / "col", node_type="array", zarr_format=2)
    (v2 / ".zmetadata").write_text(
        json.dumps(
            {
                "zarr_consolidated_format": 1,
                "metadata": {
                    ".zgroup": {"zarr_format": 2},
                    "table/.zgroup": {"zarr_format": 2},
                    "table/col/.zarray": {"zarr_format": 2, **pickle_v2},
                },
            }
        )
    )
    assert get_pickled_zarr_arrays(v2) == ["table/col"]
    v3 = tmp_path / "v3.nwb.zarr"
    mkzarrnode(
        v3,
        metadata={
            "consolidated_metadata": {
                "kind": "inline",
                "metadata": {
                    "table": {
                        "node_type": "group",
                        "consolidated_metadata": {"metadata": {}},
                    },
                    "table/col": {
                        "node_type": "array",
                        "codecs": [{"name": "numcodecs.pickle"}],
                    },
                },
            }
        },
    )
    mkzarrnode(v3 / "table")
    mkzarrnode(v3 / "table" / "col", node_type="array")
    assert get_pickled_zarr_arrays(v3) == ["table/col"]
    # Metadata of unexpected shapes is not looked into
    mkzarrnode(
        v2 / "table" / "col", node_type="array", zarr_format=2, metadata={"filters": 5}
    )
    (v2 / ".zmetadata").write_text(json.dumps({"metadata": ["table/col/.zarray"]}))
    assert get_pickled_zarr_arrays(v2) == []
    mkzarrnode(v3, metadata={"consolidated_metadata": {"metadata": ["table/col"]}})
    assert get_pickled_zarr_arrays(v3) == []


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "problem", ["not-a-group", "no-metadata", "bad-json", "bad-zmetadata"]
)
def test_nwb_zarr_reading_problem_malformed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    disallow_pickle_decoding: None,
    problem: str,
) -> None:
    """Zarr metadata which cannot be read is a reading problem, not an error"""
    # As hdmf-zarr >= 0.14, so that the metadata is checked
    monkeypatch.setitem(
        sys.modules,
        "hdmf_zarr",
        SimpleNamespace(__version__="0.14.0", NWBZarrV2IO=object),
    )
    root = tmp_path / "bad.nwb.zarr"
    if problem == "not-a-group":
        mkzarrnode(root, node_type="array")
    elif problem == "no-metadata":
        root.mkdir()
        (root / "data").write_text("")
    elif problem == "bad-json":
        mkzarrnode(root)
        (root / "group").mkdir()
        (root / "group" / "zarr.json").write_text("{bad")
    else:
        mkzarrnode(root, zarr_format=2)
        (root / ".zmetadata").write_text("[]")
    reason = get_nwb_zarr_reading_problem(root)
    assert reason is not None
    assert reason.startswith("its Zarr metadata cannot be read")


@pytest.mark.ai_generated
def test_nwb_zarr_v2_pickled(
    ecephys_v2_nwb_zarr: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An NWB file stored as Zarr v2 by hdmf-zarr < 0.14, with pickled data, is
    read (by hdmf-zarr >= 0.14) only if decoding pickled data is allowed"""
    assert get_pickled_zarr_arrays(ecephys_v2_nwb_zarr) == [
        "general/extracellular_ephys/electrodes/group"
    ]
    # Read without hdmf-zarr in any case
    assert get_nwb_version(ecephys_v2_nwb_zarr) == "2.11.0"
    assert re.fullmatch(r"[0-9a-f-]{36}", get_object_id(ecephys_v2_nwb_zarr))
    assert get_nwb_extensions(ecephys_v2_nwb_zarr) == {}
    assert not nwb_has_external_links(ecephys_v2_nwb_zarr)
    assert {"ElectrodeGroup", "Subject", "Units"} <= {
        t.split(" ")[0] for t in get_neurodata_types(ecephys_v2_nwb_zarr)
    }

    monkeypatch.delenv("NUMCODECS_ALLOW_UNSAFE_PICKLE_DECODE", raising=False)
    monkeypatch.setattr(
        numcodecs.pickles, "ALLOW_UNSAFE_PICKLE_DECODE", False, raising=False
    )
    problem = get_nwb_zarr_reading_problem(ecephys_v2_nwb_zarr)
    assert problem is not None
    assert "general/extracellular_ephys/electrodes/group" in problem
    assert "NUMCODECS_ALLOW_UNSAFE_PICKLE_DECODE=1" in problem
    with pytest.raises(NWBZarrReadError, match="pickle"):
        _get_pynwb_metadata(ecephys_v2_nwb_zarr)
    assert [e.id for e in pynwb_validate(ecephys_v2_nwb_zarr)] == ["pynwb.GENERIC"]

    monkeypatch.setenv("NUMCODECS_ALLOW_UNSAFE_PICKLE_DECODE", "1")
    monkeypatch.setattr(
        numcodecs.pickles, "ALLOW_UNSAFE_PICKLE_DECODE", True, raising=False
    )
    assert get_nwb_zarr_reading_problem(ecephys_v2_nwb_zarr) is None
    metadata = _get_pynwb_metadata(ecephys_v2_nwb_zarr)
    assert metadata["subject_id"] == "mouse001"
    assert metadata["species"] == "Mus musculus"
    assert metadata["session_id"] == "session1"
    assert list(metadata["keywords"]) == ["ecephys", "zarr"]
    assert pynwb_validate(ecephys_v2_nwb_zarr) == []


@pytest.mark.ai_generated
def test_nwb_zarr_pynwb(simple2_nwb: Path, simple2_nwb_zarr: Path) -> None:
    """An NWB file stored as Zarr is read like the same file stored as HDF5"""
    assert not is_nwb_zarr(simple2_nwb)
    assert is_nwb_zarr(simple2_nwb_zarr)
    assert get_nwb_version(simple2_nwb_zarr) == get_nwb_version(simple2_nwb)
    assert re.fullmatch(r"[0-9a-f-]{36}", get_object_id(simple2_nwb_zarr))
    assert get_neurodata_types(simple2_nwb_zarr) == ["Subject"]
    assert get_nwb_extensions(simple2_nwb_zarr) == {}
    assert not nwb_has_external_links(simple2_nwb_zarr)
    zarr_metadata = _get_pynwb_metadata(simple2_nwb_zarr)
    hdf5_metadata = _get_pynwb_metadata(simple2_nwb)
    for key in (
        "experimenter",
        "identifier",
        "keywords",
        "session_start_time",
        "species",
        "subject_id",
    ):
        assert zarr_metadata[key] == hdf5_metadata[key], key
    assert pynwb_validate(simple2_nwb_zarr) == []
