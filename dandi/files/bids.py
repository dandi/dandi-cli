from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Optional
import weakref

from .bases import GenericAsset, LocalFileAsset, NWBAsset
from .zarr import ZarrAsset


@dataclass
class BIDSDatasetDescriptionAsset(LocalFileAsset):
    """
    The :file:`dataset_description.json` file for a BIDS dataset, used to
    perform operations on the dataset as a whole
    """

    #: A list of all other assets in the dataset
    dataset_files: list[BIDSAsset] = field(default_factory=list)

    #: A list of validation error messages pertaining to the dataset as a
    #: whole, populated by `_validate()`
    _dataset_errors: Optional[list[str]] = None

    #: A list of validation error messages for individual assets in the
    #: dataset, keyed by `bids_path` properties; populated by `_validate()`
    _asset_errors: Optional[dict[str, list[str]]] = None

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
                results = validate_bids(*bids_paths)
                self._dataset_errors: list[str] = []
                if len(results["path_listing"]) == len(results["path_tracking"]):
                    self._dataset_errors.append("No valid BIDS files were found")
                for entry in results["schema_tracking"]:
                    if entry["mandatory"]:
                        self._dataset_errors.append(
                            f"The `{entry['regex']}` regex pattern file"
                            " required by BIDS was not found."
                        )
                self._asset_errors = defaultdict(list)
                for path in results["path_tracking"]:
                    bids_path = Path(path).relative_to(self.bids_root).as_posix()
                    self._dataset_errors.append(
                        f"The `{bids_path}` file was not matched by any regex schema entry."
                    )
                    self._asset_errors[bids_path].append(
                        "File not matched by any regex schema entry"
                    )

    def get_asset_errors(self, asset: BIDSAsset) -> list[str]:
        self._validate()
        errors: list[str] = []
        if self._dataset_errors:
            errors.append("BIDS dataset is invalid")
        assert self._asset_errors is not None
        errors.extend(self._asset_errors[asset.bids_path])
        return errors

    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> list[str]:
        self._validate()
        assert self._dataset_errors is not None
        return list(self._dataset_errors)


@dataclass
class BIDSAsset(LocalFileAsset):
    """
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
    ) -> list[str]:
        return self.bids_dataset_description.get_asset_errors(self)


class NWBBIDSAsset(BIDSAsset, NWBAsset):
    """An NWB file in a BIDS dataset"""

    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> list[str]:
        return NWBAsset.get_validation_errors(
            self, schema_version, devel_debug
        ) + BIDSAsset.get_validation_errors(self)


class ZarrBIDSAsset(BIDSAsset, ZarrAsset):
    """A Zarr directory in a BIDS dataset"""

    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> list[str]:
        return ZarrBIDSAsset.get_validation_errors(
            self, schema_version, devel_debug
        ) + BIDSAsset.get_validation_errors(self)


class GenericBIDSAsset(BIDSAsset, GenericAsset):
    """
    An asset in a BIDS dataset that is not an NWB file, a Zarr directory, or a
    :file:`dataset_description.json` file.  Note that, unlike the non-BIDS
    classes, this includes video files.
    """

    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> list[str]:
        return GenericAsset.get_validation_errors(
            self, schema_version, devel_debug
        ) + BIDSAsset.get_validation_errors(self)
