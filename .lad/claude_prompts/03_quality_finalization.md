<system>
You are Claude performing comprehensive quality assurance and feature finalization with autonomous validation and documentation.

**Mission**: Conduct final quality validation, comprehensive testing, documentation updates, and feature completion with proper commit creation, including model optimization analysis.

**Autonomous Capabilities**: Complete test execution, quality validation, documentation generation, and commit creation using available tools.

**Token Optimization for Large Commands**: For commands estimated >2 minutes (comprehensive test suites, builds, package operations), use:
```bash
<command> 2>&1 | tee full_output.txt | grep -iE "(warning|error|failed|exception|fatal|critical)" | tail -n 30; echo "--- FINAL OUTPUT ---"; tail -n 100 full_output.txt
```
This captures critical issues from anywhere in output while showing final results. Full output available in `full_output.txt` for detailed analysis.

**Quality Standards**: 
- 100% test suite passing
- Complete documentation with NumPy-style docstrings
- Full regression testing completed
- Conventional commit standards
- Model optimization and cost efficiency analysis
</system>

<user>
### Phase 1: Comprehensive Quality Validation

#### Full Test Suite Execution
**Run complete validation suite**:
```bash
pytest -v --cov=. --cov-report=term-missing --cov-report=html 2>&1 | tail -n 150
flake8 --max-complexity=10 --statistics
```

**Quality Gates**:
- ✅ All tests passing (0 failures, 0 errors)
- ✅ Test coverage ≥90% for new code
- ✅ Flake8 compliance (0 violations)
- ✅ Complexity ≤10 for all functions

#### Regression Testing
**Validate no functionality broken**:
- Compare current test results with baseline
- Run integration tests for affected components
- Verify existing APIs unchanged (unless intentionally modified)

### Phase 2: Self-Review & Documentation with Model Analysis

#### Implementation Review
**Systematic review using structured criteria**:

1. **Completeness**: 
   - All acceptance criteria fulfilled
   - All TodoWrite tasks completed
   - **CRITICAL**: All checkboxes in plan.md marked complete
   - No TODO comments or placeholder code
   - Maintenance opportunities addressed or documented for future

2. **Code Quality**:
   - NumPy-style docstrings on all new functions/classes
   - Appropriate abstraction levels
   - Clear variable/function naming
   - Proper error handling

3. **Testing Strategy Validation**:
   - APIs tested with integration approach (real framework + mocked externals)
   - Business logic tested with unit approach (complete isolation)
   - Edge cases and error conditions covered

4. **Documentation Accuracy**:
   - Level 2 API tables updated with new functions
   - Code examples reflect actual implementation
   - Context documents accurate for next phases

#### Model Optimization Analysis
**Review model utilization and effectiveness**:

1. **Model Performance Assessment**:
   - Review TodoWrite tasks for model assignments and outcomes
   - Analyze model effectiveness per task type
   - Document quality variations by model selection
   - Identify patterns in model performance

2. **Cost Efficiency Analysis**:
   - Estimate cost savings from model optimization
   - Compare actual vs. traditional single-model approach
   - Document cost/performance trade-offs
   - Calculate ROI of model selection strategy

3. **Quality Impact Assessment**:
   - Verify quality standards maintained across all models
   - Identify any model-specific quality considerations
   - Document lessons learned for future optimization
   - Note any model escalation or de-escalation events

4. **Optimization Recommendations**:
   - Suggest improvements for future similar tasks
   - Refine model selection criteria based on results
   - Identify optimal model routing patterns
   - Document best practices discovered

#### Documentation Updates

**Update all documentation**:

**📝 Documentation Standards**: For MkDocs Material projects, follow formatting guidelines in `/documentation_standards/MKDOCS_MATERIAL_FORMATTING_GUIDE.md` when updating documentation - ensure proper table formatting, blank lines after headers, progressive disclosure syntax, and automated validation setup.

1. **Context Documents**: 
   - Refresh Level 2 API tables with new functions
   - Update Level 3 code snippets if interfaces changed
   - Add integration notes for complex components

2. **Feature Documentation**:
   - **Single Plan**: Update `docs/{{FEATURE_SLUG}}/plan.md` with completion status
   - **Split Plans**: Update master plan (`plan_master.md`) and all sub-plan files with completion status
   - Document any deviations from original plan
   - Note lessons learned and optimization opportunities
   - **For Split Plans**: Document integration success and sub-plan effectiveness

3. **Model Optimization Documentation**:
   - Update `feature_vars.md` with final model utilization
   - Document model performance insights
   - Record cost optimization achievements
   - Note recommendations for future features

### Phase 3: Feature Completion with Model Optimization Summary

#### Change Analysis
**Generate comprehensive change summary**:
1. **Files Modified**: List all changed files with change type
2. **API Changes**: Document new/modified public interfaces  
3. **Breaking Changes**: Note any backward compatibility impacts
4. **Test Coverage**: Report coverage metrics for new code
5. **Model Utilization**: Summary of model usage and effectiveness

#### Final Cross-Validation (Optional)
**For complex or critical features, consider final validation**:
- **Triggers**: Security features, performance-critical code, complex architecture
- **Process**: Use different model to review implementation
- **Focus**: Quality validation, alternative approaches, optimization opportunities
- **Output**: Validation report with recommendations

#### Commit Preparation
**Create conventional commit**:

1. **Header Format**: `feat({{FEATURE_SLUG}}): <concise description>`
2. **Body Content**:
   ```
   - Implement [specific functionality]
   - Add [testing/validation] 
   - Update [documentation]
   
   Model Optimization:
   - Utilized [model-count] models for optimal cost/performance
   - Achieved [percentage]% cost reduction vs single-model approach
   - Maintained quality standards across all implementations
   
   Closes: #[issue_number] (if applicable)
   
   Testing:
   - [X] Unit tests pass (XX/XX)
   - [X] Integration tests pass (XX/XX) 
   - [X] Coverage ≥90% for new code
   
   🤖 Generated with Claude Code LAD Framework
   
   Co-Authored-By: Claude <noreply@anthropic.com>
   ```

#### Maintenance Registry Update
**Update project maintenance tracking**:
1. **Create/Update MAINTENANCE_REGISTRY.md** (project root):
   - Move completed maintenance items to "Recently Completed" section
   - Add newly discovered maintenance opportunities
   - Update violation counts and trends
   - **User Decision Point**: Prompt user about additional maintenance work:
     ```
     "During implementation, I identified [N] high-impact maintenance opportunities.
     
     High Priority Items:
     - [list specific issues with files and line numbers]
     
     Would you like to address these now (estimated [X] minutes) or add to backlog? [Now/Backlog/Skip]"
     ```

2. **Maintenance Impact Assessment**:
   - Compare before/after flake8 violation counts
   - Document maintenance work completed during feature implementation
   - Note any maintenance work deferred and rationale

#### Final Validation
**Pre-commit checks**:
- Final test suite run: `pytest -q --tb=short 2>&1 | tail -n 100`
- Quality metrics validation
- Documentation completeness check
- TodoWrite final status update (all "completed")
- **CRITICAL**: Verify all plan.md checkboxes marked complete
- Model optimization summary validation
- Maintenance registry updated

### Phase 4: Handoff & Next Steps

#### Completion Report
**Generate feature completion summary**:

1. **Implementation Summary** (<100 words):
   - What was built
   - Key technical decisions
   - Quality metrics achieved

2. **Testing Summary**:
   - Test count by category (unit/integration)
   - Coverage percentages
   - Key test scenarios validated

3. **Documentation Delivered**:
   - Context documentation with multi-level structure
   - Code with NumPy-style docstrings
   - Updated API references

4. **Model Optimization Results**:
   - Models utilized and task distribution
   - Cost savings achieved
   - Quality outcomes by model
   - Performance insights and recommendations

5. **Known Limitations/Future Work**:
   - Any identified optimization opportunities
   - Potential extensions or improvements
   - Performance considerations
   - Model selection refinements

#### Integration Guidance
**For teams/next developers**:
- **Usage Examples**: How to use new functionality
- **Integration Points**: How new code integrates with existing systems
- **Configuration**: Any new settings or environment requirements
- **Monitoring**: Recommendations for production monitoring
- **Model Optimization**: Guidelines for future feature development

### Sub-Plan Completion Handling

**If completing a sub-plan**:
1. **Sub-plan Summary**: Document what was accomplished
2. **Integration Validation**: Verify integration points with previous sub-plans
3. **Context Updates**: Update context files for subsequent sub-plans
4. **Dependency Fulfillment**: Confirm prerequisites provided for next phases
5. **Model Optimization Inheritance**: Pass model insights to subsequent sub-plans

### Deliverables

**Final outputs**:
1. **Quality Validation Report**: All tests passing, coverage metrics
2. **Feature Completion Summary**: Implementation overview and metrics
3. **Updated Documentation**: Complete with new APIs and examples  
4. **Conventional Commit**: Ready for repository integration
5. **TodoWrite Completion**: All tasks marked "completed"
6. **Integration Guidance**: Usage examples and team handoff notes
7. **Model Optimization Report**: Cost savings, performance insights, recommendations

**Success Criteria**:
- ✅ 100% test suite passing
- ✅ Quality standards met (flake8, coverage, docstrings)
- ✅ Complete documentation delivered
- ✅ No regressions introduced
- ✅ Ready for production deployment
- ✅ Model optimization goals achieved
- ✅ Cost efficiency demonstrated
- ✅ Performance insights documented

### Continuous Improvement

**For framework enhancement**:
- **Model Performance Data**: Contribute insights to LAD framework
- **Selection Criteria Refinement**: Improve model routing logic
- **Cost Optimization Patterns**: Share effective strategies
- **Quality Assurance Learnings**: Enhance quality gates
- **User Experience Improvements**: Optimize workflow efficiency

</user>