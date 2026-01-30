<system>
You are Claude, an expert software architect setting up a robust development environment for test-driven feature implementation.

**Mission**: Initialize the development environment, establish quality standards, and prepare for feature implementation using the LAD framework.

**Autonomous Capabilities**: File operations (Read, Write, Edit), command execution (Bash), environment validation, and configuration setup.

**Quality Standards**: 
- Flake8 compliance (max-complexity 10)
- Test coverage ≥90% for new code
- NumPy-style docstrings required
- Conventional commit standards

**Objectivity Guidelines**: 
- Challenge assumptions - Ask "How do I know this is true?"
- State limitations clearly - "I cannot verify..." or "This assumes..."
- Avoid enthusiastic agreement - Use measured language
- Test claims before endorsing - Verify before agreeing
- Question feasibility - "This would require..." or "The constraint is..."
- Admit uncertainty - "I'm not confident about..." 
- Provide balanced perspectives - Show multiple viewpoints
- Request evidence - "Can you demonstrate this works?"
</system>

<user>
### Feature Kickoff & Environment Setup

**Feature Request**: {{FEATURE_DESCRIPTION}}

**Instructions**: Set up the development environment and initialize quality standards before beginning feature implementation.

### Step 1: Environment Validation

**Check development environment**:
1. **Verify LAD Framework**:
   - Confirm `.lad/` folder exists and is properly structured
   - Check that all required prompt files are present
   - Validate framework integrity (don't modify `.lad/` contents)

2. **Python Environment**:
   - Check Python version (3.11+ required)
   - Verify required packages are installable
   - Test basic development tools

3. **Git Repository**:
   - Confirm we're in a git repository
   - Check current branch status
   - Verify clean working directory or document current state

### Step 2: Quality Standards Setup

**Create/verify quality configuration files**:

1. **Flake8 Configuration** (`.flake8`):
   ```ini
   [flake8]
   max-line-length = 88
   max-complexity = 10
   ignore = E203, E266, E501, W503
   exclude = .git,__pycache__,docs/,build/,dist/,.lad/
   ```

2. **Coverage Configuration** (`.coveragerc`):
   ```ini
   [run]
   branch = True
   source = .
   omit = 
       */tests/*
       */test_*
       */__pycache__/*
       */.*
       .lad/*
       setup.py
       */venv/*
       */env/*

   [report]
   show_missing = True
   skip_covered = False
   
   [html]
   directory = coverage_html
   ```

3. **Pytest Configuration** (add to `pytest.ini` or `pyproject.toml` if missing):
   ```ini
   [tool:pytest]
   testpaths = tests
   python_files = test_*.py
   python_classes = Test*
   python_functions = test_*
   addopts = --strict-markers --strict-config
   markers =
       slow: marks tests as slow (deselect with '-m "not slow"')
       integration: marks tests as integration tests
   ```

### Step 3: Baseline Quality Assessment

**Establish current state**:
1. **Test Suite Baseline**:
   ```bash
   pytest --collect-only  # Count existing tests
   pytest -q --tb=short   # Run existing tests
   ```

2. **Coverage Baseline**:
   ```bash
   pytest --cov=. --cov-report=term-missing --cov-report=html
   ```

3. **Code Quality Baseline**:
   ```bash
   flake8 --statistics
   ```

4. **Document Baseline**:
   - Record current test count
   - Record current coverage percentage
   - Record current flake8 violations
   - Save baseline metrics for comparison

### Step 4: Development Environment Preparation

**Prepare for feature implementation**:
1. **Create docs structure** (if not exists):
   ```
   docs/
   ├── _scratch/          # Temporary analysis files
   └── [feature-slug]/    # Feature-specific documentation
   ```

2. **Validate required tools**:
   - pytest (testing framework)
   - flake8 (linting)
   - coverage (coverage measurement)
   - git (version control)

3. **Environment Summary**:
   - Python version and virtual environment status
   - Git repository status
   - Baseline quality metrics
   - Development tools availability

### Step 5: Feature Preparation

**Initialize feature context**:
1. **Feature Identification**:
   - Extract feature slug from description
   - **Validate feature requirements are clear**:
     - If {{FEATURE_DESCRIPTION}} is vague (e.g., "add an API", "improve performance"), STOP and ask user:
       - What specific functionality should this feature provide?
       - What are the expected inputs and outputs?
       - What are the acceptance criteria for completion?
       - What constraints or limitations should be considered?
     - If requirements are unclear, respond: "I need more specific requirements before proceeding. Please clarify [specific questions]."
   - Identify any immediate blockers or dependencies

2. **Documentation Structure**:
   - Create `docs/{{FEATURE_SLUG}}/` directory
   - Prepare for context documentation
   - Set up plan and review file structure

3. **Variable Persistence**: Save feature variables to `docs/{{FEATURE_SLUG}}/feature_vars.md` (create folders if missing):
   ```bash
   FEATURE_SLUG={{FEATURE_SLUG}}
   PROJECT_NAME={{PROJECT_NAME}}
   FEATURE_DESCRIPTION="{{FEATURE_DESCRIPTION}}"
   # Additional variables as established during kickoff
   ```

4. **Quality Gates Preparation**:
   - Establish quality standards for this feature
   - Set coverage targets
   - Define complexity limits
   - Prepare testing strategy framework

### Deliverables

**Output the following**:
1. **Environment Status Report**: Current state of development environment
2. **Quality Configuration**: Created/verified configuration files
3. **Baseline Metrics**: Current test count, coverage, and quality metrics
4. **Feature Setup**: Prepared documentation structure and development context
5. **Variable Map**: Saved feature variables to `docs/{{FEATURE_SLUG}}/feature_vars.md`
6. **Next Steps**: Clear guidance for proceeding to Phase 1 (Context Planning)

**Quality Gates**:
- ✅ All required configuration files exist and are valid
- ✅ Development environment is functional
- ✅ Baseline metrics are established
- ✅ Feature documentation structure is prepared
- ✅ Quality standards are defined and measurable

**Success Criteria**:
- Development environment is ready for TDD implementation
- Quality standards are established and measurable
- Baseline metrics provide comparison point for improvements
- Feature context is prepared for autonomous implementation
- All tools and configurations are functional

**Important**: 
- Never modify files in `.lad/` folder - this contains the framework
- All feature work goes in `docs/` folder
- Preserve existing project structure and configurations
- Document any environment issues or limitations discovered

### Next Phase
After successful kickoff, proceed to Phase 1: Autonomous Context Planning using `.lad/claude_prompts/01_autonomous_context_planning.md`

</user>