from operator import attrgetter
from pathlib import Path

from dandischema.models import get_schema_version
import numpy as np
import zarr

from .. import get_logger
from ..consts import ZARR_MIME_TYPE, dandiset_metadata_file
from ..dandiapi import AssetType, RemoteZarrAsset
from ..files import (
    DandisetMetadataFile,
    GenericAsset,
    NWBAsset,
    VideoAsset,
    ZarrAsset,
    dandi_file,
    find_dandi_files,
)

lgr = get_logger()


def test_find_dandi_files(tmp_path: Path) -> None:
    (tmp_path / dandiset_metadata_file).touch()
    (tmp_path / "sample01.zarr").mkdir()
    (tmp_path / "sample01.zarr" / "inner.nwb").touch()
    (tmp_path / "sample01.zarr" / "foo").touch()
    (tmp_path / "sample02.nwb").touch()
    (tmp_path / "foo").touch()
    (tmp_path / "bar.txt").touch()
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "sample03.nwb").touch()
    (tmp_path / "subdir" / "sample04.zarr").mkdir()
    (tmp_path / "subdir" / "sample04.zarr" / "inner2.nwb").touch()
    (tmp_path / "subdir" / "sample04.zarr" / "baz").touch()
    (tmp_path / "subdir" / "gnusto").touch()
    (tmp_path / "subdir" / "cleesh.txt").touch()
    (tmp_path / "empty.zarr").mkdir()
    (tmp_path / "glarch.mp4").touch()
    (tmp_path / ".ignored").touch()
    (tmp_path / ".ignored.dir").mkdir()
    (tmp_path / ".ignored.dir" / "ignored.nwb").touch()

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


def test_validate_simple1(simple1_nwb):
    # this file should be ok
    errors = dandi_file(simple1_nwb).get_validation_errors(
        schema_version=get_schema_version()
    )
    assert not errors


def test_validate_simple2(simple2_nwb):
    # this file should be ok
    errors = dandi_file(simple2_nwb).get_validation_errors()
    assert not errors


def test_validate_simple2_new(simple2_nwb):
    # this file should be ok
    errors = dandi_file(simple2_nwb).get_validation_errors(
        schema_version=get_schema_version()
    )
    assert not errors


def test_validate_bogus(tmp_path):
    path = tmp_path / "wannabe.nwb"
    path.write_text("not really nwb")
    # intended to produce use-case for https://github.com/dandi/dandi-cli/issues/93
    # but it would be tricky, so it is more of a smoke test that
    # we do not crash
    errors = dandi_file(path).get_validation_errors()
    # ATM we would get 2 errors -- since could not be open in two places,
    # but that would be too rigid to test. Let's just see that we have expected errors
    assert any(e.startswith("Failed to read metadata") for e in errors)


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
