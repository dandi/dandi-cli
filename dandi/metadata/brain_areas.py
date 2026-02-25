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


def _is_numeric(val: str) -> bool:
    """Return True if *val* looks like a number (int or float)."""
    try:
        float(val)
        return True
    except ValueError:
        return False


# Canonicalised area key names recognised in dict-style location strings.
# Keys are normalised by lowering, stripping whitespace, and removing hyphens
# and underscores so that "brain-area", "brain_area", "BrainArea" all match.
_AREA_KEYS = frozenset(
    {
        "area",
        "areaname",
        "brainarea",
        "brainregion",
        "location",
        "name",
        "region",
        "regionname",
    }
)


def _normalise_key(key: str) -> str:
    """Lower-case and strip spaces, hyphens, underscores from *key*."""
    return re.sub(r"[\s_-]", "", key).lower()


def _extract_area_from_dict(d: dict) -> str | None:
    """Return the first non-trivial area value from a dict with flexible key matching."""
    for key, val in d.items():
        if _normalise_key(str(key)) in _AREA_KEYS:
            val = str(val).strip()
            if val and val.lower() not in _TRIVIAL_VALUES:
                return val
    return None


def _parse_location_string(location: str) -> list[str]:
    """Parse a raw NWB location string into area tokens ignoring numerics etc.

    Handles:
    - Simple strings: ``"VISp"``
    - Dict literals: ``"{'area': 'VISp', 'depth': '20'}"``
    - Key-value pairs: ``"area: VISp, depth: 175"``
    - Comma-separated lists: ``"VISp,VISrl,VISlm"``

    In examples above, depth numerical values are getting ignored.
    """
    location = location.strip()
    if not location or location.lower() in _TRIVIAL_VALUES:
        return []

    # Try dict literal (e.g. "{'area': 'VISp', 'depth': 20}")
    if location.startswith("{"):
        try:
            d = ast.literal_eval(location)
            if isinstance(d, dict):
                val = _extract_area_from_dict(d)
                if val is not None:
                    return [val]
                # If no known key, return all non-trivial, non-numeric values
                tokens = []
                for v in d.values():
                    v = str(v).strip()
                    if v and v.lower() not in _TRIVIAL_VALUES and not _is_numeric(v):
                        tokens.append(v)
                return tokens
        except (ValueError, SyntaxError):
            lgr.debug("Location %r looks like a dict but failed to parse", location)

    # Try key-value format (e.g. "area: VISp, depth: 175")
    if re.search(r"\w+\s*:", location) and "://" not in location:
        pairs = re.split(r",\s*", location)
        kv: dict[str, str] = {}
        for pair in pairs:
            m = re.match(r"(\w+)\s*:\s*(.+)", pair.strip())
            if m:
                kv[m.group(1).lower()] = m.group(2).strip()
        if kv:
            val = _extract_area_from_dict(kv)
            if val is not None:
                return [val]
            # Fall through — return non-trivial, non-numeric values
            tokens = []
            for v in kv.values():
                if v.lower() not in _TRIVIAL_VALUES and not _is_numeric(v):
                    tokens.append(v)
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
