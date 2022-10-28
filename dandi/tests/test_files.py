from operator import attrgetter
from pathlib import Path
import subprocess
from typing import cast
from unittest.mock import ANY

from dandischema.models import get_schema_version
import numpy as np
import pytest
import zarr

from .fixtures import SampleDandiset
from .. import get_logger
from ..consts import ZARR_MIME_TYPE, dandiset_metadata_file
from ..dandiapi import AssetType, RemoteZarrAsset
from ..exceptions import UnknownAssetError
from ..files import (
    BIDSDatasetDescriptionAsset,
    DandisetMetadataFile,
    GenericAsset,
    GenericBIDSAsset,
    NWBAsset,
    NWBBIDSAsset,
    VideoAsset,
    ZarrAsset,
    ZarrBIDSAsset,
    dandi_file,
    find_dandi_files,
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
        ".ignored",
        ".ignored.dir/ignored.nwb",
    )

    files = sorted(
        find_dandi_files(tmp_path, dandiset_path=tmp_path), key=attrgetter("filepath")
    )
    assert files == [
        VideoAsset(filepath=tmp_path / "glarch.mp4", path="glarch.mp4"),
        ZarrAsset(filepath=tmp_path / "sample01.zarr", path="sample01.zarr"),
        NWBAsset(filepath=tmp_path / "sample02.nwb", path="sample02.nwb"),
        NWBAsset(
            filepath=tmp_path / "subdir" / "sample03.nwb", path="subdir/sample03.nwb"
        ),
        ZarrAsset(
            filepath=tmp_path / "subdir" / "sample04.zarr", path="subdir/sample04.zarr"
        ),
    ]

    files = sorted(
        find_dandi_files(tmp_path, dandiset_path=tmp_path, allow_all=True),
        key=attrgetter("filepath"),
    )
    assert files == [
        GenericAsset(filepath=tmp_path / "bar.txt", path="bar.txt"),
        DandisetMetadataFile(filepath=tmp_path / dandiset_metadata_file),
        GenericAsset(filepath=tmp_path / "foo", path="foo"),
        VideoAsset(filepath=tmp_path / "glarch.mp4", path="glarch.mp4"),
        ZarrAsset(filepath=tmp_path / "sample01.zarr", path="sample01.zarr"),
        NWBAsset(filepath=tmp_path / "sample02.nwb", path="sample02.nwb"),
        GenericAsset(
            filepath=tmp_path / "subdir" / "cleesh.txt", path="subdir/cleesh.txt"
        ),
        GenericAsset(filepath=tmp_path / "subdir" / "gnusto", path="subdir/gnusto"),
        NWBAsset(
            filepath=tmp_path / "subdir" / "sample03.nwb", path="subdir/sample03.nwb"
        ),
        ZarrAsset(
            filepath=tmp_path / "subdir" / "sample04.zarr", path="subdir/sample04.zarr"
        ),
    ]

    files = sorted(
        find_dandi_files(tmp_path, dandiset_path=tmp_path, include_metadata=True),
        key=attrgetter("filepath"),
    )
    assert files == [
        DandisetMetadataFile(filepath=tmp_path / dandiset_metadata_file),
        VideoAsset(filepath=tmp_path / "glarch.mp4", path="glarch.mp4"),
        ZarrAsset(filepath=tmp_path / "sample01.zarr", path="sample01.zarr"),
        NWBAsset(filepath=tmp_path / "sample02.nwb", path="sample02.nwb"),
        NWBAsset(
            filepath=tmp_path / "subdir" / "sample03.nwb", path="subdir/sample03.nwb"
        ),
        ZarrAsset(
            filepath=tmp_path / "subdir" / "sample04.zarr", path="subdir/sample04.zarr"
        ),
    ]


def test_find_dandi_files_with_bids(tmp_path: Path) -> None:
    mkpaths(
        tmp_path,
        dandiset_metadata_file,
        "foo.txt",
        "bar.nwb",
        "bids1/dataset_description.json",
        "bids1/file.txt",
        "bids1/subdir/quux.nwb",
        "bids1/subdir/glarch.zarr/dataset_description.json",
        "bids2/dataset_description.json",
        "bids2/movie.mp4",
        "bids2/subbids/dataset_description.json",
        "bids2/subbids/data.json",
    )

    files = sorted(
        find_dandi_files(tmp_path, dandiset_path=tmp_path, allow_all=False),
        key=attrgetter("filepath"),
    )

    assert files == [
        NWBAsset(filepath=tmp_path / "bar.nwb", path="bar.nwb"),
        BIDSDatasetDescriptionAsset(
            filepath=tmp_path / "bids1" / "dataset_description.json",
            path="bids1/dataset_description.json",
            dataset_files=ANY,
        ),
        GenericBIDSAsset(
            filepath=tmp_path / "bids1" / "file.txt",
            path="bids1/file.txt",
            bids_dataset_description_ref=ANY,
        ),
        ZarrBIDSAsset(
            filepath=tmp_path / "bids1" / "subdir" / "glarch.zarr",
            path="bids1/subdir/glarch.zarr",
            bids_dataset_description_ref=ANY,
        ),
        NWBBIDSAsset(
            filepath=tmp_path / "bids1" / "subdir" / "quux.nwb",
            path="bids1/subdir/quux.nwb",
            bids_dataset_description_ref=ANY,
        ),
        BIDSDatasetDescriptionAsset(
            filepath=tmp_path / "bids2" / "dataset_description.json",
            path="bids2/dataset_description.json",
            dataset_files=ANY,
        ),
        GenericBIDSAsset(
            filepath=tmp_path / "bids2" / "movie.mp4",
            path="bids2/movie.mp4",
            bids_dataset_description_ref=ANY,
        ),
        GenericBIDSAsset(
            filepath=tmp_path / "bids2" / "subbids" / "data.json",
            path="bids2/subbids/data.json",
            bids_dataset_description_ref=ANY,
        ),
        BIDSDatasetDescriptionAsset(
            filepath=tmp_path / "bids2" / "subbids" / "dataset_description.json",
            path="bids2/subbids/dataset_description.json",
            dataset_files=ANY,
        ),
    ]

    bidsdd = cast(BIDSDatasetDescriptionAsset, files[1])
    assert sorted(bidsdd.dataset_files, key=attrgetter("filepath")) == [
        GenericBIDSAsset(
            filepath=tmp_path / "bids1" / "file.txt",
            path="bids1/file.txt",
            bids_dataset_description_ref=ANY,
        ),
        ZarrBIDSAsset(
            filepath=tmp_path / "bids1" / "subdir" / "glarch.zarr",
            path="bids1/subdir/glarch.zarr",
            bids_dataset_description_ref=ANY,
        ),
        NWBBIDSAsset(
            filepath=tmp_path / "bids1" / "subdir" / "quux.nwb",
            path="bids1/subdir/quux.nwb",
            bids_dataset_description_ref=ANY,
        ),
    ]
    for asset in bidsdd.dataset_files:
        assert asset.bids_dataset_description is bidsdd

    bidsdd = cast(BIDSDatasetDescriptionAsset, files[5])
    assert bidsdd.dataset_files == [
        GenericBIDSAsset(
            filepath=tmp_path / "bids2" / "movie.mp4",
            path="bids2/movie.mp4",
            bids_dataset_description_ref=ANY,
        ),
    ]
    for asset in bidsdd.dataset_files:
        assert asset.bids_dataset_description is bidsdd

    bidsdd = cast(BIDSDatasetDescriptionAsset, files[8])
    assert bidsdd.dataset_files == [
        GenericBIDSAsset(
            filepath=tmp_path / "bids2" / "subbids" / "data.json",
            path="bids2/subbids/data.json",
            bids_dataset_description_ref=ANY,
        ),
    ]
    for asset in bidsdd.dataset_files:
        assert asset.bids_dataset_description is bidsdd


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
    (zarr_path / "arr_0" / "foo").touch()
    zf = dandi_file(zarr_path)
    assert isinstance(zf, ZarrAsset)


def test_validate_simple1(simple1_nwb):
    # this file should be ok as long as schema_version is specified
    errors = dandi_file(simple1_nwb).get_validation_errors(
        schema_version=get_schema_version()
    )
    assert not errors


def test_validate_simple1_no_subject(simple1_nwb):
    errors = dandi_file(simple1_nwb).get_validation_errors()
    assert [e.message for e in errors] == ["Subject is missing."]


def test_validate_simple2(simple2_nwb):
    # this file should be ok since a Subject is included
    errors = dandi_file(simple2_nwb).get_validation_errors()
    assert not errors


def test_validate_simple2_new(simple2_nwb):
    # this file should be ok
    errors = dandi_file(simple2_nwb).get_validation_errors(
        schema_version=get_schema_version()
    )
    assert not errors


def test_validate_simple3_no_subject_id(simple3_nwb):
    errors = dandi_file(simple3_nwb).get_validation_errors()
    assert [e.message for e in errors] == ["subject_id is missing."]


def test_validate_bogus(tmp_path):
    path = tmp_path / "wannabe.nwb"
    path.write_text("not really nwb")
    # intended to produce use-case for https://github.com/dandi/dandi-cli/issues/93
    # but it would be tricky, so it is more of a smoke test that
    # we do not crash
    errors = dandi_file(path).get_validation_errors()
    # ATM we would get 2 errors -- since could not be open in two places,
    # but that would be too rigid to test. Let's just see that we have expected errors
    assert any(e.message.startswith("Unable to open file") for e in errors)


def test_upload_zarr(new_dandiset, tmp_path):
    filepath = tmp_path / "example.zarr"
    zarr.save(filepath, np.arange(1000), np.arange(1000, 0, -1))
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

    for file_src in [zf, asset]:
        lgr.debug("Traversing %s", type(file_src).__name__)
        entries = sorted(file_src.iterfiles(include_dirs=True), key=attrgetter("parts"))
        assert [str(e) for e in entries] == [
            ".zgroup",
            "arr_0",
            "arr_0/.zarray",
            "arr_0/0",
            "arr_1",
            "arr_1/.zarray",
            "arr_1/0",
        ]
        assert (file_src.filetree / ".zgroup").exists()
        assert (file_src.filetree / ".zgroup").is_file()
        assert not (file_src.filetree / ".zgroup").is_dir()
        assert (file_src.filetree / "arr_0").exists()
        assert not (file_src.filetree / "arr_0").is_file()
        assert (file_src.filetree / "arr_0").is_dir()
        assert not (file_src.filetree / "0").exists()
        assert not (file_src.filetree / "0").is_file()
        assert not (file_src.filetree / "0").is_dir()
        assert not (file_src.filetree / "arr_0" / ".zgroup").exists()
        assert not (file_src.filetree / "arr_0" / ".zgroup").is_file()
        assert not (file_src.filetree / "arr_0" / ".zgroup").is_dir()
        assert not (file_src.filetree / ".zgroup" / "0").exists()
        assert not (file_src.filetree / ".zgroup" / "0").is_file()
        assert not (file_src.filetree / ".zgroup" / "0").is_dir()
        assert not (file_src.filetree / "arr_2" / "0").exists()
        assert not (file_src.filetree / "arr_2" / "0").is_file()
        assert not (file_src.filetree / "arr_2" / "0").is_dir()


def test_zarr_properties(tmp_path: Path) -> None:
    # This test assumes that the Zarr serialization format never changes
    filepath = tmp_path / "example.zarr"
    dt = np.dtype("<i8")
    zarr.save(filepath, np.arange(1000, dtype=dt), np.arange(1000, 0, -1, dtype=dt))
    zf = dandi_file(filepath)
    assert isinstance(zf, ZarrAsset)
    assert zf.filetree.size == 1516
    assert zf.filetree.get_digest().value == "4313ab36412db2981c3ed391b38604d6-5--1516"
    entries = sorted(zf.iterfiles(include_dirs=True), key=attrgetter("parts"))
    assert [(str(e), e.size, e.get_digest().value) for e in entries] == [
        (".zgroup", 24, "e20297935e73dd0154104d4ea53040ab"),
        ("arr_0", 746, "51c74ec257069ce3a555bdddeb50230a-2--746"),
        ("arr_0/.zarray", 315, "9e30a0a1a465e24220d4132fdd544634"),
        ("arr_0/0", 431, "ed4e934a474f1d2096846c6248f18c00"),
        ("arr_1", 746, "7b99a0ad9bd8bb3331657e54755b1a31-2--746"),
        ("arr_1/.zarray", 315, "9e30a0a1a465e24220d4132fdd544634"),
        ("arr_1/0", 431, "fba4dee03a51bde314e9713b00284a93"),
    ]
    assert zf.get_digest().value == "4313ab36412db2981c3ed391b38604d6-5--1516"
    stat = zf.stat()
    assert stat.size == 1516
    assert stat.digest.value == "4313ab36412db2981c3ed391b38604d6-5--1516"
    assert sorted(stat.files, key=attrgetter("parts")) == [
        e for e in entries if e.is_file()
    ]


def test_upload_zarr_with_excluded_dotfiles(
    new_dandiset: SampleDandiset, tmp_path: Path
) -> None:
    filepath = tmp_path / "example.zarr"
    zarr.save(filepath, np.arange(1000), np.arange(1000, 0, -1))
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
    assert [str(e) for e in local_entries] == [
        ".zgroup",
        "arr_0",
        "arr_0/.zarray",
        "arr_0/0",
        "arr_1",
        "arr_1/.zarray",
        "arr_1/0",
    ]
    remote_entries = sorted(asset.iterfiles(include_dirs=True), key=attrgetter("parts"))
    assert [str(e) for e in remote_entries] == [
        ".zgroup",
        "arr_0",
        "arr_0/.zarray",
        "arr_0/0",
        "arr_1",
        "arr_1/.zarray",
        "arr_1/0",
    ]


def test_validate_deep_zarr(tmp_path: Path) -> None:
    zarr_path = tmp_path / "foo.zarr"
    zarr.save(zarr_path, np.arange(1000), np.arange(1000, 0, -1))
    mkpaths(zarr_path, "a/b/c/d/e/f/g.txt")
    zf = dandi_file(zarr_path)
    assert zf.get_validation_errors() == []
    mkpaths(zarr_path, "a/b/c/d/e/f/g/h.txt")
    assert [e.id for e in zf.get_validation_errors()] == ["zarr.tree_depth_exceeded"]


def test_validate_zarr_deep_via_excluded_dotfiles(tmp_path: Path) -> None:
    zarr_path = tmp_path / "foo.zarr"
    zarr.save(zarr_path, np.arange(1000), np.arange(1000, 0, -1))
    mkpaths(zarr_path, ".git/a/b/c/d/e/f/g.txt", "a/b/c/.git/d/e/f/g.txt")
    zf = dandi_file(zarr_path)
    assert zf.get_validation_errors() == []
