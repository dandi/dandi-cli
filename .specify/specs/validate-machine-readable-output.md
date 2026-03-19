# Design: Machine-Readable Validation Output with Store/Reload

## Summary

Add machine-readable output formats to `dandi validate`, support saving validation
results to disk, and reloading/re-rendering them later with different grouping,
filtering, and display options. This enables workflows like:

- Sweeping all BIDS example datasets or all DANDI datasets, storing results
- Storing validation errors during `upload` for later inspection
- Re-rendering stored results with alternative groupings/filters without re-running validation

## Related Issues & PRs

| # | Title | Status | Relevance |
|---|-------|--------|-----------|
| [#1515](https://github.com/dandi/dandi-cli/issues/1515) | `validate: Add -f\|--format option` | Open | Direct: requests JSON/YAML output formats |
| [#1753](https://github.com/dandi/dandi-cli/issues/1753) | Provide easy means for introspecting upload validation failures | Open | Direct: decouple execution from rendering via JSON dumps |
| [#1743](https://github.com/dandi/dandi-cli/pull/1743) | Add filtering of issues by type/ID or by file location | Draft | Related: post-validation filtering, blocked pending store/cache |
| [#1737](https://github.com/dandi/dandi-cli/issues/1737) | `upload,validate: Add --validators option` | Open | Related: selective validator control |
| [#1748](https://github.com/dandi/dandi-cli/issues/1748) | Tidy up the validate command function | Open | Prerequisite: refactor before adding options |
| [#1448](https://github.com/dandi/dandi-cli/issues/1448) | Align validation with server | Open | Consistency between client/server validation |
| [#1624](https://github.com/dandi/dandi-cli/pull/1624) | Serialize Severity by name | Merged | Prerequisite: meaningful JSON Severity output |
| [#1514](https://github.com/dandi/dandi-cli/pull/1514) | Overhaul validation results (Pydantic Origins) | Merged | Foundation: Pydantic-based models, JSON-ready |
| [#1619](https://github.com/dandi/dandi-cli/pull/1619) | Deduplicate validation results | Merged | Foundation: no duplicate records |
| [#1597](https://github.com/dandi/dandi-cli/issues/1597) | Replace bidsschematools with bids-validator-deno | Closed | Mentions filtering + result summaries as follow-ups |

## Current State

### What exists

- **`ValidationResult`** (Pydantic `BaseModel` in `validate_types.py`): fully JSON-serializable
  with `model_dump(mode="json")` and `model_validate_json()` round-trip support.
  Fields: `id`, `origin` (validator+standard+versions), `scope`, `severity`, `message`,
  `path`, `dandiset_path`, `dataset_path`, `asset_paths`, `within_asset_paths`,
  `path_regex`, `metadata`. The `origin_result` field is excluded from serialization.
  **No schema/format version field exists on the model itself.**
- **`Severity_`** annotated type serializes as `"ERROR"`, `"WARNING"`, etc. (not numeric).
- **`Origin`** is a Pydantic `BaseModel` with `type`, `validator`, `validator_version`,
  `standard`, `standard_version`, `standard_schema_version`.
- **CLI output** is human-only: colored text via `click.secho()` with grouping by
  `none`/`path`, filtering by `--min-severity` and `--ignore REGEX`.
- **`dandi ls`** already supports `-f json|json_pp|json_lines|yaml` via `formatter.py`
  with `JSONFormatter`, `JSONLinesFormatter`, `YAMLFormatter` context-manager classes.
- **Upload** runs `get_validation_errors()` per-file but only logs/raises on errors;
  no structured output is saved.
- **Log files** are written to `platformdirs.user_log_dir("dandi-cli", "dandi")`
  (typically `~/.local/share/logs/dandi-cli/`) with pattern
  `YYYY.MM.DD-HH.MM.SSZ-PID.log`. The path is stored in `ctx.obj.logfile` in the
  Click context (set in `command.py:main()`).
- **Current module layout**: `dandi/validate.py` + `dandi/validate_types.py` as
  top-level modules. As more validation modules are anticipated (I/O, reporting,
  additional validator backends), this needs to become a subpackage.

### What's missing

1. No `--format` option on `validate` (only human-readable output)
2. No `--output` to save results to a file
3. No `--load` to reload previously-saved results
4. No summary statistics
5. No grouping by `validator`, `severity`, `id`, `standard`, etc.
6. Upload validation results are not persisted for later review
7. No shared utility for writing/reading validation JSONL files
8. No schema version on `ValidationResult` for forward-compatible serialization
9. Validation modules are flat files, not a subpackage

### Importers of current validation modules

The following files import from `validate.py` or `validate_types.py` and will
need import path updates after the subpackage refactoring:

- `dandi/cli/cmd_validate.py` — `from ..validate import validate`; `from ..validate_types import ...`
- `dandi/cli/tests/test_cmd_validate.py` — `from ...validate_types import ...`
- `dandi/cli/tests/test_command.py` — `from ..cmd_validate import validate`
- `dandi/upload.py` — `from .validate_types import Severity`
- `dandi/organize.py` — `from .validate_types import ...`
- `dandi/pynwb_utils.py` — `from .validate_types import ...`
- `dandi/files/bases.py` — `from dandi.validate_types import ...`
- `dandi/files/bids.py` — `from ..validate_types import ...`; `from dandi.validate import validate_bids`
- `dandi/files/zarr.py` — `from ..validate_types import ...`
- `dandi/bids_validator_deno/_validator.py` — `from dandi.validate_types import ...`
- `dandi/tests/test_validate.py` — `from ..validate import validate`; `from ..validate_types import ...`
- `dandi/tests/test_validate_types.py` — `from dandi.validate_types import ...`

## Design Principles

### Separation of concerns (per #1753)

Three decoupled stages:

1. **Execution**: Run validators, produce `ValidationResult` objects
2. **Serialization**: Dump results to JSONL (the interchange format)
3. **Rendering**: Display results with grouping, filtering, formatting

Currently stages 1+3 are coupled in `cmd_validate.py`. This design introduces
stage 2 and makes stage 3 work from either stage 1 (live) or stage 2 (loaded).

```
Live validation:   validate() → [ValidationResult] → filter/group → render
                                       ↓
                                  save(sidecar)

Stored results:    load(files) → [ValidationResult] → filter/group → render

Upload results:    upload() → [ValidationResult] → save(sidecar)
                                      ↓
                    load(sidecar) → filter/group → render
```

### Uniform output across all formats — no envelope/non-envelope split

All structured formats (`json`, `json_pp`, `json_lines`, `yaml`) emit the
**same data** — a flat list of `ValidationResult` records. No format gets a
special envelope wrapper that others lack. This avoids having two schemas to
maintain and document.

**JSONL**: one `ValidationResult` per line (pure results, `cat`-composable):

```bash
cat results/*.jsonl | jq 'select(.severity == "ERROR")'  # just works
wc -l results/*.jsonl                                      # = issue count
grep BIDS.NON_BIDS results/*.jsonl                         # fast text search
vd results/*.jsonl                                         # instant tabular view
```

**VisiData integration**: VisiData natively loads `.jsonl` as tabular data —
each `ValidationResult` becomes a row with columns for `id`, `severity`,
`path`, `origin.validator`, `message`, etc. This gives immediate interactive
sorting, filtering, frequency tables, and pivoting with no extra code. Since
VisiData is Python-based, future integration is possible (e.g., a `dandi`
VisiData plugin that adds custom commands for grouping by dandiset, linking
to BIDS spec rules, or opening the offending file).

**JSON / JSON pretty-printed**: a JSON array of `ValidationResult` objects:

```json
[
  {"id": "BIDS.NON_BIDS_PATH_PLACEHOLDER", "origin": {...}, "severity": "ERROR", ...},
  {"id": "NWBI.check_data_orientation", "origin": {...}, "severity": "WARNING", ...}
]
```

**YAML**: same array structure in YAML syntax.

Summary statistics are handled separately via `--summary` (human output) or
post-processing (`jq`, `--load` + `--summary`). They are not baked into the
serialized data.

### Prior art: bids-validator `output.json`

The bids-validator ([example](https://github.com/bids-standard/bids-examples/blob/3aa560cc/2d_mb_pcasl/derivatives/bids-validator/output.json))
uses an envelope format:

```json
{
  "issues": {
    "issues": [{"code": "...", "severity": "warning", "location": "...", ...}],
    "codeMessages": {"JSON_KEY_RECOMMENDED": "A JSON file is missing..."}
  },
  "summary": {"subjects": [...], "totalFiles": 11, "schemaVersion": "1.2.1", ...}
}
```

Their format is a **final report** — one monolithic JSON per dataset. Our design
differs intentionally: we produce **composable JSONL records** that can be
concatenated across datasets, piped through standard Unix tools, and loaded
into tabular tools like VisiData. The `_record_version` field on each record
provides the self-describing property that their envelope provides at the
file level.

### Schema version on `ValidationResult`

Add a `_record_version` field to `ValidationResult` to enable forward-compatible
deserialization. This lets loaders detect and handle older record formats
gracefully:

```python
class ValidationResult(BaseModel):
    _record_version: str = "1"  # schema version for this record format
    id: str
    origin: Origin
    # ... rest of fields
```

Serialized as `"_record_version": "1"` in every JSON line. The loader can
check this and warn/adapt if it encounters a newer version. The underscore
prefix signals it is metadata about the record format, not validation content.

### Grouping is human-rendering only

Structured output always emits a flat results list. `--grouping` only affects
human-readable display. Downstream tools can trivially group with
`jq group_by(.id)` etc., and a stable flat schema is more useful than a format
that varies by grouping option.

### Orthogonal options

`--format` and `--output` are independent:
- `--format` controls serialization format (default: `human`)
- `--output` controls destination (default: stdout)
- Neither implies the other — if `--output` is given without `--format`,
  the format must be specified explicitly (error otherwise, since writing
  colored human text to a file is not useful)

## Design

### Step 0a: Refactor into `dandi/validate/` subpackage

**Goal**: Convert flat validation modules into a proper subpackage to
accommodate growing validation functionality (I/O, reporting, future validators).

**Critical**: The `git mv` must be committed **separately** from any content
changes to preserve git rename tracking.

#### Commit 1: Pure rename (git mv only)

```bash
mkdir -p dandi/validate
git mv dandi/validate.py dandi/validate/core.py
git mv dandi/validate_types.py dandi/validate/types.py
# Create __init__.py that re-exports everything for backwards compatibility
```

`dandi/validate/__init__.py` (created, not moved):

```python
"""Validation of DANDI datasets against schemas and standards.

This package provides validation functionality for dandisets, including:
- DANDI schema validation
- BIDS standard validation
- File layout and organization validation
- Metadata completeness checking
"""
# Re-export public API for backwards compatibility
from .core import validate, validate_bids  # noqa: F401
from .types import (  # noqa: F401
    ORIGIN_INTERNAL_DANDI,
    ORIGIN_VALIDATION_DANDI,
    ORIGIN_VALIDATION_DANDI_LAYOUT,
    ORIGIN_VALIDATION_DANDI_ZARR,
    Origin,
    OriginType,
    Scope,
    Severity,
    Severity_,
    Standard,
    ValidationResult,
    Validator,
)
```

This `__init__.py` means **all existing imports continue to work unchanged**:
- `from dandi.validate import validate` — works (via `__init__.py`)
- `from dandi.validate_types import ValidationResult` — **breaks**, needs update

#### Commit 2: Update all import paths

Update all importers listed above to use the new subpackage paths:
- `from dandi.validate_types import X` → `from dandi.validate.types import X`
  (or `from dandi.validate import X` where re-exported)
- `from dandi.validate import validate` — already works via `__init__.py`
- `from ..validate_types import X` → `from ..validate.types import X`

Also move test files:
- `dandi/tests/test_validate.py` → `dandi/validate/tests/test_core.py`
- `dandi/tests/test_validate_types.py` → `dandi/validate/tests/test_types.py`

#### Resulting subpackage layout

```
dandi/validate/
├── __init__.py          # Re-exports for backwards compat
├── core.py              # validate(), validate_bids() — was validate.py
├── types.py             # ValidationResult, Origin, etc. — was validate_types.py
├── io.py                # NEW: JSONL read/write utilities
└── tests/
    ├── __init__.py
    ├── test_core.py     # was dandi/tests/test_validate.py
    ├── test_types.py    # was dandi/tests/test_validate_types.py
    └── test_io.py       # NEW: tests for I/O utilities
```

### Step 0b: Refactor `cmd_validate.py` (addresses #1748)

Before adding new options, decompose the `validate()` CLI function. It currently
handles argument parsing, validation execution, filtering, and rendering in one
function. Extract:

- `_collect_results()` — run validation, return `list[ValidationResult]`
- `_filter_results()` — apply `--min-severity`, `--ignore`
- `_render_results()` — dispatch to human or structured output

This keeps complexity per function under the LAD threshold (max-complexity 10)
and makes it natural to slot in `--load` as an alternative to `_collect_results()`.

Adds `@click.pass_context` to `validate()` to access `ctx.obj.logfile`.

### Step 0c: Add `_record_version` to `ValidationResult`

Add the schema version field to `ValidationResult` in `dandi/validate/types.py`:

```python
class ValidationResult(BaseModel):
    _record_version: str = "1"
    id: str
    origin: Origin
    # ... existing fields unchanged
```

This is a backwards-compatible addition — existing serialized records without
`_record_version` will deserialize fine (Pydantic fills the default). The loader
in `io.py` can log a debug message if it encounters an unknown version.

### Shared I/O utility: `dandi/validate/io.py`

New module shared by `cmd_validate.py` and `upload.py`:

```python
"""Read and write validation results in JSONL format.

JSONL files contain one ValidationResult per line — pure results, no envelope.
This makes them fully cat-composable, grep-searchable, and jq-processable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .types import ValidationResult

lgr = logging.getLogger(__name__)

CURRENT_RECORD_VERSION = "1"


def write_validation_jsonl(
    results: list[ValidationResult],
    path: str | Path,
) -> Path:
    """Write validation results to a JSONL file (one result per line).

    Parameters
    ----------
    results : list[ValidationResult]
        Validation results to write.
    path : str | Path
        Output file path.

    Returns
    -------
    Path
        The path written to.
    """
    path = Path(path)
    with open(path, "w") as f:
        for r in results:
            f.write(r.model_dump_json() + "\n")
    return path


def append_validation_jsonl(
    results: list[ValidationResult],
    path: str | Path,
) -> None:
    """Append validation results to an existing JSONL file."""
    path = Path(path)
    with open(path, "a") as f:
        for r in results:
            f.write(r.model_dump_json() + "\n")


def load_validation_jsonl(*paths: str | Path) -> list[ValidationResult]:
    """Load and concatenate validation results from JSONL files.

    Each line must be a JSON-serialized ValidationResult. Blank lines and
    lines that fail to parse as ValidationResult are skipped with a warning.

    Parameters
    ----------
    *paths
        One or more JSONL file paths.

    Returns
    -------
    list[ValidationResult]
        Concatenated results from all files.
    """
    results: list[ValidationResult] = []
    for p in paths:
        p = Path(p)
        with open(p) as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    vr = ValidationResult.model_validate_json(line)
                except Exception:
                    lgr.debug(
                        "Skipping unrecognized line %d in %s", lineno, p
                    )
                    continue
                rv = getattr(vr, "_record_version", CURRENT_RECORD_VERSION)
                if rv != CURRENT_RECORD_VERSION:
                    lgr.debug(
                        "Record version %s (expected %s) at %s:%d",
                        rv, CURRENT_RECORD_VERSION, p, lineno,
                    )
                results.append(vr)
    return results


def validation_sidecar_path(logfile: str | Path) -> Path:
    """Derive the validation sidecar path from a log file path.

    Given ``2026.03.19-14.30.00Z-12345.log``, returns
    ``2026.03.19-14.30.00Z-12345_validation.jsonl`` in the same directory.
    """
    logfile = Path(logfile)
    return logfile.with_name(logfile.stem + "_validation.jsonl")
```

### Phase 1a: Format output (`-f/--format`) — addresses #1515

**Goal**: Add structured output formats to `dandi validate`.

#### CLI changes

```python
@click.option(
    "--format", "-f",
    "output_format",  # avoid shadowing builtin
    help="Output format.",
    type=click.Choice(["human", "json", "json_pp", "json_lines", "yaml"]),
    default="human",
)
```

#### Structured output schema (uniform across formats)

All structured formats emit a flat list of `ValidationResult` records.

**json / json_pp** — JSON array:
```json
[
  {
    "_record_version": "1",
    "id": "BIDS.NON_BIDS_PATH_PLACEHOLDER",
    "origin": {
      "type": "VALIDATION",
      "validator": "bids-validator-deno",
      "validator_version": "2.0.6",
      "standard": "BIDS",
      "standard_version": "1.9.0",
      "standard_schema_version": "0.11.3"
    },
    "scope": "file",
    "severity": "ERROR",
    "message": "File does not match any pattern known to BIDS.",
    "path": "sub-01/anat/junk.txt",
    "dandiset_path": "/data/dandiset001",
    "dataset_path": "/data/dandiset001",
    "asset_paths": null,
    "within_asset_paths": null,
    "path_regex": null,
    "metadata": null
  }
]
```

**json_lines** — one record per line (same fields, `cat`-composable):
```
{"_record_version":"1","id":"BIDS.NON_BIDS_PATH_PLACEHOLDER","origin":{...},...}
{"_record_version":"1","id":"NWBI.check_data_orientation","origin":{...},...}
```

**yaml** — YAML list of the same records.

No envelope in any format. Summary is a separate concern (see Phase 1c).

#### Implementation approach

Reuse `formatter.py` infrastructure. `ValidationResult.model_dump(mode="json")`
produces a dict compatible with existing `JSONFormatter`/`YAMLFormatter`.
The `validate()` CLI function collects all results into a list (already does
for filtering), then dispatches to `display_errors()` (human) or structured
formatter.

### Phase 1b: File output (`-o/--output`) + auto-save sidecar

**Goal**: Write results to file and auto-save a `_validation.jsonl` sidecar
alongside the `.log` file.

#### CLI changes

```python
@click.option(
    "--output", "-o",
    help="Write output to file instead of stdout. "
         "Requires --format to be set to a structured format.",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
)
```

Validation:
- If `--output` is given and `--format` is `human` (default), raise
  `click.UsageError("--output requires --format to be set to a structured format")`

#### Auto-save sidecar

`dandi validate` writes a `_validation.jsonl` sidecar next to its log file
**by default**, but **skips the sidecar when `--output` is specified** (the
user has already chosen where to save structured results — no need for a
redundant copy):

```python
# After collecting all_results:
if all_results and not output:
    sidecar = validation_sidecar_path(ctx.obj.logfile)
    write_validation_jsonl(all_results, sidecar)
    lgr.info("Validation results saved to %s", sidecar)
```

Empty results (clean validation) also skip the sidecar to avoid clutter.
The sidecar accumulation rate matches the already-existing `.log` files.

### Phase 1c: Summary flag (`--summary`)

**Goal**: Add summary statistics as a display option, decoupled from the
serialized data format.

```python
@click.option(
    "--summary / --no-summary",
    help="Show summary statistics after validation output.",
    default=False,
)
```

Human output appends:

```
Summary:
  Total issues: 42
  By severity:  ERROR: 5, WARNING: 12, HINT: 25
  By validator: bids-validator-deno: 30, nwbinspector: 10, dandi: 2
  Files with errors: 8/150
```

For structured formats, `--summary` appends a summary object **to stderr**
(keeping stdout as pure machine-parseable results), or is simply computed by
the consumer from the flat results list. The summary is never mixed into the
structured output stream itself.

### Phase 2: Load and Re-Render (`--load`) — addresses #1753

**Goal**: Reload previously-saved validation results and apply all display options.

#### CLI option

```python
@click.option(
    "--load",
    help="Load validation results from JSONL file(s) instead of running "
         "validation. Accepts multiple --load flags. Shell glob expansion "
         "is supported (e.g. results/*.jsonl).",
    type=click.Path(exists=True, dir_okay=False),
    multiple=True,
    default=(),
)
```

#### Mutual exclusivity with paths

`--load` and positional `paths` are mutually exclusive. Enforced explicitly:

```python
if load and paths:
    raise click.UsageError(
        "--load and PATH arguments are mutually exclusive. "
        "Use --load to re-render stored results, or provide paths to validate."
    )
```

#### Behavior

- When `--load` is specified, skip all validation execution
- Use `load_validation_jsonl()` from `dandi/validate/io.py` to read and concatenate
- Apply `--min-severity`, `--ignore`, `--grouping`, `--format`, `--output` identically
- **Exit code**: reflects the loaded results — non-zero if any ERROR-severity
  issues are present after filtering. Rationale: the user is asking "are there
  errors in these results?" and the answer should be in the exit code regardless
  of whether validation was live or loaded.
- Records with unknown `_record_version` are loaded with a debug-level warning
  but not rejected (forward-compatible reading)

#### Example workflows

```bash
# Run validation (auto-saves _validation.jsonl sidecar)
dandi validate /data/dandiset001

# Re-render the auto-saved results with different filters
dandi validate --load ~/.local/share/logs/dandi-cli/*_validation.jsonl \
  --min-severity ERROR
dandi validate --load results.jsonl --grouping path
dandi validate --load results.jsonl -f json_pp --ignore "NWBI\."

# Cross-dataset sweep: validate many, then analyze together
for ds in bids-examples/*/; do
  dandi validate "$ds" -f json_lines -o "results/$(basename $ds).jsonl" || true
done
dandi validate --load results/*.jsonl --grouping id --min-severity ERROR
```

Note: shell glob expansion is done by the shell, not by Click. `--load
results/*.jsonl` works because the shell expands the glob into multiple
`--load` arguments before the CLI sees them.

### Phase 3: Upload validation sidecar — addresses #1753

**Goal**: Persist all validation results from `dandi upload` for later inspection.

#### The problem with `ctx.obj.logfile` in upload

The `upload()` function in `upload.py` is both a Python API and a CLI backend.
The Click context (`ctx.obj.logfile`) is only available via CLI. The upload
function's validation happens inside a deeply nested generator (`_upload_item`).

**Solution**: Pass the sidecar path as an optional parameter to `upload()`:

```python
def upload(
    paths: Sequence[str | Path] | None = None,
    existing: UploadExisting = UploadExisting.REFRESH,
    validation: UploadValidation = UploadValidation.REQUIRE,
    # ... existing params ...
    validation_log_path: str | Path | None = None,  # NEW
) -> None:
```

The CLI wrapper (`cmd_upload.py`) derives the sidecar path from `ctx.obj.logfile`
and passes it in. Programmatic callers can pass their own path or leave it as
`None` (no sidecar written).

#### Implementation

```python
# In cmd_upload.py, the CLI function:
sidecar = validation_sidecar_path(ctx.obj.logfile)
upload(..., validation_log_path=sidecar)

# In upload.py, inside the upload loop:
# Collect all validation results as each file is validated
if validation_log_path is not None:
    append_validation_jsonl(validation_statuses, validation_log_path)
```

After the upload completes (or if it fails due to validation errors):

```python
if validation_log_path and Path(validation_log_path).exists():
    lgr.info(
        "Validation results saved to %s\n"
        "  Use `dandi validate --load %s` to review.",
        validation_log_path, validation_log_path,
    )
```

Uses `append_validation_jsonl()` from `dandi/validate/io.py` — the file is
opened in append mode for each batch, allowing incremental writes as files are
validated during upload without holding all results in memory.

### Phase 4: Extended grouping options — enhances #1743 work

**Goal**: Support additional grouping strategies for human-readable output.

Extend `--grouping` from `{none, path}` to:

| Value | Groups by | Use case |
|-------|-----------|----------|
| `none` | No grouping (flat list) | Default, simple review |
| `path` | File/dataset path | Per-file review |
| `severity` | Severity level | Triage by priority |
| `id` | Error ID | Find most common issues |
| `validator` | Validator name | Per-tool review |
| `standard` | Standard (BIDS/NWB/etc) | Per-standard review |
| `dandiset` | Dandiset path | Multi-dandiset sweeps |

Human output with grouping adds section headers and counts:

```
=== ERROR (5 issues) ===
[BIDS.NON_BIDS_PATH_PLACEHOLDER] sub-01/junk.txt — File does not match...
...

=== WARNING (12 issues) ===
[NWBI.check_data_orientation] sub-01/sub-01.nwb — Data may not be...
...
```

**Structured output is unaffected** — always a flat results list regardless
of `--grouping`. Downstream tools group trivially:
`jq -s 'group_by(.origin.validator)'`.

### Phase 5: Cross-dataset sweep support and tooling integration (optional)

- Helper script or command for batch validation across directories
- Consider a `dandi validate-report` subcommand for aggregate analysis
  across multiple loaded JSONL files (cross-tabulation, top-N errors, etc.)
- **VisiData plugin**: Since VisiData is Python-based and already opens JSONL
  natively, a `dandi` VisiData plugin could add:
  - Custom column extractors for nested `origin.*` fields (flattened for tabular view)
  - Frequency sheet by error ID / validator / standard
  - Keybinding to open the offending file or jump to BIDS spec rule
  - Integration with `dandi validate --load` for round-trip editing
    (e.g., mark false positives, export filtered subset)

## Path Serialization

Paths in `ValidationResult` are serialized as-is (whatever `Path.__str__`
produces). For portability across machines:

- **Recommendation**: When the path is within a dandiset, make it relative
  to `dandiset_path`. When within a BIDS dataset, make it relative to
  `dataset_path`. This is not a requirement for Phase 1 but should be
  considered for Phase 2+ to make loaded results meaningful across machines.

## Use Case: Sweeping BIDS Example Datasets / All DANDI Datasets

```bash
# Validate all BIDS examples, save results per-dataset
for ds in bids-examples/*/; do
  dandi validate "$ds" -f json_lines -o "results/$(basename $ds).jsonl" || true
done

# Combine and analyze with jq
cat results/*.jsonl | jq 'select(.severity == "ERROR")' | jq -s 'group_by(.id)'

# Or reload individual results with different views
dandi validate --load results/ds001.jsonl --grouping id --min-severity ERROR
dandi validate --load results/ds001.jsonl -f json_pp

# Reload ALL results across datasets
dandi validate --load results/*.jsonl --grouping id --min-severity ERROR --summary

# Interactive exploration with VisiData — sort, filter, pivot, frequency tables
vd results/*.jsonl
```

For all DANDI datasets:

```bash
for dandiset_id in $(dandi ls -f json_lines https://dandiarchive.org/ | jq -r '.identifier'); do
  dandi download "DANDI:${dandiset_id}/draft" -o "/data/${dandiset_id}" --download dandiset.yaml
  dandi validate "/data/${dandiset_id}" -f json_lines -o "results/${dandiset_id}.jsonl" || true
done

# Aggregate cross-dandiset analysis
cat results/*.jsonl | jq -s '
  group_by(.id)
  | map({id: .[0].id, count: length, severity: .[0].severity})
  | sort_by(-.count)
'
```

## Implementation Order

### Step 0a: Refactor into `dandi/validate/` subpackage

- `git mv dandi/validate.py dandi/validate/core.py` — committed alone
- `git mv dandi/validate_types.py dandi/validate/types.py` — committed alone
- Create `dandi/validate/__init__.py` with re-exports for backwards compat
- Separate commit: update all import paths across the codebase
- Separate commit: move test files to `dandi/validate/tests/`
- All existing tests must pass after each commit

### Step 0b: Refactor `cmd_validate.py` — addresses #1748

- Extract `_collect_results()`, `_filter_results()`, `_render_results()`
- Keep `validate()` CLI function as thin orchestrator
- Existing behavior unchanged, existing tests must pass
- Add `@click.pass_context` to `validate()` to access `ctx.obj.logfile`

### Step 0c: Add `_record_version` to `ValidationResult`

- Add `_record_version: str = "1"` field
- Verify serialization round-trip includes it
- No behavioral change to existing code

### Step 1a: `--format` (structured output to stdout) — addresses #1515

- Add `--format` option with choices `human|json|json_pp|json_lines|yaml`
- All structured formats emit flat list of ValidationResult records
- Reuse `formatter.py` infrastructure for JSON/YAML
- Tests: CliRunner for each format, round-trip serialization

### Step 1b: `--output` + auto-save sidecar

- Add `--output` option, enforce `--format` must be structured
- Create `dandi/validate/io.py` with shared `write_validation_jsonl()`,
  `append_validation_jsonl()`, `load_validation_jsonl()`,
  `validation_sidecar_path()`
- Auto-save `_validation.jsonl` sidecar when results are non-empty and
  `--output` is not specified (user already has their output file)
- Tests: file creation, sidecar naming, empty-results no-op, sidecar
  suppressed when `--output` is used

### Step 1c: `--summary`

- Add `--summary` flag for human output
- For structured formats, summary to stderr (not mixed into data stream)
- Tests: summary output format, counts accuracy

### Step 2: `--load` (reload and re-render) — addresses #1753

- Add `--load` option (multiple, mutually exclusive with paths)
- Use `load_validation_jsonl()` from shared utility
- All filtering/grouping/format options work on loaded results
- Exit code reflects loaded results
- `_record_version` checked with debug-level warning for unknown versions
- Tests: load + filter, multi-file concatenation, mutual exclusivity error,
  forward-compatible loading of unknown versions

### Step 3: Upload validation sidecar — addresses #1753

- Add `validation_log_path` parameter to `upload()`
- CLI wrapper passes sidecar path derived from `ctx.obj.logfile`
- Use `append_validation_jsonl()` for incremental writes
- Announce sidecar path on validation errors
- Tests: sidecar creation during upload, content correctness

### Step 4: Extended grouping (human-only) — enhances #1743

- Add `severity`, `id`, `validator`, `standard`, `dandiset` grouping options
- Implement section headers + counts for human output
- Structured output unchanged (always flat)
- This subsumes some of the filtering work in draft PR #1743

### Step 5: Cross-dataset sweep support (optional)

- Helper script or `dandi validate-report` subcommand
- Aggregate analysis across multiple JSONL files

## Backwards Compatibility

- `dandi validate` with no new options behaves identically to today
- Exit code semantics preserved: non-zero if any ERROR-severity issues
- When using `--format` other than `human`, colored output is suppressed
- When using `--load`, exit code reflects loaded results
- The auto-save sidecar is the only new side effect; it writes when there
  are results and `--output` is not specified (for `validate`), or always
  (for `upload`). Follows the same lifecycle as the existing `.log` files
- The `dandi/validate/` subpackage `__init__.py` re-exports all public API,
  so `from dandi.validate import validate` continues to work. Only direct
  `from dandi.validate_types import ...` imports need updating.

## Testing Strategy

| Component | Test type | Approach |
|-----------|-----------|----------|
| Subpackage refactor | Smoke | All existing tests pass after `git mv` + import updates |
| `--format` output | CLI unit | `click.CliRunner`, assert JSON structure, round-trip |
| `dandi/validate/io.py` | Unit | Write → load round-trip, append, empty files, corrupt lines |
| `_record_version` | Unit | Serialization includes field, loader handles missing/unknown |
| `--load` | CLI unit | Load from fixture files, multi-file concat, mutual exclusivity |
| `--output` | CLI unit | Verify file creation, content matches stdout format |
| Sidecar auto-save | CLI unit | Verify `_validation.jsonl` created next to mock logfile |
| Upload sidecar | Integration | Upload with Docker Compose fixture, verify sidecar |
| Extended grouping | CLI unit | Each grouping value, section headers, counts |
| Summary | CLI unit | Verify counts match actual results |
| Edge cases | Unit | Empty results, None severity, very long paths, Unicode messages |

All new tests marked `@pytest.mark.ai_generated`.

## File Inventory

| File | Change |
|------|--------|
| `dandi/validate/__init__.py` | **New** — subpackage with re-exports |
| `dandi/validate/core.py` | **Renamed** from `dandi/validate.py` |
| `dandi/validate/types.py` | **Renamed** from `dandi/validate_types.py` + add `_record_version` |
| `dandi/validate/io.py` | **New** — shared JSONL read/write utilities |
| `dandi/validate/tests/__init__.py` | **New** |
| `dandi/validate/tests/test_core.py` | **Renamed** from `dandi/tests/test_validate.py` |
| `dandi/validate/tests/test_types.py` | **Renamed** from `dandi/tests/test_validate_types.py` |
| `dandi/validate/tests/test_io.py` | **New** — tests for I/O utilities |
| `dandi/cli/cmd_validate.py` | Refactor + add `--format`, `--output`, `--load`, `--summary`, grouping extensions |
| `dandi/upload.py` | Add `validation_log_path` parameter, write sidecar |
| `dandi/cli/cmd_upload.py` | Pass sidecar path to `upload()` |
| `dandi/cli/tests/test_cmd_validate.py` | Extend with format/load/output/summary tests |
| `dandi/pynwb_utils.py` | Update imports |
| `dandi/organize.py` | Update imports |
| `dandi/files/bases.py` | Update imports |
| `dandi/files/bids.py` | Update imports |
| `dandi/files/zarr.py` | Update imports |
| `dandi/bids_validator_deno/_validator.py` | Update imports |
