# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MANDATORY: Read before making any code changes

You MUST read [`DEVELOPMENT.md`](./DEVELOPMENT.md) before making any code changes, commits, or
pull requests.  It contains the authoritative project conventions including:

- Build/test commands and CI/CD overview
- Codebase architecture, directory layout, key classes, and design patterns
- Code style rules (formatting, imports, type annotations, docstrings)
- Backward compatibility rules for supporting new dandi-archive features
- Testing requirements, including the **mandatory `@pytest.mark.ai_generated` marker on any test
  written with AI assistance**
- PR labeling and release workflow (intuit/auto)

Do NOT guess or assume conventions — read the file.

Additional developer documentation (testing and contributing guides) is in the Sphinx
docs under [`docs/source/development/`](./docs/source/development/).

## LLM-Assisted Development (LAD) Framework

The [`.lad/`](./.lad/) directory contains the
[LAD framework](https://github.com/chrisfoulon/LAD) — structured prompt
workflows for feature development using Claude Code or GitHub Copilot Agent
Mode.  When asked to "use LAD" or to follow a phased development workflow,
start from [`.lad/claude_prompts/00_feature_kickoff.md`](./.lad/claude_prompts/00_feature_kickoff.md).
See [`.lad/README.md`](./.lad/README.md) for the full overview and
[`.lad/CLAUDE.md`](./.lad/CLAUDE.md) for project-specific LAD context.

## Committing

Due to use of `pre-commit` with black and other auto-fixers, if changes were reported, just
rerun commit a 2nd time.  Only then if it still does not commit, analyze output further.

## Pull Requests

Keep PR descriptions short: a single paragraph saying what changes and why.
No section headings, file-by-file change lists, test logs or verification
write-ups; put details in commit messages or in replies to reviewers.

## Issue Tracking with git-bug

This project has GitHub issues synced locally via git-bug.  Use these commands
to get issue context without needing GitHub API access:
- `git bug ls status:open` — list open issues
- `git bug show <id-prefix>` — show issue details and comments
- `git bug ls "title:keyword"` — search issues by title
- `git bug ls "label:bug"` — filter by label
- `git bug bridge pull` — sync latest issues from GitHub

When working on a bug fix or feature, check `git bug ls` for related issues
to understand context and prior discussion.

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
