<system>
You are Claude establishing systematic test execution infrastructure with timeout prevention and comprehensive baseline analysis.

**Mission**: Set up robust test execution framework that prevents timeouts, handles large test suites efficiently, and establishes comprehensive test health baselines.

**Autonomous Capabilities**: Test execution (Bash), result aggregation, pattern analysis, and baseline establishment.

**Token Optimization for Large Test Runs**: For comprehensive test suites:
```bash
<command> 2>&1 | tee full_output.txt | grep -iE "(warning|error|failed|exception|fatal|critical)" | tail -n 30; echo "--- FINAL OUTPUT ---"; tail -n 100 full_output.txt
```

**Context Management**: Use `/compact <description>` after completing execution phases to preserve test results while optimizing context.

**CRITICAL**: Before any code modifications during phase 04 execution, follow the **Regression Risk Management Protocol** below to prevent destabilizing mature codebases.
</system>

<user>
### Phase 4a: Test Execution Infrastructure

**Purpose**: Establish systematic test execution capabilities that prevent timeouts and provide comprehensive baseline analysis for large test suites.

**Scope**: Test execution infrastructure setup - foundation for subsequent analysis phases.

### ⚠️ **Regression Risk Management Protocol**

**MANDATORY** before any code changes during phases 04a-04d. For mature codebases with complex integration points, systematic risk assessment prevents regressions in working systems.

#### Pre-Change Impact Analysis

**1. Codebase Context Mapping**:
```bash
# Analyze affected components and their interactions
target_function="function_to_modify"
echo "# Impact Analysis for: $target_function" > impact_analysis.md

# Find all references and dependencies
echo "## Direct References:" >> impact_analysis.md
grep -r "$target_function" --include="*.py" . >> impact_analysis.md

# Check import dependencies
echo "## Import Dependencies:" >> impact_analysis.md  
grep -r "from.*import.*$target_function\|import.*$target_function" --include="*.py" . >> impact_analysis.md

# Identify calling patterns
echo "## Calling Patterns:" >> impact_analysis.md
grep -r "$target_function(" --include="*.py" . -A 2 -B 2 >> impact_analysis.md
```

**2. Documentation Cross-Reference**:
```bash
# Check if change affects documented behavior
echo "## Documentation Impact:" >> impact_analysis.md
grep -r "$target_function" docs/ README.md *.md 2>/dev/null >> impact_analysis.md

# Verify user guide examples remain valid
grep -r "$target_function" docs/USER_GUIDE.md docs/QUICK_START.md 2>/dev/null >> impact_analysis.md

# Check API documentation accuracy
grep -r "$target_function" docs/API_REFERENCE.md docs/**/api*.md 2>/dev/null >> impact_analysis.md
```

**3. Integration Point Analysis**:
```bash
# Map critical system interactions
echo "## Integration Points:" >> impact_analysis.md

# Statistical analysis pipeline interactions
grep -r "$target_function" emuses/**/statistical*.py emuses/**/analysis*.py 2>/dev/null >> impact_analysis.md

# Model registry interactions
grep -r "$target_function" emuses/**/model_registry*.py emuses/**/registry*.py 2>/dev/null >> impact_analysis.md

# Multi-user service compatibility  
grep -r "$target_function" emuses/**/service*.py emuses/**/multi_user*.py 2>/dev/null >> impact_analysis.md

# CLI and API endpoints
grep -r "$target_function" emuses/cli/*.py emuses/api/*.py 2>/dev/null >> impact_analysis.md
```

**4. Test Impact Prediction**:
```bash
# Identify which test categories could be affected
echo "## Affected Test Categories:" >> impact_analysis.md
grep -r "$target_function" tests/ --include="*.py" | cut -d'/' -f2 | sort -u >> impact_analysis.md

# Find specific test files
echo "## Specific Test Files:" >> impact_analysis.md
grep -l "$target_function" tests/**/*.py 2>/dev/null >> impact_analysis.md
```

#### Change Safety Protocol

**5. Baseline Establishment**:
```bash
# Commit current working state before changes
git add -A
git commit -m "baseline: pre-change checkpoint for $target_function modification

Impact analysis completed in impact_analysis.md
Safe to proceed with targeted changes.

This commit enables clean rollback if regressions occur."

# Run focused pre-change test validation
echo "## Pre-Change Test Results:" >> impact_analysis.md
pytest $(grep -l "$target_function" tests/**/*.py 2>/dev/null) -v --tb=short >> impact_analysis.md 2>&1
```

**6. Rollback Strategy**:
```bash
# Document specific tests that must pass post-change
echo "## Post-Change Validation Requirements:" >> impact_analysis.md
echo "- All tests in affected categories must remain green" >> impact_analysis.md
echo "- Integration tests for related components must pass" >> impact_analysis.md
echo "- Documentation examples must remain accurate" >> impact_analysis.md
echo "- API compatibility must be preserved" >> impact_analysis.md

# Store rollback command for quick recovery
echo "# Rollback command if needed:" >> impact_analysis.md
echo "git reset --hard $(git rev-parse HEAD)" >> impact_analysis.md
```

#### Risk Assessment Matrix

**Low Risk Changes** (proceed with standard validation):
- Test fixture improvements, test data updates
- Documentation clarifications, comment additions
- Logging enhancements, debug output improvements
- Non-functional refactoring within single modules

**Medium Risk Changes** (requires focused validation):
- Algorithm parameter adjustments, performance optimizations
- Error handling improvements, validation enhancements
- Configuration changes, environment variable modifications
- API response format changes (backward compatible)

**High Risk Changes** (requires comprehensive validation):
- Core algorithm modifications, statistical analysis changes
- Database schema changes, model registry structure changes
- Multi-user authentication/authorization changes
- Breaking API changes, CLI interface modifications

#### Validation Protocol Post-Change

**Immediate Validation** (run after each change):
```bash
# Test affected categories immediately
pytest $(grep -l "$target_function" tests/**/*.py 2>/dev/null) -x --tb=short

# Quick integration smoke test
python scripts/dev_test_runner.py

# Verify documentation examples still work
python -c "exec(open('docs/examples/validate_examples.py').read())" 2>/dev/null || echo "No example validation script"
```

**Comprehensive Validation** (before committing):
```bash
# Full category testing for affected areas
affected_categories=$(grep -r "$target_function" tests/ --include="*.py" | cut -d'/' -f2 | sort -u | tr '\n' ' ')
for category in $affected_categories; do
    pytest tests/$category/ -q --tb=short
done

# Cross-integration validation
pytest tests/integration/ -k "$target_function" -v --tb=short 2>/dev/null || echo "No integration tests found"
```

### ⚠️ **Emergency Rollback Procedure**

If regressions are detected during phases 04:

```bash
# Immediate rollback to baseline
git reset --hard baseline_commit_hash

# Verify rollback success
python scripts/dev_test_runner.py

# Document rollback in analysis
echo "## ROLLBACK EXECUTED: $(date)" >> impact_analysis.md
echo "Reason: [describe regression detected]" >> impact_analysis.md
echo "Recovery: Baseline restored, ready for alternative approach" >> impact_analysis.md
```

### Systematic Test Execution Protocol

#### Intelligent Chunking Strategy (Timeout Prevention)

**Proven Chunk Sizing for Different Test Categories**:

```bash
# Security tests (typically fast, stable execution)
pytest tests/security/ -v --tb=short 2>&1 | tee security_results.txt | grep -E "(PASSED|FAILED|SKIPPED|ERROR|warnings|collected)" | tail -n 15

# Model registry (large category - requires chunking)
pytest tests/model_registry/test_local*.py tests/model_registry/test_api*.py tests/model_registry/test_database*.py -v --tb=short 2>&1 | tee registry_chunk1.txt | tail -n 10

pytest tests/model_registry/test_advanced*.py tests/model_registry/test_analytics*.py tests/model_registry/test_benchmarking*.py -v --tb=short 2>&1 | tee registry_chunk2.txt | tail -n 10

# Integration tests (complex, potentially slow)
pytest tests/integration/test_unified*.py tests/integration/test_cross*.py -v --tb=short 2>&1 | tee integration_chunk1.txt | tail -n 10

# Performance tests (timeout-prone)
pytest tests/performance/ -v --tb=short 2>&1 | tee performance_results.txt | grep -E "(PASSED|FAILED|SKIPPED|ERROR)" | tail -n 10

# Tools and CLI (mixed complexity)
pytest tests/tools/ -v --tb=short 2>&1 | tee tools_results.txt | grep -E "(PASSED|FAILED|SKIPPED|ERROR)" | tail -n 10

pytest tests/enhanced-cli-typer/test_cli_integration.py tests/enhanced-cli-typer/test_service_client.py -v --tb=short 2>&1 | tee cli_chunk1.txt | tail -n 10

# Multi-user service (complex setup requirements)
pytest tests/multi-user-service/test_auth*.py tests/multi-user-service/test_workspace*.py -v --tb=short 2>&1 | tee multiuser_chunk1.txt | tail -n 10
```

**Dynamic Chunk Size Guidelines**:
- **Simple tests**: 10-20 tests per chunk (security, unit tests)
- **Integration tests**: 5-10 tests per chunk (API, database, multi-component)
- **Complex tests**: 3-5 tests per chunk (performance, load testing, end-to-end)
- **Timeout-prone tests**: Individual execution if needed

#### Comprehensive Baseline Establishment

**Complete Test Discovery and Categorization**:
```bash
# Establish comprehensive test inventory
pytest --collect-only 2>&1 | tee test_collection_baseline.txt

# Extract collection statistics
python -c "
import re
with open('test_collection_baseline.txt') as f:
    content = f.read()
    collected = re.findall(r'collected (\d+) item', content)
    errors = content.count('ERROR')
    print(f'Total tests collected: {collected[-1] if collected else 0}')
    print(f'Collection errors: {errors}')
    print(f'Collection success rate: {((int(collected[-1]) if collected else 0) / (int(collected[-1]) + errors) * 100) if (collected and (int(collected[-1]) + errors) > 0) else 0:.1f}%')
"
```

**Category-wise Execution Tracking**:
```bash
# Track execution results per category
echo "# Test Execution Baseline - $(date)" > test_execution_baseline.md

# Execute and track each category
for category in security model_registry integration performance tools multi-user-service enhanced-cli-typer; do
    echo "## $category Category Results" >> test_execution_baseline.md
    if [ -f "${category}_results.txt" ] || ls ${category}_chunk*.txt 1> /dev/null 2>&1; then
        # Aggregate results from category files
        cat ${category}_*.txt 2>/dev/null | grep -E "(PASSED|FAILED|SKIPPED|ERROR)" | tail -n 5 >> test_execution_baseline.md
        cat ${category}_*.txt 2>/dev/null | grep "===.*===" | tail -n 1 >> test_execution_baseline.md
    else
        echo "Category not executed" >> test_execution_baseline.md
    fi
    echo "" >> test_execution_baseline.md
done
```

#### Result Aggregation and Health Metrics

**Comprehensive Results Analysis**:
```bash
# Aggregate all test results for pattern analysis
cat *_results.txt *_chunk*.txt > comprehensive_test_output.txt 2>/dev/null

# Extract key metrics
echo "# Test Health Metrics - $(date)" > test_health_metrics.md
echo "## Overall Statistics" >> test_health_metrics.md

# Count totals across all categories
python -c "
import re
with open('comprehensive_test_output.txt') as f:
    content = f.read()
    
# Extract final summary lines that show totals
summary_lines = [line for line in content.split('\n') if '=====' in line and ('passed' in line or 'failed' in line)]

total_passed = 0
total_failed = 0
total_skipped = 0
total_warnings = 0

for line in summary_lines:
    passed = re.findall(r'(\d+) passed', line)
    failed = re.findall(r'(\d+) failed', line)
    skipped = re.findall(r'(\d+) skipped', line)
    warnings = re.findall(r'(\d+) warning', line)
    
    if passed: total_passed += int(passed[0])
    if failed: total_failed += int(failed[0])
    if skipped: total_skipped += int(skipped[0])
    if warnings: total_warnings += int(warnings[0])

total_tests = total_passed + total_failed + total_skipped
success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

print(f'Total Tests: {total_tests}')
print(f'Passed: {total_passed} ({total_passed/total_tests*100:.1f}%)' if total_tests > 0 else 'Passed: 0')
print(f'Failed: {total_failed} ({total_failed/total_tests*100:.1f}%)' if total_tests > 0 else 'Failed: 0')
print(f'Skipped: {total_skipped} ({total_skipped/total_tests*100:.1f}%)' if total_tests > 0 else 'Skipped: 0')
print(f'Warnings: {total_warnings}')
print(f'Success Rate: {success_rate:.1f}%')
" >> test_health_metrics.md
```

#### Token Efficiency Optimization

**Large Output Management**:
```bash
# For very large test suites (>500 tests), use aggressive filtering
pytest tests/large_category/ 2>&1 | tee full_test_output.txt | grep -iE "(error|failed|warning|exception)" | tail -n 30; echo "--- SUMMARY ---"; tail -n 50 full_test_output.txt

# Store detailed results for later analysis if needed
ls -la *_results.txt *_chunk*.txt > detailed_results_inventory.txt
```

**Context Preservation Strategy**:
```bash
# Before using /compact, save essential baseline data
echo "# Test Execution Context Preservation" > test_context_summary.md
echo "## Key Findings" >> test_context_summary.md
echo "- Total tests executed: $(grep -h "passed\|failed" *_results.txt *_chunk*.txt 2>/dev/null | wc -l)" >> test_context_summary.md
echo "- Categories completed: $(ls *_results.txt *_chunk*.txt 2>/dev/null | cut -d'_' -f1 | sort -u | wc -l)" >> test_context_summary.md
echo "- Collection errors: $(grep -c "ERROR" test_collection_baseline.txt 2>/dev/null || echo 0)" >> test_context_summary.md
echo "## Next Phase: Ready for analysis framework (04b)" >> test_context_summary.md
```

### Quality Gates for Execution Phase

**Execution Success Criteria**:
- [ ] Test collection completes without critical errors
- [ ] All major test categories execute within timeout limits
- [ ] Comprehensive baseline established with health metrics
- [ ] Results properly aggregated for subsequent analysis
- [ ] No execution infrastructure failures

**Readiness for Next Phase**:
- [ ] `test_execution_baseline.md` contains category results
- [ ] `test_health_metrics.md` shows overall statistics  
- [ ] `comprehensive_test_output.txt` available for pattern analysis
- [ ] Context preserved for analysis phase (04b)

### Deliverables

**Test Execution Infrastructure**:
1. **Systematic Chunking Protocol**: Proven chunk sizes preventing timeouts
2. **Comprehensive Baseline**: Complete test health metrics and category analysis
3. **Efficient Result Aggregation**: Structured output for pattern recognition
4. **Token-Optimized Execution**: Large test suite handling without context overflow

**Documentation Outputs**:
1. **`test_execution_baseline.md`**: Category-wise execution results
2. **`test_health_metrics.md`**: Overall statistics and success rates
3. **`comprehensive_test_output.txt`**: Complete aggregated results for analysis
4. **`test_context_summary.md`**: Context preservation for next phase

### Next Phase Integration

**Preparation for 04b (Analysis Framework)**:
- Test execution baseline established ✅
- Results aggregated and ready for pattern analysis ✅
- Health metrics available for comparison ✅
- Context optimized for analysis phase ✅

**Usage**: Complete this phase before proceeding to `04b_test_analysis_framework.md` for holistic pattern recognition and root cause analysis.

This phase provides the robust foundation needed for systematic test improvement while ensuring efficient resource usage and timeout prevention.
</user>