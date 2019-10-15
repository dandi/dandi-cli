import h5py
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


def get_metadata(filepath):
    """Get selected metadata from a .nwb file

    Parameters
    ----------
    filepath: str

    Returns
    -------
    dict
    """
    out = dict()

    # First read out possibly available versions of specifications for NWB(:N)
    out["nwb_version"] = get_nwb_version(filepath)

    with NWBHDF5IO(filepath, "r") as io:
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
