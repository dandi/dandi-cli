# Contributing to dandi-cli

This document covers the conventions and workflows for contributing to
dandi-cli.  For detailed environment setup, environment variables, and
release procedures, see [DEVELOPMENT.md](./DEVELOPMENT.md).

## Build & Test Quick Reference

```bash
# Run full test suite
hatch run test:run                # via hatch
tox -e py3                        # via tox
python -m pytest dandi            # in a venv

# Run a single test
hatch run test:run dandi/tests/test_file.py::test_function -v
tox r -e py3 -- dandi/tests/test_file.py::test_function -v

# Lint + type checking
tox -e lint,typing

# Lint only (codespell + flake8)
tox -e lint

# Type checking only (mypy)
tox -e typing

# Build docs
tox -e docs

# Install pre-commit hooks (if .git/hooks/pre-commit is absent)
pre-commit install
```

### Integration tests

Tests that need a running DANDI Archive instance use the `local_dandi_api`
docker-compose fixture.  Set `DANDI_TESTS_PULL_DOCKER_COMPOSE=""` to skip
`docker compose pull` and speed up repeated runs.

## Codebase Architecture

### Directory layout

```
dandi/
  cli/              # Click-based CLI commands
    command.py      # Entry point — Click group with DYMGroup (did-you-mean)
    base.py         # Shared CLI utilities, decorators, custom param types
    cmd_*.py        # One file per command (download, upload, organize, …)
    formatter.py    # Output formatters (JSON, YAML, JSONL, PYOUT)
  files/            # File-type abstractions
    bases.py        # DandiFile hierarchy (LocalAsset, NWBAsset, …)
    bids.py         # BIDS-specific file types (NWBBIDSAsset, …)
    zarr.py         # Zarr archive handling (ZarrAsset, LocalZarrEntry)
  metadata/         # Metadata extraction
    core.py         # Entry points for metadata extraction
    nwb.py          # NWB-specific extraction via PyNWB
    util.py         # get_metadata(), field extraction, caching
  validate/         # Validation engine
    _types.py       # ValidationResult, Severity, Scope, Standard enums
    _core.py        # validate() generator, validate_bids()
    _io.py          # JSON Lines I/O for validation results
  support/          # Shared utilities
    digests.py      # Checksum/digest computation (DANDI eTag, Zarr)
    pyout.py        # Progress display with pyout (LogSafeTabular)
    iterators.py    # IteratorWithAggregation for progress tracking
    threaded_walk.py # Parallel directory traversal
  tests/            # Test suite
    fixtures.py     # Core test fixtures (NWB files, local API, dandisets)
    skip.py         # Conditional skip helpers
    data/           # Test data files
  consts.py         # Constants: metadata fields, known instances, layout fields
  dandiapi.py       # API client (RESTFullAPIClient, DandiAPIClient)
  dandiarchive.py   # URL parsing (ParsedDandiURL, parse_dandi_url())
  dandiset.py       # Local dandiset representation (dandiset.yaml)
  download.py       # Download engine with resume/retry support
  upload.py         # Upload engine with validation
  organize.py       # File organization by NWB metadata
  delete.py         # Asset/dandiset deletion
  move.py           # Asset move/rename (local + remote)
  exceptions.py     # Custom exceptions (all end with "Error")
  misctypes.py      # Shared types: Digest, BasePath
  pynwb_utils.py    # PyNWB helpers for reading/creating NWB files
  utils.py          # General utilities
```

### Key design patterns

- **CLI delegation** — CLI commands (`cmd_*.py`) are thin wrappers that
  delegate to core modules (e.g. `cmd_upload.py` → `upload.upload()`).
- **File-type hierarchy** — `DandiFile` abstract base with factory function
  `dandi_file()` and discovery via `find_dandi_files()`.
- **Enum-based configuration** — Operations use enums for modes
  (`DownloadExisting`, `FileOperationMode`, `UploadValidation`, …).
- **Generator-based processing** — Validation, download, and file finding
  all yield results lazily.
- **Context managers** — API clients (`DandiAPIClient`) and URL navigation.
- **Retry logic** — HTTP operations use `tenacity` for exponential backoff.
- **Lazy imports** — Heavy modules (`pynwb`, `h5py`) are imported at point
  of use, not at module level.

### Key classes

| Class | Module | Role |
|-------|--------|------|
| `DandiAPIClient` | `dandiapi.py` | High-level API client; authentication (keyring), pagination, asset management |
| `RESTFullAPIClient` | `dandiapi.py` | Base HTTP client with session management and retry logic |
| `ParsedDandiURL` | `dandiarchive.py` | Abstract base for URL parsing; subclasses `DandisetURL`, `SingleAssetURL`, `AssetItemURL`, `AssetDirURL` |
| `DandiFile` | `files/bases.py` | Abstract base for all file types; subclasses `NWBAsset`, `ZarrAsset`, `GenericAsset`, `VideoAsset` |
| `ValidationResult` | `validate/_types.py` | Pydantic model: origin, severity, scope, message, paths |
| `Dandiset` | `dandiset.py` | Local dandiset representation wrapping `dandiset.yaml` |
| `DandiInstance` | `consts.py` | Frozen dataclass for known archive instances |

## Code Style

- **Formatter**: Black (line length 100)
- **Import sorting**: isort (`profile="black"`, `force_sort_within_sections`,
  `reverse_relative`)
- **Linting**: flake8 (`max-line-length=100`, ignore `E203`/`W503`)
- **Spell checking**: codespell
- **Type checking**: mypy with pydantic plugin
- **Type annotations**: Required for new code
- **Naming**: `CamelCase` for classes, `snake_case` for functions/variables
- **Exceptions**: Names must end with `Error` (e.g. `UploadError`,
  `NotFoundError`)
- **Docstrings**: NumPy style for public APIs
- **Dataclass field docs**: `#:` comments above the field (Sphinx autodoc
  format — see [DEVELOPMENT.md](./DEVELOPMENT.md#dataclass-and-attrs-field-documentation))
- **Imports**: stdlib → third-party → local (alphabetical within groups)
- **CLI**: Click library with `DYMGroup` (did-you-mean suggestions)
- **Excluded from formatting**: `_version.py`, `due.py`, `versioneer.py`

### Pre-commit hooks

The following hooks run on commit (`.pre-commit-config.yaml`):

1. trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files
2. black (code formatting)
3. isort (import sorting)
4. codespell (spell checking)
5. flake8 (linting)

Because black and isort auto-fix files, a commit that triggers fixes will
fail the first time.  Simply re-run `git commit` — the second attempt should
succeed.  Investigate further only if it still fails.

## Test Infrastructure

### pytest markers

| Marker | Purpose |
|--------|--------|
| `@pytest.mark.integration` | Tests requiring a running archive instance |
| `@pytest.mark.obolibrary` | Tests hitting the OBO ontology library |
| `@pytest.mark.flaky` | Known-flaky tests |
| `@pytest.mark.ai_generated` | **Mandatory** on any test written with AI assistance |

New markers must be registered in `pytest_configure()` in
`dandi/pytest_plugin.py`.

### Key fixtures (`dandi/tests/fixtures.py`)

- `simple1_nwb_metadata()` / `simple1_nwb()` — session-scoped sample NWB file
- `local_dandi_api` — Docker-based local DANDI Archive instance
- `new_dandiset()` — creates a fresh dandiset on the test instance
- `publish_dandiset()` — publishes a dandiset version
- `capture_all_logs` — autouse; sets DEBUG level for `dandi` logger

### Test organization

- Tests mirror the module structure: `test_download.py`, `test_upload.py`, etc.
- Integration tests use the `local_dandi_api` fixture
- `--dandi-api` flag: run only integration tests
- `--scheduled` flag: enable configuration for scheduled daily runs
- VCR (vcrpy) records/replays HTTP interactions; disable with
  `DANDI_TESTS_NO_VCR`

### pytest configuration (`tox.ini [pytest]`)

- Default timeout: 300 s per test
- `--tb=short --durations=10`
- `filterwarnings = error` with specific ignores for known third-party warnings

## CI/CD

| Workflow | What it checks |
|----------|---------------|
| `run-tests.yml` | Full test matrix — Python 3.10–3.13 × Ubuntu, macOS (M1 + Intel), Windows |
| `lint.yml` | codespell + flake8 |
| `typing.yml` | mypy |
| `docs.yml` | Sphinx build |
| `release.yml` | Automated release via `auto` — see [DEVELOPMENT.md](./DEVELOPMENT.md#releasing-with-github-actions-auto-and-pull-requests) |

### PR labels (intuit/auto)

Every PR should carry a semver or category label; `auto` uses them for
changelog sections and version bumps.  Recognized labels:

`major`, `minor`, `patch` (default), `internal`, `documentation`, `tests`,
`dependencies`, `performance`

A release is published only when the **`release`** label is present.
