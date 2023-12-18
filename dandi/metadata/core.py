from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from dandischema import models
from pydantic import ByteSize

from .util import extract_model, get_generator
from .. import get_logger
from ..misctypes import Digest, LocalReadableFile, Readable
from ..utils import get_mime_type, get_utcnow_datetime

lgr = get_logger()


def get_default_metadata(
    path: str | Path | Readable, digest: Digest | None = None
) -> models.BareAsset:
    metadata = models.BareAsset.model_construct()  # type: ignore[call-arg]
    start_time = end_time = datetime.now().astimezone()
    add_common_metadata(metadata, path, start_time, end_time, digest)
    return metadata


def add_common_metadata(
    metadata: models.BareAsset,
    path: str | Path | Readable,
    start_time: datetime,
    end_time: datetime,
    digest: Digest | None = None,
) -> None:
    """
    Update a `dict` of raw "schemadata" with the fields that are common to both
    NWB assets and non-NWB assets
    """
    if digest is not None:
        metadata.digest = digest.asdict()
    else:
        metadata.digest = {}
    metadata.dateModified = get_utcnow_datetime()
    if isinstance(path, Readable):
        r = path
    else:
        r = LocalReadableFile(path)
    mtime = r.get_mtime()
    if mtime is not None:
        metadata.blobDateModified = mtime
        if mtime > metadata.dateModified:
            lgr.warning("mtime %s of %s is in the future", mtime, r)
    size = r.get_size()
    if digest is not None and digest.algorithm is models.DigestType.dandi_zarr_checksum:
        m = re.fullmatch(
            r"(?P<hash>[0-9a-f]{32})-(?P<files>[0-9]+)--(?P<size>[0-9]+)", digest.value
        )
        if m:
            size = int(m["size"])
    metadata.contentSize = ByteSize(size)
    if metadata.wasGeneratedBy is None:
        metadata.wasGeneratedBy = []
    metadata.wasGeneratedBy.append(get_generator(start_time, end_time))
    metadata.encodingFormat = get_mime_type(r.get_filename())


def prepare_metadata(metadata: dict) -> models.BareAsset:
    """
    Convert "flatdata" [1]_ for an asset into "schemadata" [2]_ as a
    `BareAsset`

    .. [1] a flat `dict` mapping strings to strings & other primitive types;
       returned by `get_metadata()`

    .. [2] metadata in the form used by the ``dandischema`` library
    """
    return extract_model(models.BareAsset, metadata)
