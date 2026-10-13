"""
Mapping of BIDS schema versions to the BIDS versions they belong to

The deno-compiled BIDS validator reports only the version of the BIDS schema it
validates against, not the version of BIDS; see
https://github.com/bids-standard/bids-validator/issues/10#issuecomment-2848121538.
Until it does, the BIDS version is looked up in the mapping that bids-schema
publishes (https://github.com/bids-standard/bids-schema/issues/20): first in the
copy bundled as ``schema_to_bids.json`` next to this module (refresh it from
`SCHEMA_TO_BIDS_URL`), then, for schema versions newer than that copy, in the
published one.
"""

from __future__ import annotations

from functools import cache
import json
from pathlib import Path
from typing import Any

import requests

from dandi import get_logger

lgr = get_logger()

SCHEMA_TO_BIDS_URL = (
    "https://raw.githubusercontent.com/bids-standard/bids-schema/main/"
    "versions/schema_to_bids.json"
)

_BUNDLED_SCHEMA_TO_BIDS = Path(__file__).with_name("schema_to_bids.json")


def get_bids_version(schema_version: str | None) -> str | None:
    """
    Return the BIDS version that a BIDS schema version belongs to

    Parameters
    ----------
    schema_version : str | None
        A BIDS schema version, as reported by the BIDS validator, e.g. ``"1.2.1"``

    Returns
    -------
    str | None
        The BIDS version, e.g. ``"1.11.1"``.  For a schema released between BIDS
        releases, the preceding BIDS release followed by the number of commits
        since it and the commit of the schema release, e.g.
        ``"1.11.1+22-ge37e21053"``.  `None` if ``schema_version`` is `None` or
        unknown.
    """
    if schema_version is None:
        return None
    if (bids_version := _bundled_mapping().get(schema_version)) is None:
        bids_version = _published_mapping().get(schema_version)
    return bids_version


def _parse_mapping(data: Any) -> dict[str, str]:
    return {
        schema_version: record["bids_version"]
        for schema_version, record in data["schemas"].items()
        if record["bids_version"] is not None
    }


@cache
def _bundled_mapping() -> dict[str, str]:
    return _parse_mapping(json.loads(_BUNDLED_SCHEMA_TO_BIDS.read_text()))


@cache
def _published_mapping() -> dict[str, str]:
    try:
        r = requests.get(SCHEMA_TO_BIDS_URL, timeout=10)
        r.raise_for_status()
        return _parse_mapping(r.json())
    except Exception as e:
        # Without it, we just do not know the BIDS version
        lgr.warning(
            "Failed to obtain mapping of BIDS schema versions to BIDS versions "
            "from %s: %s",
            SCHEMA_TO_BIDS_URL,
            e,
        )
        return {}
