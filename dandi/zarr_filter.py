"""
Filtering of entries within Zarr assets for partial download.

Provides filter parsing, matching, and predefined aliases for selecting
subsets of entries within Zarr assets (e.g., only metadata files).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
import re
from typing import Callable, Literal


@dataclass
class ZarrFilter:
    """Filter for selecting entries within a Zarr asset."""

    filter_type: Literal["glob", "path", "regex"]
    pattern: str
    _compiled_regex: re.Pattern[str] | None = field(
        init=False, default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if self.filter_type == "regex":
            try:
                self._compiled_regex = re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern {self.pattern!r}: {e}") from e

    def matches(self, entry_path: str) -> bool:
        """Test if a zarr-internal path matches this filter.

        Parameters
        ----------
        entry_path : str
            A zarr-internal path like ``"0/0/0/.zarray"`` (no leading slash).

        Returns
        -------
        bool
            True if the path matches, False otherwise.
        """
        if self.filter_type == "glob":
            return _glob_match(self.pattern, entry_path)
        elif self.filter_type == "path":
            # Prefix match: the entry path equals the pattern or is under it
            return entry_path == self.pattern or entry_path.startswith(
                self.pattern.rstrip("/") + "/"
            )
        elif self.filter_type == "regex":
            assert self._compiled_regex is not None
            return self._compiled_regex.search(entry_path) is not None
        else:
            raise ValueError(f"Unknown filter type: {self.filter_type!r}")


def _glob_match(pattern: str, path: str) -> bool:
    """Match a glob pattern against a zarr-internal path.

    Supports ``*`` (within a single component) and ``**`` (across directories),
    consistent with ``fnmatchcase`` semantics used elsewhere in the codebase
    (``BasePath.match()``, ``RemoteZarrEntry.match()``).
    """
    patparts = [p for p in pattern.split("/") if p]
    pathparts = [p for p in path.split("/") if p]
    # Collapse consecutive ** into a single ** to avoid exponential backtracking
    collapsed: list[str] = []
    for p in patparts:
        if p == "**" and collapsed and collapsed[-1] == "**":
            continue
        collapsed.append(p)
    return _glob_match_parts(collapsed, pathparts)


def _glob_match_parts(patparts: list[str], pathparts: list[str]) -> bool:
    """Recursively match pattern parts against path parts."""
    pi = 0  # pattern index
    si = 0  # path (string) index
    while pi < len(patparts) and si < len(pathparts):
        if patparts[pi] == "**":
            # ** matches zero or more path components
            # Try matching the rest of the pattern against every suffix
            for k in range(si, len(pathparts) + 1):
                if _glob_match_parts(patparts[pi + 1 :], pathparts[k:]):
                    return True
            return False
        elif fnmatchcase(pathparts[si], patparts[pi]):
            pi += 1
            si += 1
        else:
            return False
    # Handle trailing ** which can match zero components
    while pi < len(patparts) and patparts[pi] == "**":
        pi += 1
    return pi == len(patparts) and si == len(pathparts)


ZARR_FILTER_ALIASES: dict[str, list[ZarrFilter]] = {
    "metadata": [
        ZarrFilter("glob", "**/.z*"),
        ZarrFilter("glob", "**/zarr.json"),
        ZarrFilter("glob", "**/.zmetadata"),
    ],
}


def parse_zarr_filter(spec: str) -> list[ZarrFilter]:
    """Parse a ``--zarr`` filter spec like ``'glob:**/.z*'`` or ``'metadata'``.

    Parameters
    ----------
    spec : str
        Either a predefined alias (e.g., ``"metadata"``) or a
        ``TYPE:PATTERN`` string where TYPE is ``glob``, ``path``, or ``regex``.

    Returns
    -------
    list[ZarrFilter]
        One or more filters (aliases may expand to multiple).

    Raises
    ------
    ValueError
        If the spec is not a valid alias or ``TYPE:PATTERN`` string,
        or if a regex pattern is invalid.
    """
    if spec in ZARR_FILTER_ALIASES:
        return list(ZARR_FILTER_ALIASES[spec])
    type_, _, pattern = spec.partition(":")
    if not pattern:
        raise ValueError(
            f"Invalid zarr filter: {spec!r}. "
            f"Expected TYPE:PATTERN or one of {list(ZARR_FILTER_ALIASES)}"
        )
    if type_ not in ("glob", "path", "regex"):
        raise ValueError(
            f"Unknown zarr filter type: {type_!r}. Expected 'glob', 'path', or 'regex'"
        )
    # type_ is validated above; narrow str -> Literal for the dataclass
    return [ZarrFilter(type_, pattern)]  # type: ignore[arg-type]


def make_zarr_entry_filter(filters: list[ZarrFilter]) -> Callable[[str], bool]:
    """Return a predicate that tests whether a zarr entry path should be included.

    Multiple filters are combined with OR semantics: an entry is included
    if it matches **any** of the provided filters.

    Parameters
    ----------
    filters : list[ZarrFilter]
        Filters to combine.  An empty list produces a predicate that
        rejects every path.

    Returns
    -------
    Callable[[str], bool]
        A predicate ``(entry_path) -> bool``; returns True to include.
    """

    def predicate(entry_path: str) -> bool:
        return any(f.matches(entry_path) for f in filters)

    return predicate
