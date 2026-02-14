# Test Quality Analysis & Systematic Remediation for GitHub Copilot

## Overview

This prompt is designed to work with GitHub Copilot's comment-based and function header prompting model. Unlike Claude Code's conversational interface, GitHub Copilot responds best to structured comments, descriptive function headers, and incremental code completion.

## Copilot Adaptation Strategy

### Core Differences from Claude Version:

1. **Comment-Based Prompting**: Use structured comments before code blocks instead of conversational instructions
2. **Incremental Development**: Break down complex analysis into smaller, manageable functions
3. **Function Header Driven**: Use descriptive function signatures to guide Copilot's code generation
4. **Context Provision**: Provide explicit examples and context in comments
5. **Natural Language Integration**: Leverage Copilot's natural language understanding in comments

## Implementation Approach

### Phase 1: Test Analysis Infrastructure

```python
# Create comprehensive test execution and analysis framework
# Purpose: Systematic test quality improvement for solo programmers
# Methodology: PDCA cycles with holistic pattern recognition

import subprocess
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

class TestPriority(Enum):
    """
    Test fix priority levels based on research software standards
    and solo programmer resource constraints
    """
    P1_CRITICAL = "P1_CRITICAL"  # Scientific validity, immediate fix required
    P2_HIGH = "P2_HIGH"          # System reliability, research workflow essential
    P3_MEDIUM = "P3_MEDIUM"      # Performance, integration support
    P4_LOW = "P4_LOW"            # Cosmetic, non-essential functionality

class TestFailureCategory(Enum):
    """
    Root cause taxonomy for systematic pattern recognition
    """
    INFRASTRUCTURE = "INFRASTRUCTURE"  # Imports, dependencies, environment
    API_COMPATIBILITY = "API_COMPATIBILITY"  # Method signatures, interfaces
    TEST_DESIGN = "TEST_DESIGN"       # Brittle tests, wrong expectations
    COVERAGE_GAPS = "COVERAGE_GAPS"   # Untested integration points
    CONFIGURATION = "CONFIGURATION"   # Settings, paths, service dependencies

@dataclass
class TestFailure:
    """
    Structured representation of test failure for analysis
    """
    test_name: str
    category: TestFailureCategory
    priority: TestPriority
    root_cause: str
    error_message: str
    affected_files: List[str] = field(default_factory=list)
    fix_strategy: str = ""
    fix_complexity: str = "UNKNOWN"  # SIMPLE, MODERATE, COMPLEX
    dependencies: List[str] = field(default_factory=list)  # Other fixes this depends on

def execute_test_chunk_with_timeout_prevention(test_category: str) -> Dict[str, any]:
    """
    Execute test category using proven chunking strategy to prevent timeouts
    
    Args:
        test_category: Category like 'security', 'model_registry', 'integration'
        
    Returns:
        Dict containing test results and execution metadata
        
    Example usage:
        # Test security category with comprehensive error capture
        security_results = execute_test_chunk_with_timeout_prevention('security')
    """
    # [Copilot will generate implementation based on this comment structure]
    pass

def aggregate_failure_patterns_across_categories(test_results: List[Dict]) -> Dict[TestFailureCategory, List[TestFailure]]:
    """
    Perform holistic pattern recognition across ALL test failures
    
    Instead of analyzing failures sequentially, this function aggregates
    all failures first to identify:
    - Cascading failure patterns (one root cause affects multiple tests)
    - Cross-cutting concerns (similar issues across different modules)
    - Solution interaction opportunities (single fix resolves multiple issues)
    
    Args:
        test_results: List of test execution results from all categories
        
    Returns:
        Dictionary mapping failure categories to structured failure objects
        
    Implementation approach:
        1. Extract all FAILED and ERROR entries from test outputs
        2. Classify each failure using root cause taxonomy
        3. Group failures by category and identify patterns
        4. Map interdependencies between failures
    """
    # [Copilot will implement pattern recognition logic]
    pass

def validate_test_against_industry_standards(test_failure: TestFailure) -> Dict[str, bool]:
    """
    Multi-tier validation of test justification against industry standards
    
    Validates each test failure against:
    - Research Software Standard (30-60% baseline acceptable)
    - Enterprise Standard (85-95% expectation)
    - IEEE Testing Standard (industry best practices)
    - Solo Programmer Context (resource constraints)
    
    Args:
        test_failure: Structured test failure object
        
    Returns:
        Dictionary with justification status for each standard level
        
    Example output:
        {
            'research_justified': True,
            'enterprise_justified': False,
            'ieee_justified': False,
            'solo_programmer_recommendation': 'FIX'
        }
    """
    # [Copilot will generate multi-standard validation logic]
    pass
```

### Phase 2: PDCA Implementation Functions

```python
def plan_phase_solution_optimization(failures: Dict[TestFailureCategory, List[TestFailure]]) -> Dict[str, any]:
    """
    PLAN phase: Strategic solution planning with resource optimization
    
    Performs comprehensive solution interaction analysis:
    - Identifies fixes that can be batched together (compatible)
    - Maps dependency ordering (Fix A must complete before Fix B)
    - Assesses risk levels for regression prevention
    - Optimizes resource allocation for solo programmer context
    
    Priority Matrix (Enhanced for Solo Programmer):
    - P1-CRITICAL: Scientific validity + High impact/Low effort
    - P2-HIGH: System reliability + Quick wins enabling other fixes
    - P3-MEDIUM: Performance + Moderate effort with clear value
    - P4-LOW: Cosmetic + High effort/Low value (defer or remove)
    
    Args:
        failures: Categorized and structured test failures
        
    Returns:
        Implementation plan with optimized fix sequence
    """
    # [Copilot will generate strategic planning logic]
    pass

def do_phase_systematic_implementation(implementation_plan: Dict) -> List[str]:
    """
    DO phase: Execute fixes using optimized sequence
    
    Implementation strategy:
    1. Quick wins first (high-impact/low-effort for momentum)
    2. Dependency resolution (fixes that enable other fixes)
    3. Batch compatible fixes (minimize context switching)
    4. Risk management (high-risk fixes with validation)
    
    Integrates with TodoWrite-style progress tracking for session continuity
    
    Args:
        implementation_plan: Output from plan_phase_solution_optimization
        
    Returns:
        List of completed fix descriptions for check phase validation
    """
    # [Copilot will generate systematic implementation logic]
    pass

def check_phase_comprehensive_validation(completed_fixes: List[str]) -> Dict[str, any]:
    """
    CHECK phase: Validate implementation with regression prevention
    
    Validation protocol:
    - Targeted validation for affected test categories
    - Integration validation (import testing)
    - Regression prevention for critical modules
    - Health metrics tracking (baseline vs current)
    
    Generates comparative health report:
    - Test collection success rate
    - Category-wise success rates
    - Critical system status validation
    
    Args:
        completed_fixes: List of fixes implemented in DO phase
        
    Returns:
        Comprehensive validation report with success metrics
    """
    # [Copilot will generate validation and health tracking logic]
    pass

def act_phase_decision_framework(validation_report: Dict) -> str:
    """
    ACT phase: Generate user decision prompt for next iteration
    
    Analyzes validation results and presents structured options:
    A) Continue cycles - Implement next priority fixes
    B) Adjust approach - Modify strategy based on findings  
    C) Add coverage analysis - Integrate coverage improvement
    D) Complete current level - Achieve target success threshold
    
    Provides specific metrics and recommendations for each option
    
    Args:
        validation_report: Output from check_phase_comprehensive_validation
        
    Returns:
        Formatted decision prompt string for user choice
    """
    # [Copilot will generate decision framework logic]
    pass
```

### Phase 3: Coverage Integration

```python
def integrate_coverage_analysis_with_test_quality(module_name: str) -> Dict[str, any]:
    """
    Coverage-driven test improvement using CoverUp-style methodology
    
    Links test failures to coverage gaps:
    - Identifies critical functions with <80% coverage requiring tests
    - Maps uncovered integration points to test failure patterns
    - Prioritizes test improvements by coverage impact
    
    Implementation approach:
    1. Run coverage analysis for specified module
    2. Parse coverage report for low-coverage functions
    3. Cross-reference with existing test failures
    4. Generate priority list for coverage-driven test creation
    
    Args:
        module_name: Python module to analyze (e.g., 'emuses.model_registry')
        
    Returns:
        Coverage analysis with linked test improvement recommendations
    """
    # [Copilot will generate coverage integration logic]
    pass

def generate_coverage_driven_tests(coverage_gaps: List[str], test_failures: List[TestFailure]) -> List[str]:
    """
    Generate test code for critical coverage gaps
    
    Uses iterative improvement approach:
    - Focus on critical system components with <80% coverage
    - Prioritize uncovered integration points
    - Quality over quantity - meaningful tests vs coverage padding
    
    Args:
        coverage_gaps: List of functions/methods with insufficient coverage
        test_failures: Related test failures that might be coverage-related
        
    Returns:
        List of generated test code snippets ready for implementation
    """
    # [Copilot will generate test creation logic]
    pass
```

### Phase 4: Session Management

```python
def save_session_state_for_resumption(current_pdca_cycle: int, analysis_findings: Dict) -> None:
    """
    Enhanced session state preservation for seamless resumption
    
    Saves comprehensive session state including:
    - Current PDCA cycle and phase
    - TodoWrite progress tracking
    - Analysis findings and patterns discovered
    - Critical context for next session
    
    Uses structured markdown files for human readability and tool parsing
    
    Args:
        current_pdca_cycle: Which PDCA iteration we're currently in
        analysis_findings: Key patterns and insights discovered
    """
    # [Copilot will generate session state preservation logic]
    pass

def load_session_state_and_resume() -> Dict[str, any]:
    """
    Automatic session resumption with state detection
    
    Detects current state and determines next action:
    - Checks for existing TodoWrite tasks
    - Identifies current PDCA cycle phase
    - Loads previous analysis findings
    - Determines optimal resumption point
    
    Returns:
        Session state dictionary with resumption context
    """
    # [Copilot will generate resumption logic]
    pass

def optimize_context_for_token_efficiency(session_data: Dict) -> Dict[str, any]:
    """
    Context optimization strategy for long-running sessions
    
    Implements equivalent of Claude's /compact command:
    - Identifies critical context to preserve
    - Archives resolved issues and outdated analysis
    - Maintains active analysis context
    - Saves detailed findings to permanent files
    
    Args:
        session_data: Current session context and analysis data
        
    Returns:
        Optimized context dictionary with preserved essentials
    """
    # [Copilot will generate context optimization logic]
    pass
```

## Usage Instructions for Copilot

### 1. Initial Setup
```python
# Initialize test quality improvement session
# This comment will prompt Copilot to create setup code
# Initialize comprehensive test analysis environment

test_analyzer = TestQualityAnalyzer()  # Copilot will suggest class structure
```

### 2. Pattern Recognition
```python
# Execute holistic pattern recognition across all test categories
# Aggregate failures from security, model_registry, integration, performance, tools
# Classify failures using root cause taxonomy: INFRASTRUCTURE, API_COMPATIBILITY, TEST_DESIGN, COVERAGE_GAPS, CONFIGURATION

all_failures = aggregate_failure_patterns_across_categories(test_results)
```

### 3. PDCA Cycle Execution  
```python
# PLAN: Strategic solution optimization for solo programmer context
# Prioritize fixes: P1-CRITICAL (scientific validity), P2-HIGH (system reliability), P3-MEDIUM (performance), P4-LOW (cosmetic)
# Identify solution interactions: compatible batches, dependency ordering, risk assessment

implementation_plan = plan_phase_solution_optimization(all_failures)

# DO: Execute fixes using resource-optimized sequence
# Quick wins first, dependency resolution, batch compatible fixes, risk management

completed_fixes = do_phase_systematic_implementation(implementation_plan)

# CHECK: Comprehensive validation with regression prevention
# Targeted validation, integration testing, health metrics tracking

validation_report = check_phase_comprehensive_validation(completed_fixes)

# ACT: Generate decision prompt for next iteration
# Options: Continue cycles, Adjust approach, Add coverage, Complete level

decision_prompt = act_phase_decision_framework(validation_report)
```

### 4. Session Continuity
```python
# Save session state for seamless resumption across interruptions
# Include PDCA cycle progress, analysis findings, TodoWrite state

save_session_state_for_resumption(current_cycle, findings)

# Resume from saved state in next session
# Automatic state detection and resumption point identification

session_state = load_session_state_and_resume()
```

## Key Adaptations for Copilot

1. **Structured Function Headers**: Each function has clear purpose, parameters, and return types
2. **Comment-Driven Development**: Detailed comments before code blocks guide Copilot's generation
3. **Incremental Implementation**: Complex processes broken into smaller, manageable functions
4. **Natural Language Integration**: Comments use natural language to describe implementation approaches
5. **Context Provision**: Examples and usage patterns provided in function docstrings
6. **Explicit Parameter Documentation**: Clear argument descriptions help Copilot understand intent

This framework provides the same systematic test improvement capabilities as the Claude version while adapting to GitHub Copilot's strengths in function completion and comment-based prompting.