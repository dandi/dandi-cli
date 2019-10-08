import h5py
from pynwb import NWBHDF5IO

from . import get_logger

lgr = get_logger()

# A list of metadata fields which dandi extracts from .nwb files.
# Additional fields (such as `number_of_*`) might be added by the
# get_metadata`
metadata_fields = (
    "experiment_description",
    "experimenter",
    "identifier",  # note: required arg2 of NWBFile
    "institution",
    "keywords",
    "lab",
    "related_publications",
    "session_description",  # note: required arg1 of NWBFile
    "session_id",
    "session_start_time",
)


def get_nwb_version(filepath):
    """Return a version of the NWB standard used by a file

    Returns
    -------
    str or None
       None if there is no version detected
    """
    with h5py.File(filepath, "r") as h5file:
        try:
            return h5file["nwb_version"][...].tostring().decode()
        except KeyError:
            lgr.debug("%s has no nwb_version" % filepath)


def get_metadata(filepath):
    """Get selected metadata from a .nwb file

    Parameters
    ----------
    filepath: str
    query_nwb_version: bool, optional
      Either to query/include nwb_version field

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
        for subject_feature in (
            "subject_id",
            "genotype",
            "sex",
            "species",
            "date_of_birth",
            "age",
        ):
            out[subject_feature] = getattr(nwb.subject, subject_feature, None)
        # Add a few additional useful fields

        # Counts
        for f in ["electrodes", "units"]:
            out["number_of_{}".format(f)] = len(getattr(nwb, f, []) or [])

    return out
