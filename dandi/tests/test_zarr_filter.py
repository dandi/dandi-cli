"""Tests for dandi.zarr_filter module."""

from __future__ import annotations

import pytest

from dandi.zarr_filter import (
    ZARR_FILTER_ALIASES,
    ZarrFilter,
    make_zarr_entry_filter,
    parse_zarr_filter,
)

# Sample paths representing entries inside a Zarr asset
SAMPLE_PATHS = [
    ".zgroup",
    ".zattrs",
    ".zmetadata",
    "zarr.json",
    "0/.zarray",
    "0/.zattrs",
    "0/0/0",
    "0/0/1",
    "0/1/0",
    "1/.zarray",
    "1/0/0",
    "1/0/1",
    "scale0/.zarray",
    "scale0/0/0/0",
    "scale0/0/0/1",
]


class TestZarrFilterGlob:
    @pytest.mark.ai_generated
    @pytest.mark.parametrize(
        "pattern,path,expected",
        [
            # ** matches across directories
            ("**/.z*", ".zgroup", True),
            ("**/.z*", ".zattrs", True),
            ("**/.z*", "0/.zarray", True),
            ("**/.z*", "0/.zattrs", True),
            ("**/.z*", "0/0/0", False),
            ("**/.z*", "zarr.json", False),
            # ** with specific filename
            ("**/zarr.json", "zarr.json", True),
            ("**/zarr.json", "sub/zarr.json", True),
            ("**/zarr.json", ".zgroup", False),
            # ** matches .zmetadata
            ("**/.zmetadata", ".zmetadata", True),
            ("**/.zmetadata", "sub/.zmetadata", True),
            ("**/.zmetadata", ".zgroup", False),
            # * within a single component
            ("0/*", "0/.zarray", True),
            ("0/*", "0/.zattrs", True),
            ("0/*", "0/0/0", False),  # * does not cross /
            ("0/*", "1/.zarray", False),
            # Exact component match
            ("0/0/0", "0/0/0", True),
            ("0/0/0", "0/0/1", False),
            # Pattern with * in middle
            ("scale*/.zarray", "scale0/.zarray", True),
            ("scale*/.zarray", "scale1/.zarray", True),
            ("scale*/.zarray", "0/.zarray", False),
        ],
    )
    def test_glob_match(self, pattern: str, path: str, expected: bool) -> None:
        f = ZarrFilter("glob", pattern)
        assert f.matches(path) is expected


class TestZarrFilterPath:
    @pytest.mark.ai_generated
    @pytest.mark.parametrize(
        "pattern,path,expected",
        [
            # Exact match
            ("0/0/0", "0/0/0", True),
            # Prefix match
            ("0", "0/.zarray", True),
            ("0", "0/0/0", True),
            ("0/0", "0/0/0", True),
            ("0/0", "0/0/1", True),
            # Not a prefix
            ("0/0", "0/1/0", False),
            ("1", "0/0/0", False),
            # Trailing slash in pattern
            ("0/", "0/.zarray", True),
            ("0/", "0/0/0", True),
            # No false prefix match (0 should not match 01)
            ("0", "01/data", False),
        ],
    )
    def test_path_match(self, pattern: str, path: str, expected: bool) -> None:
        f = ZarrFilter("path", pattern)
        assert f.matches(path) is expected


class TestZarrFilterRegex:
    @pytest.mark.ai_generated
    @pytest.mark.parametrize(
        "pattern,path,expected",
        [
            (r"\.z(array|group|attrs)$", ".zgroup", True),
            (r"\.z(array|group|attrs)$", "0/.zarray", True),
            (r"\.z(array|group|attrs)$", "0/0/0", False),
            (r"^0/0/", "0/0/0", True),
            (r"^0/0/", "0/0/1", True),
            (r"^0/0/", "0/1/0", False),
            (r"zarr\.json$", "zarr.json", True),
            (r"zarr\.json$", "sub/zarr.json", True),
        ],
    )
    def test_regex_match(self, pattern: str, path: str, expected: bool) -> None:
        f = ZarrFilter("regex", pattern)
        assert f.matches(path) is expected


class TestParseZarrFilter:
    @pytest.mark.ai_generated
    def test_parse_glob(self) -> None:
        filters = parse_zarr_filter("glob:**/.z*")
        assert len(filters) == 1
        assert filters[0].filter_type == "glob"
        assert filters[0].pattern == "**/.z*"

    @pytest.mark.ai_generated
    def test_parse_path(self) -> None:
        filters = parse_zarr_filter("path:0/0")
        assert len(filters) == 1
        assert filters[0].filter_type == "path"
        assert filters[0].pattern == "0/0"

    @pytest.mark.ai_generated
    def test_parse_regex(self) -> None:
        filters = parse_zarr_filter(r"regex:\.zarray$")
        assert len(filters) == 1
        assert filters[0].filter_type == "regex"
        assert filters[0].pattern == r"\.zarray$"

    @pytest.mark.ai_generated
    def test_parse_alias_metadata(self) -> None:
        filters = parse_zarr_filter("metadata")
        assert len(filters) == len(ZARR_FILTER_ALIASES["metadata"])
        # Should be separate objects (not the alias list itself)
        assert filters is not ZARR_FILTER_ALIASES["metadata"]
        for f, expected in zip(filters, ZARR_FILTER_ALIASES["metadata"]):
            assert f.filter_type == expected.filter_type
            assert f.pattern == expected.pattern

    @pytest.mark.ai_generated
    def test_parse_invalid_no_colon(self) -> None:
        with pytest.raises(ValueError, match="Invalid zarr filter"):
            parse_zarr_filter("notanalias")

    @pytest.mark.ai_generated
    def test_parse_invalid_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown zarr filter type"):
            parse_zarr_filter("badtype:pattern")

    @pytest.mark.ai_generated
    def test_parse_pattern_with_colon(self) -> None:
        """Pattern containing a colon should keep everything after the first colon."""
        filters = parse_zarr_filter("regex:a:b")
        assert filters[0].pattern == "a:b"


class TestMakeZarrEntryFilter:
    @pytest.mark.ai_generated
    def test_or_composition(self) -> None:
        """Multiple filters should combine with OR semantics."""
        filters = [
            ZarrFilter("glob", "**/.z*"),
            ZarrFilter("path", "0/0"),
        ]
        predicate = make_zarr_entry_filter(filters)
        # Matches glob
        assert predicate(".zgroup") is True
        assert predicate("1/.zarray") is True
        # Matches path prefix
        assert predicate("0/0/0") is True
        assert predicate("0/0/1") is True
        # Matches neither
        assert predicate("1/0/0") is False

    @pytest.mark.ai_generated
    def test_metadata_alias_matches_all_metadata(self) -> None:
        """The 'metadata' alias should match typical Zarr metadata files."""
        filters = parse_zarr_filter("metadata")
        predicate = make_zarr_entry_filter(filters)
        # Zarr v2 metadata
        assert predicate(".zgroup") is True
        assert predicate(".zattrs") is True
        assert predicate(".zmetadata") is True
        assert predicate("0/.zarray") is True
        assert predicate("0/.zattrs") is True
        # Zarr v3 metadata
        assert predicate("zarr.json") is True
        assert predicate("sub/zarr.json") is True
        # Data chunks should NOT match
        assert predicate("0/0/0") is False
        assert predicate("0/0/1") is False

    @pytest.mark.ai_generated
    def test_single_filter(self) -> None:
        predicate = make_zarr_entry_filter([ZarrFilter("path", "scale0")])
        assert predicate("scale0/0/0/0") is True
        assert predicate("scale0/.zarray") is True
        assert predicate("0/0/0") is False

    @pytest.mark.ai_generated
    def test_empty_filter_list(self) -> None:
        """Empty filter list should match nothing."""
        predicate = make_zarr_entry_filter([])
        assert predicate("anything") is False
