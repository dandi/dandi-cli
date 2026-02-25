from __future__ import annotations

import pytest

from ..metadata.brain_areas import (
    _parse_location_string,
    locations_to_anatomy,
    match_location_to_allen,
)


@pytest.mark.ai_generated
class TestParseLocationString:
    @pytest.mark.parametrize(
        "input_str, expected",
        [
            ("VISp", ["VISp"]),
            ("Primary visual area", ["Primary visual area"]),
            ("VISp,VISrl,VISlm", ["VISp", "VISrl", "VISlm"]),
            ("VISp, VISrl, VISlm", ["VISp", "VISrl", "VISlm"]),
            ("area: VISp, depth: 175", ["VISp"]),
            ("VISp, unknown, CA1", ["VISp", "CA1"]),
        ],
    )
    def test_parses_locations(self, input_str: str, expected: list[str]) -> None:
        assert _parse_location_string(input_str) == expected

    @pytest.mark.parametrize(
        "input_str",
        [
            "{'area': 'VISp', 'depth': '20'}",
            "{'region_name': 'VISp', 'depth': '20'}",
        ],
    )
    def test_dict_literal_extracts_visp(self, input_str: str) -> None:
        assert "VISp" in _parse_location_string(input_str)

    @pytest.mark.parametrize(
        "input_str",
        ["unknown", "none", "n/a", "brain", "", "   "],
    )
    def test_trivial_returns_empty(self, input_str: str) -> None:
        assert _parse_location_string(input_str) == []


@pytest.mark.ai_generated
class TestMatchLocationToAllen:
    @pytest.mark.parametrize(
        "token, expected_name",
        [
            ("VISp", "Primary visual area"),
            ("visp", "Primary visual area"),
            ("Primary visual area", "Primary visual area"),
            ("primary visual area", "Primary visual area"),
        ],
    )
    def test_matches(self, token: str, expected_name: str) -> None:
        result = match_location_to_allen(token)
        assert result is not None
        assert "MBA_" in str(result.identifier)
        assert result.name == expected_name

    @pytest.mark.parametrize("token", ["nonexistent_area_xyz", ""])
    def test_no_match(self, token: str) -> None:
        assert match_location_to_allen(token) is None

    def test_ca1(self) -> None:
        result = match_location_to_allen("CA1")
        assert result is not None
        assert "CA1" in result.name or "Field CA1" in result.name


@pytest.mark.ai_generated
class TestLocationsToAnatomy:
    def test_basic(self) -> None:
        result = locations_to_anatomy(["VISp"])
        assert len(result) == 1
        assert result[0].name == "Primary visual area"

    def test_deduplication(self) -> None:
        result = locations_to_anatomy(["VISp", "VISp", "visp"])
        assert len(result) == 1

    def test_multiple_locations(self) -> None:
        result = locations_to_anatomy(["VISp", "CA1"])
        assert len(result) == 2

    @pytest.mark.parametrize(
        "locations",
        [
            [],
            ["nonexistent_xyz"],
            ["unknown", "n/a", "none"],
        ],
    )
    def test_returns_empty(self, locations: list[str]) -> None:
        assert locations_to_anatomy(locations) == []

    def test_mixed_matched_unmatched(self) -> None:
        result = locations_to_anatomy(["VISp", "nonexistent_xyz"])
        assert len(result) == 1

    def test_comma_separated_input(self) -> None:
        result = locations_to_anatomy(["VISp,CA1"])
        assert len(result) == 2
