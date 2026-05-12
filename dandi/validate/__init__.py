"""Validation of DANDI datasets against schemas and standards.

This subpackage provides validation functionality for dandisets, including:
- DANDI schema validation
- BIDS standard validation
- File layout and organization validation
- Metadata completeness checking

Private submodules:
- _core: Main validation functions (validate, validate_bids)
- _types: Data types and models (ValidationResult, Origin, Severity, etc.)
- _io: JSONL read/write utilities for validation results

Note: _core is NOT eagerly imported here to avoid circular imports
(_core → dandi.files → dandi.validate._types → dandi.validate.__init__).
Import from dandi.validate._core directly for validate/validate_bids.
"""

from ._io import (
    load_validation_jsonl,
    validation_companion_path,
    write_validation_jsonl,
)
from ._types import (
    CURRENT_RECORD_VERSION,
    ORIGIN_INTERNAL_DANDI,
    ORIGIN_VALIDATION_DANDI,
    ORIGIN_VALIDATION_DANDI_LAYOUT,
    ORIGIN_VALIDATION_DANDI_ZARR,
    MissingFileContent,
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
    "CURRENT_RECORD_VERSION",
    "MissingFileContent",
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
    "load_validation_jsonl",
    "validation_companion_path",
    "write_validation_jsonl",
]
