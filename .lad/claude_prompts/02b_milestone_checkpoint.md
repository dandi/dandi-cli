# Phase 2b: Milestone Checkpoint & User Approval

## Purpose
Provide structured milestone checkpoints during implementation to ensure user visibility, gather feedback, and maintain development momentum with appropriate approval gates.

## Note-Taking Protocol for Decision Tracking
For complex milestone decisions and cross-session continuity, create decision tracking notes to maintain context:
- **Milestone Notes**: `notes/milestone_{{date}}_{{feature}}.md` - Track checkpoint decisions, user feedback, and next steps
- **Decision Log**: `notes/decisions_{{feature}}.md` - Cumulative record of architectural and implementation decisions
- **Session Continuity**: `notes/session_{{date}}_state.md` - Current progress, blockers, and resumption context

## When to Use This Phase
This checkpoint is triggered automatically during Phase 2 (Iterative Implementation) when:
- 2-3 tasks have been completed in sequence
- A major implementation milestone is reached
- **Sub-plan completion** (all tasks in current sub-plan finished)
- Significant architectural or design decisions were made
- Quality gates indicate issues that need attention
- Before making breaking changes to existing code

## Pre-Checkpoint Assessment

### 0. Plan Structure Detection
**Determine if working with single plan or split plans**:
```bash
# Check for split plan structure
if [ -f "docs/{{FEATURE_SLUG}}/split_decision.md" ]; then
  echo "Split plan detected"
  # Identify current sub-plan
  current_plan=$(ls -t docs/{{FEATURE_SLUG}}/plan_*_*.md | head -1)
  echo "Current sub-plan: $current_plan"
fi
```

### 1. Progress Summary Generation
**Automatically generate summary of completed work:**

```markdown
## MILESTONE CHECKPOINT: {{FEATURE_SLUG}}

### ✅ Completed This Session
{{#each completed_tasks}}
- [x] {{name}}: {{description}}
  {{#if subtasks}}
  {{#each subtasks}}
    - [x] {{name}}
  {{/each}}
  {{/if}}
{{/each}}

### 📊 Quality Status
- **Tests Status**: {{test_status}} ({{passing_tests}}/{{total_tests}} passing)
- **Lint Compliance**: {{lint_status}} ({{lint_issues}} issues)
- **Coverage**: {{coverage_percent}}% (target: 90%+)
- **Complexity**: {{complexity_score}} (target: <10)

### 🔄 Integration Status
- **Modified Files**: {{modified_files_count}} files
- **New Files**: {{new_files_count}} files  
- **Test Files**: {{test_files_count}} files
- **Documentation**: {{docs_status}}
```

### 2. Change Impact Assessment
**Show user what has changed:**

```bash
# Show staged and unstaged changes
git status --porcelain
git diff --stat --staged
git diff --stat
```

### 3. Quality Validation with Manual Verification
**Run comprehensive quality checks with systematic manual validation:**

```bash
# Full test suite
pytest -q --tb=short

# Lint check on modified files  
flake8 {{modified_files}}

# Coverage report
pytest --cov={{feature_module}} --cov-report=term-missing --tb=no -q | tail -n 20
```

**Manual Validation Checklist**:
- **Implementation Verification**: Use `grep -r "key_function\|key_class" .` to verify planned components exist
- **Context Accuracy**: Compare context file claims with actual implementation using `Read` tool
- **Integration Points**: Test critical integration points manually: `python -c "from module import component; print('✅ Import works')"`
- **Functional Validation**: Run key functionality manually to verify it works as intended
- **Documentation Review**: Ensure documentation matches actual implementation behavior

## User Interaction Protocol

### 1. Milestone Presentation  
**Create milestone notes first, then present to user:**

```markdown
**CREATE MILESTONE NOTES**: `notes/milestone_{{date}}_{{feature}}.md`

## Checkpoint Summary
- **Milestone Type**: [Task completion, sub-plan completion, major decision point]
- **Completed Work**: [Specific deliverables and functionality implemented]
- **Quality Status**: [Test results, lint compliance, coverage metrics]
- **Integration Status**: [Working integration points, verified functionality]

## Decision Context
- **Architectural Decisions**: [Key technical choices made during implementation]  
- **Trade-offs**: [Performance vs. maintainability, complexity vs. flexibility decisions]
- **Deviations**: [Changes from original plan and rationale]
- **Discoveries**: [Unexpected findings or opportunities identified]

## Next Steps Analysis
- **Pending Tasks**: [Remaining work and estimated complexity]
- **Dependencies**: [What needs to be completed before next phase]
- **Risk Assessment**: [Potential blockers or integration challenges]
- **User Input Needed**: [Decisions requiring user guidance]
```

**Then present clear, structured information to user:**

```markdown
**MILESTONE REACHED: {{milestone_description}}**

**Summary**: {{brief_summary_of_progress}}

**Quality Metrics**:
- Tests: {{status_icon}} {{details}}
- Lint: {{status_icon}} {{details}}
- Coverage: {{status_icon}} {{details}}
- **Implementation Verification**: {{implementation_status_icon}} {{implementation_details}}
- **Context Accuracy**: {{context_status_icon}} {{context_details}}
- **Integration Status**: {{integration_status_icon}} {{integration_details}}

**Changes Made**:
{{git_diff_summary}}

**Next Planned Steps**:
{{#each upcoming_tasks}}
- [ ] {{name}}: {{description}}
{{/each}}
```

### 2. Approval Options
**Present clear choices to user:**

```markdown
**Please choose your next action:**

**A) ✅ APPROVE & COMMIT** - Everything looks good, commit and continue
   - Will commit changes with generated message
   - Will push to remote branch  
   - **Single Plan**: Will continue with next tasks
   - **Split Plans**: If sub-plan complete, will offer sub-plan transition

**B) 🔍 REVIEW NEEDED** - I need to examine the changes more closely
   - Will pause implementation
   - User can review code, run tests, check functionality
   - Will wait for explicit instruction to continue

**C) 🔧 MODIFICATIONS NEEDED** - Changes required before committing
   - Will pause implementation
   - User can specify what needs to be modified
   - Will implement requested changes before continuing

**D) 📝 COMMIT MESSAGE EDIT** - Approve changes but customize commit message
   - Will use user-provided commit message
   - Will commit and continue normally

**E) 🚀 TRANSITION SUB-PLAN** - (Split plans only) Complete current sub-plan and start next
   - Will commit current changes
   - Will update context files for next sub-plan
   - Will load next sub-plan and continue implementation

**Your choice (A/B/C/D/E):**
```

### 3. Response Handling

#### Option A - Approve & Commit
```bash
# Generate descriptive commit message
COMMIT_MSG="feat({{FEATURE_SLUG}}): {{milestone_description}}

{{#each completed_tasks}}
- {{description}}
{{/each}}

🤖 Generated with Claude Code LAD Framework

Co-Authored-By: Claude <noreply@anthropic.com>"

# Execute commit workflow
git add -A
git commit -m "$COMMIT_MSG"
git push -u origin HEAD

# Continue implementation
echo "✅ Committed and pushed. Continuing with next tasks..."
```

#### Option B - Review Needed
```markdown
**Implementation Paused for Review**

**Current State**: All changes are staged and ready for review

**To resume implementation**, tell me:
- "Continue implementation" - Resume with next tasks
- "Implement [specific change]" - Make modifications then continue  
- "Commit and continue" - Commit current changes then continue

**For detailed review**:
- `git diff --staged` - See staged changes
- `pytest -v` - Run full test suite
- `flake8 .` - Check lint compliance
```

#### Option C - Modifications Needed
```markdown
**Implementation Paused for Modifications**

**Please specify what changes you'd like me to make:**

**Common modification requests:**
- "Refactor [function/class] to improve [specific aspect]"
- "Add error handling for [specific case]"  
- "Update tests to cover [specific scenario]"
- "Change API design for [specific endpoint]"
- "Improve performance of [specific operation]"

**After modifications**, I'll run quality checks and return to this checkpoint.
```

#### Option D - Custom Commit Message
```markdown
**Please provide your custom commit message:**

**Format suggestion:**
```
feat({{FEATURE_SLUG}}): [your description]

[optional body with details]
```

**I'll use your message and commit immediately.**
```

#### Option E - Sub-Plan Transition (Split Plans Only)
```markdown
**SUB-PLAN TRANSITION INITIATED**

**Current Sub-Plan**: {{current_sub_plan_name}} ✅ COMPLETED
**Next Sub-Plan**: {{next_sub_plan_name}}

**Manual Transition Steps**:
1. **Review Deliverables**:
   - Use `grep -r "class\|def" .` to inventory what was actually built
   - Use `Read` tool to review key implementation files
   - Test major integration points: `python -c "from module import component"`

2. **Context Evolution**: Updating `context_{{next_number}}_{{next_name}}.md` with:
   - **Actual components created** (verified through code inspection)
   - **Working integration examples** (tested import statements and usage)
   - **Interface documentation** (based on actual implementation)
   - **Prerequisites satisfied** (confirmed through manual testing)

3. **Integration Validation**:
   - Manually test that key components work as expected
   - Verify that next sub-plan's expectations can be met
   - Document any deviations from original integration plan

4. **Loading Next Phase**:
   - Plan: `plan_{{next_number}}_{{next_name}}.md`
   - Context: `context_{{next_number}}_{{next_name}}.md` (updated with verified deliverables)
   - TodoWrite: Initialized with next phase tasks

**✅ Manual validation complete. Proceeding with next sub-plan implementation...**
```

## Checkpoint Recovery
**If interrupted or resumed later:**

1. **Detect checkpoint state** from TodoWrite and plan files
2. **Regenerate progress summary** based on current state
3. **Validate quality status** with fresh test runs
4. **Present resumption options** to user

## Integration with TodoWrite
**Maintain dual tracking:**

```python
# Update TodoWrite with checkpoint status
TodoWrite([
    # Mark completed tasks
    {"id": "1", "content": "Task A", "status": "completed", "priority": "high"},
    # Mark current checkpoint task
    {"id": "checkpoint", "content": "Milestone checkpoint - awaiting user approval", 
     "status": "in_progress", "priority": "high"},
    # Keep pending tasks
    {"id": "3", "content": "Task C", "status": "pending", "priority": "medium"}
])
```

## Success Metrics
**Each checkpoint should achieve:**
- ✅ Clear progress visualization for user
- ✅ Quality validation completed  
- ✅ User feedback incorporated
- ✅ Appropriate commit/push action taken
- ✅ Implementation momentum maintained

---
*This phase ensures user stays informed and engaged throughout the implementation process*