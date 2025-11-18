# Creating bids-duckdb as a Standalone Package

This guide shows how to replicate the BIDS DuckDB loader as an independent project at https://github.com/con/bids-duckdb.

## Repository Structure

```
bids-duckdb/
├── .github/
│   └── workflows/
│       ├── test.yml              # CI for testing
│       └── publish.yml            # CD for PyPI releases
├── src/
│   └── bids_duckdb/
│       ├── __init__.py            # Package entry point
│       ├── loader.py              # Main BIDSDuckDBLoader class
│       ├── schema.py              # Schema fetching/parsing
│       ├── _version.py            # Version info
│       └── py.typed               # PEP 561 marker for type hints
├── tests/
│   ├── __init__.py
│   ├── test_loader.py             # Main functionality tests
│   ├── test_schema.py             # Schema parsing tests
│   └── conftest.py                # Pytest fixtures
├── examples/
│   ├── basic_usage.py
│   ├── advanced_queries.py
│   └── version_comparison.py
├── docs/
│   ├── index.md
│   ├── quickstart.md
│   ├── api.md
│   └── examples.md
├── .gitignore
├── .pre-commit-config.yaml        # Pre-commit hooks
├── pyproject.toml                 # Modern Python packaging
├── README.md                      # Main documentation
├── LICENSE                        # Apache 2.0 recommended
├── CHANGELOG.md                   # Version history
└── CONTRIBUTING.md                # Contribution guidelines
```

## Step-by-Step Setup

### 1. Initialize Repository

```bash
# Clone the new repository
git clone https://github.com/con/bids-duckdb.git
cd bids-duckdb

# Create directory structure
mkdir -p src/bids_duckdb tests examples docs .github/workflows
```

### 2. Create pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "setuptools-scm>=8.0"]
build-backend = "setuptools.build_meta"

[project]
name = "bids-duckdb"
description = "Schema-driven BIDS dataset loader for DuckDB"
readme = "README.md"
requires-python = ">=3.9"
license = {text = "Apache-2.0"}
authors = [
    {name = "Your Name", email = "your.email@example.com"},
]
maintainers = [
    {name = "Your Name", email = "your.email@example.com"},
]
keywords = [
    "BIDS",
    "Brain Imaging Data Structure",
    "DuckDB",
    "neuroimaging",
    "data analysis",
    "metadata",
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: Apache Software License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Scientific/Engineering",
    "Topic :: Database",
]
dependencies = [
    "duckdb >= 0.9.0",
    "pyyaml >= 5.0",
]
dynamic = ["version"]

[project.optional-dependencies]
dev = [
    "pytest >= 7.0",
    "pytest-cov",
    "pytest-timeout",
    "black >= 23.0",
    "isort >= 5.0",
    "mypy >= 1.0",
    "pre-commit",
]
docs = [
    "mkdocs",
    "mkdocs-material",
    "mkdocstrings[python]",
]
examples = [
    "pandas >= 1.0",  # For displaying query results
    "matplotlib",     # For visualizations
]
all = [
    "bids-duckdb[dev]",
    "bids-duckdb[docs]",
    "bids-duckdb[examples]",
]

[project.urls]
Homepage = "https://github.com/con/bids-duckdb"
Documentation = "https://bids-duckdb.readthedocs.io"
Repository = "https://github.com/con/bids-duckdb"
"Bug Tracker" = "https://github.com/con/bids-duckdb/issues"
Changelog = "https://github.com/con/bids-duckdb/blob/main/CHANGELOG.md"

[project.scripts]
bids-duckdb = "bids_duckdb.cli:main"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
include = ["bids_duckdb*"]
namespaces = false

[tool.setuptools_scm]
version_file = "src/bids_duckdb/_version.py"

[tool.black]
line-length = 100
target-version = ["py39", "py310", "py311", "py312"]
exclude = '''
/(
    \.git
  | \.venv
  | \.tox
  | build
  | dist
  | _version\.py
)/
'''

[tool.isort]
profile = "black"
line_length = 100
force_sort_within_sections = true
known_first_party = ["bids_duckdb"]

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
strict_equality = true
plugins = []

[[tool.mypy.overrides]]
module = [
    "yaml.*",
]
ignore_missing_imports = true

[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
addopts = [
    "-v",
    "--tb=short",
    "--strict-markers",
    "--cov=bids_duckdb",
    "--cov-report=term-missing",
    "--cov-report=html",
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
]

[tool.coverage.run]
source = ["src"]
omit = ["src/bids_duckdb/_version.py"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@abstractmethod",
]
```

### 3. Split the Code into Modules

#### `src/bids_duckdb/__init__.py`

```python
"""BIDS to DuckDB loader with schema-driven entity extraction."""

from .loader import BIDSDuckDBLoader
from .schema import fetch_bids_schema, get_entity_patterns

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

__all__ = [
    "BIDSDuckDBLoader",
    "fetch_bids_schema",
    "get_entity_patterns",
    "__version__",
]
```

#### `src/bids_duckdb/schema.py`

Extract the schema-related functions from the original `bids_duckdb.py`:

```python
"""BIDS schema fetching and parsing utilities."""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from urllib.request import urlopen

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class BIDSSchemaError(Exception):
    """Raised when there's an error loading or parsing the BIDS schema."""
    pass


@lru_cache(maxsize=1)
def fetch_bids_schema(
    schema_url: str = "https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/objects/entities.yaml",
) -> dict[str, dict[str, Any]]:
    """Fetch and parse the BIDS schema from the official specification."""
    # ... (copy implementation from dandi-cli version)


def get_entity_patterns(
    schema: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Generate regex patterns for extracting BIDS entities from filenames."""
    # ... (copy implementation from dandi-cli version)
```

#### `src/bids_duckdb/loader.py`

Main loader class (copy from `dandi/bids_duckdb.py` but adjust imports):

```python
"""Main BIDSDuckDBLoader class for loading BIDS datasets into DuckDB."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

try:
    import duckdb
    from duckdb import DuckDBPyConnection
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False
    DuckDBPyConnection = Any

from .schema import fetch_bids_schema, get_entity_patterns


class DuckDBNotInstalledError(ImportError):
    """Raised when DuckDB is required but not installed."""
    # ... (copy implementation)


class BIDSDuckDBLoader:
    """Load BIDS datasets into DuckDB with schema-driven entity extraction."""
    # ... (copy full implementation from dandi-cli)
```

#### `src/bids_duckdb/cli.py` (Optional)

Add a CLI for convenience:

```python
"""Command-line interface for bids-duckdb."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loader import BIDSDuckDBLoader


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Load BIDS datasets into DuckDB for analysis"
    )
    parser.add_argument(
        "bids_root",
        type=Path,
        help="Path to BIDS dataset root directory",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output DuckDB database file (default: in-memory)",
    )
    parser.add_argument(
        "--schema-url",
        help="URL to BIDS schema (default: latest master)",
    )
    parser.add_argument(
        "--load-all",
        action="store_true",
        help="Load all data types (participants, JSON, TSV)",
    )

    args = parser.parse_args()

    if not args.bids_root.exists():
        print(f"Error: BIDS root not found: {args.bids_root}", file=sys.stderr)
        return 1

    try:
        with BIDSDuckDBLoader(
            args.bids_root,
            db_path=str(args.output) if args.output else None,
            schema_url=args.schema_url,
        ) as loader:
            if args.load_all:
                print("Loading dataset...")
                loader.load_participants()
                loader.load_sidecar_json()
                loader.load_tsv_files()

                tables = loader.get_tables()
                print(f"✓ Loaded {len(tables)} tables: {', '.join(tables)}")

                if args.output:
                    print(f"✓ Saved to: {args.output}")
            else:
                print("Use --load-all to load data into the database")
                print(f"Available entities: {len(loader.entities)}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

#### `src/bids_duckdb/py.typed`

Empty file to enable type checking (PEP 561):

```bash
touch src/bids_duckdb/py.typed
```

### 4. Set Up Tests

#### `tests/conftest.py`

```python
"""Pytest configuration and fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def mock_bids_dataset(tmp_path: Path) -> Path:
    """Create a minimal BIDS dataset for testing."""
    # ... (copy from dandi-cli test_bids_duckdb.py)
    return dataset_root
```

#### `tests/test_schema.py`

```python
"""Tests for BIDS schema fetching and parsing."""

import pytest

from bids_duckdb import fetch_bids_schema, get_entity_patterns


def test_fetch_bids_schema() -> None:
    """Test fetching and parsing the BIDS schema."""
    schema = fetch_bids_schema()

    assert isinstance(schema, dict)
    assert len(schema) > 0
    assert "subject" in schema
    assert schema["subject"]["name"] == "sub"


def test_get_entity_patterns() -> None:
    """Test entity pattern extraction from schema."""
    patterns = get_entity_patterns()

    assert isinstance(patterns, dict)
    assert "subject" in patterns
    assert patterns["subject"] == "sub"
```

#### `tests/test_loader.py`

```python
"""Tests for BIDSDuckDBLoader."""

from pathlib import Path

import pytest

from bids_duckdb import BIDSDuckDBLoader

# Copy tests from dandi-cli test_bids_duckdb.py
```

### 5. Create Documentation

#### `README.md`

```markdown
# bids-duckdb

[![PyPI](https://img.shields.io/pypi/v/bids-duckdb.svg)](https://pypi.org/project/bids-duckdb/)
[![Tests](https://github.com/con/bids-duckdb/workflows/Tests/badge.svg)](https://github.com/con/bids-duckdb/actions)
[![codecov](https://codecov.io/gh/con/bids-duckdb/branch/main/graph/badge.svg)](https://codecov.io/gh/con/bids-duckdb)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Schema-driven loader for BIDS datasets into DuckDB, enabling efficient SQL-based querying and analysis of neuroimaging metadata.

## Features

- 🔄 **Schema-driven**: Automatically adapts to different BIDS versions
- 🚀 **Fast**: Leverages DuckDB's analytical performance
- 🎯 **Dynamic**: Extracts all BIDS entities from filenames automatically
- 📊 **SQL-based**: Use familiar SQL for complex queries
- 🔧 **Flexible**: Works with JSON sidecars, TSV files, and participants data

## Installation

```bash
pip install bids-duckdb
```

Or install from source:

```bash
git clone https://github.com/con/bids-duckdb.git
cd bids-duckdb
pip install -e .
```

## Quick Start

```python
from pathlib import Path
from bids_duckdb import BIDSDuckDBLoader

# Load BIDS dataset
with BIDSDuckDBLoader(Path("/path/to/bids")) as loader:
    loader.load_participants()
    loader.load_sidecar_json()

    # Query with SQL
    df = loader.query("""
        SELECT subject, task, COUNT(*) as n_scans
        FROM sidecar_metadata
        GROUP BY subject, task
    """)
    print(df)
```

## Documentation

Full documentation available at: https://bids-duckdb.readthedocs.io

- [Quick Start Guide](docs/quickstart.md)
- [API Reference](docs/api.md)
- [Examples](docs/examples.md)

## How It Works

1. Fetches BIDS schema from official specification
2. Parses entity definitions (sub, ses, task, etc.)
3. Dynamically generates SQL with regex patterns
4. Loads BIDS files into queryable DuckDB tables

## Examples

See [examples/](examples/) directory for complete examples:

- `basic_usage.py` - Basic loading and querying
- `advanced_queries.py` - Complex analysis patterns
- `version_comparison.py` - Using different BIDS versions

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

## Citation

If you use this tool in your research, please cite:

```bibtex
@software{bids_duckdb,
  title = {bids-duckdb: Schema-driven BIDS to DuckDB loader},
  author = {Your Name},
  year = {2024},
  url = {https://github.com/con/bids-duckdb}
}
```

## Related Projects

- [BIDS Specification](https://bids-specification.readthedocs.io/)
- [PyBIDS](https://github.com/bids-standard/pybids)
- [DuckDB](https://duckdb.org/)
```

### 6. GitHub Actions CI/CD

#### `.github/workflows/test.yml`

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.9", "3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # For setuptools-scm

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run type checking
        run: mypy src

      - name: Run linting
        run: |
          black --check src tests
          isort --check-only src tests

      - name: Run tests
        run: pytest --cov --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        if: matrix.os == 'ubuntu-latest' && matrix.python-version == '3.11'
        with:
          file: ./coverage.xml
```

#### `.github/workflows/publish.yml`

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install build dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Build package
        run: python -m build

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

### 7. Pre-commit Configuration

#### `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: debug-statements

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-PyYAML]
        args: [--strict, --ignore-missing-imports]
```

### 8. Additional Files

#### `CONTRIBUTING.md`

```markdown
# Contributing to bids-duckdb

We welcome contributions! Please follow these guidelines:

## Development Setup

1. Fork and clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate it: `source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
4. Install in dev mode: `pip install -e ".[dev]"`
5. Install pre-commit hooks: `pre-commit install`

## Making Changes

1. Create a new branch: `git checkout -b feature-name`
2. Make your changes
3. Run tests: `pytest`
4. Run linting: `black src tests && isort src tests && mypy src`
5. Commit with clear message
6. Push and create a pull request

## Code Style

- Black formatting (line length 100)
- isort for imports
- Type hints for all functions
- Docstrings in NumPy style
- Tests for new features

## Testing

- Write tests for new functionality
- Ensure all tests pass
- Maintain >90% code coverage
```

#### `CHANGELOG.md`

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release
- Schema-driven BIDS entity extraction
- Support for JSON sidecars and TSV files
- Dynamic SQL generation based on BIDS schema
- Comprehensive test suite
- CLI interface

## [0.1.0] - 2024-XX-XX

### Added
- Initial alpha release
```

#### `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Type checking
.mypy_cache/
.dmypy.json

# DuckDB
*.duckdb
*.duckdb.wal
```

## Migration Checklist

- [ ] Create repository at https://github.com/con/bids-duckdb
- [ ] Set up directory structure
- [ ] Copy and adapt code from dandi-cli implementation
- [ ] Create pyproject.toml with dependencies
- [ ] Write comprehensive README
- [ ] Set up GitHub Actions CI/CD
- [ ] Configure pre-commit hooks
- [ ] Write additional examples
- [ ] Set up documentation (ReadTheDocs or GitHub Pages)
- [ ] Add CITATION.cff for academic citation
- [ ] Create first release (v0.1.0)
- [ ] Publish to PyPI
- [ ] Announce on BIDS forum/mailing list

## Differences from dandi-cli Version

### Simplifications:
1. **No dandi-specific dependencies** - Pure BIDS/DuckDB focus
2. **Simpler error handling** - Removed dandi validation integration
3. **CLI interface** - Added standalone CLI tool
4. **Documentation** - Focused on general BIDS use cases

### Enhancements:
1. **Better packaging** - Modern pyproject.toml with setuptools-scm
2. **More examples** - Dedicated examples directory
3. **CI/CD** - Full test matrix across Python versions and OSes
4. **Type checking** - Stricter mypy configuration
5. **Versioning** - Automatic version from git tags

## Publishing to PyPI

```bash
# Install build tools
pip install build twine

# Build distribution
python -m build

# Test upload (requires TestPyPI account)
twine upload --repository testpypi dist/*

# Production upload (requires PyPI account)
twine upload dist/*
```

## Documentation Hosting

### Option 1: ReadTheDocs

1. Connect GitHub repo to ReadTheDocs
2. Add `docs/` with MkDocs or Sphinx
3. Configure `.readthedocs.yaml`

### Option 2: GitHub Pages

```bash
# Install mkdocs
pip install mkdocs-material

# Build docs
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy
```

## Community Integration

1. **Announce on BIDS forum**: https://neurostars.org/
2. **Add to awesome-bids**: https://github.com/bids-standard/bids-awesome
3. **Integration with PyBIDS**: Potential future collaboration
4. **BIDS Apps**: Could be used in BIDS Apps for metadata extraction

## Maintenance

- **Versioning**: Use semantic versioning (MAJOR.MINOR.PATCH)
- **Releases**: Create GitHub releases with changelog
- **Dependencies**: Update quarterly, test with latest BIDS schema
- **BIDS schema**: Monitor for changes in entity definitions
- **DuckDB**: Track DuckDB releases for new features

## Future Enhancements

1. **Performance**: Add benchmarks for large datasets
2. **Validation**: Integrate BIDS validator for quality checks
3. **Export**: Add Parquet export functionality
4. **Views**: Predefined SQL views for common analyses
5. **Caching**: Cache parsed schemas locally
6. **Streaming**: Support for very large datasets
7. **Plugins**: Extension system for custom entity extractors
