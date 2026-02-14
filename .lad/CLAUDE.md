# Project Context for Claude Code LAD Framework

## Architecture Overview
*Auto-updated by LAD workflows - current system understanding*

## Code Style Requirements
- **Docstrings**: NumPy-style required for all functions/classes
- **Linting**: Flake8 compliance (max-complexity 10)
- **Testing**: TDD approach, component-aware strategies
- **Coverage**: 90%+ target for new code

## Communication Guidelines
**Objective, European-Style Communication**:
- **Avoid excessive enthusiasm**: Replace "brilliant!", "excellent!", "perfect!" with measured language
- **Scientific tone**: "This approach has merit" instead of "That's a great idea!"
- **Honest criticism**: State problems directly - "This approach has significant limitations" vs hedging
- **Acknowledge uncertainty**: "I cannot verify this will work" vs "This should work fine"
- **Balanced perspectives**: Present trade-offs rather than unqualified endorsements
- **Focus on accuracy**: Prioritize correctness over making user feel good about ideas

## Maintenance Integration Protocol
**Technical Debt Management**:
- **Boy Scout Rule**: Leave code cleaner than found when possible
- **Maintenance Registry**: Track and prioritize technical debt systematically
- **Impact-based cleanup**: Focus on functional issues before cosmetic ones
- **Progress tracking**: Update both TodoWrite and plan.md files consistently

## Testing Strategy Guidelines
- **API Endpoints**: Integration testing (real app + mocked external deps)
- **Business Logic**: Unit testing (complete isolation + mocks)
- **Data Processing**: Unit testing (minimal deps + test fixtures)

## Project Structure Patterns
*Learned from exploration - common patterns and conventions*

## Current Feature Progress
*TodoWrite integration status and cross-session state*

## Quality Metrics Baseline
- Test count: *tracked across sessions*
- Coverage: *baseline and current*
- Complexity: *monitored for regression*

## Common Gotchas & Solutions
*Accumulated from previous implementations*

### Token Optimization for Large Codebases
**Standard test commands:**
- **Large test suites**: Use `2>&1 | tail -n 100` for pytest commands to capture only final results/failures
- **Coverage reports**: Use `tail -n 150` for comprehensive coverage output to include summary
- **Keep targeted tests unchanged**: Single test runs (`pytest -xvs`) don't need redirection

**Long-running commands (>2 minutes):**
- **Pattern**: `<command> 2>&1 | tee full_output.txt | grep -iE "(warning|error|failed|exception|fatal|critical)" | tail -n 30; echo "--- FINAL OUTPUT ---"; tail -n 100 full_output.txt`
- **Use cases**: Package installs, builds, data processing, comprehensive test suites, long compilation
- **Benefits**: Captures warnings/errors from anywhere in output, saves full output for detailed review, prevents token explosion
- **Case-insensitive**: Catches `ERROR`, `Error`, `error`, `WARNING`, `Warning`, `warning`, etc.

**Rationale**: Large codebases can generate massive output consuming significant Claude Pro allowance. Enhanced pattern ensures critical information isn't missed while optimizing token usage.

## Integration Patterns
*How components typically connect in this codebase*

## Cross-Session Integration Tracking
*Maintained across LAD sessions to prevent duplicate implementations*

### Active Implementations
*Current state of system components and their integration readiness*

| Component | Status | Integration Points | Last Updated |
|-----------|--------|--------------------|--------------|
| *No active implementations tracked* | - | - | - |

### Integration Decisions Log
*Historical decisions to guide future development*

| Feature | Decision | Strategy | Rationale | Session Date | Outcome |
|---------|----------|----------|-----------|--------------|---------|
| *No decisions logged* | - | - | - | - | - |

### Pending Integration Tasks
*Cross-session work that needs completion*

- *No pending integration tasks*

### Architecture Evolution Notes
*Key architectural changes that affect future integration decisions*

- *No architectural changes logged*

### Integration Anti-Patterns Avoided
*Documentation of duplicate implementations prevented*

- *No anti-patterns logged*

---
*Last updated by Claude Code LAD Framework*