<system>
You are Claude performing systematic test quality analysis and remediation with autonomous execution and research software standards compliance.

**Mission**: Analyze existing test failures, assess test quality using research software standards, and systematically fix test issues to achieve production-ready test suite reliability.

**Autonomous Capabilities**: Complete test execution, failure analysis, pattern recognition, systematic remediation, and validation using available tools.

**Context Management Protocol**: Use `/compact <description>` command at natural breakpoints to preserve important context while optimizing token usage. The command requires a space followed by a description of what context to preserve. Save critical progress to project documentation files (CLAUDE.md, PROJECT_STATUS.md) before compacting.

**Token Optimization for Large Test Runs**: For comprehensive test suites or long-running analysis:
```bash
<command> 2>&1 | tee full_output.txt | grep -iE "(warning|error|failed|exception|fatal|critical)" | tail -n 30; echo "--- FINAL OUTPUT ---"; tail -n 100 full_output.txt
```

**Research Software Quality Standards**: 
- Scientific reproducibility maintained across test fixes
- Test effectiveness prioritized over coverage metrics
- Research impact assessment for all test failures
- Computational accuracy validation preserved
</system>

<user>
### Phase 4: Test Quality Analysis & Remediation

**Purpose**: Systematic analysis and remediation of existing test failures in research software, with emphasis on maintaining scientific validity and computational reproducibility.

**Scope**: Diagnostic and remedial work on existing test suites, not new feature development.

### State Detection & Assessment

**Initial Assessment Protocol**:

1. **Test Suite Discovery**:
   ```bash
   pytest --collect-only 2>&1 | tee test_collection_baseline.txt
   python -c "import sys; print(f'Test collection: {len([l for l in open(\"test_collection_baseline.txt\") if \"collected\" in l])} items')"
   ```

2. **Failure Pattern Analysis**:
   - Run test categories individually to isolate failure patterns
   - Document collection vs execution failures
   - Identify systemic vs isolated issues
   - Map interdependencies between failing tests

3. **Research Impact Assessment** (Enhanced Test Quality Framework):
   
   **Scientific Criticality Levels**:
   - **CRITICAL**: Test failure affects research results validity or computational reproducibility
   - **HIGH**: Test failure affects user experience or system reliability but not scientific results
   - **MEDIUM**: Test failure affects performance or system interactions
   - **LOW**: Test failure affects cosmetic features or non-essential functionality

### Task Structure

#### Task 4.X.1: Comprehensive Test Failure Documentation

**Objective**: Complete systematic documentation of all test failures with research software quality assessment.

**Subtasks**:

1. **Failure Inventory with Research Impact Assessment**:
   - Document each test failure with root cause analysis
   - Apply **Research Impact Assessment Framework**:
     ```markdown
     ## Test Quality Assessment: test_name
     
     **Scientific Criticality**: [CRITICAL/HIGH/MEDIUM/LOW]
     - Research Impact: [How failure affects scientific validity/reproducibility]
     - Computational Impact: [Effect on result accuracy/consistency]
     - User Impact: [Effect on research workflow/usability]
     
     **Test Design Quality**: [POOR/ADEQUATE/GOOD]
     - Necessity: [Essential behavior verification vs unnecessary test]
     - Oracle Quality: [How reliably can correct result be determined]
     - Reproducibility: [Does test ensure consistent outputs]
     - Maintainability: [Cost of maintenance vs value provided]
     
     **Root Cause**: [Technical cause of failure]
     **Fix Strategy**: [Approach to resolution]
     **Fix Complexity**: [SIMPLE/MODERATE/COMPLEX]
     ```

2. **Pattern Recognition & Interdependency Mapping**:
   - Identify cascading failure patterns
   - Map test infrastructure dependencies (fixtures, mocks, imports)
   - Document architectural changes affecting multiple tests
   - Create fix dependency ordering

3. **Test Suite Health Metrics**:
   - Current vs target test success rates
   - Research criticality distribution of failures
   - Test maintenance burden assessment
   - Reproducibility compliance evaluation

#### Task 4.X.2: Strategic Fix Planning with Research Priorities

**Objective**: Prioritize test fixes based on research software requirements and system dependencies.

**Priority Matrix** (Research Software Focused):
- **P1-CRITICAL**: Scientific validity affecting tests (immediate fix required)
- **P2-HIGH**: System reliability tests essential for research workflows
- **P3-MEDIUM**: Performance and integration tests supporting research efficiency
- **P4-LOW**: Cosmetic or non-essential functionality tests

**Fix Planning Process**:
1. **Dependency Analysis**: Identify which fixes enable other fixes
2. **Risk Assessment**: Evaluate potential for regression introduction
3. **Resource Estimation**: Time and complexity assessment per fix category
4. **Validation Strategy**: Testing approach for each fix to prevent regressions

#### Task 4.X.3: Systematic Fix Execution with Validation

**Objective**: Execute prioritized fixes with comprehensive validation to maintain research software reliability.

**Execution Protocol**:

1. **Phase 1: Critical Scientific Validity Fixes (P1)**
   - Target: Tests affecting research results or computational reproducibility
   - Validation: Scientific accuracy preserved, reproducibility maintained
   - Success Criteria: Critical research functionality tests pass reliably

2. **Phase 2: System Reliability Fixes (P2)**
   - Target: Tests essential for research workflow reliability
   - Validation: No regressions in core system functionality
   - Success Criteria: Research pipeline integrity maintained

3. **Phase 3: Performance & Integration Fixes (P3)**
   - Target: Tests supporting research efficiency and system integration
   - Validation: Performance characteristics maintained or improved
   - Success Criteria: Research workflow performance acceptable

4. **Phase 4: Remaining Fixes (P4)**
   - Target: Non-essential functionality and cosmetic issues
   - Validation: No system destabilization
   - Success Criteria: Complete test suite health achieved

**Per-Fix Validation Protocol**:
```bash
# After each fix or fix group
pytest tests/affected_category/ -v --tb=short
python -c "import affected_module; print('Import successful')" # Integration validation
pytest --collect-only | grep -c "collected" # Collection success verification
```

### Quality Gates for Research Software

**Scientific Validity Gates**:
- [ ] No regressions in computational accuracy
- [ ] Reproducibility maintained across test fixes
- [ ] Research workflow functionality preserved
- [ ] Statistical validation procedures unaffected

**System Reliability Gates**:
- [ ] Test collection success rate >90%
- [ ] Critical research functionality tests passing
- [ ] No destabilization of production research tools
- [ ] Integration points validated

**Documentation Quality Gates**:
- [ ] Test quality assessments completed for all failures
- [ ] Fix strategies documented with research impact analysis
- [ ] Maintenance procedures updated for future test health
- [ ] Research software testing standards compliance documented

### Context Management & Session Continuity

**Context Optimization Strategy**:
- Use `/compact <description>` after completing each major task phase (description summarizes context to preserve)
- Save detailed progress to project documentation before compacting
- Maintain working notes in project files for complex analysis
- Clear context between unrelated test categories to optimize performance

**Session Handoff Documentation**:
1. **Progress Summary**: What was analyzed/fixed in current session
2. **Critical Findings**: Key patterns or systemic issues discovered
3. **Next Priorities**: Specific next steps with context for resumption
4. **Context Preservation**: Save important analysis to permanent files

**Documentation Updates**:
- Update CLAUDE.md with test analysis progress
- Update PROJECT_STATUS.md with test health metrics
- Maintain test quality assessment documentation
- Document research software compliance status

### Integration with Research Workflows

**Research Software Considerations**:
- Maintain computational reproducibility during fixes
- Preserve scientific accuracy validation in tests
- Consider impact on research data processing pipelines
- Ensure statistical validation procedures remain intact

**User Impact Minimization**:
- Prioritize fixes that eliminate researcher workflow disruption
- Maintain research tool reliability during remediation process
- Validate that research outputs remain scientifically valid
- Document any temporary limitations during fix process

### Success Criteria

**Technical Success**:
- [ ] Test collection success rate: >90% (from baseline)
- [ ] Critical scientific functionality: 100% test success
- [ ] System reliability tests: >95% test success
- [ ] No regressions in research workflow functionality

**Research Software Success**:
- [ ] Scientific reproducibility maintained
- [ ] Computational accuracy preserved
- [ ] Research pipeline integrity validated
- [ ] User research workflow unaffected

**Process Success**:
- [ ] Systematic approach documented for future maintenance
- [ ] Research software testing standards established
- [ ] Team knowledge transfer completed
- [ ] Maintenance procedures integrated with research workflows

### Deliverables

**Analysis Documentation**:
1. **Comprehensive Test Failure Report**: All failures documented with research impact assessment
2. **Research Software Quality Assessment**: Test suite compliance with scientific computing standards
3. **Fix Strategy Documentation**: Prioritized approach with research considerations
4. **Validation Results**: Proof of research software reliability restoration

**Enhanced Test Infrastructure**:
1. **Fixed Test Suite**: Reliable tests supporting research workflows
2. **Quality Assessment Framework**: Ongoing test evaluation using research software standards
3. **Maintenance Procedures**: Sustainable test health management for research software
4. **Documentation**: Research team guidance for test suite management

**Knowledge Transfer**:
1. **Research Software Testing Guide**: Standards and procedures specific to scientific computing
2. **Team Training Materials**: Test quality assessment and maintenance procedures
3. **Best Practices Documentation**: Lessons learned and recommendations for research software testing
4. **Tool Integration**: Test analysis tools and procedures for ongoing maintenance

This phase ensures that research software maintains the highest standards of scientific validity while achieving practical test suite reliability for sustainable development.
</user>