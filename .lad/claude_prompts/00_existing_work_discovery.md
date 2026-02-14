# Phase 0: Existing Work Discovery and Integration Assessment

## Purpose
Prevent duplicate implementations by discovering and assessing existing functionality before starting new development. This phase ensures architectural coherence and optimal resource utilization.

## Note-Taking Protocol for Architecture Discovery
For complex codebases requiring systematic architectural analysis, create working notes to maintain comprehensive understanding:
- **Discovery Notes**: `notes/discovery_{{feature}}.md` - Track search patterns, findings, and architectural insights
- **Architecture Map**: `notes/architecture_{{feature}}.md` - Document component relationships, dependencies, and integration points
- **Integration Analysis**: `notes/integration_{{feature}}.md` - Assess compatibility, conflicts, and enhancement opportunities

## Discovery Requirements

### 1. Codebase Scan
Search for existing implementations related to the requested feature:
- Use comprehensive search patterns (keywords, functionality, similar concepts)
- Examine API endpoints, services, modules, and utilities
- Check test files for functionality hints
- Review documentation for existing capabilities

### 2. Architecture Mapping
**Create systematic architecture notes for complex systems:**

```markdown  
**CREATE ARCHITECTURE NOTES**: `notes/architecture_{{feature}}.md`

## Component Inventory
- **Services**: [List discovered services and their roles]
- **Data Models**: [Key models, schemas, and relationships]  
- **APIs/Endpoints**: [Existing interfaces and contracts]
- **Utilities**: [Shared libraries and helper functions]

## Integration Landscape
- **Dependencies**: [What existing components depend on]
- **Dependents**: [What depends on existing components]
- **Data Flow**: [How information moves through the system]
- **Communication Patterns**: [Sync/async, events, direct calls]

## Architectural Patterns  
- **Design Patterns**: [MVC, Repository, Factory, etc. in use]
- **Data Patterns**: [Database access, caching, validation]
- **Security Patterns**: [Auth, authorization, data protection]
- **Integration Patterns**: [API design, service communication]
```

**Then systematically identify current system components:**
- Map existing services and their responsibilities
- Identify data models and schemas
- Document integration points and dependencies
- Assess current architectural patterns

### 3. Capability Assessment
Evaluate what already exists vs. what's needed:
- Compare existing functionality to new requirements
- Assess code quality, test coverage, and production readiness
- Identify gaps between current and required capabilities
- Document technical debt and improvement opportunities

### 4. Integration Decision
Decide whether to integrate, enhance, or build new:
- Apply Integration Decision Matrix (below)
- Consider long-term maintainability
- Evaluate impact on existing systems
- Plan deprecation strategy if needed

## Discovery Checklist
- [ ] **Keyword Search**: Search codebase for feature-related terms
- [ ] **API Analysis**: Review existing endpoints and services
- [ ] **Model Review**: Check data models and database schemas
- [ ] **Test Examination**: Analyze test files for functionality insights
- [ ] **Documentation Review**: Check README, API docs, and comments
- [ ] **Dependency Mapping**: Identify related components and libraries
- [ ] **Quality Assessment**: Evaluate code quality and test coverage
- [ ] **Integration Points**: Map how components connect
- [ ] **Performance Analysis**: Assess scalability and performance characteristics
- [ ] **Security Review**: Check authentication, authorization, and security patterns

## Integration Decision Matrix

| Existing Implementation Quality | Coverage of Requirements | Recommended Action | Justification |
|--------------------------------|-------------------------|-------------------|---------------|
| Production-ready, well-tested | 80%+ coverage | **INTEGRATE/ENHANCE** | Avoid duplication, build on solid foundation |
| Production-ready, well-tested | 50-80% coverage | **ENHANCE** | Extend existing with missing functionality |
| Production-ready, well-tested | <50% coverage | **ASSESS → ENHANCE or NEW** | Evaluate cost/benefit of extension vs. new |
| Prototype/incomplete | 80%+ coverage | **ENHANCE** | Complete and productionize existing work |
| Prototype/incomplete | 50-80% coverage | **ASSESS → ENHANCE or REBUILD** | Case-by-case evaluation based on architecture fit |
| Prototype/incomplete | <50% coverage | **BUILD NEW** | Start fresh with lessons learned |
| Poor quality/untested | Any coverage | **REBUILD** | Don't build on unstable foundation |
| No existing implementation | N/A | **BUILD NEW** | Justified new development |
| Conflicts with requirements | Any coverage | **BUILD NEW + DEPRECATION PLAN** | Document migration path |

## Assessment Report Template

### Existing Work Summary
- **Components Found**: [List relevant components]
- **Quality Level**: [Production/Development/Prototype/Poor]
- **Test Coverage**: [Percentage and quality]
- **Documentation Level**: [Complete/Partial/Missing]

### Requirements Mapping
- **Requirements Covered**: [List covered requirements]
- **Requirements Missing**: [List gaps]
- **Coverage Percentage**: [Overall coverage estimate]

### Architecture Compatibility
- **Integration Points**: [How new feature connects]
- **Dependencies**: [Required libraries/services]
- **Conflicts**: [Potential architectural issues]
- **Migration Needs**: [If replacing existing code]

### Decision and Rationale
- **Chosen Strategy**: [Integrate/Enhance/New]
- **Primary Reasons**: [Why this approach]
- **Risk Assessment**: [Implementation risks]
- **Success Metrics**: [How to measure success]

## Next Phase Preparation
Based on the discovery results:
1. **If INTEGRATE/ENHANCE**: Focus context planning on extension points
2. **If BUILD NEW**: Plan for coexistence and eventual migration
3. **If REBUILD**: Plan deprecation strategy and migration path

## Deliverables for Context Planning Phase
1. **Existing Work Assessment Report** - Save to `docs/{{FEATURE_SLUG}}/existing_work_assessment.md`
2. **Integration Strategy Decision** - Save to `docs/{{FEATURE_SLUG}}/integration_strategy.md` 
3. **Architecture Impact Analysis** - Save to `docs/{{FEATURE_SLUG}}/architecture_analysis.md`
4. **Implementation Approach** - Save to `docs/{{FEATURE_SLUG}}/implementation_approach.md`
5. **Component Baseline Summary** - Save to `docs/{{FEATURE_SLUG}}/component_baseline.md` (existing components that will be used or extended)

### Component Baseline Format
Document existing components that are relevant to the new feature:

```markdown
## Existing Components to Integrate With

### Code Components
- **Module/Class**: `module.ClassName` (location: `path/file.py:line`)
  - **Relevant functionality**: Description of what it does
  - **Integration approach**: How new feature will use/extend it
  - **Dependencies**: What it depends on

### Data Structures
- **Data Model**: `ModelName` (location: `path/models.py`)
  - **Schema/Format**: Key fields and their types
  - **Usage patterns**: How it's currently used
  - **Extension needs**: What might need to be added

### Infrastructure
- **Service/Tool**: `ServiceName` 
  - **Current usage**: How it's used in the system
  - **Integration points**: Where new feature connects
  - **Configuration**: Relevant settings or setup
```

---
*This phase must be completed before proceeding to Phase 1: Autonomous Context Planning*