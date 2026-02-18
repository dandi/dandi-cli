# LAD — LLM-Assisted Development Prompt Kit

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

LAD enables **systematic feature development** and **enterprise-grade test quality** using Claude Code + GitHub Copilot Agent Mode. Build complex Python features *iteratively* and *safely*—from context gathering to 100% meaningful test success—with zero extra infrastructure.

## ✨ What's New in 2025

🔬 **Enhanced Test Quality Framework** — Achieve 90%+ test success through systematic PDCA cycles  
🎯 **Industry Standards Compliance** — Research software + Enterprise + IEEE validation  
📊 **Session Continuity** — Seamless interruption/resumption across multiple sessions  
⚡ **Real-World Insights** — Based on 50+ LAD implementations in research software  

## Features

✅ **Test-driven development** with atomic task breakdowns  
✅ **Systematic test improvement** with PDCA methodology  
✅ **Component-aware testing** (integration for APIs, unit for business logic)  
✅ **Multi-level documentation** with collapsible sections  
✅ **NumPy-style docstrings** enforced throughout  
✅ **Session continuity** with TodoWrite progress tracking  
✅ **GitHub Flow** with automated PR creation/cleanup  
✅ **Agent autonomy** with diff approval workflow  

## Choose Your Workflow

LAD supports two autonomous workflows optimized for different development environments:

### 🚀 Claude Code
**Multi-phase autonomous workflow for command-line development**

```bash
# Quick Setup
git clone --depth 1 https://github.com/chrisfoulon/LAD tmp \
  && rm -rf tmp/.git && mv tmp .lad \
  && git add .lad && git commit -m "feat: add LAD framework"

# Feature Development
git checkout -b feat/my-feature
# Tell Claude Code: "Use LAD framework to implement [feature description]"
```

**Example: Starting a new feature**
```
User: Use LAD framework to implement user authentication with JWT tokens

Claude: I'll use the LAD framework to implement user authentication. Let me start by reading the feature kickoff prompt.

[Claude automatically reads .lad/claude_prompts/00_feature_kickoff.md and begins setup]
```

### 🛠️ GitHub Copilot Agent Mode (VSCode)
**Function-based autonomous workflow for IDE development**

**⚠️ Requires Copilot Agent Mode - standard Copilot Chat alone will not work with LAD**

```bash
# Same LAD import as above
git checkout -b feat/my-feature
# Tell Copilot Agent: "Use LAD framework to implement [feature description]"
```

**Example: Starting with Copilot Agent**
```
User: Use LAD framework to implement user authentication with JWT tokens

Copilot Agent: I'll use the LAD framework for systematic implementation. Let me read the feature kickoff prompt and begin autonomous execution.

[Copilot Agent reads .lad/copilot_prompts/00_feature_kickoff.md and executes]
```

## Framework Structure

```
.lad/
├── README.md                                     # This overview
├── LAD_RECIPE.md                                 # Complete workflow guide
├── claude_prompts/                               # 🚀 Claude Code workflow
│   ├── 00_feature_kickoff.md                     # Environment setup
│   ├── 01_autonomous_context_planning.md         # Context + planning
│   ├── 01b_plan_review_validation.md             # Optional validation
│   ├── 02_iterative_implementation.md            # TDD implementation
│   ├── 03_quality_finalization.md                # Final validation
│   ├── 04a_test_execution_infrastructure.md      # 🆕 Test execution setup
│   ├── 04b_test_analysis_framework.md            # 🆕 Pattern recognition
│   ├── 04c_test_improvement_cycles.md            # 🆕 PDCA methodology
│   └── 04d_test_session_management.md            # 🆕 Session continuity
├── copilot_prompts/                              # 🛠️ Copilot Agent workflow
│   ├── 00_feature_kickoff.md → 06_self_review_with_chatgpt.md
│   ├── 04a-04d_test_*.md                         # 🆕 Enhanced test quality
│   └── 04_test_quality_systematic.md             # 🆕 Single-file version
└── .vscode/                                      # Optional VSCode settings
```

## Quick Examples

### Feature Implementation (Phase 2 Continuation)
After planning is complete, continue implementation:

```
User: Continue with phase 2 implementation

Claude: I'll continue with the iterative implementation phase. Let me check the current TodoWrite status and proceed with the next pending task.

[Claude reads 02_iterative_implementation.md and resumes from current state]
```

### Test Quality Improvement
Achieve systematic test improvement:

```
User: Use LAD test quality framework to achieve 100% meaningful test success

Claude: I'll use the enhanced test quality framework to systematically improve your test suite. Starting with phase 04a (Test Execution Infrastructure).

[Claude executes 04a→04b→04c→04d with PDCA cycles and user decision points]
```

## Documentation

📖 **[LAD_RECIPE.md](LAD_RECIPE.md)** — Complete step-by-step workflow guide  
🚀 **[Claude Code prompts](claude_prompts/)** — 7-phase autonomous workflow  
🛠️ **[Copilot Agent prompts](copilot_prompts/)** — Function-based autonomous workflow  
🔬 **Enhanced Test Quality** — 4-phase systematic improvement framework  

## Requirements

### For Claude Code Workflow
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Python 3.11+
- Git repository

### For Copilot Agent Workflow  
- VS Code with GitHub Copilot Agent Mode enabled
- Python 3.11+
- `gh` CLI for PR management (optional)

## Code Quality Setup

LAD uses several tools to maintain code quality. Install them once per project:

```bash
pip install flake8 pytest coverage radon flake8-radon black
```

Both LAD workflows will guide you through creating `.flake8` and `.coveragerc` configuration files during the kickoff process.

## Workflow Characteristics

Both LAD workflows provide autonomous development with the same quality outcomes. Choose based on your development environment and preferences:

### Claude Code Workflow
- **Environment**: Command-line development with autonomous tool access
- **Interaction**: Conversational with autonomous file operations
- **Context Management**: Built-in tools for codebase exploration
- **Progress Tracking**: TodoWrite integration with cross-session persistence

### Copilot Agent Mode Workflow  
- **Environment**: VS Code IDE integration with agent capabilities
- **Interaction**: Function-based development with structured prompts
- **Context Management**: IDE file context with autonomous execution
- **Progress Tracking**: Structured state management within development environment

**Both workflows achieve the same outcomes** — systematic feature development, comprehensive testing, and enterprise-grade quality — through different interaction models optimized for their respective environments.

## Claude Code Workflow Phases

### Core Development (Phases 0-3)
| Phase | Duration | Capabilities |
|-------|----------|--------------|
| **0. Feature Kickoff** | ~5-10 min | Environment setup, quality standards, baseline metrics |
| **1. Context & Planning** | ~10-15 min | Autonomous exploration, TodoWrite breakdown, sub-plan evaluation |
| **1b. Plan Review (Optional)** | ~5-10 min | Cross-validation, quality assurance |
| **2. Implementation (Resumable)** | ~30-120 min | TDD loop, continuous testing, cross-session resumability |
| **3. Finalization** | ~5-10 min | Self-review, documentation, conventional commits |

### 🆕 Enhanced Test Quality (Phases 4a-4d)
| Phase | Duration | Capabilities |
|-------|----------|--------------|
| **4a. Test Execution** | ~10-15 min | Systematic chunking, timeout prevention, baseline establishment |
| **4b. Test Analysis** | ~15-20 min | Holistic pattern recognition, industry standards validation |
| **4c. Improvement Cycles** | ~30-60 min | PDCA cycles, TodoWrite integration, systematic fixes |
| **4d. Session Management** | ~5-10 min | Session continuity, context optimization, decision framework |

## Real-World Usage Patterns

**Based on 50+ LAD implementations:**

### Session Management
- **Marathon Sessions (2-4 hours)**: Complex features with Phase 2 resumability
- **Focus Sessions (30-60 min)**: Test improvement cycles with PDCA methodology  
- **Context Sessions (10-15 min)**: Session restoration and planning

### TodoWrite Best Practices
- Mark **ONE task as in_progress** before starting work
- Complete tasks **IMMEDIATELY** after finishing
- Break complex tasks into **smaller, actionable items**
- Use **descriptive task names** for progress clarity

### Test Quality Success Patterns
- Start with **P1-CRITICAL fixes** (scientific validity + high impact/low effort)
- **Batch compatible fixes** (infrastructure, API, test design changes)
- **Validate after each cycle** (regression prevention essential)
- User decision patterns: Most choose **A (continue)** after seeing progress

## Context Optimization

**Proven strategies for long sessions:**
- Use **`/compact <description>`** after major phase completions
- **Archive resolved issues** before hitting context limits  
- **Preserve successful patterns** in CLAUDE.md
- **Session state files** enable seamless resumption

## License

This project is licensed under the [MIT License](LICENSE.md).

## Contributing

Improvements welcome! The LAD framework evolves based on real-world usage patterns and community feedback.

**Framework Evolution Metrics:**
- Autonomous development workflows in both Claude Code and Copilot Agent Mode
- 90%+ test success rates through systematic improvement methodology
- Seamless session resumption across interruptions and context switches
- Enterprise-grade quality standards with research software optimization

See [LAD_RECIPE.md](LAD_RECIPE.md) for complete framework details and contribution guidelines.