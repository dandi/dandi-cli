from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import os.path
from pathlib import Path
from threading import Lock
import weakref

from dandischema.models import BareAsset

from .bases import GenericAsset, LocalFileAsset, NWBAsset
from .zarr import ZarrAsset
from ..consts import ZARR_MIME_TYPE
from ..metadata.core import add_common_metadata, prepare_metadata
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
    _dataset_errors: list[ValidationResult] | None = None

    #: A list of validation error messages for individual assets in the
    #: dataset, keyed by `bids_path` properties; populated by `_validate()`
    _asset_errors: dict[str, list[ValidationResult]] | None = None

    #: Asset metadata for individual assets in the dataset, keyed by
    #: `bids_path` properties; populated by `_validate()`
    _asset_metadata: dict[str, BareAsset] | None = None

    #: Version of BIDS used for the validation;
    #: populated by `_validate()`
    #: In future this might be removed and the information included in the
    #: BareAsset via dandischema.
    _bids_version: str | None = None

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
                    readme_candidate = self.bids_root / Path("README" + ext)
                    if (
                        os.path.lexists(readme_candidate)
                        and str(readme_candidate) not in bids_paths
                    ):
                        bids_paths += [str(readme_candidate)]
                # end of ad-hoc fix.

                results = validate_bids(self.bids_root)
                self._dataset_errors: list[ValidationResult] = []
                self._asset_errors: dict[str, list[ValidationResult]] = defaultdict(
                    list
                )
                # Don't apply eta-reduction to the lambda, as mypy needs to be
                # assured that defaultdict's argument takes no parameters.
                self._asset_metadata = defaultdict(
                    lambda: BareAsset.model_construct()  # type: ignore[call-arg]
                )
                for result in results:
                    if result.id in BIDS_ASSET_ERRORS:
                        assert result.path
                        bids_path = result.path.relative_to(self.bids_root).as_posix()
                        self._asset_errors[bids_path].append(result)
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

    def get_asset_metadata(self, asset: BIDSAsset) -> BareAsset:
        """:meta private:"""
        self._validate()
        assert self._asset_metadata is not None
        return self._asset_metadata[asset.bids_path]

    def get_validation_errors(
        self,
        schema_version: str | None = None,
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
        schema_version: str | None = None,
        devel_debug: bool = False,
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

    def get_validation_bids_version(self) -> str:
        self.bids_dataset_description._validate()
        assert self.bids_dataset_description._bids_version is not None
        return self.bids_dataset_description._bids_version


class NWBBIDSAsset(BIDSAsset, NWBAsset):
    """
    .. versionadded:: 0.46.0

    An NWB file in a BIDS dataset
    """

    def get_validation_errors(
        self,
        schema_version: str | None = None,
        devel_debug: bool = False,
    ) -> list[ValidationResult]:
        return NWBAsset.get_validation_errors(
            self, schema_version, devel_debug
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
    ) -> list[ValidationResult]:
        return ZarrAsset.get_validation_errors(
            self, schema_version, devel_debug
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
    ) -> list[ValidationResult]:
        return GenericAsset.get_validation_errors(
            self, schema_version, devel_debug
        ) + BIDSAsset.get_validation_errors(self)
