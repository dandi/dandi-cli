from __future__ import annotations

import pytest

from ..metadata.brain_areas import (
    _parse_location_string,
    locations_to_anatomy,
    match_location_to_allen,
)


@pytest.mark.ai_generated
class TestParseLocationString:
    def test_simple_acronym(self) -> None:
        assert _parse_location_string("VISp") == ["VISp"]

    def test_simple_name(self) -> None:
        assert _parse_location_string("Primary visual area") == ["Primary visual area"]

    def test_comma_separated(self) -> None:
        assert _parse_location_string("VISp,VISrl,VISlm") == ["VISp", "VISrl", "VISlm"]

    def test_comma_separated_with_spaces(self) -> None:
        assert _parse_location_string("VISp, VISrl, VISlm") == [
            "VISp",
            "VISrl",
            "VISlm",
        ]

    def test_dict_literal_with_area(self) -> None:
        result = _parse_location_string("{'area': 'VISp', 'depth': '20'}")
        assert result == ["VISp"]

    def test_dict_literal_no_area_key(self) -> None:
        result = _parse_location_string("{'region_name': 'VISp', 'depth': '20'}")
        # Should return non-numeric string values
        assert "VISp" in result

    def test_key_value_pairs(self) -> None:
        result = _parse_location_string("area: VISp, depth: 175")
        assert result == ["VISp"]

    def test_trivial_unknown(self) -> None:
        assert _parse_location_string("unknown") == []

    def test_trivial_none(self) -> None:
        assert _parse_location_string("none") == []

    def test_trivial_na(self) -> None:
        assert _parse_location_string("n/a") == []

    def test_trivial_brain(self) -> None:
        assert _parse_location_string("brain") == []

    def test_empty_string(self) -> None:
        assert _parse_location_string("") == []

    def test_whitespace_only(self) -> None:
        assert _parse_location_string("   ") == []

    def test_comma_list_with_trivial(self) -> None:
        result = _parse_location_string("VISp, unknown, CA1")
        assert result == ["VISp", "CA1"]


@pytest.mark.ai_generated
class TestMatchLocationToAllen:
    def test_exact_acronym(self) -> None:
        result = match_location_to_allen("VISp")
        assert result is not None
        assert "MBA_" in str(result.identifier)
        assert result.name == "Primary visual area"

    def test_case_insensitive_acronym(self) -> None:
        result = match_location_to_allen("visp")
        assert result is not None
        assert result.name == "Primary visual area"

    def test_exact_name(self) -> None:
        result = match_location_to_allen("Primary visual area")
        assert result is not None
        assert "MBA_" in str(result.identifier)

    def test_case_insensitive_name(self) -> None:
        result = match_location_to_allen("primary visual area")
        assert result is not None
        assert "MBA_" in str(result.identifier)

    def test_no_match(self) -> None:
        result = match_location_to_allen("nonexistent_area_xyz")
        assert result is None

    def test_empty_string(self) -> None:
        result = match_location_to_allen("")
        assert result is None

    def test_ca1(self) -> None:
        result = match_location_to_allen("CA1")
        assert result is not None
        assert result.name is not None
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

    def test_empty_list(self) -> None:
        result = locations_to_anatomy([])
        assert result == []

    def test_all_unmatched(self) -> None:
        result = locations_to_anatomy(["nonexistent_xyz"])
        assert result == []

    def test_mixed_matched_unmatched(self) -> None:
        result = locations_to_anatomy(["VISp", "nonexistent_xyz"])
        assert len(result) == 1

    def test_trivial_values_filtered(self) -> None:
        result = locations_to_anatomy(["unknown", "n/a", "none"])
        assert result == []

    def test_comma_separated_input(self) -> None:
        result = locations_to_anatomy(["VISp,CA1"])
        assert len(result) == 2
