# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

## Issue Tracking with git-bug
This project has GitHub issues synced locally via git-bug.  Use these commands
to get issue context without needing GitHub API access:
- `git bug ls status:open` - list open issues
- `git bug show <id-prefix>` - show issue details and comments
- `git bug ls "title:keyword"` - search issues by title
- `git bug ls "label:bug"` - filter by label
- `git bug bridge pull` - sync latest issues from GitHub

When working on a bug fix or feature, check `git bug ls` for related issues
to understand context and prior discussion.
