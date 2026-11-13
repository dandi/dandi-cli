from __future__ import annotations

from importlib.metadata import version
import json
from operator import attrgetter
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY

from dandischema.models import BareAsset, get_schema_version
import h5py
import numpy as np
from packaging.version import Version
import pytest
import zarr

from .fixtures import SampleDandiset
from .test_helpers import TWO_ARRAY_ZARR_LAYOUT, mkzarrnode, zarr_format_of
from .. import get_logger
from ..bids_validator_deno import _bids_version, bids_validate
from ..consts import ZARR_MIME_TYPE, dandiset_metadata_file
from ..dandiapi import AssetType, RemoteZarrAsset
from ..exceptions import NWBDirectoryError, NWBZarrReadError, UnknownAssetError
from ..files import (
    BIDSDatasetDescriptionAsset,
    DandisetMetadataFile,
    GenericAsset,
    GenericBIDSAsset,
    ImageAsset,
    LocalAsset,
    NWBAsset,
    NWBBIDSAsset,
    VideoAsset,
    ZarrAsset,
    ZarrBIDSAsset,
    dandi_file,
    find_bids_dataset_description,
    find_dandi_files,
)
from ..files.bases import _SCHEMA_BAREASSET_HAS_DATASTANDARD
from ..files.bids import bids_dataset_description_problem
from ..misctypes import DUMMY_DANDI_ETAG
from ..pynwb_utils import NWB_ZARR_INSTALL_HINT, get_nwb_version, make_nwb_file
from ..validate._types import (
    MissingFileContent,
    Origin,
    OriginType,
    Scope,
    Severity,
    Standard,
    ValidationResult,
    Validator,
)

lgr = get_logger()


def mkpaths(root: Path, *paths: str) -> None:
    for p in paths:
        pp = root / p
        pp.parent.mkdir(parents=True, exist_ok=True)
        if p.endswith("/"):
            pp.mkdir()
        else:
            pp.touch()


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "name", ["missing.nwb", "missing.txt", "missing.zarr", ".missing"]
)
@pytest.mark.parametrize("allow_all", [False, True])
def test_find_dandi_files_missing_path(
    tmp_path: Path, name: str, allow_all: bool
) -> None:
    existing = tmp_path / "existing.nwb"
    existing.touch()
    missing = tmp_path / name
    discovery = find_dandi_files(
        existing, missing, dandiset_path=tmp_path, allow_all=allow_all
    )
    with pytest.raises(FileNotFoundError) as exc:
        next(discovery)
    assert exc.value.filename == str(missing)


@pytest.mark.ai_generated
@pytest.mark.skipif(
    os.name == "nt", reason="Creating symlinks requires Windows privileges"
)
def test_find_dandi_files_broken_symlink(tmp_path: Path) -> None:
    link = tmp_path / "unfetched.nwb"
    link.symlink_to(tmp_path / "absent.nwb")
    assets = list(find_dandi_files(link))
    assert len(assets) == 1
    assert isinstance(assets[0], NWBAsset)
    assert assets[0].filepath == link


@pytest.mark.ai_generated
def test_find_dandi_files_empty_directory(tmp_path: Path) -> None:
    assert list(find_dandi_files(tmp_path, dandiset_path=tmp_path)) == []


def test_find_dandi_files(tmp_path: Path) -> None:
    mkpaths(
        tmp_path,
        dandiset_metadata_file,
        "sample01.zarr/inner.nwb",
        "sample01.zarr/foo",
        "sample02.nwb",
        "foo",
        "bar.txt",
        "subdir/sample03.nwb",
        "subdir/sample04.zarr/inner2.nwb",
        "subdir/sample04.zarr/baz",
        "subdir/gnusto",
        "subdir/cleesh.txt",
        "empty.zarr/",
        "glarch.mp4",
        "quux.png",
        ".ignored",
        ".ignored.dir/ignored.nwb",
    )

    video = VideoAsset(
        filepath=tmp_path / "glarch.mp4", path="glarch.mp4", dandiset_path=tmp_path
    )
    image = ImageAsset(
        filepath=tmp_path / "quux.png", path="quux.png", dandiset_path=tmp_path
    )
    zarr1 = ZarrAsset(
        filepath=tmp_path / "sample01.zarr",
        path="sample01.zarr",
        dandiset_path=tmp_path,
    )
    nwb2 = NWBAsset(
        filepath=tmp_path / "sample02.nwb",
        path="sample02.nwb",
        dandiset_path=tmp_path,
    )
    nwb3 = NWBAsset(
        filepath=tmp_path / "subdir" / "sample03.nwb",
        path="subdir/sample03.nwb",
        dandiset_path=tmp_path,
    )
    zarr4 = ZarrAsset(
        filepath=tmp_path / "subdir" / "sample04.zarr",
        path="subdir/sample04.zarr",
        dandiset_path=tmp_path,
    )
    metadata_file = DandisetMetadataFile(
        filepath=tmp_path / dandiset_metadata_file, dandiset_path=tmp_path
    )

    files = sorted(
        find_dandi_files(tmp_path, dandiset_path=tmp_path), key=attrgetter("filepath")
    )
    assert files == [video, image, zarr1, nwb2, nwb3, zarr4]

    files = sorted(
        find_dandi_files(tmp_path, dandiset_path=tmp_path, allow_all=True),
        key=attrgetter("filepath"),
    )
    assert files == [
        GenericAsset(
            filepath=tmp_path / "bar.txt", path="bar.txt", dandiset_path=tmp_path
        ),
        metadata_file,
        GenericAsset(filepath=tmp_path / "foo", path="foo", dandiset_path=tmp_path),
        video,
        image,
        zarr1,
        nwb2,
        GenericAsset(
            filepath=tmp_path / "subdir" / "cleesh.txt",
            path="subdir/cleesh.txt",
            dandiset_path=tmp_path,
        ),
        GenericAsset(
            filepath=tmp_path / "subdir" / "gnusto",
            path="subdir/gnusto",
            dandiset_path=tmp_path,
        ),
        nwb3,
        zarr4,
    ]

    files = sorted(
        find_dandi_files(tmp_path, dandiset_path=tmp_path, include_metadata=True),
        key=attrgetter("filepath"),
    )
    assert files == [metadata_file, video, image, zarr1, nwb2, nwb3, zarr4]


@pytest.mark.ai_generated
def test_find_dandi_files_with_bids(tmp_path: Path) -> None:
    mkpaths(
        tmp_path,
        dandiset_metadata_file,
        "foo.txt",
        "bar.nwb",
        "bids1/.bidsignore",
        "bids1/dataset_description.json",
        "bids1/file.txt",
        "bids1/subdir/quux.nwb",
        "bids1/subdir/glarch.zarr/dataset_description.json",
        "bids2/dataset_description.json",
        "bids2/movie.mp4",
        "bids2/subbids/dataset_description.json",
        "bids2/subbids/data.json",
    )
    for ds in ("bids1", "bids2"):
        (tmp_path / ds / "dataset_description.json").write_text(
            '{"Name": "test", "BIDSVersion": "1.9.0"}'
        )

    bidsignore = GenericBIDSAsset(
        filepath=tmp_path / "bids1" / ".bidsignore",
        path="bids1/.bidsignore",
        dandiset_path=tmp_path,
        bids_dataset_description_ref=ANY,  # type: ignore[arg-type]
    )
    bids1_dd = BIDSDatasetDescriptionAsset(
        filepath=tmp_path / "bids1" / "dataset_description.json",
        path="bids1/dataset_description.json",
        dandiset_path=tmp_path,
        dataset_files=ANY,  # type: ignore[arg-type]
    )
    bids1_file = GenericBIDSAsset(
        filepath=tmp_path / "bids1" / "file.txt",
        path="bids1/file.txt",
        dandiset_path=tmp_path,
        bids_dataset_description_ref=ANY,  # type: ignore[arg-type]
    )
    bids1_zarr = ZarrBIDSAsset(
        filepath=tmp_path / "bids1" / "subdir" / "glarch.zarr",
        path="bids1/subdir/glarch.zarr",
        dandiset_path=tmp_path,
        bids_dataset_description_ref=ANY,  # type: ignore[arg-type]
    )
    bids1_nwb = NWBBIDSAsset(
        filepath=tmp_path / "bids1" / "subdir" / "quux.nwb",
        path="bids1/subdir/quux.nwb",
        dandiset_path=tmp_path,
        bids_dataset_description_ref=ANY,  # type: ignore[arg-type]
    )
    bids2_dd = BIDSDatasetDescriptionAsset(
        filepath=tmp_path / "bids2" / "dataset_description.json",
        path="bids2/dataset_description.json",
        dandiset_path=tmp_path,
        dataset_files=ANY,  # type: ignore[arg-type]
    )
    bids2_movie = GenericBIDSAsset(
        filepath=tmp_path / "bids2" / "movie.mp4",
        path="bids2/movie.mp4",
        dandiset_path=tmp_path,
        bids_dataset_description_ref=ANY,  # type: ignore[arg-type]
    )
    bids2_data = GenericBIDSAsset(
        filepath=tmp_path / "bids2" / "subbids" / "data.json",
        path="bids2/subbids/data.json",
        dandiset_path=tmp_path,
        bids_dataset_description_ref=ANY,  # type: ignore[arg-type]
    )
    bids2_subdd = GenericBIDSAsset(
        filepath=tmp_path / "bids2" / "subbids" / "dataset_description.json",
        path="bids2/subbids/dataset_description.json",
        dandiset_path=tmp_path,
        bids_dataset_description_ref=ANY,  # type: ignore[arg-type]
    )

    files = sorted(
        find_dandi_files(tmp_path, dandiset_path=tmp_path, allow_all=False),
        key=attrgetter("filepath"),
    )

    assert files == [
        NWBAsset(filepath=tmp_path / "bar.nwb", path="bar.nwb", dandiset_path=tmp_path),
        bidsignore,
        bids1_dd,
        bids1_file,
        bids1_zarr,
        bids1_nwb,
        bids2_dd,
        bids2_movie,
        bids2_data,
        bids2_subdd,
    ]

    bidsdd = files[2]
    assert isinstance(bidsdd, BIDSDatasetDescriptionAsset)
    assert sorted(bidsdd.dataset_files, key=attrgetter("filepath")) == [
        bidsignore,
        bids1_file,
        bids1_zarr,
        bids1_nwb,
    ]
    for asset in bidsdd.dataset_files:
        assert asset.bids_dataset_description is bidsdd

    bidsdd = files[6]
    assert isinstance(bidsdd, BIDSDatasetDescriptionAsset)
    assert sorted(bidsdd.dataset_files, key=attrgetter("filepath")) == [
        bids2_movie,
        bids2_data,
        bids2_subdd,
    ]
    for asset in bidsdd.dataset_files:
        assert asset.bids_dataset_description is bidsdd


# This test sometimes fails and sometimes passes when running on NFS.
@pytest.mark.flaky(reruns=10)
def test_dandi_file_zarr_with_excluded_dotfiles(tmp_path: Path) -> None:
    zarr_path = tmp_path / "foo.zarr"
    mkpaths(
        zarr_path,
        ".git/data",
        ".gitattributes",
        ".dandi/somefile.txt",
        ".datalad/",
        "arr_0/.gitmodules",
    )
    with pytest.raises(UnknownAssetError):
        dandi_file(zarr_path)
    with (zarr_path / "arr_0" / "foo").open("w") as fp:
        print("Text.", file=fp)
        # Force changes to be synced when testing on NFS:
        fp.flush()
        os.fsync(fp.fileno())
    zf = dandi_file(zarr_path)
    assert isinstance(zf, ZarrAsset)


@pytest.mark.ai_generated
def test_dandi_file_nwb_zarr(simple2_nwb_zarr: Path, tmp_path: Path) -> None:
    dandiset_path = tmp_path
    (dandiset_path / dandiset_metadata_file).write_text("{}\n")
    nwb_zarr = dandiset_path / "sub-mouse001" / "sub-mouse001.nwb.zarr"
    shutil.copytree(simple2_nwb_zarr, nwb_zarr)
    df = dandi_file(nwb_zarr, dandiset_path)
    assert isinstance(df, ZarrAsset)
    assert df.is_nwb
    assert list(find_dandi_files(dandiset_path, dandiset_path=dandiset_path)) == [df]

    metadata = df.get_metadata(digest=df.get_digest(), ignore_errors=False)
    assert metadata.path == "sub-mouse001/sub-mouse001.nwb.zarr"
    assert metadata.encodingFormat == ZARR_MIME_TYPE
    assert metadata.contentSize == df.size
    assert metadata.wasAttributedTo is not None
    participant = metadata.wasAttributedTo[0]
    assert participant.identifier == "mouse001"
    assert participant.species is not None
    assert participant.species.name == "Mus musculus - House mouse"
    if _SCHEMA_BAREASSET_HAS_DATASTANDARD:
        assert {name: s.version for name, s in _data_standards(metadata).items()} == {
            "Neurodata Without Borders (NWB)": get_nwb_version(nwb_zarr)
        }

    assert df.get_validation_errors() == []
    assert df.get_validation_errors(schema_version=get_schema_version()) == []


@pytest.mark.ai_generated
def test_validate_nwb_zarr_layout_and_content(
    simple1_nwb_metadata: dict[str, Any], tmp_path: Path
) -> None:
    """An NWB file stored as Zarr is validated by NWB Inspector and for its
    location in the Dandiset, like one stored as HDF5"""
    pytest.importorskip("hdmf_zarr", minversion="0.14")
    # Without a Subject
    nwb_zarr = make_nwb_file(
        tmp_path / "foo" / "simple1.nwb.zarr", **simple1_nwb_metadata
    )
    df = dandi_file(nwb_zarr, tmp_path)
    assert isinstance(df, ZarrAsset) and df.is_nwb
    assert sorted(e.id for e in df.get_validation_errors()) == [
        "DANDI.NON_DANDI_FILENAME",
        "DANDI.NON_DANDI_FOLDERNAME",
        "NWBI.check_subject_exists",
    ]


@pytest.mark.ai_generated
def test_validate_nwb_zarr_without_hdmf_zarr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zarr_path = tmp_path / "foo" / "bar.nwb.zarr"
    zarr.save(zarr_path, np.arange(1000), np.arange(1000, 0, -1))
    df = dandi_file(zarr_path, tmp_path)
    assert isinstance(df, ZarrAsset) and df.is_nwb
    monkeypatch.setitem(sys.modules, "hdmf_zarr", None)
    errors = df.get_validation_errors()
    # Its path is still validated
    assert [e.id for e in errors] == [
        "dandi_zarr.nwb_unreadable",
        "DANDI.NON_DANDI_FILENAME",
        "DANDI.NON_DANDI_FOLDERNAME",
    ]
    assert "hdmf-zarr is not installed" in str(errors[0].message)
    assert NWB_ZARR_INSTALL_HINT in str(errors[0].message)
    # Content is not validated, so neither is its absence
    assert [
        e.id
        for e in df.get_validation_errors(
            missing_file_content=MissingFileContent.only_non_data
        )
    ] == ["DANDI.NON_DANDI_FILENAME", "DANDI.NON_DANDI_FOLDERNAME"]


def _organized_nwb_zarr_asset(nwb_zarr: Path, dandiset_path: Path) -> ZarrAsset:
    """The `ZarrAsset` of a copy of ``nwb_zarr`` organized in a Dandiset at
    ``dandiset_path``"""
    path = dandiset_path / "sub-mouse001" / "sub-mouse001_ecephys.nwb.zarr"
    shutil.copytree(nwb_zarr, path)
    df = dandi_file(path, dandiset_path)
    assert isinstance(df, ZarrAsset) and df.is_nwb
    return df


@pytest.mark.ai_generated
def test_validate_nwb_zarr_malformed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, disallow_pickle_decoding: None
) -> None:
    """Zarr metadata which cannot be read is reported, not raised, keeping the
    other validation results"""
    # As hdmf-zarr >= 0.14, so that the metadata is checked
    monkeypatch.setitem(
        sys.modules,
        "hdmf_zarr",
        SimpleNamespace(__version__="0.14.0", NWBZarrV2IO=object),
    )
    zarr_path = tmp_path / "foo" / "bar.nwb.zarr"
    mkzarrnode(zarr_path)
    (zarr_path / "group").mkdir()
    (zarr_path / "group" / "zarr.json").write_text("{bad")
    df = dandi_file(zarr_path, tmp_path)
    assert isinstance(df, ZarrAsset) and df.is_nwb
    ids = [e.id for e in df.get_validation_errors()]
    assert "dandi_zarr.nwb_unreadable" in ids
    assert {"DANDI.NON_DANDI_FILENAME", "DANDI.NON_DANDI_FOLDERNAME"} <= set(ids)


@pytest.mark.ai_generated
def test_validate_nwb_zarr_not_nwb(tmp_path: Path) -> None:
    """A Zarr which PyNWB cannot read is reported like an HDF5 file it cannot
    read, keeping the other validation results"""
    pytest.importorskip("hdmf_zarr", minversion="0.14")
    zarr_path = tmp_path / "foo" / "bar.nwb.zarr"
    zarr.save(zarr_path, a=np.arange(10), b=np.arange(5))
    df = dandi_file(zarr_path, tmp_path)
    assert isinstance(df, ZarrAsset) and df.is_nwb
    ids = [e.id for e in df.get_validation_errors()]
    assert "pynwb.GENERIC" in ids
    # With the same text as nwbinspector.inspect_nwbfile() for HDF5 files
    assert any(
        re.fullmatch(
            r"NWBI\.During io\.read\(\), an error occurred: [\w.]+\. This"
            r" indicates that PyNWB was unable to read the file\. See the"
            r" traceback message for more details\.",
            i,
        )
        for i in ids
    )
    assert {"DANDI.NON_DANDI_FILENAME", "DANDI.NON_DANDI_FOLDERNAME"} <= set(ids)


@pytest.mark.ai_generated
def test_validate_nwb_zarr_v2_pickled_disallowed(
    ecephys_v2_nwb_zarr: Path, tmp_path: Path, disallow_pickle_decoding: None
) -> None:
    """An NWB file stored as Zarr with pickled data is not read unless allowed"""
    df = _organized_nwb_zarr_asset(ecephys_v2_nwb_zarr, tmp_path)
    errors = df.get_validation_errors()
    assert [e.id for e in errors] == ["dandi_zarr.nwb_unreadable"]
    assert "NUMCODECS_ALLOW_UNSAFE_PICKLE_DECODE=1" in str(errors[0].message)
    with pytest.raises(NWBZarrReadError):
        df.get_metadata(ignore_errors=False)


@pytest.mark.ai_generated
def test_validate_nwb_zarr_v2_pickled_allowed(
    ecephys_v2_nwb_zarr: Path, tmp_path: Path, allow_pickle_decoding: None
) -> None:
    """An NWB file stored as Zarr v2 by hdmf-zarr < 0.14, with tables, is read
    and validated with whichever hdmf-zarr, once decoding pickled data is
    allowed, with no error from NWB Inspector"""
    df = _organized_nwb_zarr_asset(ecephys_v2_nwb_zarr, tmp_path)
    errors = df.get_validation_errors()
    assert [e.id for e in errors if e.severity is Severity.ERROR] == []
    assert "NWBI.check_units_resolution_is_set" in [e.id for e in errors]
    metadata = df.get_metadata(digest=df.get_digest(), ignore_errors=False)
    assert metadata.wasAttributedTo is not None
    assert metadata.wasAttributedTo[0].identifier == "mouse001"
    assert metadata.encodingFormat == ZARR_MIME_TYPE


@pytest.mark.ai_generated
def test_nwb_directory(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A directory named like an NWB file is neither an asset nor a directory
    of assets"""
    (tmp_path / dandiset_metadata_file).write_text("{}\n")
    zarr.save(tmp_path / "foo.nwb", np.arange(1000), np.arange(1000, 0, -1))
    mkpaths(tmp_path, "foo.nwb/bar.nwb", "baz.txt")
    with pytest.raises(NWBDirectoryError, match=r"\*\.nwb\.zarr"):
        dandi_file(tmp_path / "foo.nwb", tmp_path)
    found = find_dandi_files(tmp_path, dandiset_path=tmp_path, allow_all=True)
    # In the (filesystem-dependent) order of the directory listing
    assert sorted(df.filepath.relative_to(tmp_path).as_posix() for df in found) == [
        "baz.txt",
        dandiset_metadata_file,
    ]
    assert "foo.nwb: Directory has NWB file extension" in caplog.text


@pytest.mark.ai_generated
@pytest.mark.parametrize("zarr_format", [2, 3])
def test_validate_deep_zarr_chunk_keys(tmp_path: Path, zarr_format: int) -> None:
    """The chunk keys of an array do not count towards the depth of a Zarr
    (https://github.com/dandi/dandi-cli/issues/1919)"""
    zarr_path = tmp_path / "foo.zarr"
    groups = "processing/pose_estimation/RightCamera/PoseEstimationSeriesTubeTop"
    parts = groups.split("/")
    for i in range(len(parts) + 1):
        mkzarrnode(zarr_path.joinpath(*parts[:i]), zarr_format=zarr_format)
    array = zarr_path / groups / "data"
    mkzarrnode(array, node_type="array", zarr_format=zarr_format)
    # As with the default chunk key encoding of Zarr v3, or with "/" as
    # dimension separator in Zarr v2
    mkpaths(array, "c/1/0" if zarr_format == 3 else "1/0/0/0")
    zf = ZarrAsset(filepath=zarr_path, path="foo.zarr", dandiset_path=None)
    assert not zf._is_too_deep()
    # But groups count: a file 8 directories deep is too deep
    for subgroup in ("a", "a/b", "a/b/c"):
        mkzarrnode(zarr_path / groups / subgroup, zarr_format=zarr_format)
    assert zf._is_too_deep()


def test_validate_simple1(simple1_nwb: Path) -> None:
    # this file should be ok as long as schema_version is specified
    errors = dandi_file(simple1_nwb).get_validation_errors(
        schema_version=get_schema_version()
    )
    assert errors == []


def test_validate_simple1_no_subject(simple1_nwb: Path) -> None:
    errors = dandi_file(simple1_nwb).get_validation_errors()
    errmsgs = []
    for e in errors:
        assert e.message is not None
        errmsgs.append(e.message)
    assert errmsgs == ["Subject is missing."]


def test_validate_simple2(organized_nwb_dir: Path) -> None:
    # this file should be ok since a Subject is included
    errors = dandi_file(
        organized_nwb_dir / "sub-mouse001" / "sub-mouse001.nwb",
        dandiset_path=organized_nwb_dir,
    ).get_validation_errors()
    assert not errors


def test_validate_simple2_new(organized_nwb_dir: Path) -> None:
    # this file should be ok
    errors = dandi_file(
        organized_nwb_dir / "sub-mouse001" / "sub-mouse001.nwb",
        dandiset_path=organized_nwb_dir,
    ).get_validation_errors(schema_version=get_schema_version())
    assert not errors


def test_validate_simple3_no_subject_id(simple3_nwb: Path) -> None:
    errors = dandi_file(simple3_nwb).get_validation_errors()
    errmsgs = []
    for e in errors:
        assert e.message is not None
        errmsgs.append(e.message)
    assert errmsgs == ["subject_id is missing."]


def test_validate_bogus(tmp_path):
    """
    Notes
    -----
    * Intended to produce use-case for https://github.com/dandi/dandi-cli/issues/93
        but it would be tricky, so it is more of a smoke test that
        we do not crash
    """
    path = tmp_path / "wannabe.nwb"
    path.write_text("not really nwb")
    errors = dandi_file(path).get_validation_errors()
    # ATM we would get 2 errors -- since could not be open in two places,
    # but that would be too rigid to test. Let's just see that we have expected errors
    assert any(
        e.message.startswith(
            (
                "Unable to open file",
                "Unable to synchronously open file",
                "Could not find an IO to read the file",
            )
        )
        for e in errors
    )
    # Recent versions of hdf5 changed the error message, hence the need to
    # check for two different patterns.


@pytest.mark.ai_generated
def test_validate_nwb_records_nwbinspector_version(simple4_nwb: Path) -> None:
    errors = dandi_file(simple4_nwb).get_validation_errors()
    nwbi_errors = [e for e in errors if e.origin.validator is Validator.nwbinspector]
    # simple4_nwb has a data orientation best practice violation
    assert nwbi_errors
    assert {e.origin.validator_version for e in nwbi_errors} == {
        str(Version(version("nwbinspector")))
    }


# Run in a fresh interpreter so that the module-level version cache starts out
# in its initial state, as it does for `dandi validate`.
GET_NWBI_VERSION_SCRIPT = """\
import json
import sys

import etelemetry

from dandi.files.bases import _get_nwb_inspector_version

lookups = []


def get_project(repo, **kwargs):
    lookups.append(repo)
    return json.loads(sys.argv[1])


etelemetry.get_project = get_project
versions = [str(_get_nwb_inspector_version()) for _ in range(2)]
print(json.dumps({"versions": versions, "lookups": lookups}))
"""


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "project,outdated_warnings",
    [
        # What etelemetry.get_project() returns when NO_ET is set
        (None, 0),
        ({"version": "9999.0.0"}, 1),
    ],
)
def test_get_nwb_inspector_version_cached(
    project: dict[str, Any] | None, outdated_warnings: int
) -> None:
    r = subprocess.run(
        [sys.executable, "-c", GET_NWBI_VERSION_SCRIPT, json.dumps(project)],
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(r.stdout.splitlines()[-1])
    assert result["versions"] == [str(Version(version("nwbinspector")))] * 2
    assert result["lookups"] == ["NeurodataWithoutBorders/nwbinspector"]
    assert r.stderr.count("please use the latest release") == outdated_warnings
    assert "Failed to retrieve" not in r.stderr


def test_upload_zarr(new_dandiset, tmp_path):
    filepath = tmp_path / "example.zarr"
    zarr.save(filepath, np.arange(1000), np.arange(1000, 0, -1))
    layout = TWO_ARRAY_ZARR_LAYOUT[zarr_format_of(filepath)]
    root_meta = layout["root_meta"]
    zf = dandi_file(filepath)
    assert isinstance(zf, ZarrAsset)
    asset = zf.upload(new_dandiset.dandiset, {"description": "A test Zarr"})
    assert isinstance(asset, RemoteZarrAsset)
    assert asset.asset_type is AssetType.ZARR
    assert asset.path == "example.zarr"
    md = asset.get_raw_metadata()
    assert md["encodingFormat"] == ZARR_MIME_TYPE
    assert md["description"] == "A test Zarr"
    md["description"] = "A modified Zarr"
    asset.set_raw_metadata(md)
    md = asset.get_raw_metadata()
    assert md["description"] == "A modified Zarr"

    entries = sorted(asset.iterfiles(), key=attrgetter("parts"))
    assert [str(e) for e in entries] == layout["files"]

    entries = sorted(zf.iterfiles(include_dirs=True), key=attrgetter("parts"))
    assert [str(e) for e in entries] == layout["files_and_dirs"]
    # The root group metadata file is ``.zgroup`` in V2 and ``zarr.json`` in
    # V3; either way it must be a real file at the Zarr root.
    assert (zf.filetree / root_meta).exists()
    assert (zf.filetree / root_meta).is_file()
    assert not (zf.filetree / root_meta).is_dir()
    assert (zf.filetree / "arr_0").exists()
    assert not (zf.filetree / "arr_0").is_file()
    assert (zf.filetree / "arr_0").is_dir()
    assert not (zf.filetree / "0").exists()
    assert not (zf.filetree / "0").is_file()
    assert not (zf.filetree / "0").is_dir()
    # ``arr_0/.zgroup`` never exists: in V2 ``arr_0`` is an array (uses
    # ``.zarray``); in V3 ``.zgroup`` is not used at all.
    assert not (zf.filetree / "arr_0" / ".zgroup").exists()
    assert not (zf.filetree / "arr_0" / ".zgroup").is_file()
    assert not (zf.filetree / "arr_0" / ".zgroup").is_dir()
    assert not (zf.filetree / ".zgroup" / "0").exists()
    assert not (zf.filetree / ".zgroup" / "0").is_file()
    assert not (zf.filetree / ".zgroup" / "0").is_dir()
    assert not (zf.filetree / "arr_2" / "0").exists()
    assert not (zf.filetree / "arr_2" / "0").is_file()
    assert not (zf.filetree / "arr_2" / "0").is_dir()


# V2 (``.zgroup`` / ``.zarray``) and V3 (``zarr.json``, ``c/<chunk>`` layout,
# different default compressor) Zarr serialisations have different on-disk
# byte layouts and therefore different digests. Key expected values on the
# format that was *actually* produced rather than on ``zarr.__version__``:
# zarr-python 3.x can still write V2 via ``zarr_format=2``.
_ZARR_PROPERTIES_EXPECTED = {
    "2": {
        "total_size": 1516,
        "total_digest": "4313ab36412db2981c3ed391b38604d6-5--1516",
        "entries": [
            (".zgroup", 24, "e20297935e73dd0154104d4ea53040ab"),
            ("arr_0", 746, "51c74ec257069ce3a555bdddeb50230a-2--746"),
            ("arr_0/.zarray", 315, "9e30a0a1a465e24220d4132fdd544634"),
            ("arr_0/0", 431, "ed4e934a474f1d2096846c6248f18c00"),
            ("arr_1", 746, "7b99a0ad9bd8bb3331657e54755b1a31-2--746"),
            ("arr_1/.zarray", 315, "9e30a0a1a465e24220d4132fdd544634"),
            ("arr_1/0", 431, "fba4dee03a51bde314e9713b00284a93"),
        ],
    },
    "3": {
        "total_size": 3935,
        "total_digest": "00157f091c9a6295e89eb3c4c2efaeff-5--3935",
        "entries": [
            ("arr_0", 2192, "ae16256ae750e4303674ccf1e23fa3c6-2--2192"),
            ("arr_0/c", 1573, "93912a45f2107a08090f7b283297d662-1--1573"),
            ("arr_0/c/0", 1573, "6c237f8d2d4a41bc1e26e31518dafd9e"),
            ("arr_0/zarr.json", 619, "850fae056c97aa9c76df0a52411f4086"),
            ("arr_1", 1677, "debc9ca4b2184a6ef1a3d6fcf7d79fd9-2--1677"),
            ("arr_1/c", 1058, "2642f5d2df2cddf469313abd9910b371-1--1058"),
            ("arr_1/c/0", 1058, "084d662af7251a807649fb48edc36e95"),
            ("arr_1/zarr.json", 619, "850fae056c97aa9c76df0a52411f4086"),
            ("zarr.json", 66, "457126c0639af2eba0140851c39c1aad"),
        ],
    },
}


def test_zarr_properties(tmp_path: Path) -> None:
    # Expected sizes and digests are selected by the Zarr serialisation
    # format ``zarr.save`` actually produced (V2 vs V3 layouts differ).
    filepath = tmp_path / "example.zarr"
    dt = np.dtype("<i8")
    zarr.save(filepath, np.arange(1000, dtype=dt), np.arange(1000, 0, -1, dtype=dt))
    expected = _ZARR_PROPERTIES_EXPECTED[zarr_format_of(filepath)]
    zf = dandi_file(filepath)
    assert isinstance(zf, ZarrAsset)
    assert zf.filetree.size == expected["total_size"]
    assert zf.filetree.get_digest().value == expected["total_digest"]
    entries = sorted(zf.iterfiles(include_dirs=True), key=attrgetter("parts"))
    assert [(str(e), e.size, e.get_digest().value) for e in entries] == expected[
        "entries"
    ]
    assert zf.get_digest().value == expected["total_digest"]
    stat = zf.stat()
    assert stat.size == expected["total_size"]
    assert stat.digest.value == expected["total_digest"]
    assert sorted(stat.files, key=attrgetter("parts")) == [
        e for e in entries if e.is_file()
    ]


def test_upload_zarr_with_excluded_dotfiles(
    new_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    filepath = tmp_path / "example.zarr"
    zarr.save(filepath, np.arange(1000), np.arange(1000, 0, -1))
    layout = TWO_ARRAY_ZARR_LAYOUT[zarr_format_of(filepath)]
    subprocess.run(["git", "init"], cwd=str(filepath), check=True)
    (filepath / ".dandi").mkdir()
    (filepath / ".dandi" / "somefile.txt").write_text("Hello world!\n")
    (filepath / ".gitattributes").write_text("* eol=lf\n")
    (filepath / "arr_0" / ".gitmodules").write_text("# Empty\n")
    (filepath / "arr_1" / ".datalad").mkdir()
    (filepath / "arr_1" / ".datalad" / "config").write_text("# Empty\n")
    zf = dandi_file(filepath)
    assert isinstance(zf, ZarrAsset)
    asset = zf.upload(new_dandiset.dandiset, {})
    assert isinstance(asset, RemoteZarrAsset)
    local_entries = sorted(zf.iterfiles(include_dirs=True), key=attrgetter("parts"))
    assert [str(e) for e in local_entries] == layout["files_and_dirs"]
    remote_entries = sorted(asset.iterfiles(), key=attrgetter("parts"))
    assert [str(e) for e in remote_entries] == layout["files"]


def test_upload_zarr_entry_content_type(new_dandiset, tmp_path):
    filepath = tmp_path / "example.zarr"
    zarr.save(filepath, np.arange(1000), np.arange(1000, 0, -1))
    root_meta = TWO_ARRAY_ZARR_LAYOUT[zarr_format_of(filepath)]["root_meta"]
    zf = dandi_file(filepath)
    assert isinstance(zf, ZarrAsset)
    asset = zf.upload(new_dandiset.dandiset, {"description": "A test Zarr"})
    assert isinstance(asset, RemoteZarrAsset)
    e = asset.get_entry_by_path(root_meta)
    r = new_dandiset.client.get(e.download_url, json_resp=False)
    assert r.headers["Content-Type"] == "application/json"


def test_validate_deep_zarr(tmp_path: Path) -> None:
    zarr_path = tmp_path / "foo.zarr"
    zarr.save(zarr_path, np.arange(1000), np.arange(1000, 0, -1))
    mkpaths(zarr_path, "a/b/c/d/e/f/g.txt")
    zf = dandi_file(zarr_path)
    assert zf.get_validation_errors() == []
    mkpaths(zarr_path, "a/b/c/d/e/f/g/h.txt")
    assert [e.id for e in zf.get_validation_errors()] == [
        "dandi_zarr.tree_depth_exceeded"
    ]


def test_validate_zarr_deep_via_excluded_dotfiles(tmp_path: Path) -> None:
    zarr_path = tmp_path / "foo.zarr"
    zarr.save(zarr_path, np.arange(1000), np.arange(1000, 0, -1))
    mkpaths(zarr_path, ".git/a/b/c/d/e/f/g.txt", "a/b/c/.git/d/e/f/g.txt")
    zf = dandi_file(zarr_path)
    assert zf.get_validation_errors() == []


VALID_STORES_PATH = "data/zarr3_stores/valid_stores"


@pytest.mark.parametrize(
    "path",
    [
        "arrays_in_groups.zarr",
        "single_array.zarr",
    ],
)
def test_validate_valid_zarr3(path: str) -> None:
    """
    Test validating valid Zarr format 3 objects, Zarr groups or arrays

    Parameters
    ----------
    path : Path
        The path to the store of the Zarr object in the filesystem relative to
        `VALID_STORES_PATH` which is relative to the parent of the path of this
        test file
    """
    zf = dandi_file(Path(__file__).parent / VALID_STORES_PATH / path)
    assert zf.get_validation_errors() == []


INVALID_STORES_PATH = "data/zarr3_stores/invalid_stores"


@pytest.mark.parametrize(
    "path, expected_result_ids",
    [
        # Expects "zarr.cannot_open" because Zarr format version can't be determined
        # without a zarr.json file
        ("arrays_in_groups_missing_zarr_json.zarr", {"zarr.cannot_open"}),
        ("single_array_missing_zarr_json.zarr", {"zarr.cannot_open"}),
        # Stores with the `node_type` field in some zarr.json missing or having
        # invalid values
        (
            "arrays_in_groups_node_type_problem.zarr",
            {"zarr.invalid_zarr_json", "zarr.invalid_zarr_json"},
        ),
        (
            "single_array_node_type_problem.zarr",
            {"zarr.invalid_zarr_json"},
        ),
        # A store with a corrupt zarr.json for an array (missing fields other than
        # `node_type`)
        (
            "array_v3_corrupt_zarr_json.zarr",
            {"zarr.invalid_zarr_json", "zarr.cannot_open"},
        ),
    ],
)
def test_validate_invalid_zarr3(path: str, expected_result_ids: set[str]) -> None:
    """
    Test validating valid Zarr format 3 objects, Zarr groups or arrays

    Parameters
    ----------
    path : Path
        The path to the store of the Zarr object in the filesystem relative to
        `INVALID_STORES_PATH` which is relative to the parent of the path of this
        test file
    """
    zf = dandi_file(Path(__file__).parent / INVALID_STORES_PATH / path)

    result_ids = {r.id for r in zf.get_validation_errors()}
    assert result_ids == expected_result_ids


@pytest.mark.ai_generated
def test_validate_zarr3_string_array(tmp_path: Path) -> None:
    # Variable-length strings are an extension data type in Zarr format V3,
    # and NWB files store most of their text in them
    zarr_path = tmp_path / "strings.zarr"
    group = zarr.open_group(zarr_path, mode="w", zarr_format=3)
    group.create_array("identifier", shape=(1,), dtype=str)[:] = ["session"]
    assert dandi_file(zarr_path).get_validation_errors() == []


@pytest.mark.ai_generated
def test_validate_zarr3_attributes_not_an_object(tmp_path: Path) -> None:
    # zarr-python opens an array whose attributes are a list, which the Zarr
    # format V3 specification does not allow
    zarr_path = tmp_path / "example.zarr"
    zarr.open_array(zarr_path, mode="w", shape=(4,), dtype="int8", zarr_format=3)
    meta_path = zarr_path / "zarr.json"
    meta = json.loads(meta_path.read_text())
    meta["attributes"] = []
    meta_path.write_text(json.dumps(meta))
    assert [r.id for r in dandi_file(zarr_path).get_validation_errors()] == [
        "zarr.invalid_zarr_json"
    ]


@pytest.mark.ai_generated
def test_validate_zarr2_invalid_array_metadata(tmp_path: Path) -> None:
    # Opening the root group does not read the metadata of its arrays
    zarr_path = tmp_path / "example.zarr"
    group = zarr.open_group(zarr_path, mode="w", zarr_format=2)
    group.create_array("x", shape=(4,), dtype="int8")
    meta_path = zarr_path / "x" / ".zarray"
    meta = json.loads(meta_path.read_text())
    meta["order"] = "Z"
    meta_path.write_text(json.dumps(meta))
    assert [r.id for r in dandi_file(zarr_path).get_validation_errors()] == [
        "zarr.invalid_metadata"
    ]


@pytest.mark.ai_generated
def test_validate_zarr3_array_metadata_not_json(tmp_path: Path) -> None:
    zarr_path = tmp_path / "example.zarr"
    group = zarr.open_group(zarr_path, mode="w", zarr_format=3)
    group.create_array("x", shape=(4,), dtype="int8")
    (zarr_path / "x" / "zarr.json").write_text("not json")
    assert [r.id for r in dandi_file(zarr_path).get_validation_errors()] == [
        "zarr.invalid_zarr_json"
    ]


@pytest.mark.ai_generated
def test_validate_zarr2_array_metadata_not_json(tmp_path: Path) -> None:
    zarr_path = tmp_path / "example.zarr"
    group = zarr.open_group(zarr_path, mode="w", zarr_format=2)
    group.create_array("x", shape=(4,), dtype="int8")
    (zarr_path / "x" / ".zarray").write_text("not json")
    assert [r.id for r in dandi_file(zarr_path).get_validation_errors()] == [
        "zarr.invalid_metadata"
    ]


@pytest.mark.ai_generated
def test_validate_zarr2_unparseable_consolidated_metadata(tmp_path: Path) -> None:
    # zarr-python 2.x wrote a fill value of 0 for object arrays, which
    # zarr-python 3.x cannot parse.  hdmf-zarr wrote such arrays in NWB files
    # (e.g. `session_start_time`) and consolidated their metadata at the root.
    zarr_path = tmp_path / "example.zarr"
    array_meta = {
        "chunks": [1],
        "compressor": None,
        "dtype": "|O",
        "fill_value": 0,
        "filters": [{"id": "vlen-bytes"}],
        "order": "C",
        "shape": [1],
        "zarr_format": 2,
    }
    metadata = {".zgroup": {"zarr_format": 2}, "session_start_time/.zarray": array_meta}
    (zarr_path / "session_start_time").mkdir(parents=True)
    for name, meta in metadata.items():
        (zarr_path / name).write_text(json.dumps(meta))
    (zarr_path / ".zmetadata").write_text(
        json.dumps({"metadata": metadata, "zarr_consolidated_format": 1})
    )
    assert dandi_file(zarr_path).get_validation_errors() == []


@pytest.mark.ai_generated
@pytest.mark.parametrize("zarr_version", [None, "2.18.7"])
def test_validate_zarr_requires_zarr_python_3(
    zarr_version: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `None` stands for zarr-python not being installed
    if zarr_version is None:
        monkeypatch.setitem(sys.modules, "zarr", None)
    else:
        monkeypatch.setattr(zarr, "__version__", zarr_version)
    zf = dandi_file(Path(__file__).parent / VALID_STORES_PATH / "single_array.zarr")
    assert [r.id for r in zf.get_validation_errors()] == [
        "dandi_zarr.zarr_python_required"
    ]


@pytest.mark.ai_generated
def test_validate_deep_zarr_without_zarr_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zarr_path = tmp_path / "foo.zarr"
    zarr.save(zarr_path, np.arange(1000), np.arange(1000, 0, -1))
    mkpaths(zarr_path, "a/b/c/d/e/f/g/h.txt")
    monkeypatch.setitem(sys.modules, "zarr", None)
    assert [r.id for r in dandi_file(zarr_path).get_validation_errors()] == [
        "dandi_zarr.tree_depth_exceeded",
        "dandi_zarr.zarr_python_required",
    ]


@pytest.mark.ai_generated
def test_pytest_plugin_loads_without_zarr() -> None:
    # pytest loads dandi's plugin through its `pytest11` entry point in any
    # environment that has dandi installed, with or without the `zarr` extra
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['zarr'] = None; import dandi.pytest_plugin",
        ],
        check=True,
    )


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "zarr_format, meta_name, result_id",
    [
        (2, ".zarray", "zarr.invalid_metadata"),
        (3, "zarr.json", "zarr.invalid_zarr_json"),
    ],
)
def test_validate_zarr_broken_metadata_symlink(
    tmp_path: Path, zarr_format: int, meta_name: str, result_id: str
) -> None:
    # For example, git-annex content that has not been fetched
    zarr_path = tmp_path / "example.zarr"
    group = zarr.open_group(zarr_path, mode="w", zarr_format=zarr_format)
    group.create_array("x", shape=(4,), dtype="int8")
    meta_path = zarr_path / "x" / meta_name
    meta_path.unlink()
    try:
        meta_path.symlink_to(tmp_path / "absent")
    except OSError as exc:
        pytest.skip(f"Cannot create symlink: {exc}")
    assert [r.id for r in dandi_file(zarr_path).get_validation_errors()] == [result_id]


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "content",
    [
        pytest.param("not json", id="not-json"),
        pytest.param(json.dumps({"zarr_consolidated_format": 1}), id="no-metadata-key"),
    ],
)
def test_validate_zarr2_invalid_consolidated_metadata(
    tmp_path: Path, content: str
) -> None:
    zarr_path = tmp_path / "example.zarr"
    group = zarr.open_group(zarr_path, mode="w", zarr_format=2)
    group.create_array("x", shape=(4,), dtype="int8")
    zarr.consolidate_metadata(zarr_path, zarr_format=2)
    assert dandi_file(zarr_path).get_validation_errors() == []
    (zarr_path / ".zmetadata").write_text(content)
    assert [r.id for r in dandi_file(zarr_path).get_validation_errors()] == [
        "zarr.invalid_metadata"
    ]


@pytest.mark.ai_generated
@pytest.mark.parametrize("ds", ["ds", ""], ids=["subdir", "dandiset-root"])
@pytest.mark.parametrize(
    "content, problem, bids_version",
    [
        pytest.param(
            '{"Name": "x", "BIDSVersion": "1.9.0"}', None, "1.9.0", id="valid"
        ),
        pytest.param(
            '\ufeff{"Name": "x", "BIDSVersion": "1.9.0"}', None, "1.9.0", id="bom"
        ),
        # Invalid but declared BIDS datasets, for the BIDS validator to report on
        pytest.param(
            '{"Name": "x", "BIDSVersion": ""}', None, None, id="empty-version"
        ),
        pytest.param(
            '{"Name": "x", "BIDSVersion": 1.9}', None, None, id="non-string-version"
        ),
        pytest.param(
            '{"Name": "x", "BIDSVersion": "1.9.0",}', None, None, id="invalid-json"
        ),
        pytest.param(
            '{"Name": "\xe9t\xe9", "BIDSVersion": "1.9.0"}'.encode("latin-1"),
            None,
            None,
            id="latin-1",
        ),
        # Not BIDS datasets
        pytest.param(
            '{"Name": "x"}', 'has no "BIDSVersion" field', None, id="no-version"
        ),
        pytest.param("[]", 'has no "BIDSVersion" field', None, id="list"),
        pytest.param(
            '["BIDSVersion"]', 'has no "BIDSVersion" field', None, id="list-with-key"
        ),
        pytest.param("", 'is not valid JSON with "BIDSVersion"', None, id="empty"),
        pytest.param(
            '{"Name": "x",}',
            'is not valid JSON with "BIDSVersion"',
            None,
            id="invalid-json-no-version",
        ),
        # e.g., to annexed content which is not present
        pytest.param(None, "cannot be read", None, id="broken-symlink"),
    ],
)
def test_bids_dataset_description_bids_version(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    ds: str,
    content: str | bytes | None,
    problem: str | None,
    bids_version: str | None,
) -> None:
    ds_path = tmp_path / ds
    dd_path = ds_path / "dataset_description.json"
    mkpaths(ds_path, "sub-01/sub-01.nwb", "sub-01/notes.txt")
    if content is None:
        try:
            dd_path.symlink_to(tmp_path / "absent")
        except OSError as exc:
            pytest.skip(f"Cannot create symlink: {exc}")
    elif isinstance(content, bytes):
        dd_path.write_bytes(content)
    else:
        dd_path.write_text(content, encoding="utf-8")

    assert bids_dataset_description_problem(dd_path) == problem
    bidsdd = find_bids_dataset_description(ds_path / "sub-01", tmp_path)

    def file_types(**kwargs: bool) -> dict[str, type]:
        return {
            df.filepath.relative_to(ds_path).as_posix(): type(df)
            for df in find_dandi_files(tmp_path, dandiset_path=tmp_path, **kwargs)
        }

    types = file_types(allow_all=True)
    if problem is None:
        assert isinstance(bidsdd, BIDSDatasetDescriptionAsset)
        assert bidsdd.bids_version == bids_version
        assert types["dataset_description.json"] is BIDSDatasetDescriptionAsset
        assert types["sub-01/sub-01.nwb"] is NWBBIDSAsset
        assert "not treating" not in caplog.text
    else:
        assert bidsdd is None
        assert types["dataset_description.json"] is GenericAsset
        assert types["sub-01/sub-01.nwb"] is NWBAsset
        assert f"{problem}, so not treating" in caplog.text
        # and not BIDS without allow_all either, so non-NWB files are skipped
        assert file_types() == {"sub-01/sub-01.nwb": NWBAsset}
        # warned about the marker file only, once per walk
        warnings = [
            r.getMessage() for r in caplog.records if "not treating" in r.getMessage()
        ]
        assert len(warnings) == 2
        assert all("dataset_description.json" in w for w in warnings)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "standard_versions, expected",
    [
        (["1.11.1"], "1.11.1"),
        # BIDS version unknown for the schema the validator used
        ([None], "1.9.0"),
        # no validation results to take it from
        ([], "1.9.0"),
    ],
)
def test_get_validation_bids_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    standard_versions: list[str | None],
    expected: str,
) -> None:
    mkpaths(tmp_path, "sub-01/sub-01.nwb")
    (tmp_path / "dataset_description.json").write_text(
        '{"Name": "x", "BIDSVersion": "1.9.0"}'
    )
    results = [
        ValidationResult(
            id="BIDS.SOME_ISSUE",
            origin=Origin(
                type=OriginType.VALIDATION,
                validator=Validator.bids_validator_deno,
                validator_version="0",
                standard=Standard.BIDS,
                standard_version=v,
                standard_schema_version="1.2.7",
            ),
            scope=Scope.DATASET,
            dataset_path=tmp_path,
        )
        for v in standard_versions
    ]
    monkeypatch.setattr("dandi.files.bids.bids_validate", lambda *_a, **_kw: results)

    bidsdd = dandi_file(tmp_path / "dataset_description.json", tmp_path)
    assert isinstance(bidsdd, BIDSDatasetDescriptionAsset)
    asset = dandi_file(
        tmp_path / "sub-01" / "sub-01.nwb", tmp_path, bids_dataset_description=bidsdd
    )
    assert isinstance(asset, NWBBIDSAsset)
    assert asset.get_validation_bids_version() == expected
    assert bidsdd.get_validation_bids_version() == expected
    # the declared version stays the declared one
    assert bidsdd.bids_version == "1.9.0"


@pytest.mark.ai_generated
def test_get_validation_bids_version_bids_examples(
    bids_examples: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The version of BIDS used in validation is known
    (https://github.com/dandi/dandi-cli/issues/1961)
    """
    # Do not fetch the published mapping
    monkeypatch.setattr(_bids_version, "_published_mapping", dict)
    ds_path = bids_examples / "ieeg_epilepsyNWB"
    nwb_path = (
        ds_path
        / "sub-01"
        / "ses-postimp"
        / "ieeg"
        / "sub-01_ses-postimp_task-seizure_run-01_ieeg.nwb"
    )
    bidsdd = find_bids_dataset_description(nwb_path.parent, ds_path)
    assert isinstance(bidsdd, BIDSDatasetDescriptionAsset)
    assert bidsdd.bids_version is not None
    asset = dandi_file(nwb_path, ds_path, bids_dataset_description=bidsdd)
    assert isinstance(asset, NWBBIDSAsset)
    validation_bids_version = asset.get_validation_bids_version()
    assert validation_bids_version is not None
    assert (results := bids_validate(ds_path))
    # the declared version, if that of the validator's schema is not known
    assert validation_bids_version == (
        results[0].origin.standard_version or bidsdd.bids_version
    )


def _data_standards(metadata: BareAsset) -> dict[str, Any]:
    # TODO: use metadata.dataStandard directly, and type the result as
    # dict[str, StandardsType], once min dandischema >= 0.15.0
    return {s.name: s for s in getattr(metadata, "dataStandard", None) or []}


@pytest.mark.ai_generated
@pytest.mark.skipif(
    not _SCHEMA_BAREASSET_HAS_DATASTANDARD,
    reason="dandischema too old, no dataStandard on BareAsset",
)
class TestDataStandard:
    """Tests for per-asset dataStandard population"""

    BIDS = "Brain Imaging Data Structure (BIDS)"
    HED = "Hierarchical Event Descriptors (HED)"
    NWB = "Neurodata Without Borders (NWB)"
    OME_NGFF = "OME/NGFF Standard"

    @staticmethod
    def _bids_dd_metadata(tmp_path: Path, content: str) -> BareAsset:
        dd_path = tmp_path / "dataset_description.json"
        dd_path.write_text(content)
        return BIDSDatasetDescriptionAsset(
            filepath=dd_path,
            path="dataset_description.json",
            dandiset_path=tmp_path,
        ).get_metadata()

    @pytest.mark.parametrize(
        "description, bids_version, hed_version, hed_extensions",
        [
            ({"BIDSVersion": "1.9.0"}, "1.9.0", None, None),
            ({}, None, None, None),
            # non-string values must not cause a crash
            ({"BIDSVersion": 1.8}, "1.8", None, None),
            ({"BIDSVersion": "1.9.0", "HEDVersion": "8.2.0"}, "1.9.0", "8.2.0", None),
            ({"BIDSVersion": "1.9.0", "HEDVersion": []}, "1.9.0", None, None),
            # library schemas, with and without namespace prefix
            (
                {
                    "BIDSVersion": "1.9.0",
                    "HEDVersion": ["8.2.0", "sc:score_1.0.0", "lang_1.1.0"],
                },
                "1.9.0",
                "8.2.0",
                {"score": "1.0.0", "lang": "1.1.0"},
            ),
            # partnered library schema without explicit standard schema
            (
                {"BIDSVersion": "1.10.0", "HEDVersion": "score_2.1.0"},
                "1.10.0",
                None,
                {"score": "2.1.0"},
            ),
            # prefixed standard schema
            (
                {"BIDSVersion": "1.9.0", "HEDVersion": ["ts:8.3.0"]},
                "1.9.0",
                "8.3.0",
                None,
            ),
            # non-string entries are ignored
            (
                {"BIDSVersion": "1.9.0", "HEDVersion": [{"8.2.0": 1}, "8.2.0"]},
                "1.9.0",
                "8.2.0",
                None,
            ),
        ],
    )
    def test_bids_dataset_description(
        self,
        tmp_path: Path,
        description: dict,
        bids_version: str | None,
        hed_version: str | None,
        hed_extensions: dict[str, str] | None,
    ) -> None:
        standards = _data_standards(
            self._bids_dd_metadata(
                tmp_path, json.dumps({"Name": "Test", **description})
            )
        )
        assert standards[self.BIDS].version == bids_version
        if "HEDVersion" in description and description["HEDVersion"]:
            assert set(standards) == {self.BIDS, self.HED}
            hed = standards[self.HED]
            assert hed.version == hed_version
            if hed_extensions is None:
                assert hed.extensions is None
            else:
                assert hed.extensions is not None
                assert {e.name: e.version for e in hed.extensions} == hed_extensions
        else:
            assert set(standards) == {self.BIDS}

    @pytest.mark.parametrize("content", ["{not json", "[]"])
    def test_bids_dataset_description_invalid(
        self, tmp_path: Path, content: str
    ) -> None:
        standards = _data_standards(self._bids_dd_metadata(tmp_path, content))
        assert set(standards) == {self.BIDS}
        assert standards[self.BIDS].version is None

    def test_bids_dataset_assets(self, simple1_nwb: Path, tmp_path: Path) -> None:
        """All assets in a BIDS dataset declare BIDS, dataset_description.json
        also declares HED"""
        (tmp_path / "dataset_description.json").write_text(
            json.dumps({"Name": "Test", "BIDSVersion": "1.9.0", "HEDVersion": "8.2.0"})
        )
        (tmp_path / "participants.tsv").write_text("participant_id\nsub-01\n")
        session = tmp_path / "sub-01" / "ses-1"
        nwb_path = session / "ecephys" / "sub-01_ses-1_ecephys.nwb"
        nwb_path.parent.mkdir(parents=True)
        shutil.copy(simple1_nwb, nwb_path)
        zarr.save(
            session / "micr" / "sub-01_ses-1_sample-A_SPIM.ome.zarr", np.arange(10)
        )
        files = {
            f.path: f
            for f in find_dandi_files(tmp_path, dandiset_path=tmp_path)
            if isinstance(f, LocalAsset)
        }
        expected = {
            "dataset_description.json": {self.BIDS: "1.9.0", self.HED: "8.2.0"},
            "participants.tsv": {self.BIDS: "1.9.0"},
            "sub-01/ses-1/ecephys/sub-01_ses-1_ecephys.nwb": {
                self.BIDS: "1.9.0",
                self.NWB: get_nwb_version(simple1_nwb),
            },
            "sub-01/ses-1/micr/sub-01_ses-1_sample-A_SPIM.ome.zarr": {
                self.BIDS: "1.9.0",
                self.OME_NGFF: None,
            },
        }
        assert set(files) == set(expected)
        for path, versions in expected.items():
            standards = _data_standards(
                files[path].get_metadata(digest=DUMMY_DANDI_ETAG)
            )
            assert {name: s.version for name, s in standards.items()} == versions, path

    def test_nwb(self, simple1_nwb: Path, tmp_path: Path) -> None:
        nwb_path = tmp_path / "sub-1.nwb"
        shutil.copy(simple1_nwb, nwb_path)
        with h5py.File(nwb_path, "a") as f:
            specs = f.require_group("specifications")
            specs.create_group("ndx-test/0.1.0")
            specs.create_group("ndx-test/0.2.0")
        metadata = NWBAsset(
            filepath=nwb_path, path="sub-1.nwb", dandiset_path=tmp_path
        ).get_metadata()
        nwb = _data_standards(metadata)[self.NWB]
        assert nwb.version == get_nwb_version(nwb_path)
        assert nwb.extensions is not None
        assert [(e.name, e.version) for e in nwb.extensions] == [("ndx-test", "0.2.0")]

    def test_nwb_unreadable(self, tmp_path: Path) -> None:
        nwb_path = tmp_path / "sub-1.nwb"
        nwb_path.write_text("not an HDF5 file")
        metadata = NWBAsset(
            filepath=nwb_path, path="sub-1.nwb", dandiset_path=tmp_path
        ).get_metadata(ignore_errors=True)
        nwb = _data_standards(metadata)[self.NWB]
        assert nwb.version is None
        assert nwb.extensions is None

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("sample.ome.zarr", True),
            ("sample_1.5x.ome.zarr", True),
            ("sample.zarr", False),
        ],
    )
    def test_zarr(self, tmp_path: Path, path: str, expected: bool) -> None:
        zarr_path = tmp_path / path
        zarr.save(zarr_path, np.arange(10))
        zf = dandi_file(zarr_path, tmp_path)
        assert isinstance(zf, ZarrAsset)
        standards = _data_standards(zf.get_metadata())
        assert (self.OME_NGFF in standards) is expected
