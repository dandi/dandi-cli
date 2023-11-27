from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar
import weakref

from dandi.consts import (
    BIDS_DATASET_DESCRIPTION,
    VIDEO_FILE_EXTENSIONS,
    ZARR_EXTENSIONS,
)
from dandi.exceptions import UnknownAssetError

from .bases import DandiFile, GenericAsset, LocalAsset, NWBAsset, VideoAsset
from .bids import (
    BIDSAsset,
    BIDSDatasetDescriptionAsset,
    GenericBIDSAsset,
    NWBBIDSAsset,
    ZarrBIDSAsset,
)
from .zarr import ZarrAsset


class DandiFileType(Enum):
    """:meta private:"""

    NWB = 1
    ZARR = 2
    VIDEO = 3
    GENERIC = 4
    BIDS_DATASET_DESCRIPTION = 5

    @staticmethod
    def classify(path: Path) -> DandiFileType:
        if path.is_dir():
            if path.suffix in ZARR_EXTENSIONS:
                if is_empty_zarr(path):
                    raise UnknownAssetError("Empty directories cannot be Zarr assets")
                return DandiFileType.ZARR
            raise UnknownAssetError(
                f"Directory has unrecognized suffix {path.suffix!r}"
            )
        elif path.name == BIDS_DATASET_DESCRIPTION:
            return DandiFileType.BIDS_DATASET_DESCRIPTION
        elif path.suffix == ".nwb":
            return DandiFileType.NWB
        elif path.suffix in VIDEO_FILE_EXTENSIONS:
            return DandiFileType.VIDEO
        else:
            return DandiFileType.GENERIC


class DandiFileFactory:
    """:meta private:"""

    CLASSES: ClassVar[Mapping[DandiFileType, type[LocalAsset]]] = {
        DandiFileType.NWB: NWBAsset,
        DandiFileType.ZARR: ZarrAsset,
        DandiFileType.VIDEO: VideoAsset,
        DandiFileType.GENERIC: GenericAsset,
        DandiFileType.BIDS_DATASET_DESCRIPTION: BIDSDatasetDescriptionAsset,
    }

    def __call__(
        self, filepath: Path, path: str, dandiset_path: Path | None
    ) -> DandiFile:
        return self.CLASSES[DandiFileType.classify(filepath)](
            filepath=filepath, path=path, dandiset_path=dandiset_path
        )


@dataclass
class BIDSFileFactory(DandiFileFactory):
    """:meta private:"""

    bids_dataset_description: BIDSDatasetDescriptionAsset

    CLASSES: ClassVar[Mapping[DandiFileType, type[BIDSAsset]]] = {
        DandiFileType.NWB: NWBBIDSAsset,
        DandiFileType.ZARR: ZarrBIDSAsset,
        DandiFileType.VIDEO: GenericBIDSAsset,
        DandiFileType.GENERIC: GenericBIDSAsset,
    }

    def __call__(
        self, filepath: Path, path: str, dandiset_path: Path | None
    ) -> DandiFile:
        ftype = DandiFileType.classify(filepath)
        if ftype is DandiFileType.BIDS_DATASET_DESCRIPTION:
            if filepath == self.bids_dataset_description.filepath:
                return self.bids_dataset_description
            else:
                ftype = DandiFileType.GENERIC
        df = self.CLASSES[ftype](
            filepath=filepath,
            path=path,
            dandiset_path=dandiset_path,
            bids_dataset_description_ref=weakref.ref(self.bids_dataset_description),
        )
        self.bids_dataset_description.dataset_files.append(df)
        return df


def is_empty_zarr(path: Path) -> bool:
    """:meta private:"""
    zf = ZarrAsset(filepath=path, path=path.name, dandiset_path=None)
    return not any(zf.iterfiles())
