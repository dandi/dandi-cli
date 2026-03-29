from __future__ import annotations

import pytest

from ..metadata.brain_areas import (
    _parse_location_string,
    locations_to_ccf_mouse_anatomy,
    locations_to_mouse_anatomy,
    locations_to_uberon_anatomy,
    match_location_to_allen,
    match_location_to_uberon,
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
            # Dict literal with no known area key → _non_trivial_values fallback
            ("{'custom': 'VISp', 'depth': '20'}", ["VISp"]),
            # Key-value format with no known area key → _non_trivial_values fallback
            ("custom: VISp, depth: 175", ["VISp"]),
            # Dict literal with flexible key names (hyphens/underscores)
            ("{'brain-area': 'VISp', 'depth': '20'}", ["VISp"]),
            ("{'brain_region': 'CA1'}", ["CA1"]),
            # Dict literal where area key has trivial value → _non_trivial_values
            ("{'area': 'unknown', 'tag': 'VISp'}", ["VISp"]),
            # Non-dict set literal starting with { → falls through to comma split
            ("{1, 2, 3}", ["{1", "2", "3}"]),
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

    def test_malformed_dict_literal(self) -> None:
        """Dict-like string that fails ast.literal_eval falls through."""
        result = _parse_location_string("{not valid python}")
        # Falls through to key-value parser or simple string
        assert isinstance(result, list)
        assert len(result) > 0

    def test_url_skips_kv_parser(self) -> None:
        """Strings containing :// should not be parsed as key-value pairs."""
        result = _parse_location_string("http://example.com/brain")
        assert result == ["http://example.com/brain"]


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
        assert result.name is not None and (
            "CA1" in result.name or "Field CA1" in result.name
        )


@pytest.mark.ai_generated
class TestLocationsToAnatomy:
    def test_basic(self) -> None:
        result = locations_to_ccf_mouse_anatomy(["VISp"])
        assert len(result) == 1
        assert result[0].name == "Primary visual area"

    def test_deduplication(self) -> None:
        result = locations_to_ccf_mouse_anatomy(["VISp", "VISp", "visp"])
        assert len(result) == 1

    def test_multiple_locations(self) -> None:
        result = locations_to_ccf_mouse_anatomy(["VISp", "CA1"])
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
        assert locations_to_ccf_mouse_anatomy(locations) == []

    def test_mixed_matched_unmatched(self) -> None:
        result = locations_to_ccf_mouse_anatomy(["VISp", "nonexistent_xyz"])
        assert len(result) == 1

    def test_comma_separated_input(self) -> None:
        result = locations_to_ccf_mouse_anatomy(["VISp,CA1"])
        assert len(result) == 2


@pytest.mark.ai_generated
class TestMatchLocationToUberon:
    @pytest.mark.parametrize(
        "token, expected_name",
        [
            ("brain", "brain"),
            ("hippocampal formation", "hippocampal formation"),
            ("primary visual cortex", "primary visual cortex"),
            ("cerebral cortex", "cerebral cortex"),
        ],
    )
    def test_matches(self, token: str, expected_name: str) -> None:
        result = match_location_to_uberon(token)
        assert result is not None
        assert "UBERON_" in str(result.identifier)
        assert result.name == expected_name

    def test_case_insensitive(self) -> None:
        result = match_location_to_uberon("Hippocampal Formation")
        assert result is not None
        assert result.name == "hippocampal formation"

    def test_exact_synonym(self) -> None:
        # "brain fornix" is an EXACT synonym for "fornix of brain"
        result = match_location_to_uberon("brain fornix")
        assert result is not None
        assert result.name == "fornix of brain"

    def test_related_synonym_excluded_by_default(self) -> None:
        # "encephalon" is a RELATED synonym for "brain"
        result = match_location_to_uberon("encephalon")
        assert result is None

    def test_related_synonym_included_when_requested(self) -> None:
        result = match_location_to_uberon(
            "encephalon", synonym_scopes=frozenset({"EXACT", "RELATED"})
        )
        assert result is not None
        assert result.name == "brain"

    @pytest.mark.parametrize("token", ["nonexistent_area_xyz", ""])
    def test_no_match(self, token: str) -> None:
        assert match_location_to_uberon(token) is None

    def test_ca1_synonym(self) -> None:
        # CA1 is an exact synonym for "CA1 field of hippocampus"
        result = match_location_to_uberon("CA1")
        assert result is not None
        assert result.name is not None and "CA1" in result.name


@pytest.mark.ai_generated
class TestLocationsToUberonAnatomy:
    def test_basic(self) -> None:
        result = locations_to_uberon_anatomy(["hippocampal formation"])
        assert len(result) == 1
        assert result[0].name == "hippocampal formation"

    def test_deduplication(self) -> None:
        result = locations_to_uberon_anatomy(
            ["hippocampal formation", "Hippocampal Formation"]
        )
        assert len(result) == 1

    def test_empty(self) -> None:
        assert locations_to_uberon_anatomy([]) == []

    def test_unmatched(self) -> None:
        assert locations_to_uberon_anatomy(["nonexistent_xyz"]) == []


@pytest.mark.ai_generated
class TestLocationsToMouseAnatomy:
    def test_allen_preferred(self) -> None:
        """Allen CCF match should be used over UBERON for mouse."""
        result = locations_to_mouse_anatomy(["VISp"])
        assert len(result) == 1
        assert "MBA_" in str(result[0].identifier)

    def test_uberon_fallback(self) -> None:
        """Tokens not in Allen CCF should fall back to UBERON."""
        # "visual cortex" is in UBERON but not Allen CCF
        result = locations_to_mouse_anatomy(["visual cortex"])
        assert len(result) == 1
        assert "UBERON_" in str(result[0].identifier)

    def test_mixed_allen_and_uberon(self) -> None:
        """Allen-matched and UBERON-matched tokens should coexist."""
        result = locations_to_mouse_anatomy(["VISp", "visual cortex"])
        assert len(result) == 2
        identifiers = {str(r.identifier) for r in result}
        assert any("MBA_" in i for i in identifiers)
        assert any("UBERON_" in i for i in identifiers)

    def test_deduplication(self) -> None:
        result = locations_to_mouse_anatomy(["VISp", "VISp"])
        assert len(result) == 1
