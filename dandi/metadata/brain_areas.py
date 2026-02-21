from __future__ import annotations

import ast
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

from dandischema import models

from .. import get_logger

lgr = get_logger()

MBAO_URI_TEMPLATE = "http://purl.obolibrary.org/obo/MBA_{}"

# Values that should be treated as missing / uninformative
_TRIVIAL_VALUES = frozenset(
    {
        "",
        "unknown",
        "none",
        "n/a",
        "na",
        "null",
        "unspecified",
        "not available",
        "not applicable",
        "brain",
    }
)


@lru_cache(maxsize=1)
def _load_allen_structures() -> list[dict[str, Any]]:
    """Load the bundled Allen CCF structures JSON."""
    data_path = (
        Path(__file__).resolve().parent.parent / "data" / "allen_ccf_structures.json"
    )
    with open(data_path) as f:
        structures: list[dict[str, Any]] = json.load(f)
    return structures


@lru_cache(maxsize=1)
def _build_lookup_dicts() -> (
    tuple[dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict]]
):
    """Build lookup dictionaries for Allen CCF structures.

    Returns
    -------
    tuple of 4 dicts
        (acronym_exact, acronym_lower, name_exact, name_lower)
    """
    structures = _load_allen_structures()
    acronym_exact: dict[str, dict] = {}
    acronym_lower: dict[str, dict] = {}
    name_exact: dict[str, dict] = {}
    name_lower: dict[str, dict] = {}
    for s in structures:
        acr = s["acronym"]
        name = s["name"]
        # First match wins (structures are sorted by id)
        if acr not in acronym_exact:
            acronym_exact[acr] = s
        acr_low = acr.lower()
        if acr_low not in acronym_lower:
            acronym_lower[acr_low] = s
        if name not in name_exact:
            name_exact[name] = s
        name_low = name.lower()
        if name_low not in name_lower:
            name_lower[name_low] = s
    return acronym_exact, acronym_lower, name_exact, name_lower


def _parse_location_string(location: str) -> list[str]:
    """Parse a raw NWB location string into area tokens.

    Handles:
    - Simple strings: ``"VISp"``
    - Dict literals: ``"{'area': 'VISp', 'depth': '20'}"``
    - Key-value pairs: ``"area: VISp, depth: 175"``
    - Comma-separated lists: ``"VISp,VISrl,VISlm"``
    """
    location = location.strip()
    if not location or location.lower() in _TRIVIAL_VALUES:
        return []

    # Try dict literal (e.g. "{'area': 'VISp', 'depth': 20}")
    if location.startswith("{"):
        try:
            d = ast.literal_eval(location)
            if isinstance(d, dict):
                # Look for known area keys
                for key in ("area", "location", "region", "brain_area", "brain_region"):
                    val = d.get(key)
                    if val is not None:
                        val = str(val).strip()
                        if val and val.lower() not in _TRIVIAL_VALUES:
                            return [val]
                # If no known key, return all string values that are non-trivial
                tokens = []
                for val in d.values():
                    val = str(val).strip()
                    if val and val.lower() not in _TRIVIAL_VALUES:
                        # Skip purely numeric values (e.g. depth)
                        try:
                            float(val)
                        except ValueError:
                            tokens.append(val)
                return tokens
        except (ValueError, SyntaxError):
            pass  # Not a valid dict literal; fall through to other parsers

    # Try key-value format (e.g. "area: VISp, depth: 175")
    if re.search(r"\w+\s*:", location) and "://" not in location:
        pairs = re.split(r",\s*", location)
        kv: dict[str, str] = {}
        for pair in pairs:
            m = re.match(r"(\w+)\s*:\s*(.+)", pair.strip())
            if m:
                kv[m.group(1).lower()] = m.group(2).strip()
        if kv:
            for key in ("area", "location", "region", "brain_area", "brain_region"):
                val = kv.get(key)
                if val is not None and val.lower() not in _TRIVIAL_VALUES:
                    return [val]
            # Fall through — return non-trivial, non-numeric values
            tokens = []
            for val in kv.values():
                if val.lower() not in _TRIVIAL_VALUES:
                    try:
                        float(val)
                    except ValueError:
                        tokens.append(val)
            if tokens:
                return tokens

    # Comma-separated list
    if "," in location:
        tokens = [t.strip() for t in location.split(",")]
        return [t for t in tokens if t and t.lower() not in _TRIVIAL_VALUES]

    # Simple string
    return [location]


def match_location_to_allen(token: str) -> models.Anatomy | None:
    """Match a single location token against Allen CCF structures.

    Tries exact acronym, case-insensitive acronym, exact name,
    case-insensitive name in that order.

    Returns
    -------
    models.Anatomy or None
    """
    acronym_exact, acronym_lower, name_exact, name_lower = _build_lookup_dicts()
    token_stripped = token.strip()
    if not token_stripped:
        return None

    # 1. Exact acronym match
    s = acronym_exact.get(token_stripped)
    if s is not None:
        return _structure_to_anatomy(s)

    # 2. Case-insensitive acronym match
    s = acronym_lower.get(token_stripped.lower())
    if s is not None:
        return _structure_to_anatomy(s)

    # 3. Exact name match
    s = name_exact.get(token_stripped)
    if s is not None:
        return _structure_to_anatomy(s)

    # 4. Case-insensitive name match
    s = name_lower.get(token_stripped.lower())
    if s is not None:
        return _structure_to_anatomy(s)

    lgr.debug("Could not match brain location %r to Allen CCF", token_stripped)
    return None


def _structure_to_anatomy(s: dict[str, Any]) -> models.Anatomy:
    return models.Anatomy(
        identifier=MBAO_URI_TEMPLATE.format(s["id"]),
        name=s["name"],
    )


def locations_to_anatomy(locations: list[str]) -> list[models.Anatomy]:
    """Convert raw NWB location strings to deduplicated Anatomy list.

    Parameters
    ----------
    locations : list[str]
        Raw location strings from NWB file.

    Returns
    -------
    list[models.Anatomy]
        Matched and deduplicated anatomy entries.
    """
    seen_ids: set[str] = set()
    results: list[models.Anatomy] = []
    for loc in locations:
        tokens = _parse_location_string(loc)
        for token in tokens:
            anatomy = match_location_to_allen(token)
            if anatomy is not None:
                id_str = str(anatomy.identifier)
                if id_str not in seen_ids:
                    seen_ids.add(id_str)
                    results.append(anatomy)
    return results
