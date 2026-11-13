from __future__ import annotations

import pytest

from ..misctypes import (
    _match_parts,
    _path_stem,
    _path_suffix,
    _path_suffixes,
    _split_path,
)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "name,suffix,suffixes,stem",
    [
        ("foo.txt", ".txt", [".txt"], "foo"),
        ("foo.tar.gz", ".gz", [".tar", ".gz"], "foo.tar"),
        ("foo", "", [], "foo"),
        (".bashrc", "", [], ".bashrc"),
        ("foo.", "", [], "foo."),
        ("..foo.txt", ".txt", [".txt"], "..foo"),
    ],
)
def test_path_suffix_suffixes_stem(
    name: str, suffix: str, suffixes: list[str], stem: str
) -> None:
    assert _path_suffix(name) == suffix
    assert _path_suffixes(name) == suffixes
    assert _path_stem(name) == stem


@pytest.mark.ai_generated
def test_split_path() -> None:
    assert _split_path("a/b//c/") == ("a", "b", "c")
    assert _split_path("") == ()
    with pytest.raises(ValueError, match="Absolute paths not allowed"):
        _split_path("/a")


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "pattern,result",
    [
        ("*.txt", True),
        ("b/*.txt", True),
        ("a/b/c.txt", True),
        ("x/b/*.txt", False),
        ("*.dat", False),
        ("z/a/b/c.txt", False),
    ],
)
def test_match_parts(pattern: str, result: bool) -> None:
    assert _match_parts(("a", "b", "c.txt"), pattern) is result


@pytest.mark.ai_generated
def test_match_parts_invalid_pattern() -> None:
    with pytest.raises(ValueError, match="Empty pattern"):
        _match_parts(("a",), "")
    with pytest.raises(ValueError, match="Absolute paths not allowed"):
        _match_parts(("a",), "/a")
