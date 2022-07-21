from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
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

    @property
    def bids_root(self) -> Path:
        """
        The directory on the filesystem in which the BIDS dataset is located
        """
        return self.filepath.parent


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


class NWBBIDSAsset(BIDSAsset, NWBAsset):
    """An NWB file in a BIDS dataset"""

    pass


class ZarrBIDSAsset(BIDSAsset, ZarrAsset):
    """A Zarr directory in a BIDS dataset"""

    pass


class GenericBIDSAsset(BIDSAsset, GenericAsset):
    """
    An asset in a BIDS dataset that is not an NWB file, a Zarr directory, or a
    :file:`dataset_description.json` file.  Note that, unlike the non-BIDS
    classes, this includes video files.
    """

    pass
