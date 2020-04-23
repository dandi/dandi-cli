import os.path as op
from .pynwb_utils import (
    _get_pynwb_metadata,
    get_neurodata_types,
    get_nwb_version,
    ignore_benign_pynwb_warnings,
    metadata_cache,
)
import numpy as np
from hdmf.build import GroupBuilder, DatasetBuilder
from pynwb import NWBHDF5IO
from h5py import File
import json

from . import get_logger
from .dandiset import Dandiset

lgr = get_logger()


@metadata_cache.memoize_path
def get_metadata(path):
    """Get selected metadata from a .nwb file or a dandiset directory

    If a directory given and it is not a Dandiset, None is returned

    Parameters
    ----------
    path: str or Path

    Returns
    -------
    dict
    """
    # when we run in parallel, these annoying warnings appear
    ignore_benign_pynwb_warnings()
    path = str(path)  # for Path
    meta = dict()

    if op.isdir(path):
        try:
            dandiset = Dandiset(path)
            return dandiset.metadata
        except ValueError as exc:
            lgr.debug("Failed to get metadata for %s: %s", path, exc)
            return None

    # First read out possibly available versions of specifications for NWB(:N)
    meta["nwb_version"] = get_nwb_version(path)

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
            meta.update(_get_pynwb_metadata(path))
            break
        except KeyError as exc:  # ATM there is
            lgr.debug("Failed to read %s: %s", path, exc)
            import re

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

    meta["nd_types"] = get_neurodata_types(path)

    return meta


def nwb_to_json(fpath, out_fpath):
    io = NWBHDF5IO(fpath, 'r')
    file = File(fpath)
    io.read()
    root_builder = io.get_builder(file['general']).parent
    out_dict = group_builder_to_json(root_builder)
    return json.dump(out_dict, out_fpath)


def print_dataset(dataset):
    return str(dataset)  # may want to change


def dataset_builder_to_json(dataset_builder):
    if isinstance(dataset_builder, GroupBuilder):
        return dataset_builder.path
    out = dict(data=print_dataset(dataset_builder['data']))

    if dataset_builder.attributes:
        out.update(
            attributes={key: attribute_to_json(val)
                        for key, val in dataset_builder.attributes.items()}
        )
    return out


def attribute_to_json(attribute):
    if isinstance(attribute, np.ndarray):
        return str(attribute.tolist())
    elif isinstance(attribute, (GroupBuilder, DatasetBuilder)):
        return attribute.path  # This is for links. May want to change
    else:
        return str(attribute)


def group_builder_to_json(group_builder):
    out = dict()
    if group_builder.attributes:
        out.update(
            attributes={key: attribute_to_json(val)
                        for key, val in group_builder.attributes.items()}
        )

    if group_builder.datasets:
        out.update(
            datasets={key: dataset_builder_to_json(val)
                      for key, val in group_builder.datasets.items()}
        )

    if group_builder.groups:
        out.update(
            groups={key: group_builder_to_json(val)
                    for key, val in group_builder.groups.items()
                    if group_builder_to_json(val)}
        )

    return out
