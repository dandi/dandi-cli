"""I/O utilities for validation results in JSONL format.

Provides functions for writing, appending, and loading validation results
as JSONL (JSON Lines) files — one ValidationResult per line.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ._types import ValidationResult


def write_validation_jsonl(
    results: list[ValidationResult],
    path: str | Path,
    *,
    append: bool = False,
) -> Path:
    """Write validation results to a JSONL file.

    Parameters
    ----------
    results
        List of ValidationResult objects to write.
    path
        File path to write to.  Created if it does not exist.
    append
        If True, append to an existing file instead of overwriting.

    Returns
    -------
    Path
        The path written to (as a Path object).
    """
    path = Path(path)
    with path.open("a" if append else "w") as f:
        for r in results:
            f.write(r.model_dump_json())
            f.write("\n")
    return path


def load_validation_jsonl(paths: Iterable[str | Path]) -> list[ValidationResult]:
    """Load and concatenate validation results from one or more JSONL files.

    Parameters
    ----------
    paths
        Iterable of file paths to load from.

    Returns
    -------
    list[ValidationResult]
        All results from all files, in order.
    """
    results: list[ValidationResult] = []
    for p in paths:
        p = Path(p)
        with p.open() as f:
            for line in f:
                if line := line.strip():
                    results.append(ValidationResult.model_validate_json(line))
    return results


def validation_companion_path(logfile: str | Path) -> Path:
    """Derive the validation companion path from a logfile path.

    The companion is placed next to the logfile with ``_validation.jsonl``
    appended to the stem.

    Parameters
    ----------
    logfile
        Path to the logfile.

    Returns
    -------
    Path
        Path to the companion file.
    """
    logfile = Path(logfile)
    return logfile.parent / (logfile.stem + "_validation.jsonl")
