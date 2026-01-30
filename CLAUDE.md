# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

For comprehensive development information, see `DEVELOPMENT.md` and the developer documentation in `docs/source/development/`.

## Build/Test Commands
- Run tests: `tox -e py3` but should also work with just `python -m pytest dandi` if in a venv
- Tests which require an instance of the archive, would use a fixture to start on using docker-compose.
- Set env var `DANDI_TESTS_PULL_DOCKER_COMPOSE=""` (to empty value) to avoid `docker compose pull` to speed up repetitive runs
- Run single test: `tox r -e py3 -- dandi/tests/test_file.py::test_function -v`
- Lint and type checking: `tox -e lint,typing`
- Install pre-commit hooks (if not installed as could be indicated by absence of
  `.git/hooks/pre-commit`): `pre-commit install`

## Committing
- Due to use of `pre-commit` with black and other commands which auto-fix, if changes
  were reported to be done, just rerun commit again 2nd time, and if only then if still
  does not commit analyze output more

## Test Markers
- When adding AI-generated tests, mark them with `@pytest.mark.ai_generated`
- Any new pytest markers must be registered in `tox.ini` under `[pytest]` section in the `markers` list

## Code Style
- Code is formatted with Black (line length 100)
- Imports sorted with isort (profile="black")
- Type annotations required for new code
- Use PEP 440 for versioning
- Class names: CamelCase; functions/variables: snake_case
- Exception names end with "Error" (e.g., `ValidateError`)
- Docstrings in NumPy style for public APIs
- Prefer specific exceptions over generic ones
- For CLI, use click library patterns
- Imports organized: stdlib, third-party, local (alphabetical within groups)

## Documentation
- Keep docstrings updated when changing function signatures
- CLI help text should be clear and include examples where appropriate
- Documentation files go in `docs/source/` (Sphinx RST format)
- Testing documentation: See `.lad/tmp/TESTING_BEST_PRACTICES.md` and `.lad/tmp/TESTING_GUIDELINES.md`

## File Placement Guidelines
**IMPORTANT**: Do not create analysis, baseline, or temporary files in the project root.

Proper file locations:
- **LAD session artifacts**: `.lad/tmp/` (test baselines, analysis reports, session notes)
- **Documentation**: `docs/source/` (must be RST format for Sphinx)
- **Test data**: `dandi/tests/data/`
- **Development notes**: `.lad/tmp/notes/` or personal notes outside the repo
- **Temporary scratch files**: Use system temp dir or `.lad/tmp/scratchpad/`

Examples of files that should NOT be in project root:
- ❌ `test_execution_baseline.md` → ✅ `.lad/tmp/test_execution_baseline.md`
- ❌ `analysis_report.md` → ✅ `.lad/tmp/analysis_report.md`
- ❌ `session_notes.txt` → ✅ `.lad/tmp/notes/session_notes.txt`
- ❌ `TESTING_GUIDE.md` → ✅ `docs/source/development/testing.rst` (converted to RST)
