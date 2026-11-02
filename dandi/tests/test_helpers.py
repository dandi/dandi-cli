from operator import attrgetter
from pathlib import Path
from typing import TypedDict

from ..files.zarr import get_zarr_format_version


# This needs to be in a file named "test_*.py" so that pytest performs its
# assertion rewriting on it.
def assert_dirtrees_eq(tree1: Path, tree2: Path) -> None:
    """Assert that the file trees at the given paths are equal"""
    assert sorted(map(attrgetter("name"), tree1.iterdir())) == sorted(
        map(attrgetter("name"), tree2.iterdir())
    )
    for p1 in tree1.iterdir():
        p2 = tree2 / p1.name
        assert p1.is_dir() == p2.is_dir()
        if p1.is_dir():
            assert_dirtrees_eq(p1, p2)
        # TODO: Considering using the identify library to test for binary-ness.
        # (We can't use mimetypes, as .json maps to application/json instead of
        # text/json.)
        elif p1.suffix in {".txt", ".py", ".json"}:
            assert p1.read_text() == p2.read_text()
        else:
            assert p1.read_bytes() == p2.read_bytes()


def zarr_format_of(path: Path) -> str:
    """
    Return the Zarr serialisation format ("2" or "3") of the tree at ``path``.

    Thin test-only wrapper around `get_zarr_format_version` that asserts the
    format could be determined — used by tests that have just called
    ``zarr.save(...)`` and so know the path is a valid Zarr store.
    """
    fmt = get_zarr_format_version(path)
    assert fmt is not None, f"Path {path} is not a recognised Zarr store"
    return fmt


class TwoArrayZarrLayout(TypedDict):
    files: list[str]
    files_and_dirs: list[str]
    root_meta: str


# Per-Zarr-format expected on-disk paths for the canonical
# ``zarr.save(p, arr_0, arr_1)`` two-array sample used by upload/download
# tests. V2 writes ``.zgroup`` / ``arr_X/.zarray`` / ``arr_X/0``; V3 writes
# ``zarr.json`` / ``arr_X/zarr.json`` / ``arr_X/c/0``.
TWO_ARRAY_ZARR_LAYOUT: dict[str, TwoArrayZarrLayout] = {
    "2": {
        "files": [
            ".zgroup",
            "arr_0/.zarray",
            "arr_0/0",
            "arr_1/.zarray",
            "arr_1/0",
        ],
        "files_and_dirs": [
            ".zgroup",
            "arr_0",
            "arr_0/.zarray",
            "arr_0/0",
            "arr_1",
            "arr_1/.zarray",
            "arr_1/0",
        ],
        "root_meta": ".zgroup",
    },
    "3": {
        "files": [
            "arr_0/c/0",
            "arr_0/zarr.json",
            "arr_1/c/0",
            "arr_1/zarr.json",
            "zarr.json",
        ],
        "files_and_dirs": [
            "arr_0",
            "arr_0/c",
            "arr_0/c/0",
            "arr_0/zarr.json",
            "arr_1",
            "arr_1/c",
            "arr_1/c/0",
            "arr_1/zarr.json",
            "zarr.json",
        ],
        "root_meta": "zarr.json",
    },
}
