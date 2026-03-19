"""Validation of DANDI datasets against schemas and standards.

This subpackage provides validation functionality for dandisets, including:
- DANDI schema validation
- BIDS standard validation
- File layout and organization validation
- Metadata completeness checking

Submodules:
- core: Main validation functions (validate, validate_bids)
- types: Data types and models (ValidationResult, Origin, Severity, etc.)
- io: JSONL read/write utilities for validation results
"""

from .core import validate, validate_bids
from .types import (
    ORIGIN_INTERNAL_DANDI,
    ORIGIN_VALIDATION_DANDI,
    ORIGIN_VALIDATION_DANDI_LAYOUT,
    ORIGIN_VALIDATION_DANDI_ZARR,
    Origin,
    OriginType,
    Scope,
    Severity,
    Severity_,
    Standard,
    ValidationResult,
    Validator,
)

__all__ = [
    "ORIGIN_INTERNAL_DANDI",
    "ORIGIN_VALIDATION_DANDI",
    "ORIGIN_VALIDATION_DANDI_LAYOUT",
    "ORIGIN_VALIDATION_DANDI_ZARR",
    "Origin",
    "OriginType",
    "Scope",
    "Severity",
    "Severity_",
    "Standard",
    "ValidationResult",
    "Validator",
    "validate",
    "validate_bids",
]
