from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import json
import os.path
from pathlib import Path
from threading import Lock
from typing import Any
import weakref

from dandischema.models import BareAsset

from dandi.bids_validator_deno import bids_validate

from .bases import GenericAsset, LocalFileAsset, NWBAsset
from .zarr import ZarrAsset
from ..consts import ZARR_MIME_TYPE, dandiset_metadata_file
from ..metadata.core import add_common_metadata, prepare_metadata
from ..misctypes import Digest
from ..validate._types import (
    ORIGIN_VALIDATION_DANDI_LAYOUT,
    MissingFileContent,
    Scope,
    Severity,
    Standard,
    ValidationResult,
)

BIDS_ASSET_ERRORS = ("BIDS.NON_BIDS_PATH_PLACEHOLDER",)
BIDS_DATASET_ERRORS = ("BIDS.MANDATORY_FILE_MISSING_PLACEHOLDER",)


def _load_dataset_description(filepath: Path) -> dict[str, Any] | None:
    """
    Return the content of a :file:`dataset_description.json` file, or `None` if
    it cannot be read or is not a JSON object
    """
    try:
        content = json.loads(filepath.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return content if isinstance(content, dict) else None


def is_bids_dataset_description(filepath: Path) -> bool:
    """
    Whether there is a :file:`dataset_description.json` file at ``filepath``
    marking a BIDS dataset

    It does, unless it is a JSON object without a ``"BIDSVersion"`` field.  A
    file that cannot be read or parsed (e.g., a broken symlink or invalid JSON)
    still marks a, likely invalid, BIDS dataset, so that the BIDS validator gets
    to report on it.
    """
    if not os.path.lexists(filepath):
        return False
    content = _load_dataset_description(filepath)
    return content is None or "BIDSVersion" in content


@dataclass
class BIDSDatasetDescriptionAsset(LocalFileAsset):
    """
    .. versionadded:: 0.46.0

    The :file:`dataset_description.json` file for a BIDS dataset, used to
    perform operations on the dataset as a whole
    """

    #: A list of all other assets in the dataset
    dataset_files: list[BIDSAsset] = field(default_factory=list)

    #: A list of all the validation results pertaining to the containing dataset
    #: as a BIDS dataset populated by `_validate()`
    _dataset_errors: list[ValidationResult] | None = None

    #: A list of validation error messages for individual assets in the
    #: dataset, keyed by `bids_path` properties; populated by `_validate()`
    _asset_errors: defaultdict[str, list[ValidationResult]] | None = None

    #: Asset metadata for individual assets in the dataset, keyed by
    #: `bids_path` properties; populated by `_get_metadata()`
    _asset_metadata: defaultdict[str, BareAsset] | None = None

    #: Version of BIDS used in the validation, as given in the validation results
    #: (not necessarily the same as the value of the `"BIDSVersion"` field in the
    #: represented `dataset_description.json` file);
    #: populated by `_validate()`
    #: In future this might be removed and the information included in the
    #: BareAsset via dandischema.
    _validation_bids_version: str | None = None

    #: Threading lock needed in case multiple assets are validated in parallel
    #: during upload
    _lock: Lock = field(init=False, default_factory=Lock, repr=False, compare=False)

    @property
    def bids_root(self) -> Path:
        """
        The directory on the filesystem in which the BIDS dataset is located
        """
        return self.filepath.parent

    @property
    def bids_version(self) -> str | None:
        """
        The version of BIDS the dataset declares, i.e., the value of the
        ``"BIDSVersion"`` field in the represented :file:`dataset_description.json`
        file; `None` if the file cannot be read or the field is missing, empty, or
        not a string

        Note
        ----
            This value is not necessarily the version of BIDS used in validation;
            see `get_validation_bids_version()`.
        """
        content = _load_dataset_description(self.filepath) or {}
        v = content.get("BIDSVersion")
        return v if isinstance(v, str) and v else None

    def get_validation_bids_version(self) -> str | None:
        """
        The version of BIDS used in validation of the dataset

        The validator reports only the version of the BIDS schema it used, so the
        version of BIDS is looked up for it; see
        https://github.com/bids-standard/bids-validator/issues/10.  If that fails,
        or the validation produced no results to take it from, `bids_version`, the
        version the dataset declares, is assumed.
        """
        self._validate()
        return self._validation_bids_version or self.bids_version

    def _get_metadata(self) -> None:
        """
        Get metadata for all assets in the dataset

        This populates `self._asset_metadata`
        """
        with self._lock:
            if self._asset_metadata is None:
                # Import here to avoid circular import
                from dandi.validate._core import validate_bids

                # === Validate the dataset using bidsschematools ===
                #   This is done to obtain the metadata for each asset in the dataset
                results = validate_bids(self.bids_root)
                # Don't apply eta-reduction to the lambda, as mypy needs to be
                # assured that defaultdict's argument takes no parameters.
                self._asset_metadata = defaultdict(
                    lambda: BareAsset.model_construct()  # type: ignore[call-arg]
                )
                for result in results:
                    if result.id == "BIDS.MATCH":
                        assert result.path
                        bids_path = result.path.relative_to(self.bids_root).as_posix()
                        assert result.metadata is not None
                        self._asset_metadata[bids_path] = prepare_metadata(
                            result.metadata
                        )

    def _validate(self) -> None:
        with self._lock:
            if self._dataset_errors is None:

                # Obtain BIDS validation results of the entire dataset through the
                # deno-compiled BIDS validator
                v_results = bids_validate(self.bids_root)

                # Validation results from the deno BIDS validator with an additional
                # hint, represented as a `ValidationResult` object, following
                # each `dandiset.yaml` error, suggesting to add the `dandiset.yaml` file
                # to `.bidsignore`.
                v_results_extended: list[ValidationResult] = []

                for result in v_results:
                    v_results_extended.append(result)
                    if (
                        result.path is not None
                        and result.dataset_path is not None
                        and result.path.relative_to(result.dataset_path).as_posix()
                        == dandiset_metadata_file
                    ):
                        hint = ValidationResult(
                            id="DANDI.BIDSIGNORE_DANDISET_YAML",
                            origin=ORIGIN_VALIDATION_DANDI_LAYOUT,
                            scope=Scope.DATASET,
                            origin_result=result,
                            severity=Severity.HINT,
                            dandiset_path=result.dandiset_path,
                            dataset_path=result.dataset_path,
                            path=result.path,
                            message=(
                                f"Consider creating or updating a `.bidsignore` file "
                                f"in the root of your BIDS dataset to ignore "
                                f"`{dandiset_metadata_file}`. "
                                f"Add the following line to `.bidsignore`:\n"
                                f"{dandiset_metadata_file}"
                            ),
                        )
                        v_results_extended.append(hint)

                self._dataset_errors = v_results_extended

                # Categorized validation results related to individual assets by the
                # path of the asset in the BIDS dataset
                self._asset_errors = defaultdict(list)
                for result in self._dataset_errors:
                    if result.path is not None:
                        self._asset_errors[
                            result.path.relative_to(self.bids_root).as_posix()
                        ].append(result)

                # Obtain BIDS standard version from the validation results
                self._validation_bids_version = next(
                    (
                        r.origin.standard_version
                        for r in v_results
                        if r.origin.standard is Standard.BIDS
                        and r.origin.standard_version
                    ),
                    None,
                )

    def get_asset_errors(self, asset: BIDSAsset) -> list[ValidationResult]:
        """:meta private:"""
        self._validate()
        assert self._asset_errors is not None
        return self._asset_errors[asset.bids_path].copy()

    def get_asset_metadata(self, asset: BIDSAsset) -> BareAsset:
        """:meta private:"""
        self._get_metadata()
        assert self._asset_metadata is not None
        return self._asset_metadata[asset.bids_path]

    def get_validation_errors(
        self,
        schema_version: str | None = None,
        devel_debug: bool = False,
        missing_file_content: MissingFileContent | None = None,
    ) -> list[ValidationResult]:
        """
        Return all validation results for the containing dataset per the BIDS standard
        """
        self._validate()
        assert self._dataset_errors is not None
        return self._dataset_errors.copy()

    # get_metadata(): inherit use of default metadata from LocalFileAsset


@dataclass
class BIDSAsset(LocalFileAsset):
    """
    .. versionadded:: 0.46.0

    Base class for non-:file:`dataset_description.json` assets in BIDS datasets
    """

    #: A weak reference to the :file:`dataset_description.json` file for the
    #: containing dataset.
    #:
    #: Users are advised to use `bids_dataset_description` to access the
    #: :file:`dataset_description.json` file instead.
    bids_dataset_description_ref: weakref.ref[BIDSDatasetDescriptionAsset]

    @property
    def bids_dataset_description(self) -> BIDSDatasetDescriptionAsset:
        """
        The :file:`dataset_description.json` file for the containing dataset
        """
        bdd = self.bids_dataset_description_ref()
        assert bdd is not None
        return bdd

    @property
    def bids_root(self) -> Path:
        """
        The directory on the filesystem in which the BIDS dataset is located
        """
        return self.bids_dataset_description.bids_root

    @property
    def bids_path(self) -> str:
        """
        ``/``-separated path to the asset from the root of the BIDS dataset
        """
        return self.filepath.relative_to(self.bids_root).as_posix()

    def get_validation_errors(
        self,
        schema_version: str | None = None,
        devel_debug: bool = False,
        missing_file_content: MissingFileContent | None = None,
    ) -> list[ValidationResult]:
        return self.bids_dataset_description.get_asset_errors(self)

    def get_metadata(
        self,
        digest: Digest | None = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        metadata = self.bids_dataset_description.get_asset_metadata(self)
        start_time = end_time = datetime.now().astimezone()
        add_common_metadata(metadata, self.filepath, start_time, end_time, digest)
        metadata.path = self.path
        return metadata

    def get_validation_bids_version(self) -> str | None:
        return self.bids_dataset_description.get_validation_bids_version()


class NWBBIDSAsset(BIDSAsset, NWBAsset):
    """
    .. versionadded:: 0.46.0

    An NWB file in a BIDS dataset
    """

    def get_validation_errors(
        self,
        schema_version: str | None = None,
        devel_debug: bool = False,
        missing_file_content: MissingFileContent | None = None,
    ) -> list[ValidationResult]:
        return NWBAsset.get_validation_errors(
            self,
            schema_version,
            devel_debug,
            missing_file_content=missing_file_content,
        ) + BIDSAsset.get_validation_errors(self)

    def get_metadata(
        self,
        digest: Digest | None = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        bids_metadata = BIDSAsset.get_metadata(self, digest, ignore_errors)
        nwb_metadata = NWBAsset.get_metadata(self, digest, ignore_errors)
        return BareAsset(
            **{
                **bids_metadata.model_dump(),
                **nwb_metadata.model_dump(exclude_none=True),
            }
        )


class ZarrBIDSAsset(ZarrAsset, BIDSAsset):
    """
    .. versionadded:: 0.46.0

    A Zarr directory in a BIDS dataset
    """

    def get_validation_errors(
        self,
        schema_version: str | None = None,
        devel_debug: bool = False,
        missing_file_content: MissingFileContent | None = None,
    ) -> list[ValidationResult]:
        return ZarrAsset.get_validation_errors(
            self,
            schema_version,
            devel_debug,
            missing_file_content=missing_file_content,
        ) + BIDSAsset.get_validation_errors(self)

    def get_metadata(
        self,
        digest: Digest | None = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        metadata = self.bids_dataset_description.get_asset_metadata(self)
        start_time = end_time = datetime.now().astimezone()
        add_common_metadata(metadata, self.filepath, start_time, end_time, digest)
        metadata.path = self.path
        metadata.encodingFormat = ZARR_MIME_TYPE
        return metadata


class GenericBIDSAsset(BIDSAsset, GenericAsset):
    """
    .. versionadded:: 0.46.0

    An asset in a BIDS dataset that is not an NWB file, a Zarr directory, or a
    :file:`dataset_description.json` file.  Note that, unlike the non-BIDS
    classes, this includes video files.
    """

    def get_validation_errors(
        self,
        schema_version: str | None = None,
        devel_debug: bool = False,
        missing_file_content: MissingFileContent | None = None,
    ) -> list[ValidationResult]:
        return GenericAsset.get_validation_errors(
            self,
            schema_version,
            devel_debug,
            missing_file_content=missing_file_content,
        ) + BIDSAsset.get_validation_errors(self)
