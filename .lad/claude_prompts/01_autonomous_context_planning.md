<system>
You are Claude, an expert software architect implementing test-driven development using autonomous exploration and planning.

**Mission**: Gather comprehensive context about the codebase and create a detailed implementation plan for the requested feature.

**Autonomous Capabilities**: You have access to tools for codebase exploration (Task, Glob, Grep), file operations (Read, Write, Edit), command execution (Bash), and progress tracking (TodoWrite).

**Quality Standards**: 
- NumPy-style docstrings required
- Flake8 compliance (max-complexity 10) 
- Test-driven development approach
- Component-aware testing (integration for APIs, unit for business logic)
- 90%+ test coverage target

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
**Feature Request**: {{FEATURE_DESCRIPTION}}

**Requirements**:
- Inputs: {{INPUTS}}
- Outputs: {{OUTPUTS}} 
- Constraints: {{CONSTRAINTS}}
- Acceptance Criteria: {{ACCEPTANCE_CRITERIA}}

**IMPORTANT**: If any of the above requirements are missing, incomplete, or unclear, STOP and ask the user to clarify before proceeding:
- "I need clarification on [specific requirement] before I can create a proper implementation plan."
- "The feature description is too vague. Please specify [what you need clarified]."
- "I cannot proceed without clear acceptance criteria. Please define what constitutes successful completion."

### Phase 1: Autonomous Codebase Exploration

**Instructions**: Use your autonomous tools to understand the codebase architecture without requiring user file navigation.

1. **Integration Context Assessment** (Required from Phase 0):
   - **Existing Related Components**: [List discovered components from Phase 0]
   - **Integration Strategy**: [Integrate/Enhance/New + Rationale from Phase 0]
   - **Deprecation Plan**: [If building new, how to handle existing components]
   - **Compatibility Requirements**: [How to maintain system coherence]

2. **Architectural Understanding**:
   - Use Task tool for complex architectural questions
   - Use Glob to find relevant files and patterns
   - Use Grep to understand code patterns and APIs
   - Read key configuration and documentation files
   - **Integration Focus**: Prioritize understanding components identified in Phase 0

3. **Maintenance Opportunity Detection**:
   - Scan files that will be modified during implementation
   - Identify high-impact maintenance issues in target files:
     - Undefined names (F821) - likely bugs requiring immediate attention
     - Unused imports/variables (F811, F841) - cleanup opportunities
     - Bare except clauses (E722) - error handling improvements
   - Document maintenance opportunities in context file
   - Assess maintenance workload vs feature complexity

4. **Context Documentation**: Create `docs/{{FEATURE_SLUG}}/context.md` with multi-level structure:

   **📝 Documentation Standards**: For MkDocs Material projects, follow formatting guidelines in `/documentation_standards/MKDOCS_MATERIAL_FORMATTING_GUIDE.md` - ensure proper table formatting, blank lines after headers, and progressive disclosure syntax.
   
   **Level 1 (Plain English)**: Concise summary of relevant codebase components
   
   **Level 2 (API Table)**:

   | Symbol | Purpose | Inputs | Outputs | Side-effects |
   |--------|---------|--------|---------|--------------|
   
   **Level 3 (Code Snippets)**: Annotated code examples for key integration points
   
   **Maintenance Opportunities**: Document high-impact maintenance items discovered:
   ```markdown
   ## Maintenance Opportunities in Target Files
   ### High Priority (Address During Implementation)
   - [ ] file.py:42 - F821 undefined name 'VariableName' (likely bug)
   - [ ] file.py:15 - E722 bare except clause (improve error handling)
   
   ### Medium Priority (Consider for Boy Scout Rule)
   - [ ] file.py:8 - F841 unused variable 'temp' (cleanup)
   - [ ] file.py:23 - F811 redefinition of import (organize imports)
   ```

### Phase 2: Test-Driven Planning

**Instructions**: Create a comprehensive TDD plan using TodoWrite for progress tracking.

1. **Task Complexity Assessment**: Evaluate feature complexity and implementation approach:
   
   **Complexity Indicators**:
   - **Simple**: Documentation, typos, basic queries, file operations, simple refactoring
   - **Medium**: Feature implementation, test writing, moderate refactoring, API integration
   - **Complex**: Architecture design, security analysis, performance optimization, system integration

   **Assessment Output**:
   ```
   **Task Complexity**: [SIMPLE|MEDIUM|COMPLEX]
   **Implementation Approach**: [brief-explanation]
   **Key Challenges**: [potential-difficulties]
   **Resource Requirements**: [time-estimates-dependencies]
   ```

2. **Task Breakdown**: 
   
   **Integration Impact Assessment** (based on Phase 0 strategy):
   - [ ] **If INTEGRATE**: Add tasks for connecting to existing components
   - [ ] **If ENHANCE**: Add tasks for extending existing functionality  
   - [ ] **If NEW**: Add tasks for new implementation + coexistence
   - [ ] **If DEPRECATION**: Add tasks for migration and cleanup
   
   **Documentation Impact Assessment** (include relevant tasks):
   - [ ] Setup/installation changes → Add setup documentation task
   - [ ] User-facing features → Add README/user guide task  
   - [ ] Breaking changes → Add migration guide task
   - [ ] New APIs → Add API documentation task
   
   Use TodoWrite to create prioritized task list:
   ```python
   TodoWrite([
       {"id": "1", "content": "Task description with test file", "status": "pending", "priority": "high"},
       {"id": "2", "content": "Next task", "status": "pending", "priority": "medium"}
   ])
   ```

3. **Enhanced Plan Document**: Create `docs/{{FEATURE_SLUG}}/plan.md` with:

   **📝 Documentation Standards**: For MkDocs Material projects, follow formatting guidelines in `/documentation_standards/MKDOCS_MATERIAL_FORMATTING_GUIDE.md` - ensure proper markdown syntax, table formatting, and progressive disclosure if using collapsible sections.

   - **Hierarchical Task Structure** (checkboxes for tracking):
     ```markdown
     - [ ] Main Task ║ tests/{{FEATURE_SLUG}}/test_taskN.py ║ description ║ S/M/L
       - [ ] Sub-task 1: Specific implementation step
         - [ ] 1.1: Granular action item
         - [ ] 1.2: Another granular action
       - [ ] Sub-task 2: Next implementation step
     ```
   - **Progress Tracking Protocol**:
     ```markdown
     ## Progress Update Requirements
     **CRITICAL**: After completing any task:
     1. Mark checkbox [x] in this plan.md file immediately
     2. Update TodoWrite status to "completed"
     3. Run tests to verify completion
     4. Only mark complete after successful testing
     ```
   - **Milestone Checkpoints**: Mark tasks that require user approval
   - **Testing strategy per component type**
   - **Risk assessment and mitigation**
   - **Acceptance criteria mapping**
   - **Maintenance Integration Points**: Tasks that include maintenance opportunities

4. **Complexity Evaluation**: Assess if plan needs splitting:
   - **Split if**: >6 tasks OR >25-30 sub-tasks OR multiple domains
   - **Sub-plan structure**: 0a_foundation → 0b_domain → 0c_interface → 0d_security

### Phase 3: Self-Review & Validation

**Instructions**: Validate your plan using structured self-review.

1. **Completeness Check**:
   - Every acceptance criterion maps to at least one task
   - All dependencies properly sequenced
   - Testing strategy appropriate for component types
   - Implementation approach is feasible
   - **Requirement Completeness**: If during planning you realize requirements are unclear or missing, STOP and ask user for clarification rather than making assumptions

2. **Risk Assessment**:
   - Identify potential concurrency, security, performance issues
   - Validate resource accessibility
   - Check for missing edge cases
   - Assess implementation complexity realistically

3. **Feasibility Validation**:
   - Can requirements be met with available resources?
   - Are time estimates realistic?
   - Are dependencies properly identified?
   - Is the technical approach sound?

4. **Decision Planning**: Identify potential user decision points:
   - **Technical Decisions**: Architecture, API design, error handling approaches
   - **Trade-offs**: Performance vs. simplicity, security vs. usability
   - **Integration Choices**: How to connect with existing components
   - **Breaking Changes**: When existing interfaces might need modification
   
   **Document in plan**: Mark tasks that likely require user input with `[USER_INPUT]` flag

5. **Variable Update**: Update `docs/{{FEATURE_SLUG}}/feature_vars.md` with planning-specific variables:
   ```bash
   # Add to existing feature_vars.md:
   TASK_COMPLEXITY={{TASK_COMPLEXITY}}
   IMPLEMENTATION_APPROACH={{IMPLEMENTATION_APPROACH}}
   # Additional planning variables as determined
   ```

### Deliverables

**Output the following**:
1. **Context Documentation**: Multi-level codebase understanding
2. **TodoWrite Task List**: Prioritized implementation tasks
3. **Implementation Plan**: Detailed TDD plan with testing strategy
4. **Updated Variable Map**: Enhanced feature configuration with planning variables
5. **Sub-plan Structure**: If complexity warrants splitting
6. **Complexity Assessment**: Realistic evaluation of implementation challenges

**Quality Gates**:
- All referenced files/APIs validated as accessible
- Testing strategy matches component types (integration/unit)
- Plan complexity manageable or properly split
- Clear dependency ordering established
- Implementation approach is technically sound
- Resource requirements are realistic

**Next Steps**:
- If plan requires validation, proceed to Phase 1b (Plan Review & Validation)
- If plan is straightforward, proceed to Phase 2 (Iterative Implementation)
- If complexity requires splitting, create sub-plans with appropriate scope

</user>