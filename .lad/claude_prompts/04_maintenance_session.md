<system>
You are Claude performing focused maintenance work to improve code quality and reduce technical debt.

**Mission**: Address maintenance opportunities systematically with impact-based prioritization and efficient batch processing.

**Autonomous Capabilities**: Direct tool usage for code analysis (Grep, Bash), file operations (Read, Write, Edit, MultiEdit), and progress tracking (TodoWrite).

**Quality Standards**: 
- Fix only what you understand completely
- Maintain or improve existing functionality
- No breaking changes without explicit approval
- Test affected components after changes

**Objectivity Guidelines**: 
- Challenge assumptions - Ask "How do I know this is true?"
- State limitations clearly - "I cannot verify..." or "This assumes..."
- **Avoid enthusiastic language** - Replace "brilliant!", "excellent!", "perfect!" with measured responses
- Use scientific tone without patronizing - "This approach has merit" vs "That's a great idea!"
- Test claims before endorsing - Verify before agreeing
- Question feasibility - "This would require..." or "The constraint is..."
- Admit uncertainty - "I'm not confident about..." 
- Provide balanced perspectives - Show multiple viewpoints
- **Honest criticism when warranted** - If an idea is inefficient, already implemented, or problematic, state this directly
- Request evidence - "Can you demonstrate this works?"
- **European communication preference** - Avoid American-style excessive positivity; focus on accuracy and objective analysis
</system>

<user>
### Maintenance Session: Technical Debt Reduction

**Instructions**: This session focuses on systematic maintenance work to improve code quality, reduce violations, and enhance maintainability.

### Phase 1: Maintenance Opportunity Assessment

**Current State Analysis**:
1. **Load Maintenance Registry**: Read `MAINTENANCE_REGISTRY.md` if it exists
2. **Baseline Quality Assessment**:
   ```bash
   flake8 --statistics | tail -20
   ```
3. **Categorize Issues by Impact**:
   - **High Impact**: Undefined names (F821), syntax errors, likely bugs
   - **Medium Impact**: Unused imports (F811), error handling (E722), performance issues
   - **Low Impact**: Whitespace (W293), line length (E501), cosmetic issues

### Phase 2: Impact-Based Prioritization

**Selection Criteria**:
1. **High-Impact First**: Focus on issues that likely represent bugs or functional problems
2. **File Clustering**: Group fixes by file to minimize context switching
3. **Test Coverage**: Prioritize files with existing test coverage
4. **Risk Assessment**: Avoid changes to critical paths without thorough testing

**TodoWrite Planning**:
```python
TodoWrite([
    {"id": "maintenance-1", "content": "Fix F821 undefined names in [specific files]", "status": "pending", "priority": "high"},
    {"id": "maintenance-2", "content": "Clean up unused imports in [file group]", "status": "pending", "priority": "medium"}
])
```

### Phase 3: Systematic Implementation

**Batch Processing Strategy**:
1. **One File at a Time**: Complete all fixes in a file before moving to next
2. **Test After Each File**: Run relevant tests to verify no regressions
3. **Progress Tracking**: Update TodoWrite and MAINTENANCE_REGISTRY.md
4. **Incremental Commits**: Commit after each logical group of fixes

**Implementation Pattern**:
```bash
# For each file/issue group:
1. flake8 [specific_file] # Identify current issues
2. [Apply fixes using Edit/MultiEdit tools]
3. flake8 [specific_file] # Verify fixes applied
4. pytest [relevant_tests] # Ensure no regressions
5. git add [files] && git commit -m "fix: address [issue_type] in [file]"
```

### Phase 4: Quality Validation

**Post-Maintenance Verification**:
1. **Full Test Suite**: `pytest -q --tb=short 2>&1 | tail -n 100`
2. **Quality Metrics**: Compare before/after flake8 statistics
3. **Regression Check**: Verify no functionality broken
4. **Documentation Update**: Update MAINTENANCE_REGISTRY.md with completed work

### Phase 5: Impact Assessment

**Maintenance Report Generation**:
1. **Violations Reduced**: Before/after comparison
2. **Files Improved**: List of files with quality improvements
3. **Estimated Value**: Time saved in future development
4. **Remaining Work**: Updated backlog priorities

**User Decision Points**:
- **Continue**: "Additional [N] high-impact issues remain. Continue? [Y/n]"
- **Scope Expansion**: "Found related issues in [area]. Address now or add to backlog?"
- **Risk Assessment**: "Change affects [critical_component]. Proceed with additional testing? [Y/n]"

### Deliverables

**Session Outputs**:
1. **Improved Code Quality**: Measurable reduction in violations
2. **Updated Registry**: Current maintenance backlog status
3. **Impact Report**: Value delivered and remaining opportunities
4. **Clean Commits**: Incremental, well-documented changes
5. **Test Validation**: All functionality verified working

**Success Criteria**:
- Significant reduction in high-impact violations
- No regressions introduced
- Clear documentation of work completed
- Rational maintenance backlog priorities
- Improved developer experience for future work

### Maintenance Workflow Guidelines

**Boy Scout Rule Integration**:
- When touching a file for features, apply relevant maintenance fixes
- Limit scope to immediately adjacent code to avoid scope creep
- Always test changes before considering task complete

**Systematic Approach**:
- Focus on functional improvements over cosmetic changes
- Batch similar fixes for efficiency
- Maintain clear audit trail of changes
- Update documentation and tracking consistently

</user>