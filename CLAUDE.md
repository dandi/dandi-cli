# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**dandi-cli** is the command-line client for the [DANDI Archive](https://dandiarchive.org), a platform for publishing, sharing, and processing neurophysiology data. It handles uploading, downloading, organizing, and validating neuroscience data files (primarily NWB and BIDS formats).

- **Language**: Python 3.10+
- **Build system**: setuptools with versioneer (git-based PEP 440 versioning)
- **Entry point**: `dandi` CLI command (`dandi/cli/command.py:main`)
- **pytest plugin**: Registered as `dandi` entry point (`dandi/pytest_plugin.py`)

## Build/Test Commands

- **Run tests with hatch**: `hatch run test:run`
- **Run tests with tox**: `tox -e py3` or `python -m pytest dandi` if in a venv
- **Run single test with hatch**: `hatch run test:run dandi/tests/test_file.py::test_function -v`
- **Run single test with tox**: `tox r -e py3 -- dandi/tests/test_file.py::test_function -v`
- **Lint and type checking**: `tox -e lint,typing`
- **Lint only**: `tox -e lint` (runs codespell + flake8)
- **Type checking only**: `tox -e typing` (runs mypy)
- **Build docs**: `tox -e docs`
- **Install pre-commit hooks**: `pre-commit install` (check for `.git/hooks/pre-commit`)
- **Integration tests**: Tests requiring a local archive instance use docker-compose fixtures
- **Speed up docker tests**: Set `DANDI_TESTS_PULL_DOCKER_COMPOSE=""` to skip `docker compose pull`

## Codebase Architecture

### Directory Structure

```
dandi/
  cli/              # Click-based CLI commands
    command.py      # Main entry point, Click group with DYMGroup
    base.py         # Shared CLI utilities, decorators, custom param types
    cmd_*.py        # Individual commands (download, upload, organize, etc.)
    formatter.py    # Output formatters (JSON, YAML, JSONL, PYOUT)
  files/            # File type abstractions
    bases.py        # DandiFile hierarchy (LocalAsset, NWBAsset, etc.)
    bids.py         # BIDS-specific file types (NWBBIDSAsset, etc.)
    zarr.py         # Zarr archive handling (ZarrAsset, LocalZarrEntry)
  metadata/         # Metadata extraction
    core.py         # Entry points for metadata extraction
    nwb.py          # NWB-specific metadata extraction via PyNWB
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

### Key Design Patterns

- **CLI delegation**: CLI commands (`cmd_*.py`) are thin wrappers that delegate to core modules (e.g., `cmd_upload.py` calls `upload.upload()`)
- **File type hierarchy**: `DandiFile` abstract base with factory function `dandi_file()` and discovery via `find_dandi_files()`
- **Enum-based configuration**: Operations use enums for modes (e.g., `DownloadExisting`, `FileOperationMode`, `UploadValidation`)
- **Generator-based processing**: Validation, download, and file finding all use generators
- **Context managers**: API clients (`DandiAPIClient`) and URL navigation use context managers
- **Retry logic**: HTTP operations use `tenacity` for exponential backoff retries
- **Lazy imports**: Heavy modules (pynwb, h5py) are imported at point of use, not at module level

### Key Classes

- `DandiAPIClient` (`dandiapi.py`): High-level API client with authentication (keyring), pagination, asset management
- `RESTFullAPIClient` (`dandiapi.py`): Base HTTP client with session management and retry logic
- `ParsedDandiURL` (`dandiarchive.py`): Abstract base for URL parsing with subclasses `DandisetURL`, `SingleAssetURL`, `AssetItemURL`, `AssetDirURL`
- `DandiFile` (`files/bases.py`): Abstract base for all file types; subclasses include `NWBAsset`, `ZarrAsset`, `GenericAsset`, `VideoAsset`
- `ValidationResult` (`validate/_types.py`): Pydantic model with origin, severity, scope, message, paths
- `Dandiset` (`dandiset.py`): Local dandiset representation wrapping `dandiset.yaml`
- `DandiInstance` (`consts.py`): Frozen dataclass for known archive instances (dandi, dandi-sandbox, linc, ember-dandi, etc.)

## Committing

- Due to use of `pre-commit` with black and other auto-fixers, if changes were reported, just rerun commit a 2nd time. Only then if it still does not commit, analyze output further.

## Test Markers

- When adding AI-generated tests, mark them with `@pytest.mark.ai_generated`
- Any new pytest markers must be registered in `pytest_configure` function of `dandi/pytest_plugin.py`
- Existing markers: `integration`, `obolibrary`, `flaky`, `ai_generated`

## Test Infrastructure

### Key Fixtures (`dandi/tests/fixtures.py`)

- `simple1_nwb_metadata()` / `simple1_nwb()`: Session-scoped sample NWB file
- `local_dandi_api`: Docker-based local DANDI Archive instance for integration tests
- `new_dandiset()`: Creates a fresh dandiset on the test instance
- `publish_dandiset()`: Publishes a dandiset version
- `capture_all_logs`: Autouse fixture setting DEBUG level for `dandi` logger

### Test Organization

- Tests mirror the module structure: `test_download.py`, `test_upload.py`, etc.
- Integration tests requiring docker use the `local_dandi_api` fixture
- `--dandi-api` pytest flag filters to only integration tests
- `--scheduled` flag enables scheduled-only test configuration
- VCR (vcrpy) is used to record/replay HTTP interactions; disable with `DANDI_TESTS_NO_VCR`

### pytest Configuration (`tox.ini [pytest]`)

- Default timeout: 300 seconds per test
- `--tb=short --durations=10` by default
- `filterwarnings` set to `error` with specific ignores for known third-party warnings

## Code Style

- **Formatter**: Black (line length 100)
- **Import sorting**: isort (profile="black", force_sort_within_sections, reverse_relative)
- **Linting**: flake8 (max-line-length=100, ignore E203/W503)
- **Spell checking**: codespell
- **Type checking**: mypy with pydantic plugin, strict settings
- **Type annotations**: Required for new code
- **Naming**: CamelCase for classes, snake_case for functions/variables
- **Exceptions**: Names must end with "Error" (e.g., `UploadError`, `NotFoundError`)
- **Docstrings**: NumPy style for public APIs
- **Dataclass field docs**: Use `#:` comments above the field (Sphinx autodoc format)
- **Imports**: Organized as stdlib, third-party, local (alphabetical within groups)
- **CLI**: Uses click library patterns with `DYMGroup` (did-you-mean suggestions)
- **Excluded from formatting**: `_version.py`, `due.py`, `versioneer.py`

## Pre-commit Hooks

The following hooks run on commit (`.pre-commit-config.yaml`):
1. trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files
2. black (code formatting)
3. isort (import sorting)
4. codespell (spell checking)
5. flake8 (linting)

## Environment Variables

- `DANDI_DEVEL`: Enables hidden CLI options (e.g., explicit instance selection)
- `DANDI_LOG_LEVEL`: Log level (default INFO, use int like `10` for DEBUG)
- `DANDI_CACHE`: Persistent cache control (`clear` or `ignore`)
- `DANDI_INSTANCEHOST`: Host for local archive instance (default `localhost`)
- `{INSTANCE_NAME}_API_KEY`: API key per instance (e.g., `DANDI_API_KEY`, `DANDI_SANDBOX_API_KEY`)
- `DANDI_TESTS_PERSIST_DOCKER_COMPOSE`: Reuse Docker containers across test runs
- `DANDI_TESTS_PULL_DOCKER_COMPOSE`: Set to empty/`0` to skip pulling Docker images
- `DANDI_TESTS_NO_VCR`: Disable VCR HTTP replay during tests
- `DANDI_PAGINATION_DISABLE_FALLBACK`: Disable fallback to sequential pagination (set in test envs)

## CI/CD

- **Tests** (`run-tests.yml`): Matrix of Python 3.10-3.13 across Ubuntu, macOS (M1 + Intel), Windows
- **Lint** (`lint.yml`): codespell + flake8
- **Typing** (`typing.yml`): mypy
- **Docs** (`docs.yml`): Sphinx build
- **Release** (`release.yml`): Automated via `auto` tool - PR labels (`major`, `minor`, `patch`, `internal`, etc.) drive changelog and version bumps; tagged releases trigger PyPI upload

## Documentation

- Keep docstrings updated when changing function signatures
- CLI help text should be clear and include examples where appropriate
- Dataclass fields: document with `#:` comments above the field, not docstrings below

## Issue Tracking with git-bug

This project has GitHub issues synced locally via git-bug. Use these commands
to get issue context without needing GitHub API access:
- `git bug ls status:open` - list open issues
- `git bug show <id-prefix>` - show issue details and comments
- `git bug ls "title:keyword"` - search issues by title
- `git bug ls "label:bug"` - filter by label
- `git bug bridge pull` - sync latest issues from GitHub

When working on a bug fix or feature, check `git bug ls` for related issues
to understand context and prior discussion.
