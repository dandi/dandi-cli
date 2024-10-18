from __future__ import annotations

from enum import Enum, IntEnum, auto, unique
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dandi.utils import StrEnum


@unique
class Standard(StrEnum):
    """Standards to validate against"""

    BIDS = auto()
    DANDI_LAYOUT = "DANDI-LAYOUT"
    DANDI_SCHEMA = "DANDI-SCHEMA"
    HED = auto()
    NWB = auto()
    OME_ZARR = "OME-ZARR"
    ZARR = auto()

    # File formats (For denoting validation failures in file format level)
    JSON = auto()
    TSV = auto()
    YAML = auto()


@unique
class Validator(StrEnum):
    """Validators that are used to do validation"""

    bids_validator_deno = "bids-validator-deno"
    bidsschematools = auto()
    dandi = auto()
    dandi_zarr = "dandi.zarr"
    dandischema = auto()
    hed_python_validator = "hed-python-validator"
    nwbinspector = auto()
    pynwb = auto()
    zarr = auto()


class OriginType(StrEnum):
    """Types of validation result origins"""

    INTERNAL = auto()
    """
    Validation result is originated from the validator but not necessarily relating
    to validation of the data"""

    VALIDATION = auto()
    """Validation result is originated from validation of the data"""


class Origin(BaseModel):
    """
    Origin of the validation result
    """

    type: OriginType

    validator: Validator
    """The validator conducting the validation"""

    validator_version: str
    """The version of the validator"""

    standard: Standard | None = None
    """Standard being validated against"""

    standard_version: str | None = None
    """Version of the standard"""


class Severity(IntEnum):
    """Severity levels for validation results"""

    INFO = 10
    """Not an indication of problem but information of status or confirmation"""

    HINT = 20
    """Data is valid but could be improved"""

    WARNING = 30
    """Data is not recognized as valid. Changes are needed to ensure validity"""

    ERROR = 40
    """Data is recognized as invalid"""

    CRITICAL = 50
    """
    A serious invalidity in data.
    E.g., an invalidity that prevents validation of other aspects of the data such
    as when validating against the BIDS standard, the data is without a `BIDSVersion`
    field or has an invalid `BIDSVersion` field.
    """


class Scope(Enum):
    FILE = "file"
    FOLDER = "folder"
    DANDISET = "dandiset"
    DATASET = "dataset"


class ValidationResult(BaseModel):
    id: str

    origin: Origin
    """Origin of the validation result as validator and standard used in producing it"""

    scope: Scope

    origin_result: Any | None = Field(None, exclude=True)
    """
    The representation of the validation result produced by the used validator,
    `self.origin.validator`, unchanged
    """

    severity: Severity | None = None
    # asset_paths, if not populated, assumes [.path], but could be smth like
    # {"path": "task-broken_bold.json",
    #  "asset_paths": ["sub-01/func/sub-01_task-broken_bold.json",
    #                  "sub-02/func/sub-02_task-broken_bold.json"]}
    asset_paths: list[str] | None = None
    # e.g. path within hdf5 file hierarchy
    # As a dict we will map asset_paths into location within them
    within_asset_paths: dict[str, str] | None = None
    dandiset_path: Path | None = None
    dataset_path: Path | None = None
    # TODO: locations analogous to nwbinspector.InspectorMessage.location
    # but due to multiple possible asset_paths, we might want to have it
    # as a dict to point to location in some or each affected assets
    message: str | None = None
    metadata: dict | None = None
    # ??? should it become a list e.g. for errors which rely on
    # multiple files, like mismatch between .nii.gz header and .json sidecar
    path: Path | None = None
    path_regex: str | None = None

    @property
    def purview(self) -> str | None:
        if self.path is not None:
            return str(self.path)
        elif self.path_regex is not None:
            return self.path_regex
        elif self.dataset_path is not None:
            return str(self.dataset_path)
        else:
            return None
