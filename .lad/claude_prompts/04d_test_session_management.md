<system>
You are Claude managing advanced session continuity and user decision optimization for systematic test improvement with seamless interruption/resumption capabilities.

**Mission**: Provide seamless session continuity, optimize user decision workflows, and ensure productive test improvement across multiple Claude sessions.

**Autonomous Capabilities**: Session state management, context optimization, user decision facilitation, and productivity tracking.

**Prerequisites**: Requires completion of 04a-04c with PDCA cycles operational and improvement tracking established.

**Context Management**: Advanced session state preservation with automatic resumption capabilities and token-efficient context management.
</system>

<user>
### Phase 4d: Test Session Management

**Purpose**: Provide advanced session continuity and user decision optimization for uninterrupted test improvement workflows across multiple sessions.

**Scope**: Session management phase - ensures productivity and continuity regardless of interruptions.

**Prerequisites**: Must have completed Phases 4a-4c with:
- PDCA cycles operational and tested
- TodoWrite integration functional
- Decision frameworks validated
- Implementation logs and health reports generated

### Advanced Session State Preservation

#### Comprehensive State Capture

**Before Any Potential Interruption**:

```bash
# Capture complete session state for resumption
echo "# Test Quality Session State - $(date)" > notes/comprehensive_session_state.md

echo "## Session Overview" >> notes/comprehensive_session_state.md
echo "- Start time: {{session_start_time}}" >> notes/comprehensive_session_state.md
echo "- Duration: {{elapsed_time}}" >> notes/comprehensive_session_state.md
echo "- PDCA cycles completed: {{cycles_completed}}" >> notes/comprehensive_session_state.md
echo "- Current phase: {{PLAN_DO_CHECK_ACT}}" >> notes/comprehensive_session_state.md

echo "## Current Work Context" >> notes/comprehensive_session_state.md
echo "- Active task: {{current_task_description}}" >> notes/comprehensive_session_state.md
echo "- Focus area: {{P1_P2_batch_category}}" >> notes/comprehensive_session_state.md
echo "- Implementation status: {{what_is_in_progress}}" >> notes/comprehensive_session_state.md
echo "- Next planned action: {{next_immediate_step}}" >> notes/comprehensive_session_state.md

echo "## Progress Metrics" >> notes/comprehensive_session_state.md
echo "- Baseline success rate: {{original_percentage}}%" >> notes/comprehensive_session_state.md
echo "- Current success rate: {{current_percentage}}%" >> notes/comprehensive_session_state.md
echo "- Improvement this session: {{delta}}%" >> notes/comprehensive_session_state.md
echo "- Tests fixed this session: {{count}}" >> notes/comprehensive_session_state.md

echo "## TodoWrite State Snapshot" >> notes/comprehensive_session_state.md
echo "- Total tasks: {{total}}" >> notes/comprehensive_session_state.md
echo "- Completed: {{completed}} ({{percentage}}%)" >> notes/comprehensive_session_state.md
echo "- In progress: {{in_progress}}" >> notes/comprehensive_session_state.md
echo "- Pending: {{pending}}" >> notes/comprehensive_session_state.md

echo "## Critical Findings This Session" >> notes/comprehensive_session_state.md
echo "- Key patterns discovered: {{insights}}" >> notes/comprehensive_session_state.md
echo "- Successful approaches: {{what_worked}}" >> notes/comprehensive_session_state.md
echo "- Challenges encountered: {{obstacles_and_solutions}}" >> notes/comprehensive_session_state.md
echo "- Solution interactions validated: {{batching_or_dependency_learnings}}" >> notes/comprehensive_session_state.md

echo "## Decision Points and User Preferences" >> notes/comprehensive_session_state.md
echo "- User choice pattern: {{A_B_C_D_preferences}}" >> notes/comprehensive_session_state.md
echo "- Resource allocation preference: {{quality_vs_coverage_vs_features}}" >> notes/comprehensive_session_state.md
echo "- Risk tolerance: {{conservative_moderate_aggressive}}" >> notes/comprehensive_session_state.md
echo "- Completion criteria preference: {{perfectionist_pragmatic_minimal}}" >> notes/comprehensive_session_state.md
```

#### Context Files Organization

**Structured File Management**:

```bash
# Organize session files for optimal resumption
mkdir -p notes/session_archive/session_$(date +%Y%m%d_%H%M)

# Archive completed cycle details
mv cycle_*_health_report.md notes/session_archive/session_$(date +%Y%m%d_%H%M)/ 2>/dev/null || true
mv current_implementation_log.md notes/session_archive/session_$(date +%Y%m%d_%H%M)/ 2>/dev/null || true

# Preserve essential active context
cp test_analysis_summary.md notes/essential_context.md 2>/dev/null || true
cp implementation_context.md notes/active_priorities.md 2>/dev/null || true
cp comprehensive_session_state.md notes/resumption_context.md 2>/dev/null || true

# Create next session preparation file
echo "# Next Session Preparation - $(date)" > notes/next_session_prep.md
echo "## Immediate Actions Required:" >> notes/next_session_prep.md
echo "1. {{next_immediate_step}}" >> notes/next_session_prep.md
echo "2. {{validation_or_continuation_needed}}" >> notes/next_session_prep.md
echo "3. {{user_decision_awaiting}}" >> notes/next_session_prep.md

echo "## Context to Load:" >> notes/next_session_prep.md
echo "- Essential context: notes/essential_context.md" >> notes/next_session_prep.md
echo "- Active priorities: notes/active_priorities.md" >> notes/next_session_prep.md
echo "- Session state: notes/resumption_context.md" >> notes/next_session_prep.md
```

### Automatic Session Resumption

#### Smart Resumption Detection

**When Starting New Session**:

```bash
# Detect session state and determine resumption strategy
echo "# Session Resumption Analysis - $(date)" > session_resumption_analysis.md

echo "## State Detection Results:" >> session_resumption_analysis.md

# Check for existing session state
if [ -f "notes/resumption_context.md" ]; then
    echo "- Previous session state: FOUND" >> session_resumption_analysis.md
    echo "- Last session: $(grep "Start time:" notes/resumption_context.md | head -1)" >> session_resumption_analysis.md
    echo "- Last phase: $(grep "Current phase:" notes/resumption_context.md | head -1)" >> session_resumption_analysis.md
else
    echo "- Previous session state: NOT FOUND" >> session_resumption_analysis.md
    echo "- Resumption strategy: Fresh analysis required" >> session_resumption_analysis.md
fi

# Check TodoWrite state
if [ -f "notes/active_priorities.md" ]; then
    echo "- Active priorities: AVAILABLE" >> session_resumption_analysis.md
    pending_count=$(grep -c "Status: pending" notes/active_priorities.md 2>/dev/null || echo 0)
    in_progress_count=$(grep -c "Status: in_progress" notes/active_priorities.md 2>/dev/null || echo 0)
    echo "- Pending tasks: $pending_count" >> session_resumption_analysis.md
    echo "- In progress tasks: $in_progress_count" >> session_resumption_analysis.md
else
    echo "- Active priorities: NOT AVAILABLE" >> session_resumption_analysis.md
fi

# Check for recent health reports
if ls cycle_*_health_report.md 1> /dev/null 2>&1; then
    latest_cycle=$(ls cycle_*_health_report.md | sort -V | tail -1)
    echo "- Latest health report: $latest_cycle" >> session_resumption_analysis.md
    echo "- Progress tracking: AVAILABLE" >> session_resumption_analysis.md
else
    echo "- Latest health report: NOT FOUND" >> session_resumption_analysis.md
    echo "- Progress tracking: NEEDS ESTABLISHMENT" >> session_resumption_analysis.md
fi

echo "## Recommended Resumption Strategy:" >> session_resumption_analysis.md
```

**Intelligent Resumption Strategy**:

```markdown
## Session Resumption Strategy Decision

### Strategy A: CONTINUE_PDCA_CYCLES
**Conditions**: Previous session state found + Active priorities available + In-progress tasks exist
**Action**: Resume from current PDCA cycle phase
**Context Load**: Essential context + Active priorities + Session state
**Next Step**: Validate current task status and continue implementation

### Strategy B: VALIDATE_AND_RESUME  
**Conditions**: Previous session state found + Health reports available + No in-progress tasks
**Action**: Validate previous work and start next cycle
**Context Load**: Essential context + Latest health report + Standards validation
**Next Step**: Run health check and determine next priority focus

### Strategy C: FRESH_ANALYSIS_REQUIRED
**Conditions**: No previous session state OR Context files missing OR Significant time gap
**Action**: Start fresh analysis with baseline establishment
**Context Load**: Historical findings if available
**Next Step**: Execute Phase 04a (Test Execution Infrastructure)

### Strategy D: DECISION_POINT_RESUME
**Conditions**: Session ended at user decision point + Decision prompt available
**Action**: Present previous decision prompt for user choice
**Context Load**: Full session context + Decision framework
**Next Step**: Present options A/B/C/D to user with updated metrics
```

### Enhanced User Decision Optimization

#### Adaptive Decision Framework

**Context-Aware Decision Prompts**:

```markdown
**ADAPTIVE TEST QUALITY DECISION FRAMEWORK - Session {{N}}**

**Session Context Analysis**:
- **Session duration**: {{elapsed_time}} ({{productive_focused_marathon}})
- **Progress momentum**: {{steady_accelerating_plateauing}}
- **User engagement pattern**: {{detailed_high_level_delegated}}
- **Resource availability**: {{full_focused_limited_interrupted}}

**Progress Summary** (Tailored to {{user_engagement_pattern}}):
- **PDCA Cycle**: {{N}} {{completed_in_progress_paused}}
- **Success Rate**: {{baseline}}% → {{current}}% ({{improvement_trend}})
- **Key Achievement**: {{most_significant_accomplishment_this_session}}
- **Effort Investment**: {{time_spent}} on {{main_focus_area}}

**Strategic Position**:
- **Critical Systems**: {{security_registry_integration_status}}
- **Research Software Compliance**: {{current_vs_90_percent_target}}
- **Solo Programmer Optimization**: {{efficiency_assessment}}
- **Remaining High-Value Opportunities**: {{P1_P2_count}} fixes

**Intelligent Options** (Adapted for {{current_context}}):

**A) ✅ CONTINUE CYCLES** - {{context_specific_continuation_reason}}
   - Next focus: {{optimal_next_target}}
   - Estimated session time: {{realistic_time_estimate}}
   - Success probability: {{high_medium_low}} based on {{recent_patterns}}
   - Value proposition: {{specific_improvement_expected}}

**B) 🔧 ADJUST APPROACH** - {{context_specific_adjustment_reason}}
   - Recommended modification: {{strategy_refinement_needed}}
   - Time to implement: {{adjustment_time_estimate}}
   - Expected benefit: {{process_improvement_outcome}}
   - Best timing: {{now_next_session_after_milestone}}

**C) 📊 ADD COVERAGE ANALYSIS** - {{coverage_context_assessment}}
   - Coverage opportunity: {{critical_gaps_identified}}
   - Integration complexity: {{simple_moderate_complex}}
   - Resource requirement: {{coverage_effort_estimate}}
   - Strategic value: {{test_quality_vs_coverage_balance}}

**D) ✅ COMPLETE CURRENT LEVEL** - {{completion_context_justification}}
   - Current achievement: {{meets_exceeds_which_standards}}
   - Remaining issues: {{justified_acceptable_deferred}}
   - Resource optimization: {{development_focus_recommendation}}
   - Next milestone: {{feature_development_next_phase}}

**Claude's Assessment**: {{context_aware_technical_recommendation}}

**Productivity Optimization**: {{session_energy_resource_consideration}}

**User Decision Tracking** (For pattern learning):
- **Previous choices**: {{A_B_C_D_pattern}}
- **Preferred work style**: {{marathon_focused_iterative}}
- **Quality threshold**: {{perfectionist_pragmatic_minimal}}

**Your choice (A/B/C/D):**
```

#### Session Energy and Productivity Tracking

**Productivity Metrics Integration**:

```bash
# Track session productivity patterns for optimization
echo "# Session Productivity Analysis" > session_productivity.md

echo "## Productivity Metrics:" >> session_productivity.md
echo "- Tasks completed per hour: {{completion_rate}}" >> session_productivity.md
echo "- Success rate improvement per hour: {{improvement_rate}}" >> session_productivity.md
echo "- Context switching frequency: {{focus_continuity_assessment}}" >> session_productivity.md
echo "- Problem resolution efficiency: {{quick_moderate_complex_fix_ratios}}" >> session_productivity.md

echo "## Energy Pattern Recognition:" >> session_productivity.md
echo "- Peak productivity phase: {{when_most_effective}}" >> session_productivity.md
echo "- Optimal session length: {{based_on_performance_data}}" >> session_productivity.md
echo "- Break timing optimization: {{sustained_vs_interval_patterns}}" >> session_productivity.md

echo "## Recommendations for Next Session:" >> session_productivity.md
echo "- Optimal start approach: {{fresh_analysis_continue_validate}}" >> session_productivity.md
echo "- Suggested session structure: {{focus_areas_and_timing}}" >> session_productivity.md
echo "- Energy management: {{when_to_tackle_complex_vs_simple_tasks}}" >> session_productivity.md
```

### Context Optimization for Long-Term Efficiency

#### Advanced Context Management

**Before Context Limits**:

```bash
# Advanced context optimization strategy
echo "# Context Optimization - $(date)" > context_optimization_log.md

echo "## Pre-Optimization Assessment:" >> context_optimization_log.md
echo "- Active analysis files: $(ls notes/*.md analysis_*.md 2>/dev/null | wc -l)" >> context_optimization_log.md
echo "- Implementation logs: $(ls *implementation_log.md cycle_*.md 2>/dev/null | wc -l)" >> context_optimization_log.md
echo "- Health reports: $(ls *health_report.md *metrics.md 2>/dev/null | wc -l)" >> context_optimization_log.md

# Archive resolved issues
mkdir -p archive/resolved_$(date +%Y%m%d)
mv notes/implementation_decisions/*_resolved.md archive/resolved_$(date +%Y%m%d)/ 2>/dev/null || true

# Consolidate essential findings
echo "# Essential Context Preservation" > essential_findings.md
echo "## Critical Success Patterns:" >> essential_findings.md
echo "{{patterns_that_consistently_work}}" >> essential_findings.md

echo "## Avoided Approaches:" >> essential_findings.md
echo "{{approaches_that_failed_and_why}}" >> essential_findings.md

echo "## Active Priority Context:" >> essential_findings.md
echo "{{current_focus_and_immediate_next_steps}}" >> essential_findings.md

# Update permanent documentation
cat essential_findings.md >> CLAUDE.md
```

**Context Restoration Strategy**:

```bash
# When context is needed again, efficient restoration
echo "# Context Restoration Guide" > context_restoration.md

echo "## Essential Files for Quick Context:" >> context_restoration.md
echo "- CLAUDE.md: Contains consolidated learnings and patterns" >> context_restoration.md
echo "- PROJECT_STATUS.md: Current project health and priorities" >> context_restoration.md
echo "- essential_findings.md: Session-specific critical insights" >> context_restoration.md

echo "## Detailed Context if Needed:" >> context_restoration.md
echo "- archive/resolved_*/: Historical implementation decisions" >> context_restoration.md
echo "- notes/session_archive/: Complete session histories" >> context_restoration.md
echo "- test_analysis_summary.md: Comprehensive failure analysis" >> context_restoration.md
```

### Quality Gates and Success Criteria

**Session Management Success Criteria**:
- [ ] Session state preserved before any interruption
- [ ] Resumption strategy determined automatically
- [ ] User decision framework adapted to context
- [ ] Productivity patterns tracked and optimized
- [ ] Context efficiently managed without information loss

**Long-term Efficiency Criteria**:
- [ ] Session-to-session continuity seamless
- [ ] Context optimization prevents token overflow
- [ ] User decision patterns learned and applied
- [ ] Productivity metrics guide session optimization
- [ ] Knowledge preservation enables compound improvement

### Integration with Overall Framework

**Preparation for Production Use**:
- Session management operational ✅
- Context optimization proven ✅
- User decision adaptation functional ✅
- Productivity tracking established ✅

**Usage**: This phase completes the comprehensive test quality framework, enabling seamless long-term test improvement across multiple sessions while optimizing user productivity and decision-making efficiency.

### Deliverables

**Session Continuity Infrastructure**:
1. **Comprehensive State Preservation**: Complete session context capture
2. **Intelligent Resumption**: Automatic detection and strategy selection
3. **Adaptive Decision Framework**: Context-aware user decision optimization
4. **Productivity Tracking**: Session efficiency metrics and optimization

**Long-term Efficiency Systems**:
1. **Context Management**: Token-efficient preservation and restoration
2. **Pattern Learning**: User preference tracking and application
3. **Knowledge Consolidation**: Essential findings preservation
4. **Compound Improvement**: Session-to-session knowledge building

This phase ensures that test quality improvement becomes a sustainable, efficient process that builds momentum across multiple sessions while respecting user preferences and productivity patterns.
</user>