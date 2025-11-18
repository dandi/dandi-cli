#!/bin/bash
# Script to set up the bids-duckdb repository structure
# Usage: ./setup_bids_duckdb_repo.sh /path/to/bids-duckdb

set -e  # Exit on error

if [ $# -eq 0 ]; then
    echo "Usage: $0 /path/to/bids-duckdb"
    echo "Example: $0 ~/projects/bids-duckdb"
    exit 1
fi

REPO_DIR="$1"
DANDI_CLI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Setting up bids-duckdb repository at: $REPO_DIR"
echo "Source dandi-cli directory: $DANDI_CLI_DIR"
echo

# Create directory structure
echo "Creating directory structure..."
mkdir -p "$REPO_DIR"
cd "$REPO_DIR"

mkdir -p src/bids_duckdb
mkdir -p tests
mkdir -p examples
mkdir -p docs
mkdir -p .github/workflows

echo "✓ Directory structure created"
echo

# Create __init__.py files
echo "Creating package structure..."
touch src/bids_duckdb/__init__.py
touch tests/__init__.py

# Create py.typed marker
touch src/bids_duckdb/py.typed

echo "✓ Package structure created"
echo

# Copy and adapt main module
echo "Copying source code..."
if [ -f "$DANDI_CLI_DIR/dandi/bids_duckdb.py" ]; then
    # Split into schema.py and loader.py
    # For now, copy as-is and user can split manually
    cp "$DANDI_CLI_DIR/dandi/bids_duckdb.py" src/bids_duckdb/loader.py
    echo "✓ Copied loader.py (needs manual splitting into schema.py)"
else
    echo "⚠ Warning: Source bids_duckdb.py not found"
fi

# Copy tests
if [ -f "$DANDI_CLI_DIR/dandi/tests/test_bids_duckdb.py" ]; then
    cp "$DANDI_CLI_DIR/dandi/tests/test_bids_duckdb.py" tests/test_loader.py
    echo "✓ Copied tests"
else
    echo "⚠ Warning: Source tests not found"
fi

# Copy example
if [ -f "$DANDI_CLI_DIR/examples/bids_duckdb_example.py" ]; then
    cp "$DANDI_CLI_DIR/examples/bids_duckdb_example.py" examples/basic_usage.py
    echo "✓ Copied examples"
else
    echo "⚠ Warning: Source example not found"
fi

# Copy documentation
if [ -f "$DANDI_CLI_DIR/docs/bids_duckdb.md" ]; then
    cp "$DANDI_CLI_DIR/docs/bids_duckdb.md" docs/index.md
    echo "✓ Copied documentation"
fi

echo

# Create basic files
echo "Creating configuration files..."

# .gitignore
cat > .gitignore << 'EOF'
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
EOF

# LICENSE (Apache 2.0)
cat > LICENSE << 'EOF'
Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

Copyright 2024 bids-duckdb contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
EOF

# Basic README
cat > README.md << 'EOF'
# bids-duckdb

Schema-driven loader for BIDS datasets into DuckDB.

## Installation

```bash
pip install bids-duckdb
```

## Quick Start

```python
from pathlib import Path
from bids_duckdb import BIDSDuckDBLoader

with BIDSDuckDBLoader(Path("/path/to/bids")) as loader:
    loader.load_participants()
    loader.load_sidecar_json()

    df = loader.query("SELECT * FROM participants")
    print(df)
```

## Documentation

See [docs/](docs/) for full documentation.

## License

Apache License 2.0
EOF

# CHANGELOG
cat > CHANGELOG.md << 'EOF'
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Initial release
- Schema-driven BIDS entity extraction
- Support for JSON sidecars and TSV files
- CLI interface
EOF

# pyproject.toml
cat > pyproject.toml << 'EOF'
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
    {name = "BIDS DuckDB Contributors", email = ""},
]
keywords = ["BIDS", "DuckDB", "neuroimaging", "data analysis"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
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
    "black",
    "isort",
    "mypy",
]

[project.urls]
Homepage = "https://github.com/con/bids-duckdb"
Repository = "https://github.com/con/bids-duckdb"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools_scm]
version_file = "src/bids_duckdb/_version.py"

[tool.black]
line-length = 100

[tool.isort]
profile = "black"
line_length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["-v", "--cov=bids_duckdb"]
EOF

# GitHub Actions test workflow
cat > .github/workflows/test.yml << 'EOF'
name: Tests

on:
  push:
    branches: [main, master]
  pull_request:

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
          fetch-depth: 0

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run tests
        run: pytest
EOF

echo "✓ Configuration files created"
echo

# Initialize git if not already
if [ ! -d ".git" ]; then
    echo "Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit: bids-duckdb project structure"
    echo "✓ Git repository initialized"
else
    echo "Git repository already exists"
fi

echo
echo "=========================================="
echo "✓ Repository setup complete!"
echo "=========================================="
echo
echo "Next steps:"
echo "1. cd $REPO_DIR"
echo "2. Review and split src/bids_duckdb/loader.py into:"
echo "   - schema.py (schema fetching functions)"
echo "   - loader.py (BIDSDuckDBLoader class)"
echo "3. Create src/bids_duckdb/__init__.py with exports"
echo "4. Update tests/test_loader.py imports"
echo "5. Create virtual environment: python -m venv venv"
echo "6. Activate: source venv/bin/activate"
echo "7. Install dev mode: pip install -e '.[dev]'"
echo "8. Run tests: pytest"
echo "9. Push to GitHub: git remote add origin https://github.com/con/bids-duckdb.git"
echo "10. git push -u origin main"
echo
echo "See BIDS_DUCKDB_STANDALONE_GUIDE.md for detailed instructions"
