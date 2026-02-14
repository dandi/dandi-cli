# LLM‑Assisted‑Development (LAD) Framework

> **Goal**: Provide repeatable workflows for implementing complex Python features iteratively and safely.
>
> **Two Optimized Approaches:**
> 
> ## 🚀 Claude Code Workflow (Recommended for 2025)
> **3-phase autonomous workflow optimized for command-line development**
> 1. **Autonomous Context & Planning** — Dynamic codebase exploration + TDD planning
> 2. **Iterative Implementation** — TDD loop with continuous quality monitoring  
> 3. **Quality & Finalization** — Self-review + comprehensive validation
>
> ## 🛠️ GitHub Copilot Chat Workflow (VSCode)
> **8-step guided workflow for traditional development**
> 1. **Understand** a target slice of a large Python code‑base.
> 2. **Plan** a feature via test‑driven, step‑wise decomposition.
> 3. **Review** that plan (Claude & ChatGPT Plus).
> 4. **Implement** each sub‑task in tiny, self‑documenting commits while keeping tests green **and updating docs**.
> 5. **Merge & clean up** using a lightweight GitHub Flow.
>
> **Both approaches** deliver the same quality outcomes with different interaction models.

---

## 1 Repository Skeleton

```
├── README.md                                   # dual-workflow documentation
├── LAD_RECIPE.md                               # this file – complete guide
├── CLAUDE.md                                   # Claude Code persistent context
├── claude_prompts/                             # 🚀 Claude Code workflow
│   ├── 00_feature_kickoff.md
│   ├── 01_autonomous_context_planning.md
│   ├── 01b_plan_review_validation.md
│   ├── 01c_chatgpt_review.md
│   ├── 02_iterative_implementation.md
│   ├── 03_quality_finalization.md
│   ├── 04a_test_execution_infrastructure.md    # 🆕 Enhanced test quality
│   ├── 04b_test_analysis_framework.md          # 🆕 Pattern recognition
│   ├── 04c_test_improvement_cycles.md          # 🆕 PDCA methodology
│   └── 04d_test_session_management.md          # 🆕 Session continuity
├── copilot_prompts/                            # 🛠️ Copilot Chat workflow  
│   ├── 00_feature_kickoff.md
│   ├── 01_context_gathering.md
│   ├── 02_plan_feature.md
│   ├── 03_review_plan.md
│   ├── 03b_integrate_review.md
│   ├── 03_chatgpt_review.md
│   ├── 04_implement_next_task.md
│   ├── 04b_regression_recovery.md
│   ├── 04a_test_execution_infrastructure.md    # 🆕 Enhanced test quality
│   ├── 04b_test_analysis_framework.md          # 🆕 Pattern recognition
│   ├── 04c_test_improvement_cycles.md          # 🆕 PDCA methodology
│   ├── 04d_test_session_management.md          # 🆕 Session continuity
│   ├── 04_test_quality_systematic.md           # 🆕 Single-file Copilot version
│   ├── 05_code_review_package.md
│   └── 06_self_review_with_chatgpt.md
└── .vscode/                                    # optional for Copilot workflow
    ├── settings.json               
    └── extensions.json
```

Import the complete `.lad/` directory into any target project once on main.

* Target Python 3.11.
* Commit messages follow Conventional Commits.
* All generated docs follow the *plain summary + nested `<details>`* convention.

---

## 2 Claude Code Workflow (3-Phase Autonomous)

### 2.1 Quick Setup
1. **Install Claude Code**: Follow [Claude Code installation guide](https://docs.anthropic.com/en/docs/claude-code)
2. **Import LAD framework**:
   ```bash
   git clone --depth 1 https://github.com/chrisfoulon/LAD tmp \
     && rm -rf tmp/.git && mv tmp .lad \
     && git add .lad && git commit -m "feat: add LAD framework"
   ```
3. **Create feature branch**: `git checkout -b feat/<slug>`

### 2.2 Multi-Phase Execution

| Phase | Prompt | Duration | Capabilities |
|-------|--------|----------|--------------|
| **0. Feature Kickoff** | `claude_prompts/00_feature_kickoff.md` | ~5-10 min | Environment setup, quality standards, baseline metrics, configuration |
| **1. Context & Planning** | `claude_prompts/01_autonomous_context_planning.md` | ~10-15 min | Autonomous codebase exploration, TodoWrite task breakdown, sub-plan evaluation |
| **1b. Plan Review (Optional)** | `claude_prompts/01b_plan_review_validation.md` | ~5-10 min | Cross-validation, independent review, quality assurance |
| **1c. ChatGPT Review (Optional)** | `claude_prompts/01c_chatgpt_review.md` | ~5-10 min | External validation by ChatGPT, structured review, risk identification |
| **2. Implementation (Resumable)** | `claude_prompts/02_iterative_implementation.md` | ~30-120 min | TDD loop, continuous testing, cross-session resumability |
| **3. Finalization** | `claude_prompts/03_quality_finalization.md` | ~5-10 min | Self-review, documentation, conventional commits, cost optimization analysis |

### 2.3 🆕 Enhanced Test Quality Framework (Claude Code)

**4-Phase Systematic Test Improvement** - Achieve 100% meaningful test success through enterprise-grade methodologies:

| Phase | Prompt | Duration | Capabilities |
|-------|--------|----------|--------------|
| **4a. Test Execution Infrastructure** | `claude_prompts/04a_test_execution_infrastructure.md` | ~10-15 min | Systematic chunking, timeout prevention, comprehensive baseline establishment |
| **4b. Test Analysis Framework** | `claude_prompts/04b_test_analysis_framework.md` | ~15-20 min | Holistic pattern recognition, industry standards validation, priority matrix generation |
| **4c. Test Improvement Cycles** | `claude_prompts/04c_test_improvement_cycles.md` | ~30-60 min | PDCA cycles, TodoWrite integration, systematic implementation with validation |
| **4d. Test Session Management** | `claude_prompts/04d_test_session_management.md` | ~5-10 min | Session continuity, context optimization, adaptive decision framework |

**Key Benefits**: 
- 🎯 **Autonomous execution** — Minimal intervention points with autonomous tool usage
- ⚡ **3-5x faster development** — Autonomous execution with real-time feedback
- 🔄 **Continuous quality** — Integrated testing and regression prevention  
- 📊 **Progress visibility** — TodoWrite integration for status tracking
- 🛡️ **Quality assurance** — Comprehensive validation and testing
- 🔬 **Systematic improvement** — PDCA cycles for test quality optimization
- 📈 **Industry compliance** — Research software + Enterprise standards validation

### 2.4 Claude Code Workflow Features

**Autonomous Context Gathering**: 
- Uses Task/Glob/Grep tools for codebase exploration
- No need to manually open files or navigate directories
- Dynamic context based on feature requirements

**Integrated Quality Assurance**:
- Autonomous test execution with Bash tool
- Real-time regression testing
- Automated quality gates (flake8, coverage)

**Smart Progress Management**:
- TodoWrite for cross-session state persistence
- Automatic sub-plan splitting for complex features
- Context evolution for multi-phase implementations

**🆕 Enhanced Test Quality Capabilities**:
- **Systematic Test Improvement**: PDCA cycles with holistic pattern recognition
- **Industry Standards Validation**: Research software + Enterprise + IEEE compliance
- **Session Continuity**: Seamless interruption/resumption across multiple sessions
- **Token Optimization**: Efficient context management for large test suites
- **Priority Matrix**: Resource-optimized fix prioritization for solo programmers

### 2.5 Practical Usage with Claude Code

**How to use LAD with Claude Code**:

1. **Initial Setup**:
   - Import LAD framework into your project
   - Create feature branch
   - Tell Claude Code: "Use LAD framework to implement [feature description]"

2. **Phase Execution**:
   - Claude will automatically read and execute `.lad/claude_prompts/00_feature_kickoff.md`
   - After each phase, Claude returns to user for review and approval
   - User says "continue to next phase" or "proceed with implementation"
   - Claude reads the next appropriate prompt file and continues

3. **🆕 Test Quality Improvement**:
   - Say: "Use LAD test quality framework to achieve 100% meaningful test success"
   - Claude executes phases 04a→04b→04c→04d systematically
   - PDCA cycles with user decision points (Continue/Adjust/Coverage/Complete)
   - Sessions can be interrupted and resumed seamlessly

4. **Resumability**:
   - Can stop and resume at any point
   - Works across different sessions and machines
   - Phase 2 (Implementation) and 4c (Test Improvement) are especially resumable
   - User can say "continue implementation" or "continue test improvement" and Claude will detect current state

5. **User Interaction Points**:
   - After Phase 0: Review environment setup
   - After Phase 1: Review implementation plan
   - After Phase 1b/1c: Review validation
   - During Phase 2: Can stop/resume as needed
   - After Phase 3: Review final implementation
   - **🆕 During Phase 4c**: PDCA cycle decision points (A/B/C/D options)

6. **File Management**:
   - LAD framework files stay in `.lad/` folder (never modified)
   - All feature work goes in `docs/` folder
   - TodoWrite tracks progress across sessions
   - Plans and context files provide cross-session continuity
   - **🆕 Test improvement state**: Preserved in `notes/` for resumption

### 2.6 🆕 Real-World Usage Patterns & Insights

**Based on 50+ LAD sessions across research software development:**

**Session Management Patterns**:
- **Marathon Sessions (2-4 hours)**: Best for complex features, use Phase 2 resumability
- **Focus Sessions (30-60 min)**: Ideal for test improvement cycles, use Phase 4c PDCA
- **Context Switching**: Use `/compact <description>` after major phase completions

**TodoWrite Integration Success Patterns**:
- **Mark tasks in_progress BEFORE starting** (prevents duplicate work)
- **Complete tasks IMMEDIATELY after finishing** (maintains accurate state)
- **Only ONE task in_progress at a time** (maintains focus and clarity)
- **Break complex tasks into smaller, actionable items** (enables progress tracking)

**Test Quality Improvement Insights**:
- **Start with P1-CRITICAL fixes** (scientific validity + high impact/low effort)
- **Batch compatible fixes** (infrastructure changes, API updates, test design)
- **Validate after each cycle** (regression prevention is essential)
- **User decision patterns**: Most choose A (continue) after seeing progress

**Context Optimization Strategies**:
- **Archive resolved issues** before hitting context limits
- **Preserve successful patterns** in CLAUDE.md
- **Use session state files** for complex resumptions
- **Context restoration** from essential files when needed

**Common Anti-Patterns to Avoid**:
- ❌ Starting implementation without baseline testing
- ❌ Running multiple tasks in_progress simultaneously  
- ❌ Skipping validation steps in test improvement cycles
- ❌ Not using `/compact` when context becomes unwieldy
- ❌ Manual context management instead of using LAD session state

**Productivity Optimization Insights**:
- **Quick wins first** in test improvement cycles (builds momentum)
- **Context preservation** enables compound learning across sessions
- **Decision framework adaptation** improves with user pattern learning
- **Session continuity** maintains productivity across interruptions

---

## 3 Copilot Chat Workflow (8-Step Guided)

### 3.1 Quick‑Setup Checklist

1. Enable **Copilot Chat + Agent Mode** in VS Code.
2. **Import LAD kit once on main** (one-time setup):
   ```bash
   git clone --depth 1 https://github.com/chrisfoulon/LAD tmp \
     && rm -rf tmp/.git \
     && mv tmp .lad \
     && git add .lad && git commit -m "feat: add LAD framework"
   ```   * **Initialize coverage**: if `.coveragerc` is missing, scaffold it as above (branch=True, dynamic_context=test_function, omit `.lad/*`, show_missing=True, HTML dir `coverage_html`), then **manually** run:
     ```bash
     coverage run -m pytest [test_files] -q && coverage html
     ```
     in your external shell. Confirm back to Copilot with **coverage complete** before any deletion checks.
3. Install helper extensions (Python, Test Explorer, Coverage Gutters, Flake8).
4. Create **feature branch**:
   ```bash
   git checkout -b feat/<slug>
   ```
5. Open relevant files so Copilot sees context.

---

### 3.2 End‑to‑End Workflow

| # | Action                                                             | Prompt                                                 |
| - | ------------------------------------------------------------------ | ------------------------------------------------------ |
| 0 | **Kick‑off** · import kit & gather clarifications                  | `copilot_prompts/00_feature_kickoff.md`                                |
| 1 | Gather context → multi‑level docs                                  | `copilot_prompts/01_context_gathering.md`                              |
| 2 | Draft test‑driven plan                                             | `copilot_prompts/02_plan_feature.md`                                   |
| 3 | Claude plan review                                                 | `copilot_prompts/03_review_plan.md`                                    |
| 3b| Integrate reviews + evaluate plan splitting                        | `copilot_prompts/03b_integrate_review.md`                              |
| 3c| ChatGPT cross-validation                                           | `copilot_prompts/03_chatgpt_review.md`                                 |
| 4 | Implement **next** task → commit & push (supports sub-plans)       | `copilot_prompts/04_implement_next_task.md`                            |
| 4b| **Regression Recovery** (when tests break during implementation)   | `copilot_prompts/04b_regression_recovery.md`                           |
| 5 | ChatGPT self-review (optional)                                     | `copilot_prompts/06_self_review_with_chatgpt.md`                       |
| 6 | Compile review bundle → ChatGPT                                    | `copilot_prompts/05_code_review_package.md`                            |
| 7 | **Open PR** via `gh pr create`                                     | (shell)                                                |
| 8 | **Squash‑merge & delete branch** via `gh pr merge --delete-branch` | (shell)                                                |

### 3.3 🆕 Enhanced Test Quality Framework (Copilot)

**Systematic Test Improvement for GitHub Copilot** - Adapted for function-based and comment-driven development:

| Approach | Prompt | Use Case | Characteristics |
|----------|--------|----------|-----------------|
| **Single-File Framework** | `copilot_prompts/04_test_quality_systematic.md` | Simple projects, quick implementation | Comment-driven prompting, function headers, incremental development |
| **4-Phase Detailed Framework** | `copilot_prompts/04a-04d_*.md` | Complex projects, systematic improvement | Structured analysis, comprehensive documentation, enterprise-grade |

**Key Adaptations for Copilot**:
- **Comment-Based Prompting**: Structured comments before code blocks guide implementation
- **Function Header Driven**: Descriptive function signatures for code generation
- **Incremental Development**: Complex processes broken into manageable functions
- **Natural Language Integration**: Leverages Copilot's natural language understanding
- **Context Provision**: Explicit examples and patterns in function docstrings

**Usage Pattern**:
```python
# Initialize comprehensive test analysis environment  
# Purpose: Systematic test quality improvement for solo programmers
# Methodology: PDCA cycles with holistic pattern recognition

test_analyzer = TestQualityAnalyzer()  # Copilot suggests structure
categorized_failures = aggregate_failure_patterns_across_categories(test_results)
```

### 3.4 Plan Splitting for Complex Features

**Both workflows support automatic plan splitting** when complexity becomes unmanageable (>6 tasks, >25-30 sub-tasks, mixed domains):

**Splitting Benefits:**
- **Foundation-First**: Core models and infrastructure implemented first
- **Domain Separation**: Security, performance, and API concerns handled separately  
- **Context Inheritance**: Each sub-plan builds on previous implementations
- **Manageable Scope**: Each sub-plan stays ≤6 tasks, ≤25 sub-tasks

**Sub-Plan Structure:**
- `plan_0a_foundation.md` - Core models, job management, infrastructure
- `plan_0b_{{domain}}.md` - Business logic, pipeline integration
- `plan_0c_interface.md` - API endpoints, external interfaces  
- `plan_0d_security.md` - Security, performance, compatibility

**Context Evolution:** As each sub-plan completes, context files for subsequent sub-plans are updated with new APIs, interfaces, and integration points, ensuring later phases have complete system visibility.

### 3.5 Testing Strategy Framework

**LAD uses component-appropriate testing strategies** to ensure both comprehensive coverage and efficient development:

**API Endpoints & Web Services:**
- **Integration Testing**: Import and test the real FastAPI/Django/Flask app
- **Mock External Dependencies**: Only databases, external APIs, file systems
- **Test Framework Behavior**: HTTP routing, validation, serialization, error handling
- **Why**: APIs are integration points - the framework behavior is part of what you're building

**Business Logic & Algorithms:**
- **Unit Testing**: Mock all dependencies, test in complete isolation
- **Focus**: Edge cases, error conditions, algorithmic correctness
- **Benefits**: Fast execution, complete control, reliable testing
- **Why**: Pure logic should be testable without external concerns

**Data Processing & Utilities:**
- **Unit Testing**: Minimal dependencies, test data fixtures
- **Focus**: Input/output correctness, transformation accuracy
- **Benefits**: Predictable test data, isolated behavior verification

**Example - API Testing:**
```python
# ✅ Integration testing for API endpoints
from myapp.app import create_app  # Real app
from unittest.mock import patch

def test_api_endpoint():
    app = create_app()
    with patch('myapp.database.get_user') as mock_db:  # Mock external deps
        mock_db.return_value = {"id": 1, "name": "test"}
        client = TestClient(app)  # Test real routing/validation
        response = client.get("/api/users/1")
        assert response.status_code == 200
```

---

## 4 ✍️ Commit Drafting

After completing a sub‑task:

1. Draft a Conventional Commit header:
   ```
   feat({FEATURE_SLUG}): Short description
   ```
2. In the body, include a bullet list of sub‑tasks:
   ```
   - Add X functionality
   - Update tests for Y
   ```
3. Stage, commit, and push:
   ```bash
   git add .
   git commit -m "$(cat .git/COMMIT_EDITMSG)"
   git push
   ```

---

## 5 📄 Multi-level Documentation

Your context prompt generates three abstraction levels:

<details><summary>👶 Level 1 · Novice summary</summary>

Use this for a quick onboarding view.

</details>

<details><summary>🛠️ Level 2 · Key API table</summary>

Deep dive for power users.

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

Detailed implementation details with annotated source.

</details>

---

## 6 📝 Docstring Standard

All functions must use **NumPy-style docstrings**:

```python
def foo(arg1, arg2):
    """
    Short description.

    Parameters
    ----------
    arg1 : type
        Description.
    arg2 : type
        Description.

    Returns
    -------
    type
        Description.

    Raises
    ------
    Exception
        Description.
    """
    ...
```

---

## 7 🔍 PR Review Bundle

Before merging:

1. Paste the PR bundle into ChatGPT or Claude Agent.
2. Address feedback and make adjustments.
3. Merge and delete the branch.

---

## 8 🤖 Agent Autonomy Boundaries

The agent may run commands (push, commit), but will:

1. Output a diff-stat of changes.
2. Await your approval before finalizing the commit or merge.

---

## 9 ⚙️ Settings & Linting

* Lint using **Flake8**.
* Commit messages follow **Conventional Commits**.
* Docstrings follow **NumPy style**.

---

## 10 🆕 Advanced LAD Patterns & Best Practices

### 10.1 Session Continuity & Context Management

**Proven Context Management Strategies**:
- **Use `/compact <description>`** after major milestones to preserve essential context
- **Session state files** enable seamless resumption across interruptions
- **TodoWrite integration** maintains progress visibility across sessions
- **Context optimization** prevents token overflow in long-running improvements

**Session Types & Optimization**:
- **Sprint Sessions (30-60 min)**: Focus on specific phase or PDCA cycle
- **Marathon Sessions (2-4 hours)**: Complex feature implementation with breaks
- **Context Sessions (10-15 min)**: Context restoration and session planning

### 10.2 TodoWrite Integration Patterns

**Successful TodoWrite Usage**:
```markdown
# Proven TodoWrite patterns from 50+ LAD sessions

## Task State Management:
- Mark ONE task as in_progress before starting work
- Complete tasks IMMEDIATELY after finishing
- Break complex tasks into smaller, actionable items
- Use descriptive task names that indicate progress clearly

## Session Continuity:
- TodoWrite survives session interruptions
- Tasks preserve context for resumption
- Progress visibility enables compound productivity
- Cross-session state coordination
```

### 10.3 Test Quality Improvement Insights

**PDCA Cycle Success Patterns**:
- **P1-CRITICAL first**: Scientific validity + high impact/low effort
- **Batch compatible fixes**: Infrastructure, API, test design changes
- **Validate after each cycle**: Regression prevention is essential
- **User decision adaptation**: Learn from A/B/C/D choice patterns

**Resource Optimization for Solo Programmers**:
- **Quick wins build momentum**: Start cycles with simple, high-impact fixes
- **Solution interaction mapping**: Single fixes resolving multiple issues
- **Industry standards validation**: Objective prioritization through multiple standards
- **Energy management**: Complex tasks during peak productivity periods

### 10.4 Context Evolution & Knowledge Preservation

**Knowledge Accumulation Patterns**:
- **Successful approaches**: Preserve working patterns in CLAUDE.md
- **Failed approaches**: Document what to avoid and why
- **User preferences**: Learn decision patterns for framework adaptation  
- **Process optimization**: Compound improvement across multiple sessions

**Context File Organization**:
```
docs/
├── feature_context.md          # Current feature context
├── implementation_decisions/   # Decision rationale archive
├── session_archive/           # Historical session states
└── notes/
    ├── essential_context.md   # Critical information for resumption
    ├── pdca_session_state.md  # Test improvement progress
    └── next_session_prep.md   # Immediate actions for continuation
```

## 11 Extending This Framework

1. Keep prompts in VCS; refine as needed.
2. Add new templates for recurring jobs (DB migration, API client generation, etc.).
3. Share improvements back to your LAD repo.
4. **🆕 Customize test quality framework** for specific domain requirements.
5. **🆕 Adapt decision frameworks** based on team or project preferences.

Enjoy faster, safer feature development with comprehensive test quality improvement using the enhanced LAD framework!

---

### 11.1 🆕 Framework Evolution & Community Insights

**LAD Framework Maturity Indicators**:
- **50+ successful feature implementations** across research software projects
- **Systematic test improvement** achieving 90%+ meaningful success rates
- **Cross-session continuity** enabling compound productivity improvement
- **Industry standards compliance** balancing research software with enterprise quality

**Community Usage Patterns**:
- **Research Software Development**: Primary use case with domain-specific adaptations
- **Solo Programmer Optimization**: Resource-constrained development with maximum efficiency
- **Cross-Platform Compatibility**: Windows (WSL), macOS, Linux development environments
- **Multi-AI Integration**: Claude Code + GitHub Copilot + ChatGPT validation workflows

**Framework Impact Metrics**:
- **Autonomous development workflows** (both Claude Code and Copilot Agent Mode)
- **3-5x faster development cycles** through autonomous execution
- **90%+ test success rates** through systematic improvement
- **Seamless session resumption** across interruptions and context switches

This enhanced LAD framework represents the culmination of real-world usage patterns, systematic test improvement methodologies, and cross-session productivity optimization for solo programmers working on complex research software.