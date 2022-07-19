from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import weakref

from .bases import GenericAsset, LocalFileAsset, NWBAsset
from .zarr import ZarrAsset


@dataclass
class BIDSDatasetDescriptionAsset(LocalFileAsset):
    dataset_files: list[BIDSAsset] = field(default_factory=list)


@dataclass
class BIDSAsset(LocalFileAsset):
    bids_dataset_description_ref: weakref.ref[BIDSDatasetDescriptionAsset]

    @property
    def bids_dataset_description(self) -> BIDSDatasetDescriptionAsset:
        bdd = self.bids_dataset_description_ref()
        assert bdd is not None
        return bdd

    @property
    def bids_root(self) -> Path:
        return self.bids_dataset_description.filepath.parent

    @property
    def bids_path(self) -> str:
        """
        ``/``-separated path to the asset from the root of the BIDS dataset
        """
        return self.filepath.relative_to(self.bids_root).as_posix()


class NWBBIDSAsset(BIDSAsset, NWBAsset):
    pass


class ZarrBIDSAsset(BIDSAsset, ZarrAsset):
    pass


class GenericBIDSAsset(BIDSAsset, GenericAsset):
    pass
