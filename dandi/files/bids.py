from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Optional
import weakref

from dandischema.models import BareAsset

from .bases import GenericAsset, LocalFileAsset, NWBAsset
from .zarr import ZarrAsset
from ..metadata import add_common_metadata, prepare_metadata
from ..misctypes import Digest

BIDS_TO_DANDI = {
    "subject": "subject_id",
    "session": "session_id",
}


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
    _dataset_errors: Optional[list[str]] = None

    #: A list of validation error messages for individual assets in the
    #: dataset, keyed by `bids_path` properties; populated by `_validate()`
    _asset_errors: Optional[dict[str, list[str]]] = None

    #: Asset metadata (in the form of a `dict` of BareAsset fields) for
    #: individual assets in the dataset, keyed by `bids_path` properties;
    #: populated by `_validate()`
    _asset_metadata: Optional[dict[str, dict[str, Any]]] = None

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
                self._asset_metadata = defaultdict(dict)
                for meta in results["match_listing"]:
                    bids_path = (
                        Path(meta.pop("path")).relative_to(self.bids_root).as_posix()
                    )
                    meta = {
                        BIDS_TO_DANDI[k]: v
                        for k, v in meta.items()
                        if k in BIDS_TO_DANDI
                    }
                    # meta["bids_schema_version"] = results["bids_schema_version"]
                    self._asset_metadata[bids_path] = prepare_metadata(meta)

    def get_asset_errors(self, asset: BIDSAsset) -> list[str]:
        """:meta private:"""
        self._validate()
        errors: list[str] = []
        if self._dataset_errors:
            errors.append("BIDS dataset is invalid")
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
    ) -> list[str]:
        self._validate()
        assert self._dataset_errors is not None
        return list(self._dataset_errors)

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
    ) -> list[str]:
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


class NWBBIDSAsset(BIDSAsset, NWBAsset):
    """
    .. versionadded:: 0.46.0

    An NWB file in a BIDS dataset
    """

    def get_validation_errors(
        self,
        schema_version: Optional[str] = None,
        devel_debug: bool = False,
    ) -> list[str]:
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
    ) -> list[str]:
        return ZarrBIDSAsset.get_validation_errors(
            self, schema_version, devel_debug
        ) + BIDSAsset.get_validation_errors(self)


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
    ) -> list[str]:
        return GenericAsset.get_validation_errors(
            self, schema_version, devel_debug
        ) + BIDSAsset.get_validation_errors(self)
