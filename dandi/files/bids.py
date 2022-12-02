from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, List, Optional
import weakref

from dandischema.models import BareAsset

from .bases import GenericAsset, LocalFileAsset, NWBAsset
from .zarr import ZarrAsset
from ..consts import ZARR_MIME_TYPE
from ..metadata import add_common_metadata, prepare_metadata
from ..misctypes import Digest
from ..validate_types import ValidationResult

BIDS_ASSET_ERRORS = ("BIDS.NON_BIDS_PATH_PLACEHOLDER",)
BIDS_DATASET_ERRORS = ("BIDS.MANDATORY_FILE_MISSING_PLACEHOLDER",)


@dataclass
class BIDSDatasetDescriptionAsset(LocalFileAsset):
    """
    .. versionadded:: 0.46.0

    The :file:`dataset_description.json` file for a BIDS dataset, used to
    perform operations on the dataset as a whole
    """

    #: A list of all other assets in the dataset
    dataset_files: list[BIDSAsset] = field(default_factory=list)

    #: A list of validation error messages pertaining to the dataset as a
    #: whole, populated by `_validate()`
    _dataset_errors: Optional[list[ValidationResult]] = None

    #: A list of validation error messages for individual assets in the
    #: dataset, keyed by `bids_path` properties; populated by `_validate()`
    _asset_errors: Optional[dict[str, list[ValidationResult]]] = None

    #: Asset metadata (in the form of a `dict` of BareAsset fields) for
    #: individual assets in the dataset, keyed by `bids_path` properties;
    #: populated by `_validate()`
    _asset_metadata: Optional[dict[str, dict[str, Any]]] = None

    #: Version of BIDS used for the validation;
    #: populated by `_validate()`
    #: In future this might be removed and the information included in the
    #: BareAsset via dandischema.
    _bids_version: Optional[str] = None

    #: Threading lock needed in case multiple assets are validated in parallel
    #: during upload
    _lock: Lock = field(init=False, default_factory=Lock, repr=False, compare=False)

    @property
    def bids_root(self) -> Path:
        """
        The directory on the filesystem in which the BIDS dataset is located
        """
        return self.filepath.parent

    def _validate(self) -> None:
        with self._lock:
            if self._dataset_errors is None:
                # Import here to avoid circular import
                from dandi.validate import validate_bids

                bids_paths = [str(self.filepath)] + [
                    str(asset.filepath) for asset in self.dataset_files
                ]
                # This is an ad-hoc fix which should be removed once bidsschematools greater than
                # 0.6.0 is released.
                # It won't cause any trouble afterwards, but it will no longer fulfill any
                # purpose. The issue is that README* is still required and if we don't
                # include it explicitly in the listing validation will implicitly fail, even
                # if the file is present.
                readme_extensions = ["", ".md", ".rst", ".txt"]
                for ext in readme_extensions:
                    ds_root = self.filepath.parent
                    readme_candidate = ds_root / Path("README" + ext)
                    if readme_candidate.exists():
                        bids_paths += [readme_candidate]
                # end of ad-hoc fix.

                results = validate_bids(*bids_paths)
                self._dataset_errors: list[ValidationResult] = []
                self._asset_errors: dict[str, list[ValidationResult]] = defaultdict(
                    list
                )
                self._asset_metadata = defaultdict(dict)
                for result in results:
                    if result.id in BIDS_ASSET_ERRORS:
                        assert result.path
                        self._asset_errors[str(result.path)].append(result)
                    elif result.id in BIDS_DATASET_ERRORS:
                        self._dataset_errors.append(result)
                    elif result.id == "BIDS.MATCH":
                        assert result.path
                        bids_path = result.path.relative_to(self.bids_root).as_posix()
                        assert result.metadata is not None
                        self._asset_metadata[bids_path] = prepare_metadata(
                            result.metadata
                        )
                        self._bids_version = result.origin.bids_version

    def get_asset_errors(self, asset: BIDSAsset) -> list[ValidationResult]:
        """:meta private:"""
        self._validate()
        errors: list[ValidationResult] = []
        if self._dataset_errors:
            errors.extend(self._dataset_errors)
        assert self._asset_errors is not None
        errors.extend(self._asset_errors[asset.bids_path])
        return errors

    def get_asset_metadata(self, asset: BIDSAsset) -> dict[str, Any]:
        """:meta private:"""
        self._validate()
        assert self._asset_metadata is not None
        return self._asset_metadata[asset.bids_path]

    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> list[ValidationResult]:
        self._validate()
        assert self._dataset_errors is not None
        if self._asset_errors is not None:
            return self._dataset_errors + [
                i for j in self._asset_errors.values() for i in j
            ]
        else:
            return self._dataset_errors

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
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> list[ValidationResult]:
        return self.bids_dataset_description.get_asset_errors(self)

    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        metadata = self.bids_dataset_description.get_asset_metadata(self)
        start_time = end_time = datetime.now().astimezone()
        add_common_metadata(metadata, self.filepath, start_time, end_time, digest)
        metadata["path"] = self.path
        return BareAsset(**metadata)

    def get_validation_bids_version(self) -> str:
        return self.bids_dataset_description._bids_version


class NWBBIDSAsset(BIDSAsset, NWBAsset):
    """
    .. versionadded:: 0.46.0

    An NWB file in a BIDS dataset
    """

    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> list[ValidationResult]:
        return NWBAsset.get_validation_errors(
            self, schema_version, devel_debug
        ) + BIDSAsset.get_validation_errors(self)

    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        bids_metadata = BIDSAsset.get_metadata(self)
        nwb_metadata = NWBAsset.get_metadata(self, digest, ignore_errors)
        return BareAsset(
            **{**bids_metadata.dict(), **nwb_metadata.dict(exclude_none=True)}
        )


class ZarrBIDSAsset(BIDSAsset, ZarrAsset):
    """
    .. versionadded:: 0.46.0

    A Zarr directory in a BIDS dataset
    """

    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> list[ValidationResult]:
        return ZarrBIDSAsset.get_validation_errors(
            self, schema_version, devel_debug
        ) + BIDSAsset.get_validation_errors(self)

    def get_metadata(
        self,
        digest: Optional[Digest] = None,
        ignore_errors: bool = True,
    ) -> BareAsset:
        metadata = self.bids_dataset_description.get_asset_metadata(self)
        start_time = end_time = datetime.now().astimezone()
        add_common_metadata(metadata, self.filepath, start_time, end_time, digest)
        metadata["path"] = self.path
        metadata["encodingFormat"] = ZARR_MIME_TYPE
        return BareAsset(**metadata)


class GenericBIDSAsset(BIDSAsset, GenericAsset):
    """
    .. versionadded:: 0.46.0

    An asset in a BIDS dataset that is not an NWB file, a Zarr directory, or a
    :file:`dataset_description.json` file.  Note that, unlike the non-BIDS
    classes, this includes video files.
    """

    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> List[ValidationResult]:
        return GenericAsset.get_validation_errors(
            self, schema_version, devel_debug
        ) + BIDSAsset.get_validation_errors(self)
