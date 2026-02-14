<system>
You are Claude executing systematic test improvement using PDCA cycles with TodoWrite integration and comprehensive validation.

**Mission**: Implement prioritized test fixes through iterative Plan-Do-Check-Act cycles, ensuring no regressions while achieving 100% meaningful test success.

**Autonomous Capabilities**: PDCA cycle execution, TodoWrite progress tracking, systematic implementation, and validation protocols.

**Prerequisites**: Requires completion of 04a (Execution Infrastructure) and 04b (Analysis Framework) with priority matrix and implementation context available.

**Context Management**: Use `/compact <description>` after each PDCA cycle completion to preserve progress while optimizing for next iteration.

**CRITICAL**: Before implementing any test fixes, follow the **Regression Risk Management Protocol** from phase 04a to prevent destabilizing working systems.
</system>

<user>
### Phase 4c: Test Improvement Cycles

**Purpose**: Execute systematic test improvements through iterative PDCA cycles, integrating with TodoWrite for session continuity and ensuring no regressions.

**Scope**: Implementation phase - transforms analysis insights into working solutions.

### ⚠️ **Regression Risk Management Protocol**

**MANDATORY** before any code changes during test improvement cycles. Reference the full protocol in `04a_test_execution_infrastructure.md`.

#### Quick Risk Assessment for Test Fixes

**Before Each Fix Implementation**:
```bash
# Quick impact analysis for test improvements
target_area="test_or_function_to_fix"
echo "# Quick Impact Analysis: $target_area - $(date)" > cycle_impact_analysis.md

# Identify affected components
echo "## Components Affected:" >> cycle_impact_analysis.md
grep -r "$target_area" --include="*.py" . | head -10 >> cycle_impact_analysis.md

# Test impact scope
echo "## Test Scope Impact:" >> cycle_impact_analysis.md
grep -r "$target_area" tests/ --include="*.py" | cut -d':' -f1 | sort -u >> cycle_impact_analysis.md
```

**Risk-Based Implementation Strategy**:
- **Low Risk**: Test fixture improvements, test data corrections → Standard validation
- **Medium Risk**: Test logic changes, assertion updates → Focused category validation  
- **High Risk**: Core functionality fixes, algorithm changes → Comprehensive validation

#### PDCA Integration with Risk Management

**PLAN Phase**: Include risk assessment in solution planning
**DO Phase**: Implement with baseline commits and immediate validation
**CHECK Phase**: Comprehensive validation including regression testing
**ACT Phase**: Document lessons learned for risk mitigation

**Prerequisites**: Must have completed Phase 4b with:
- `test_analysis_summary.md` (comprehensive findings)
- `implementation_context.md` (priority queue and batching opportunities)
- Priority matrix with P1-P4 classifications

### PDCA Cycle Framework

#### PLAN Phase: Strategic Solution Planning

**Initialize TodoWrite with Prioritized Tasks**:

```markdown
# Initialize test improvement TodoWrite tasks
TodoWrite initialization based on analysis results:

## P1-CRITICAL Tasks (Scientific validity + High impact/Low effort):
1. {{task_1_description}} - Status: pending
2. {{task_2_description}} - Status: pending
3. {{task_3_description}} - Status: pending

## P2-HIGH Tasks (System reliability + Quick wins):
4. {{task_4_description}} - Status: pending
5. {{task_5_description}} - Status: pending

## P3-MEDIUM Tasks (Performance + Clear value):
6. {{task_6_description}} - Status: pending
7. {{task_7_description}} - Status: pending

## P4-LOW Tasks (Cosmetic + Resource permitting):
8. {{task_8_description}} - Status: pending
9. {{task_9_description}} - Status: pending
```

**Implementation Sequence Optimization**:

```markdown
## PLAN Phase Analysis

### Current PDCA Cycle: {{cycle_number}}
### Focus Area: {{P1_or_P2_or_batch_strategy}}

### Selected Tasks for This Cycle:
- {{task_name_1}}: {{brief_description}}
- {{task_name_2}}: {{brief_description}}
- {{task_name_3}}: {{brief_description}}

### Batching Strategy:
- **Compatible Fixes**: {{tasks_that_can_be_done_together}}
- **Dependency Order**: {{task_A_before_task_B_reasoning}}
- **Risk Mitigation**: {{validation_approach_for_risky_changes}}

### Success Criteria for This Cycle:
- [ ] Selected tasks completed without regressions
- [ ] Test success rate improvement: {{current}}% → {{target}}%
- [ ] No impact on critical systems (P1 tests remain passing)
- [ ] Validation shows no new failures introduced

### Resource Allocation:
- **Estimated Effort**: {{time_estimate_for_cycle}}
- **Complexity Assessment**: {{simple_moderate_complex}}
- **Validation Requirements**: {{testing_approach_needed}}
```

#### DO Phase: Systematic Implementation

**Task Execution with Progress Tracking**:

```bash
# Mark current task as in_progress in TodoWrite
# Implement first task in current cycle

# Example implementation pattern:
echo "Starting implementation of: {{current_task}}" 
echo "PDCA Cycle {{N}}, DO Phase - Task {{M}}" > current_implementation_log.md

# [Implement specific fix based on root cause analysis]
# Infrastructure fix example:
# - Update import statements
# - Fix dependency issues  
# - Resolve environment setup

# API compatibility fix example:
# - Update method signatures
# - Fix parameter mismatches
# - Resolve interface changes

# Test design fix example:  
# - Update test expectations
# - Fix brittle test logic
# - Improve test reliability

# Document implementation decision
echo "## Implementation Approach" >> current_implementation_log.md
echo "- Root cause: {{identified_cause}}" >> current_implementation_log.md
echo "- Solution: {{approach_taken}}" >> current_implementation_log.md
echo "- Files modified: {{list_of_changed_files}}" >> current_implementation_log.md
echo "- Risk level: {{low_medium_high}}" >> current_implementation_log.md
```

**Working Notes Protocol for Complex Analysis**:

```bash
# For complex implementation decisions, create analysis workspace
mkdir -p notes/implementation_decisions/
echo "# Implementation Decision Analysis - {{task_name}}" > notes/implementation_decisions/{{task}}_analysis.md

echo "## Decision Context" >> notes/implementation_decisions/{{task}}_analysis.md
echo "- Task: {{current_implementation_task}}" >> notes/implementation_decisions/{{task}}_analysis.md
echo "- Complexity: {{why_this_requires_analysis}}" >> notes/implementation_decisions/{{task}}_analysis.md
echo "- Constraints: {{technical_or_resource_constraints}}" >> notes/implementation_decisions/{{task}}_analysis.md

echo "## Analysis Workspace" >> notes/implementation_decisions/{{task}}_analysis.md
echo "- Approach A: {{details_implications_validation}}" >> notes/implementation_decisions/{{task}}_analysis.md
echo "- Approach B: {{details_implications_validation}}" >> notes/implementation_decisions/{{task}}_analysis.md

echo "## Impact Assessment" >> notes/implementation_decisions/{{task}}_analysis.md
echo "- System Architecture: {{effect_on_overall_system}}" >> notes/implementation_decisions/{{task}}_analysis.md
echo "- Future Development: {{long_term_implications}}" >> notes/implementation_decisions/{{task}}_analysis.md
echo "- Risk Analysis: {{potential_issues_and_mitigation}}" >> notes/implementation_decisions/{{task}}_analysis.md
```

#### CHECK Phase: Comprehensive Validation

**After Each Task Implementation**:

```bash
# Targeted validation for current task
echo "## CHECK Phase Validation - Task: {{current_task}}" >> current_implementation_log.md

# 1. Direct test validation
pytest tests/{{affected_category}}/ -v --tb=short 2>&1 | tail -n 20

# 2. Integration validation  
python -c "import {{affected_module}}; print('Import successful')"

# 3. Regression prevention for critical systems
pytest tests/security/ tests/model_registry/test_local*.py -q --tb=short 2>&1 | tail -n 10

# 4. Update health metrics
echo "### Validation Results:" >> current_implementation_log.md
echo "- Target tests now passing: {{Y_or_N}}" >> current_implementation_log.md  
echo "- No regressions in critical systems: {{Y_or_N}}" >> current_implementation_log.md
echo "- Integration points working: {{Y_or_N}}" >> current_implementation_log.md

# 5. Mark task as completed in TodoWrite if validation successful
# If validation fails, document issues and keep task as in_progress
```

**Comprehensive Health Metrics Update**:

```bash
# Generate updated health report after each fix
echo "# Updated Test Health Report - PDCA Cycle {{N}}" > cycle_{{N}}_health_report.md

# Re-run key categories to measure improvement
for category in security model_registry integration performance tools; do
    echo "## $category Category Status:" >> cycle_{{N}}_health_report.md
    if pytest tests/$category/ -q --tb=no 2>/dev/null; then
        pytest tests/$category/ -q --tb=no 2>&1 | grep -E "(passed|failed|skipped)" >> cycle_{{N}}_health_report.md
    else
        echo "Category execution issues detected" >> cycle_{{N}}_health_report.md
    fi
done

# Compare with baseline
echo "## Improvement Tracking:" >> cycle_{{N}}_health_report.md
echo "- Baseline success rate: {{baseline_percentage}}%" >> cycle_{{N}}_health_report.md
echo "- Current success rate: {{current_percentage}}%" >> cycle_{{N}}_health_report.md
echo "- Tests fixed this cycle: {{number_fixed}}" >> cycle_{{N}}_health_report.md
echo "- Remaining P1-P2 issues: {{remaining_high_priority}}" >> cycle_{{N}}_health_report.md
```

#### ACT Phase: Decision Framework and Next Iteration

**User Decision Point After Each PDCA Cycle**:

```markdown
**TEST QUALITY IMPROVEMENT CYCLE {{N}} COMPLETE**

**Progress Summary**:
- **PDCA Cycle**: {{N}} completed successfully
- **Tasks Completed**: {{list_of_completed_tasks}}
- **Success Rate Improvement**: {{baseline}}% → {{current}}%
- **Priority Fixes**: {{P1_completed}} P1, {{P2_completed}} P2 completed

**Current Status**:
- **Critical Systems**: {{security_status}}, {{model_registry_status}}, {{integration_status}}
- **Overall Health**: {{current_percentage}}% success rate
- **Industry Compliance**: {{research_standard_status}}, {{enterprise_standard_status}}

**Remaining Issues**:
- **{{P1_remaining}} P1-CRITICAL** remaining: {{list_P1_issues}}
- **{{P2_remaining}} P2-HIGH** remaining: {{list_P2_issues}}
- **{{P3_remaining}} P3-MEDIUM** remaining: {{list_P3_issues}}
- **{{P4_remaining}} P4-LOW** remaining: {{justified_skips_count}} justified skips

**Options**:

**A) ✅ CONTINUE CYCLES** - Implement next priority fixes
   - Will start PDCA Cycle {{N+1}}
   - Focus: {{next_cycle_focus_area}}
   - Estimated effort: {{next_cycle_time_estimate}}
   - Target improvement: {{target_success_rate}}%

**B) 🔧 ADJUST APPROACH** - Modify strategy based on findings  
   - Will pause for approach refinement
   - Address: {{any_systemic_issues_discovered}}
   - Update: {{priority_matrix_or_batching_strategy}}
   - Reassess: {{resource_allocation_or_complexity}}

**C) 📊 ADD COVERAGE ANALYSIS** - Integrate test coverage improvement
   - Will run comprehensive coverage analysis  
   - Identify: {{critical_code_gaps_requiring_tests}}
   - Balance: {{test_quality_vs_coverage_enhancement}}
   - Estimated scope: {{coverage_improvement_effort}}

**D) ✅ COMPLETE CURRENT LEVEL** - Achieve target success threshold
   - Current status meets/exceeds: {{which_standards_satisfied}}
   - Remaining issues: {{justified_as_acceptable_for_solo_programmer}}
   - Resource optimization: {{focus_on_feature_development_vs_test_perfection}}
   - Final success rate: {{final_percentage}}%

**My Assessment**: {{technical_recommendation_with_reasoning}}

**Resource Consideration**: {{solo_programmer_context_analysis}}

**Your choice (A/B/C/D):**
```

### Session Continuity and Context Management

#### Enhanced Session State Preservation

**Save Comprehensive PDCA State**:

```bash
# Save complete session state for resumption
echo "# Test Quality Session State - PDCA Cycle {{N}}" > notes/pdca_session_state.md

echo "## Current PDCA Progress:" >> notes/pdca_session_state.md
echo "- Cycle number: {{N}}" >> notes/pdca_session_state.md
echo "- Phase: {{PLAN_DO_CHECK_ACT}}" >> notes/pdca_session_state.md
echo "- Tasks in current cycle: {{list_current_tasks}}" >> notes/pdca_session_state.md
echo "- Completed this session: {{completed_tasks}}" >> notes/pdca_session_state.md

echo "## TodoWrite State:" >> notes/pdca_session_state.md
echo "- Total tasks: {{total_count}}" >> notes/pdca_session_state.md
echo "- Completed: {{completed_count}}" >> notes/pdca_session_state.md  
echo "- In progress: {{in_progress_count}}" >> notes/pdca_session_state.md
echo "- Pending: {{pending_count}}" >> notes/pdca_session_state.md

echo "## Key Findings This Session:" >> notes/pdca_session_state.md
echo "- Success rate improvement: {{improvement}}" >> notes/pdca_session_state.md
echo "- Patterns discovered: {{new_insights}}" >> notes/pdca_session_state.md
echo "- Challenges encountered: {{issues_and_resolutions}}" >> notes/pdca_session_state.md

echo "## Context for Next Session:" >> notes/pdca_session_state.md
echo "- Next priority: {{next_action}}" >> notes/pdca_session_state.md
echo "- Decision pending: {{awaiting_user_input}}" >> notes/pdca_session_state.md
echo "- Context to preserve: {{critical_information}}" >> notes/pdca_session_state.md
```

#### Context Optimization Strategy

**Before Using `/compact`**:

```bash
# Archive working notes and preserve essential context
echo "# Essential Context for Continuation" > pdca_essential_context.md

echo "## Current Achievement Level:" >> pdca_essential_context.md
echo "- Success rate: {{current_percentage}}%" >> pdca_essential_context.md
echo "- Industry standard compliance: {{status}}" >> pdca_essential_context.md
echo "- Critical systems status: {{security_registry_integration_status}}" >> pdca_essential_context.md

echo "## Active PDCA Context:" >> pdca_essential_context.md
echo "- Cycle: {{N}}, Phase: {{current_phase}}" >> pdca_essential_context.md
echo "- Current focus: {{what_we_are_working_on}}" >> pdca_essential_context.md
echo "- Next decision point: {{user_choice_or_next_implementation}}" >> pdca_essential_context.md

echo "## Key Implementation Insights:" >> pdca_essential_context.md
echo "- Successful approaches: {{what_worked_well}}" >> pdca_essential_context.md
echo "- Patterns to remember: {{important_discoveries}}" >> pdca_essential_context.md
echo "- Avoided approaches: {{what_to_avoid_and_why}}" >> pdca_essential_context.md

# Move detailed working notes to permanent documentation
cat notes/implementation_decisions/*.md >> CLAUDE.md 2>/dev/null || true
cat cycle_*_health_report.md >> PROJECT_STATUS.md 2>/dev/null || true
```

### Integration with Coverage Analysis

#### Coverage-Driven Test Enhancement

**When Option C (Coverage Analysis) is Selected**:

```bash
# Integrate coverage analysis with current test quality status
echo "# Coverage Analysis Integration - PDCA Cycle {{N}}" > coverage_integration_analysis.md

# Run coverage for key modules
pytest --cov=emuses --cov-report=term-missing tests/ 2>&1 | tee comprehensive_coverage.txt

# Identify critical functions with <80% coverage
python -c "
import re
with open('comprehensive_coverage.txt') as f:
    content = f.read()
    lines = content.split('\n')
    low_coverage = [l for l in lines if re.search(r'\s+[0-7][0-9]%\s+', l)]
    print('Critical functions below 80% coverage:')
    for line in low_coverage[:10]:  # Top 10 priorities
        print(line.strip())
" > critical_coverage_gaps.txt

echo "## Coverage-Driven Test Priorities:" >> coverage_integration_analysis.md
cat critical_coverage_gaps.txt >> coverage_integration_analysis.md

echo "## Integration with Current Test Quality:" >> coverage_integration_analysis.md
echo "- Current test success rate: {{percentage}}%" >> coverage_integration_analysis.md
echo "- Coverage enhancement opportunities: {{count}} critical gaps" >> coverage_integration_analysis.md  
echo "- Resource allocation: {{balance_quality_fixes_vs_coverage}}" >> coverage_integration_analysis.md
```

### Quality Gates and Success Criteria

**PDCA Cycle Success Criteria**:
- [ ] Selected tasks completed without introducing regressions
- [ ] Test success rate improved or maintained
- [ ] Critical systems remain at 100% success
- [ ] TodoWrite accurately reflects current state
- [ ] Health metrics updated and documented
- [ ] Decision framework presented to user

**Overall Improvement Success Criteria**:
- [ ] **Research Software Compliance**: >90% success for critical systems
- [ ] **Enterprise Standard Compliance**: >85% overall success rate
- [ ] **Solo Programmer Optimization**: High-impact/low-effort fixes prioritized
- [ ] **Systematic Process**: PDCA cycles demonstrate continuous improvement
- [ ] **Session Continuity**: Framework supports interruption and resumption

### Deliverables

**PDCA Implementation Tracking**:
1. **TodoWrite Progress**: Real-time task completion tracking
2. **Cycle Health Reports**: Success rate improvement per cycle
3. **Implementation Logs**: Detailed decision and change documentation
4. **Validation Results**: Regression prevention and integration testing

**Strategic Decision Support**:
1. **User Decision Framework**: Clear options after each cycle
2. **Resource Optimization**: Solo programmer context considerations
3. **Coverage Integration**: Optional test coverage enhancement
4. **Session Continuity**: Seamless interruption and resumption support

### Next Phase Integration

**Preparation for 04d (Session Management)**:
- PDCA cycles established and functional ✅
- TodoWrite integration operational ✅
- Decision frameworks tested ✅
- Context optimization proven ✅

**Usage**: Execute PDCA cycles until target success criteria achieved, then proceed to `04d_test_session_management.md` for advanced session continuity and user decision optimization.

This phase ensures systematic, measurable improvement toward 100% meaningful test success while maintaining productivity and preventing regressions.
</user>