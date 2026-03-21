"""I/O utilities for validation results in JSONL format.

Provides functions for writing, appending, and loading validation results
as JSONL (JSON Lines) files — one ValidationResult per line.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .types import CURRENT_RECORD_VERSION, ValidationResult

lgr = logging.getLogger(__name__)


def write_validation_jsonl(
    results: list[ValidationResult],
    path: str | Path,
) -> Path:
    """Write validation results to a JSONL file, overwriting if it exists.

    Parameters
    ----------
    results
        List of ValidationResult objects to write.
    path
        File path to write to.

    Returns
    -------
    Path
        The path written to (as a Path object).
    """
    path = Path(path)
    with path.open("w") as f:
        for r in results:
            f.write(r.model_dump_json())
            f.write("\n")
    return path


def append_validation_jsonl(
    results: list[ValidationResult],
    path: str | Path,
) -> None:
    """Append validation results to a JSONL file.

    Parameters
    ----------
    results
        List of ValidationResult objects to append.
    path
        File path to append to.  Created if it does not exist.
    """
    path = Path(path)
    with path.open("a") as f:
        for r in results:
            f.write(r.model_dump_json())
            f.write("\n")


def load_validation_jsonl(*paths: str | Path) -> list[ValidationResult]:
    """Load and concatenate validation results from one or more JSONL files.

    Parameters
    ----------
    paths
        One or more file paths to load from.

    Returns
    -------
    list[ValidationResult]
        All results from all files, in order.
    """
    results: list[ValidationResult] = []
    for p in paths:
        p = Path(p)
        with p.open() as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                version = data.get("record_version", "0")
                if version != CURRENT_RECORD_VERSION:
                    lgr.warning(
                        "%s:%d: record_version %r != current %r, " "loading anyway",
                        p,
                        line_no,
                        version,
                        CURRENT_RECORD_VERSION,
                    )
                results.append(ValidationResult.model_validate_json(line))
    return results


def validation_sidecar_path(logfile: str | Path) -> Path:
    """Derive the validation sidecar path from a logfile path.

    The sidecar is placed next to the logfile with ``_validation.jsonl``
    appended to the stem.

    Parameters
    ----------
    logfile
        Path to the logfile.

    Returns
    -------
    Path
        Path to the sidecar file.
    """
    logfile = Path(logfile)
    return logfile.parent / (logfile.stem + "_validation.jsonl")
