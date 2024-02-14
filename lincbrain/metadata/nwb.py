from __future__ import annotations

from datetime import datetime
import os.path
from pathlib import Path
import re
from typing import Any

from dandischema import models

from .core import add_common_metadata, prepare_metadata
from .util import process_ndtypes
from .. import get_logger
from ..consts import metadata_all_fields
from ..files import bids, dandi_file, find_bids_dataset_description
from ..misctypes import DUMMY_DANDI_ETAG, Digest, LocalReadableFile, Readable
from ..pynwb_utils import (
    _get_pynwb_metadata,
    get_neurodata_types,
    get_nwb_version,
    ignore_benign_pynwb_warnings,
    metadata_cache,
    nwb_has_external_links,
)
from ..utils import find_parent_directory_containing

lgr = get_logger()


# Disable this for clean hacking
@metadata_cache.memoize_path
def get_metadata(
    path: str | Path | Readable, digest: Digest | None = None
) -> dict | None:
    """
    Get "flatdata" from a .nwb file

    Parameters
    ----------
    path: str, Path, or Readable

    Returns
    -------
    dict
    """

    # when we run in parallel, these annoying warnings appear
    ignore_benign_pynwb_warnings()

    if isinstance(path, Readable):
        r = path
    else:
        r = LocalReadableFile(os.path.abspath(path))

    meta: dict[str, Any] = {}

    if isinstance(r, LocalReadableFile):
        # Is the data BIDS (as defined by the presence of a BIDS dataset descriptor)
        bids_dataset_description = find_bids_dataset_description(r.filepath)
        if bids_dataset_description:
            dandiset_path = find_parent_directory_containing(
                "dandiset.yaml", r.filepath
            )
            df = dandi_file(
                r.filepath,
                dandiset_path,
                bids_dataset_description=bids_dataset_description,
            )
            assert isinstance(df, bids.BIDSAsset)
            if not digest:
                digest = DUMMY_DANDI_ETAG
            path_metadata = df.get_metadata(digest=digest)
            meta["bids_version"] = df.get_validation_bids_version()
            # there might be a more elegant way to do this:
            if path_metadata.wasAttributedTo is not None:
                attributed = path_metadata.wasAttributedTo[0]
                for key in metadata_all_fields:
                    try:
                        value = getattr(attributed, key)
                    except AttributeError:
                        pass
                    else:
                        meta[key] = value

    if r.get_filename().endswith((".NWB", ".nwb")):
        if nwb_has_external_links(r):
            raise NotImplementedError(
                f"NWB files with external links are not supported: {r}"
            )

        # First read out possibly available versions of specifications for NWB(:N)
        meta["nwb_version"] = get_nwb_version(r)

        # PyNWB might fail to load because of missing extensions.
        # There is a new initiative of establishing registry of such extensions.
        # Not yet sure if PyNWB is going to provide "native" support for needed
        # functionality: https://github.com/NeurodataWithoutBorders/pynwb/issues/1143
        # So meanwhile, hard-coded workaround for data types we care about
        ndtypes_registry = {
            "AIBS_ecephys": "allensdk.brain_observatory.ecephys.nwb",
            "ndx-labmetadata-abf": "ndx_dandi_icephys",
        }
        tried_imports = set()
        while True:
            try:
                meta.update(_get_pynwb_metadata(r))
                break
            except KeyError as exc:  # ATM there is
                lgr.debug("Failed to read %s: %s", r, exc)
                res = re.match(r"^['\"\\]+(\S+). not a namespace", str(exc))
                if not res:
                    raise
                ndtype = res.groups()[0]
                if ndtype not in ndtypes_registry:
                    raise ValueError(
                        "We do not know which extension provides %s. "
                        "Original exception was: %s. " % (ndtype, exc)
                    )
                import_mod = ndtypes_registry[ndtype]
                lgr.debug("Importing %r which should provide %r", import_mod, ndtype)
                if import_mod in tried_imports:
                    raise RuntimeError(
                        "We already tried importing %s to provide %s, but it seems it didn't help"
                        % (import_mod, ndtype)
                    )
                tried_imports.add(import_mod)
                __import__(import_mod)

        meta["nd_types"] = get_neurodata_types(r)
    if not meta:
        raise RuntimeError(
            f"Unable to get metadata from non-BIDS, non-NWB asset: `{path}`."
        )
    return meta


def nwb2asset(
    nwb_path: str | Path | Readable,
    digest: Digest | None = None,
    schema_version: str | None = None,
) -> models.BareAsset:
    if schema_version is not None:
        current_version = models.get_schema_version()
        if schema_version != current_version:
            raise ValueError(
                f"Unsupported schema version: {schema_version}; expected {current_version}"
            )
    start_time = datetime.now().astimezone()
    metadata = get_metadata(nwb_path)
    asset_md = prepare_metadata(metadata)
    process_ndtypes(asset_md, metadata["nd_types"])
    end_time = datetime.now().astimezone()
    add_common_metadata(asset_md, nwb_path, start_time, end_time, digest)
    asset_md.encodingFormat = "application/x-nwb"
    # This gets overwritten with a better value by the caller:
    if isinstance(nwb_path, Readable):
        asset_md.path = nwb_path.get_filename()
    else:
        asset_md.path = str(nwb_path)
    return asset_md
