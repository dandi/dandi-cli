from operator import attrgetter
from pathlib import Path

from ..consts import dandiset_metadata_file
from ..files import (
    DandisetMetadataFile,
    GenericAsset,
    NWBAsset,
    ZarrAsset,
    find_dandi_files,
)


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

    files = sorted(find_dandi_files(tmp_path), key=attrgetter("filepath"))
    assert files == [
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
        find_dandi_files(tmp_path, allow_all=True), key=attrgetter("filepath")
    )
    assert files == [
        GenericAsset(filepath=tmp_path / "bar.txt", path="bar.txt"),
        DandisetMetadataFile(filepath=tmp_path / dandiset_metadata_file),
        GenericAsset(filepath=tmp_path / "foo", path="foo"),
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
        find_dandi_files(tmp_path, include_metadata=True), key=attrgetter("filepath")
    )
    assert files == [
        DandisetMetadataFile(filepath=tmp_path / dandiset_metadata_file),
        ZarrAsset(filepath=tmp_path / "sample01.zarr", path="sample01.zarr"),
        NWBAsset(filepath=tmp_path / "sample02.nwb", path="sample02.nwb"),
        NWBAsset(
            filepath=tmp_path / "subdir" / "sample03.nwb", path="subdir/sample03.nwb"
        ),
        ZarrAsset(
            filepath=tmp_path / "subdir" / "sample04.zarr", path="subdir/sample04.zarr"
        ),
    ]
