# Global Copilot Instructions

* Prioritize **minimal scope**: only edit code directly implicated by the failing test.  
* Protect existing functionality: do **not** delete or refactor code outside the immediate test context.
* Before deleting any code, follow the "Coverage & Code Safety" guidelines below.

Copilot, do not modify any files under .lad/.
All edits must occur outside .lad/, or in prompts/ when explicitly updating LAD itself.

Coding & formatting
* Follow PEP 8; run Black.
* Use type hints everywhere.
* External dependencies limited to numpy, pandas, requests.
* Target Python 3.11.

Testing & linting
* Write tests using component-appropriate strategy (see Testing Strategy below).
* Run flake8 with `--max-complexity=10`; keep complexity ≤ 10.
* Every function/class **must** include a **NumPy-style docstring** (Sections: Parameters, Returns, Raises, Examples).

## Testing Strategy by Component Type

**API Endpoints & Web Services:**
* Use **integration testing** - import the real FastAPI/Django/Flask app
* Mock only external dependencies (databases, external APIs, file systems)
* Test actual HTTP routing, validation, serialization, and error handling
* Verify real request/response behavior and framework integration

**Business Logic & Algorithms:**
* Use **unit testing** - mock all dependencies completely
* Test logic in complete isolation, focus on edge cases
* Maximize test speed and reliability
* Test pure business logic without framework concerns

**Data Processing & Utilities:**
* Use **unit testing** with minimal dependencies
* Use test data fixtures for predictable inputs
* Focus on input/output correctness and error handling

## Regression Prevention

**Before making changes:**
* Run full test suite to establish baseline: `pytest -q --tb=short`
* Identify dependencies: `grep -r "function_name" . --include="*.py"`
* Understand impact scope before modifications

**During development:**
* Run affected tests after each change: `pytest -q tests/test_modified_module.py`
* Preserve public API interfaces or update all callers
* Make minimal changes focused on the failing test

**Before commit:**
* Run full test suite: `pytest -q --tb=short`
* Verify no regressions introduced
* Ensure test coverage maintained or improved

## Code Quality Setup (One-time per project)

**1. Install quality tools:**
```bash
pip install flake8 pytest coverage radon flake8-radon black
```

**2. Configure .flake8 file in project root:**
```ini
[flake8]
max-complexity = 10
radon-max-cc = 10
exclude = 
    __pycache__,
    .git,
    .lad,
    .venv,
    venv,
    build,
    dist
```

**3. Configure .coveragerc file (see kickoff prompt for template)**

**4. Verify setup:**
```bash
flake8 --version                    # Should show flake8-radon plugin
radon --version                     # Confirm radon installation
pytest --cov=. --version           # Confirm coverage plugin
```

## Installing & Configuring Radon

**Install Radon and its Flake8 plugin:**
```bash
pip install radon flake8-radon
```
This installs Radon's CLI and enables the `--radon-max-cc` option in Flake8.

**Enable Radon in Flake8** by adding to `.flake8` or `setup.cfg`:
```ini
[flake8]
max-complexity = 10
radon-max-cc = 10
```
Functions exceeding cyclomatic complexity 10 will be flagged as errors (C901).

**Verify Radon raw metrics:**
```bash
radon raw path/to/your/module.py
```
Outputs LOC, LLOC, comments, blank lines—helping you spot oversized modules quickly.

**(Optional) Measure Maintainability Index:**
```bash
radon mi path/to/your/module.py
```
Gives a 0–100 score indicating code maintainability.

Coverage & Code Safety
* For safety checks, do **not** run coverage inside VS Code.  
  Instead, ask the user:
  > "Please run in your terminal:  
  > ```bash
  > coverage run -m pytest [test_files] -q && coverage html
  > ```  
  > then reply **coverage complete**."

* Before deleting code, verify:
  1. 0% coverage via `coverage report --show-missing`
  2. Absence from Level-2 API docs  
  If both hold, prompt:
  
  Delete <name>? (y/n)
  Reason: 0% covered and not documented.
  (Tip: use VS Code "Find All References" on <name>.)

Commits
* Use Conventional Commits. Example:  
  `feat(pipeline-filter): add ROI masking helper`
* Keep body as bullet list of sub-tasks completed.

Docs
* High-level docs live under the target project's `docs/` and are organised in three nested levels using `<details>` tags.

* After completing each **main task** (top-level checklist item), run:
  • `flake8 {{PROJECT_NAME}} --max-complexity=10`
  • `python -m pytest --cov={{PROJECT_NAME}} --cov-context=test -q --maxfail=1`
  If either step fails, pause for user guidance.

* **Radon checks:** Use `radon raw <file>` to get SLOC; use `radon mi <file>` to check maintainability. If `raw` LOC > 500 or MI < 65, propose splitting the module.
