# This file holds the models used to interface with the deno-compiled BIDS validator
# with the `--json` option. The defined entities in this file share the same names and
# structure as those defined in
# https://github.com/bids-standard/bids-validator/blob/main/src/types/validation-result.ts
# and
# https://github.com/bids-standard/bids-validator/blob/main/src/issues/datasetIssues.ts
# The only exception to that rule is that the `ValidationResult` type in the
# BIDS validator source is named `BidsValidationResult` in this file.

from __future__ import annotations

from enum import auto
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict

from dandi.utils import StrEnum


class BidsValidationResult(BaseModel):
    issues: DatasetIssues
    summary: SummaryOutput
    derivativesSummary: Optional[dict[str, BidsValidationResult]] = None

    model_config = ConfigDict(strict=True)


class DatasetIssues(BaseModel):
    issues: list[Issue]
    codeMessages: dict[str, str]

    model_config = ConfigDict(strict=True)


class Issue(BaseModel):
    code: str
    subCode: Optional[str] = None
    severity: Optional[Severity] = None
    location: Optional[str] = None
    issueMessage: Optional[str] = None
    suggestion: Optional[str] = None
    affects: Optional[list[str]] = None
    rule: Optional[str] = None
    line: Optional[int] = None
    character: Optional[int] = None

    model_config = ConfigDict(strict=True)


class Severity(StrEnum):
    warning = auto()
    error = auto()
    ignore = auto()


class SummaryOutput(BaseModel):
    sessions: list[str]
    subjects: list[str]
    subjectMetadata: list[SubjectMetadata]
    tasks: list[str]
    modalities: list[str]
    secondaryModalities: list[str]
    totalFiles: int
    size: int
    dataProcessed: bool
    pet: dict[str, Any]
    dataTypes: list[str]
    schemaVersion: str

    model_config = ConfigDict(strict=True)


class SubjectMetadata(BaseModel):
    participantId: str
    age: Union[int, Literal["89+"], None] = None
    sex: Optional[str] = None

    model_config = ConfigDict(strict=True)
