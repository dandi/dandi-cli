<system>
You are Claude performing systematic test quality analysis and remediation with autonomous execution, enterprise-grade methodologies, and research software standards compliance.

**Mission**: Systematically achieve 100% meaningful test success through iterative improvement cycles, holistic analysis, and industry-standard validation processes.

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

**Enterprise Quality Standards Integration**:
- Systematic PDCA (Plan-Do-Check-Act) improvement cycles
- Holistic pattern recognition across all test failures
- Industry standard validation for test justification
- Resource optimization for solo programmer context
</system>

<user>
### Phase 4: Systematic Test Quality Analysis & Remediation

**Purpose**: Achieve 100% meaningful test success through systematic analysis, enterprise-grade improvement cycles, and industry-standard validation, while maintaining research software quality standards.

**Scope**: Complete test suite improvement using proven methodologies adapted for solo programmer context.

### Execution Infrastructure

#### Systematic Test Execution Protocol (Timeout Prevention)

**Intelligent Chunking Strategy**:
```bash
# Category-based execution with proven chunk sizing
pytest tests/security/ -v --tb=short 2>&1 | tee security_results.txt | grep -E "(PASSED|FAILED|SKIPPED|ERROR|warnings|collected)" | tail -n 15

# Model registry chunking (large category)
pytest tests/model_registry/test_local*.py tests/model_registry/test_api*.py tests/model_registry/test_database*.py -v --tb=short 2>&1 | tee registry_chunk1.txt | tail -n 10

# Performance and tools (timeout-prone categories)
pytest tests/performance/ -v --tb=short 2>&1 | tee performance_results.txt | grep -E "(PASSED|FAILED|SKIPPED|ERROR)" | tail -n 10
pytest tests/tools/ -v --tb=short 2>&1 | tee tools_results.txt | grep -E "(PASSED|FAILED|SKIPPED|ERROR)" | tail -n 10

# Integration and multi-user (complex categories)
pytest tests/integration/test_unified*.py tests/integration/test_cross*.py -v --tb=short 2>&1 | tee integration_chunk1.txt | tail -n 10
pytest tests/multi-user-service/test_auth*.py tests/multi-user-service/test_workspace*.py -v --tb=short 2>&1 | tee multiuser_chunk1.txt | tail -n 10
```

**Comprehensive Baseline Establishment**:
```bash
# Complete test discovery and categorization
pytest --collect-only 2>&1 | tee test_collection_baseline.txt
python -c "
import re
with open('test_collection_baseline.txt') as f:
    content = f.read()
    collected = re.findall(r'collected (\d+) item', content)
    print(f'Total tests collected: {collected[-1] if collected else 0}')
"
```

### Enhanced Analysis Framework

#### Phase 1: Holistic Pattern Recognition

**Before individual analysis**, systematically aggregate ALL test failures for comprehensive pattern recognition:

```bash
# Aggregate all test results into comprehensive analysis
cat *_results.txt *_chunk*.txt > comprehensive_test_output.txt

# Extract failure patterns
grep -E "(FAILED|ERROR)" comprehensive_test_output.txt > all_failures.txt

# Pattern analysis preparation
python -c "
import re
with open('all_failures.txt') as f:
    failures = f.readlines()
    
# Group by failure types
import_failures = [f for f in failures if 'import' in f.lower() or 'modulenotfound' in f.lower()]
api_failures = [f for f in failures if 'attribute' in f.lower() or 'missing' in f.lower()]
test_design_failures = [f for f in failures if 'assert' in f.lower() or 'expect' in f.lower()]

print(f'Import/Dependency failures: {len(import_failures)}')
print(f'API compatibility failures: {len(api_failures)}')
print(f'Test design failures: {len(test_design_failures)}')
"
```

**Root Cause Taxonomy Classification**:
1. **Infrastructure Issues**: Imports, dependencies, environment setup
2. **API Compatibility**: Method signatures, interface changes, parameter mismatches
3. **Test Design Flaws**: Brittle tests, wrong expectations, outdated assumptions
4. **Coverage Gaps**: Untested integration points, missing validation paths
5. **Configuration Issues**: Settings, paths, service dependencies

**Cross-Cutting Concerns Identification**:
- Map test failures that share common root causes
- Identify cascading failure patterns (one fix enables multiple test fixes)
- Document solution interaction opportunities (single fix resolves multiple issues)

#### Phase 2: Industry Standards Validation

**Multi-Tier Test Justification Matrix**:
For each SKIPPED test, validate against multiple standards:

```markdown
## Test Justification Analysis: {{test_name}}

**Research Software Standard (30-60% pass rate baseline)**:
- Justified: [Y/N] + Reasoning
- Research impact if fixed: [Scientific validity / Workflow / Performance / Cosmetic]

**Enterprise Standard (85-95% pass rate expectation)**:
- Justified: [Y/N] + Reasoning  
- Business impact if fixed: [Critical / High / Medium / Low]

**IEEE Testing Standard (Industry best practices)**:
- Justified: [Y/N] + Reasoning
- Technical debt assessment: [Acceptable / Should fix / Must fix]

**Solo Programmer Context (Resource constraints)**:
- Effort required: [Simple / Moderate / Complex]
- Value proposition: [High impact/Low effort / Low impact/High effort / etc.]
- Recommendation: [Fix / Defer / Remove]
```

### PDCA Improvement Cycles

#### Plan Phase: Strategic Solution Planning

**Comprehensive Issue Documentation**:
```bash
# Create structured analysis workspace
mkdir -p notes/test_analysis/
echo "# Test Quality Improvement Plan - $(date)" > notes/test_analysis/improvement_plan.md

# Document all findings systematically
```

**Priority Matrix (Enhanced for Solo Programmer)**:
- **P1-CRITICAL**: Scientific validity + High impact/Low effort fixes
- **P2-HIGH**: System reliability + Quick wins enabling other fixes  
- **P3-MEDIUM**: Performance + Moderate effort with clear value
- **P4-LOW**: Cosmetic + High effort/Low value (defer or remove)

**Solution Interaction Analysis**:
```markdown
## Fix Interaction Matrix

### Compatible Fixes (Can be batched):
- [List fixes that don't conflict and can be implemented together]

### Dependency Fixes (Sequential order required):
- [List fixes where Fix A must complete before Fix B can work]

### Risk Assessment:
- [Identify fixes that might cause regressions]
- [Document validation approach for each high-risk fix]

### Resource Optimization:
- [Group fixes by file/module to minimize context switching]
- [Identify high-impact/low-effort quick wins for momentum]
```

#### Do Phase: Systematic Implementation

**TodoWrite Integration for Progress Tracking**:
```markdown
# Initialize test quality improvement TodoWrite
TodoWrite tasks:
1. Infrastructure fixes (P1-CRITICAL): Import/dependency issues
2. API compatibility fixes (P1-P2): Method signature updates  
3. Test design improvements (P2-P3): Brittle test redesign
4. Coverage gap filling (P3): Integration point testing
5. Configuration standardization (P4): Settings/path cleanup
```

**Implementation Sequence (Resource-Optimized)**:
1. **Quick Wins First**: High-impact/low-effort fixes for momentum
2. **Dependency Resolution**: Fixes that enable other fixes
3. **Batch Compatible Fixes**: Group related changes to minimize disruption
4. **Risk Management**: High-risk fixes with comprehensive validation

**Working Notes Protocol** (Enhanced for Complex Analysis):
```bash
# Create analysis workspace for complex decisions
mkdir -p notes/test_decisions/
echo "# Test Fix Decision Analysis - {{fix_category}}" > notes/test_decisions/{{category}}_analysis.md
```

#### Check Phase: Comprehensive Validation

**After Each Fix Implementation**:
```bash
# Targeted validation
pytest tests/{{affected_category}}/ -v --tb=short 2>&1 | tail -n 20

# Integration validation  
python -c "import {{affected_module}}; print('Import successful')"

# Regression prevention
pytest tests/{{critical_modules}}/ -q --tb=short 2>&1 | tail -n 10
```

**Health Metrics Tracking**:
```bash
# Generate comparative health report
echo "# Test Health Report - $(date)" > test_health_report.md
echo "## Baseline vs Current Status" >> test_health_report.md

# Test collection success
pytest --collect-only 2>&1 | grep "collected\|error" >> test_health_report.md

# Category-wise success rates
for category in security model_registry integration performance tools; do
    echo "### $category category:" >> test_health_report.md
    pytest tests/$category/ -q --tb=no 2>&1 | grep "passed\|failed\|skipped" >> test_health_report.md
done
```

#### Act Phase: Decision Points & Iteration

**User Decision Point** (After Each PDCA Cycle):
```markdown
**TEST QUALITY IMPROVEMENT CYCLE COMPLETE**

**Progress Summary**:
- Fixed: {{number}} test failures 
- Success rate improvement: {{baseline}}% → {{current}}%
- Priority fixes completed: {{P1_count}} P1, {{P2_count}} P2, {{P3_count}} P3

**Current Status**:
- Critical systems (Security/Model Registry): {{status}}
- Integration tests: {{status}}
- Total test health: {{overall_percentage}}%

**Remaining Issues**:
- {{count}} P1-CRITICAL remaining
- {{count}} P2-HIGH remaining  
- {{count}} P3-MEDIUM remaining
- {{count}} justified skips (validated against industry standards)

**Options**:
**A) ✅ CONTINUE CYCLES** - Implement next priority fixes
   - Will continue with next PDCA cycle
   - Focus on remaining P1-P2 issues
   - Estimated effort: {{time_estimate}}

**B) 🎯 ADJUST APPROACH** - Modify strategy based on findings
   - Will pause for approach refinement
   - Address any discovered systemic issues
   - Update priority matrix based on new insights

**C) 📊 ADD COVERAGE ANALYSIS** - Integrate test coverage improvement
   - Will run comprehensive coverage analysis
   - Identify critical code gaps requiring new tests
   - Balance test quality vs coverage enhancement

**D) ✅ COMPLETE CURRENT LEVEL** - Achieve target success threshold
   - Will focus on reaching defined success criteria
   - May defer lower-priority issues
   - Prepare comprehensive final report

**Your choice (A/B/C/D):**
```

**Success Criteria Thresholds** (Configurable based on context):
- **Research Software**: >90% success for critical systems, >70% overall
- **Enterprise Standard**: >95% success for critical systems, >85% overall  
- **Solo Programmer**: >100% critical systems, >80% overall (realistic for resource constraints)

### Coverage Integration Framework

**Integrated Test Quality + Coverage Analysis**:
```bash
# Coverage-driven test improvement
pytest --cov={{module}} --cov-report=term-missing tests/{{module}}/ 2>&1 | tee coverage_{{module}}.txt

# Identify critical functions with <80% coverage
python -c "
import re
with open('coverage_{{module}}.txt') as f:
    content = f.read()
    # Parse coverage report for functions below threshold
    lines = content.split('\n')
    low_coverage = [l for l in lines if re.search(r'\s+[0-7][0-9]%\s+', l)]
    print('Functions below 80% coverage:')
    for line in low_coverage[:10]:  # Top 10 priorities
        print(line.strip())
"

# Link test failures to coverage gaps
grep -n "missing coverage" coverage_{{module}}.txt
```

**Coverage-Driven Test Generation**:
- Focus on critical system components with <80% coverage
- Prioritize uncovered integration points
- Use CoverUp-style iterative improvement approach
- Quality over quantity - meaningful tests vs coverage padding

### Session Management & Continuity

**Enhanced Session State Preservation**:
```bash
# Save comprehensive session state
echo "# Test Quality Session State - $(date)" > notes/session_state.md
echo "## TodoWrite Progress:" >> notes/session_state.md  
# [TodoWrite state documentation]

echo "## Current PDCA Cycle:" >> notes/session_state.md
echo "- Phase: {{current_phase}}" >> notes/session_state.md
echo "- Cycle: {{cycle_number}}" >> notes/session_state.md
echo "- Next priority: {{next_action}}" >> notes/session_state.md

echo "## Analysis Findings:" >> notes/session_state.md
# [Key patterns and insights discovered]

echo "## Context for Resumption:" >> notes/session_state.md
# [Critical information for next session]
```

**Context Optimization Strategy**:
- Use `/compact Test quality analysis cycle {{N}} complete, {{improvements}} achieved, next: {{next_focus}}`
- Save detailed findings to permanent project files before compacting
- Maintain working notes in notes/ directory for complex reasoning
- Archive resolved issues, keep active analysis context

**Cross-Session Knowledge Transfer**:
```markdown
## Session Handoff Documentation

**Session {{N}} Summary**:
- **PDCA Cycles Completed**: {{count}}
- **Tests Fixed**: {{number}} ({{categories}})
- **Success Rate**: {{baseline}}% → {{current}}%
- **Key Patterns Found**: {{main_insights}}

**Critical Context for Next Session**:
- **Current Focus**: {{active_work}}
- **Next Priorities**: {{next_steps}}
- **Systemic Issues**: {{ongoing_concerns}}
- **Decision Points**: {{pending_decisions}}

**Documentation Updated**:
- CLAUDE.md: {{updates}}
- PROJECT_STATUS.md: {{updates}}
- Test health reports: {{files}}
```

### Success Criteria & Completion

**Tiered Success Definitions**:

**Research Software Compliance**:
- [ ] Scientific validity tests: 100% success
- [ ] Computational accuracy tests: 100% success  
- [ ] Research workflow tests: >95% success
- [ ] Overall test collection: >90% success

**Enterprise Quality Standards**:
- [ ] Critical system tests: >99% success
- [ ] Integration tests: >95% success
- [ ] Performance benchmarks: >90% success
- [ ] Overall test suite: >85% success

**Solo Programmer Realistic**:
- [ ] Core functionality: 100% success
- [ ] User-facing features: >90% success
- [ ] Development tools: >80% success
- [ ] Industry standard skips: Properly justified

**Process Success Indicators**:
- [ ] PDCA cycles demonstrate continuous improvement
- [ ] Pattern recognition identified systemic solutions
- [ ] Resource optimization achieved high impact/effort ratio
- [ ] Session continuity enables seamless resumption
- [ ] Documentation supports long-term maintenance

### Deliverables

**Enhanced Analysis Documentation**:
1. **Holistic Test Failure Analysis**: Pattern recognition across all categories
2. **Industry Standards Compliance**: Multi-tier validation of test justifications
3. **PDCA Improvement Log**: Systematic cycles with decision points
4. **Resource Optimization Report**: Solo programmer context adaptations

**Production-Ready Test Infrastructure**:
1. **Systematically Fixed Test Suite**: 100% meaningful success achieved
2. **Comprehensive Validation Framework**: Ongoing test health monitoring
3. **Session-Resumable Process**: Seamless continuation across interruptions
4. **Enterprise-Grade Quality Standards**: Industry compliance for solo context

**Knowledge Transfer & Maintenance**:
1. **Test Quality Playbook**: Systematic improvement process documentation
2. **Pattern Recognition Guide**: Common failure types and solutions
3. **Resource Management Framework**: Balancing quality vs effort for solo programmers
4. **Continuous Improvement Process**: Sustainable test maintenance procedures

This enhanced framework combines research software rigor with enterprise-grade systematic improvement methodologies, adapted for solo programmer resource constraints while ensuring production-ready quality standards.
</user>