<system>
You are Claude performing systematic test failure analysis with holistic pattern recognition and industry standards validation.

**Mission**: Analyze test execution results to identify patterns, classify root causes, and validate test justifications against multiple industry standards.

**Autonomous Capabilities**: Pattern analysis, root cause classification, industry standards research, and solution interaction assessment.

**Prerequisites**: Requires completion of 04a (Test Execution Infrastructure) with baseline results available.

**Context Management**: Use `/compact <description>` after completing analysis to preserve key findings while optimizing for improvement cycles.
</system>

<user>
### Phase 4b: Test Analysis Framework

**Purpose**: Perform holistic pattern recognition and industry-standard validation of test failures to enable optimal solution planning.

**Scope**: Analysis phase - transforms raw test results into structured improvement insights.

**Prerequisites**: Must have completed Phase 4a with:
- `test_execution_baseline.md` (category results)
- `comprehensive_test_output.txt` (aggregated results)
- `test_health_metrics.md` (baseline statistics)

### Holistic Pattern Recognition

#### Step 1: Comprehensive Failure Aggregation

**Before Individual Analysis** - Systematic aggregation of ALL test failures:

```bash
# Extract all failures from comprehensive results
grep -E "(FAILED|ERROR)" comprehensive_test_output.txt > all_failures.txt

# Categorize failures by type
python -c "
import re

with open('all_failures.txt') as f:
    failures = f.readlines()

# Classification patterns
import_failures = [f for f in failures if any(keyword in f.lower() for keyword in ['import', 'modulenotfound', 'no module'])]
api_failures = [f for f in failures if any(keyword in f.lower() for keyword in ['attribute', 'missing', 'signature', 'takes', 'got'])]
test_design_failures = [f for f in failures if any(keyword in f.lower() for keyword in ['assert', 'expect', 'should', 'timeout'])]
config_failures = [f for f in failures if any(keyword in f.lower() for keyword in ['config', 'path', 'file not found', 'permission'])]
coverage_failures = [f for f in failures if any(keyword in f.lower() for keyword in ['coverage', 'untested', 'missing test'])]

print(f'INFRASTRUCTURE failures (imports/dependencies): {len(import_failures)}')
print(f'API_COMPATIBILITY failures (method signatures): {len(api_failures)}')
print(f'TEST_DESIGN failures (assertions/expectations): {len(test_design_failures)}')
print(f'CONFIGURATION failures (paths/settings): {len(config_failures)}')
print(f'COVERAGE_GAPS failures (untested code): {len(coverage_failures)}')
print(f'UNCLASSIFIED failures: {len(failures) - len(import_failures) - len(api_failures) - len(test_design_failures) - len(config_failures) - len(coverage_failures)}')
"
```

#### Step 2: Root Cause Taxonomy Classification

**Systematic Classification Framework**:

```markdown
# Test Failure Analysis Report - $(date)

## Root Cause Taxonomy Results

### INFRASTRUCTURE Issues (Imports, Dependencies, Environment)
- Count: {{infrastructure_count}}
- Pattern: {{common_infrastructure_patterns}}
- Examples: {{top_3_infrastructure_examples}}
- Fix Strategy: {{infrastructure_approach}}

### API_COMPATIBILITY Issues (Method Signatures, Interfaces)  
- Count: {{api_count}}
- Pattern: {{common_api_patterns}}
- Examples: {{top_3_api_examples}}
- Fix Strategy: {{api_approach}}

### TEST_DESIGN Issues (Brittle Tests, Wrong Expectations)
- Count: {{test_design_count}}
- Pattern: {{common_design_patterns}}
- Examples: {{top_3_design_examples}}
- Fix Strategy: {{design_approach}}

### CONFIGURATION Issues (Settings, Paths, Services)
- Count: {{config_count}}
- Pattern: {{common_config_patterns}}
- Examples: {{top_3_config_examples}}
- Fix Strategy: {{config_approach}}

### COVERAGE_GAPS Issues (Untested Integration Points)
- Count: {{coverage_count}}
- Pattern: {{common_coverage_patterns}}
- Examples: {{top_3_coverage_examples}}
- Fix Strategy: {{coverage_approach}}
```

#### Step 3: Cross-Cutting Concerns Identification

**Pattern Analysis Across Categories**:

```bash
# Identify shared root causes across different test categories
echo "# Cross-Cutting Analysis" > cross_cutting_analysis.md

# Look for common modules/files mentioned in failures
grep -oE '[a-zA-Z_][a-zA-Z0-9_]*\.py' all_failures.txt | sort | uniq -c | sort -nr | head -10 > common_failing_files.txt

# Look for common error patterns
grep -oE 'Error: [^:]*' all_failures.txt | sort | uniq -c | sort -nr | head -10 > common_error_types.txt

echo "## Files Most Frequently Involved in Failures:" >> cross_cutting_analysis.md
cat common_failing_files.txt >> cross_cutting_analysis.md

echo "## Most Common Error Types:" >> cross_cutting_analysis.md  
cat common_error_types.txt >> cross_cutting_analysis.md
```

**Solution Interaction Mapping**:

```markdown
## Solution Interaction Analysis

### Compatible Fixes (Can be batched together):
- {{list_compatible_fixes}}
- Rationale: {{why_these_can_be_batched}}

### Dependency Fixes (Sequential order required):
- {{fix_A}} must complete before {{fix_B}}
- Rationale: {{dependency_explanation}}

### Risk Assessment for Each Fix Category:
- INFRASTRUCTURE fixes: Risk {{level}} - {{reasoning}}
- API_COMPATIBILITY fixes: Risk {{level}} - {{reasoning}}  
- TEST_DESIGN fixes: Risk {{level}} - {{reasoning}}
- CONFIGURATION fixes: Risk {{level}} - {{reasoning}}
- COVERAGE_GAPS fixes: Risk {{level}} - {{reasoning}}

### Single-Fix-Multiple-Issue Opportunities:
- {{describe_fixes_that_resolve_multiple_failures}}
```

### Industry Standards Validation

#### Multi-Tier Test Justification Framework

**For Each SKIPPED Test - Apply Multi-Standard Validation**:

```markdown
## Test Justification Analysis: {{test_name}}

### Research Software Standard (30-60% pass rate baseline):
- **Justified**: [Y/N] + Reasoning
- **Research Impact**: [Scientific validity / Workflow / Performance / Cosmetic]
- **Assessment**: {{detailed_analysis}}

### Enterprise Standard (85-95% pass rate expectation):
- **Justified**: [Y/N] + Reasoning  
- **Business Impact**: [Critical / High / Medium / Low]
- **Assessment**: {{detailed_analysis}}

### IEEE Testing Standard (Industry best practices):
- **Justified**: [Y/N] + Reasoning
- **Technical Debt**: [Acceptable / Should fix / Must fix]
- **Assessment**: {{detailed_analysis}}

### Solo Programmer Context (Resource constraints):
- **Effort Required**: [Simple / Moderate / Complex]
- **Value Proposition**: [High impact/Low effort / Low impact/High effort / etc.]
- **Recommendation**: [Fix / Defer / Remove]
- **Assessment**: {{detailed_analysis}}

### Final Recommendation:
- **Priority Level**: {{P1_CRITICAL / P2_HIGH / P3_MEDIUM / P4_LOW}}
- **Action**: {{Fix immediately / Schedule for next cycle / Defer / Remove}}
- **Rationale**: {{comprehensive_reasoning}}
```

#### Standards Research and Validation

**Industry Standards Research Protocol**:

```bash
# Create standards validation summary
echo "# Industry Standards Validation Summary" > standards_validation.md

# For complex validations, research industry standards
echo "## Research Sources Consulted:" >> standards_validation.md
echo "- IEEE 829-2008 Standard for Software Test Documentation" >> standards_validation.md
echo "- ISO/IEC/IEEE 29119 Software Testing Standards" >> standards_validation.md
echo "- Research Software Engineering Best Practices" >> standards_validation.md
echo "- Enterprise Software Testing Benchmarks" >> standards_validation.md

# Document validation results
echo "## Validation Results by Standard:" >> standards_validation.md
```

### Pattern-Driven Priority Matrix

#### Enhanced Priority Assessment (Solo Programmer Optimized)

**Priority Matrix Integration**:

```markdown
## Enhanced Priority Matrix Results

### P1-CRITICAL (Scientific validity + High impact/Low effort):
- Tests affecting research results accuracy: {{count}}
- Tests with simple fixes enabling other fixes: {{count}}
- **Total P1**: {{total}} tests
- **Estimated Effort**: {{time_estimate}}

### P2-HIGH (System reliability + Quick wins):
- Tests essential for research workflows: {{count}}
- Tests with medium effort but high system impact: {{count}}
- **Total P2**: {{total}} tests  
- **Estimated Effort**: {{time_estimate}}

### P3-MEDIUM (Performance + Clear value proposition):
- Performance tests with moderate effort/value ratio: {{count}}
- Integration tests supporting research efficiency: {{count}}
- **Total P3**: {{total}} tests
- **Estimated Effort**: {{time_estimate}}

### P4-LOW (Cosmetic + High effort/Low value):
- Non-essential functionality tests: {{count}}
- Tests requiring complex effort for minimal benefit: {{count}}
- **Total P4**: {{total}} tests
- **Recommendation**: {{defer_or_remove_reasoning}}
```

### Analysis Documentation and Context Preparation

#### Comprehensive Analysis Summary

**Create Structured Analysis Output**:

```bash
# Generate comprehensive analysis summary
echo "# Test Analysis Summary - $(date)" > test_analysis_summary.md

echo "## Executive Summary" >> test_analysis_summary.md
echo "- Total test failures analyzed: $(wc -l < all_failures.txt)" >> test_analysis_summary.md
echo "- Root cause categories identified: $(grep -c "Count:" cross_cutting_analysis.md || echo "TBD")" >> test_analysis_summary.md
echo "- Cross-cutting concerns found: $(wc -l < common_failing_files.txt)" >> test_analysis_summary.md
echo "- Priority 1 fixes identified: {{P1_count}}" >> test_analysis_summary.md

echo "## Key Patterns Discovered" >> test_analysis_summary.md
echo "{{summarize_most_important_patterns}}" >> test_analysis_summary.md

echo "## Solution Strategy Recommendations" >> test_analysis_summary.md
echo "{{high_level_approach_recommendations}}" >> test_analysis_summary.md

echo "## Readiness for Implementation Cycles" >> test_analysis_summary.md
echo "- Analysis complete: ✅" >> test_analysis_summary.md
echo "- Priority matrix established: ✅" >> test_analysis_summary.md
echo "- Solution interactions mapped: ✅" >> test_analysis_summary.md
echo "- Industry standards validated: ✅" >> test_analysis_summary.md
```

#### Context Optimization for Next Phase

**Prepare for 04c (Improvement Cycles)**:

```bash
# Create essential context for improvement cycles
echo "# Context for Implementation Cycles" > implementation_context.md

echo "## Priority Queue (Ready for PDCA cycles):" >> implementation_context.md
echo "### P1-CRITICAL fixes:" >> implementation_context.md
echo "{{list_P1_fixes_with_approach}}" >> implementation_context.md

echo "### P2-HIGH fixes:" >> implementation_context.md  
echo "{{list_P2_fixes_with_approach}}" >> implementation_context.md

echo "## Solution Batching Opportunities:" >> implementation_context.md
echo "{{compatible_fixes_that_can_be_grouped}}" >> implementation_context.md

echo "## Risk Mitigation Requirements:" >> implementation_context.md
echo "{{fixes_requiring_careful_validation}}" >> implementation_context.md
```

### Quality Gates for Analysis Phase

**Analysis Completion Criteria**:
- [ ] All test failures classified using root cause taxonomy
- [ ] Cross-cutting concerns identified and documented
- [ ] Industry standards validation completed for key failures
- [ ] Priority matrix established with effort/value analysis
- [ ] Solution interaction opportunities mapped
- [ ] Implementation context prepared for improvement cycles

**Readiness for Next Phase**:
- [ ] `test_analysis_summary.md` contains comprehensive findings
- [ ] `implementation_context.md` ready for PDCA cycles
- [ ] Priority queue established with P1-P4 classifications
- [ ] Solution batching opportunities identified

### Deliverables

**Analysis Documentation**:
1. **Root Cause Classification**: All failures categorized by taxonomy
2. **Pattern Recognition Report**: Cross-cutting concerns and shared causes
3. **Industry Standards Validation**: Multi-tier justification analysis
4. **Priority Matrix**: Resource-optimized fix prioritization

**Strategic Planning Outputs**:
1. **Solution Interaction Map**: Compatible batches and dependencies
2. **Risk Assessment**: Validation requirements for each fix category
3. **Implementation Context**: Ready-to-use priority queue for cycles
4. **Standards Compliance**: Objective validation against industry benchmarks

### Next Phase Integration

**Preparation for 04c (Improvement Cycles)**:
- Pattern analysis complete ✅
- Priority matrix established ✅
- Solution interactions mapped ✅
- Implementation context optimized ✅

**Usage**: Complete this phase before proceeding to `04c_test_improvement_cycles.md` for systematic PDCA implementation.

This phase transforms raw test results into actionable improvement insights while ensuring resource-optimized decision making for solo programmers.
</user>