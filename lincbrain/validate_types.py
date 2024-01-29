from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


@dataclass
class ValidationOrigin:
    name: str
    version: str
    bids_version: str | None = None


class Severity(Enum):
    HINT = 1
    WARNING = 2
    ERROR = 3


class Scope(Enum):
    FILE = "file"
    FOLDER = "folder"
    DANDISET = "dandiset"
    DATASET = "dataset"


@dataclass
class ValidationResult:
    id: str
    origin: ValidationOrigin
    scope: Scope
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
