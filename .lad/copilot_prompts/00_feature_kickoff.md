<system>
You are Claude, an AI onboarding engineer. Your mission is to gather ALL info needed to implement a new feature safely.
</system>
<user>
**Feature draft** ⟶ {{FEATURE_DRAFT_PARAGRAPH}}

⚠️ **Prerequisites**: 
- Ensure `.lad/` directory exists in your project root (should be committed on main branch).
- Ensure `.coveragerc` file exists in project root. If missing, create it with:
  ```ini
  [run]
  branch = True
  dynamic_context = test_function
  source = {{PROJECT_NAME}}
  omit =
      */__pycache__/*
      *.pyc
      .coverage
      .lad/*
  
  [report]
  exclude_lines =
      pragma: no cover
      if __name__ == .__main__.:
  show_missing = True
  
  [html]
  directory = coverage_html  ```
  (Replace `{{PROJECT_NAME}}` with your actual package name)

- Ensure `.flake8` file exists in project root. If missing, create it with:
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

Then:

1. Echo your understanding (≤100 words).
2. Ask for any missing inputs, outputs, edge-cases, perf/security requirements.
3. Detect obvious design forks (e.g. *pathlib* vs *os*) and ask me to choose.
4. When nothing is missing reply **READY** and output the variable map (e.g. `FEATURE_SLUG=…`) so you can substitute all `{{…}}` placeholders in future steps.

**Persist variables**  
Save the map above to `docs/{{FEATURE_SLUG}}/feature_vars.md` (create folders if missing).

**Deliverable**: Variable map printed + saved to feature_vars.md file.

</user>