import h5py
import re
import warnings
from distutils.version import LooseVersion

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
            if f in ("nwb_version",):
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
