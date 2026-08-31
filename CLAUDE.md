# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MANDATORY: Read before making any code changes

You MUST read [`DEVELOPMENT.md`](./DEVELOPMENT.md) before making any code changes, commits, or
pull requests.  It contains the authoritative project conventions including:

- Build/test commands and CI/CD overview
- Codebase architecture, directory layout, key classes, and design patterns
- Code style rules (formatting, imports, type annotations, docstrings)
- Testing requirements, including the **mandatory `@pytest.mark.ai_generated` marker on any test
  written with AI assistance**
- PR labeling and release workflow (intuit/auto)

Do NOT guess or assume conventions — read the file.

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
