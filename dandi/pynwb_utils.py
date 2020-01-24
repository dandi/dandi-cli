import h5py
import re
import warnings
from distutils.version import LooseVersion
from collections import Counter

import pynwb
from pynwb import NWBHDF5IO

from . import get_logger

lgr = get_logger()

from .consts import metadata_fields, metadata_computed_fields, metadata_subject_fields


def get_nwb_version(filepath):
    """Return a version of the NWB standard used by a file

    Returns
    -------
    str or None
       None if there is no version detected
    """
    with h5py.File(filepath, "r") as h5file:
        # 2.x stored it as an attribute
        try:
            return h5file.attrs["nwb_version"]
        except KeyError:
            pass

        # 1.x stored it as a dataset
        try:
            return h5file["nwb_version"][...].tostring().decode()
        except:
            lgr.debug("%s has no nwb_version" % filepath)


def get_neurodata_types(filepath):
    with h5py.File(filepath, "r") as h5file:
        all_pairs = _scan_neurodata_types(h5file)

    # so far descriptions are useless so let's just output actual names only
    # with a count if there is multiple
    # return [': '.join(filter(bool, p)) for p in all_pairs]
    names = [p[0] for p in all_pairs if p[0] not in {"NWBFile"}]
    counts = Counter(names)
    out = []
    for name, count in sorted(counts.items()):
        if count > 1:
            out.append("%s (%d)" % (name, count))
        else:
            out.append(name)
    return out


def _scan_neurodata_types(grp):
    out = []
    if "neurodata_type" in grp.attrs:
        out.append((grp.attrs["neurodata_type"], grp.attrs.get("description", None)))
    for v in list(grp.values()):
        if isinstance(v, h5py._hl.group.Group):
            out += _scan_neurodata_types(v)
    return out


def get_metadata(path):
    """Get selected metadata from a .nwb file

    Parameters
    ----------
    path: str or Path

    Returns
    -------
    dict
    """
    path = str(path)  # for Path
    out = dict()

    # First read out possibly available versions of specifications for NWB(:N)
    out["nwb_version"] = get_nwb_version(path)

    # PyNWB might fail to load because of missing extensions.
    # There is a new initiative of establishing registry of such extensions.
    # Not yet sure if PyNWB is going to provide "native" support for needed
    # functionality: https://github.com/NeurodataWithoutBorders/pynwb/issues/1143
    # So meanwhile, hard-coded workaround for data types we care about
    ndtypes_registry = {"AIBS_ecephys": "allensdk.brain_observatory.ecephys.nwb"}
    while True:
        try:
            out.update(_get_pynwb_metadata(path))
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
            lgr.debug(
                "Importing %r which should provide %r", ndtypes_registry[ndtype], ndtype
            )
            __import__(ndtypes_registry[ndtype])

    return out


def _get_pynwb_metadata(path):
    out = {}
    with NWBHDF5IO(path, "r") as io:
        nwb = io.read()
        for key in metadata_fields:
            value = getattr(nwb, key)
            if isinstance(value, h5py.Dataset):
                # serialize into a basic container (list), since otherwise
                # it would be a closed Dataset upon return
                value = list(value)
            out[key] = value

        # .subject can be None as the test shows
        for subject_feature in metadata_subject_fields:
            out[subject_feature] = getattr(nwb.subject, subject_feature, None)
        # Add a few additional useful fields

        # Counts
        for f in metadata_computed_fields:
            if f in ("nwb_version", "nd_types"):
                continue
            if not f.startswith("number_of_"):
                raise NotImplementedError(
                    "ATM can only compute number_of_ fields. Got {}".format(f)
                )
            key = f[len("number_of_") :]
            out[f] = len(getattr(nwb, key, []) or [])

    return out


def validate(path):
    """Run validation on a file and return errors

    In case of an exception being thrown, an error message added to the
    returned list of validation errors

    Parameters
    ----------
    path: str or Path
    """
    path = str(path)  # Might come in as pathlib's PATH
    try:
        with pynwb.NWBHDF5IO(path, "r", load_namespaces=True) as reader:
            errors = pynwb.validate(reader)
    except Exception as exc:
        errors = [f"Failed to validate {path}: {exc}"]

    # To overcome
    #   https://github.com/NeurodataWithoutBorders/pynwb/issues/1090
    #   https://github.com/NeurodataWithoutBorders/pynwb/issues/1091
    re_ok_prior_210 = re.compile(
        "general/(experimenter|related_publications)\): "
        "incorrect shape - expected an array of shape .\[None\]."
    )
    try:
        version = get_nwb_version(path)
    except:
        # we just will not remove any errors
        pass
    else:
        if version and LooseVersion(version) < "2.1.0":
            errors_ = errors[:]
            errors = [e for e in errors if not re_ok_prior_210.search(str(e))]
            if errors != errors_:
                lgr.debug(
                    "Filtered out %d validation errors on %s",
                    len(errors_) - len(errors),
                    path,
                )
    return errors


def ignore_benign_pynwb_warnings():
    #   See https://github.com/dandi/dandi-cli/issues/14 for more info
    for s in (
        "No cached namespaces found .*",
        "ignoring namespace 'core' because it already exists",
    ):
        warnings.filterwarnings("ignore", s, UserWarning)
