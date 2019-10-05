import h5py
from pynwb import NWBHDF5IO

# A list of metadata fields which dandi extracts from .nwb files.
# Additional fields (such as `number_of_*`) might be added by the
# get_metadata`
metadata_fields = (
    'experiment_description',
    'experimenter',
    'identifier',  # note: required arg2 of NWBFile
    'institution',
    'keywords',
    'lab',
    'related_publications',
    'session_description',  # note: required arg1 of NWBFile
    'session_id',
    'session_start_time',
)


def get_metadata(filepath):
    """Get selected metadata from a .nwb file

    Returns
    -------
    dict
    """
    out = dict()
    with NWBHDF5IO(filepath, 'r') as io:
        nwb = io.read()
        for key in metadata_fields:
            value = getattr(nwb, key)
            if isinstance(value, h5py.Dataset):
                # serialize into a basic container (list), since otherwise
                # it would be a closed Dataset upon return
                value = list(value)
            out[key] = value
        # .subject can be None as the test shows
        out['subject_id'] = getattr(nwb.subject, 'subject_id', None)
        # Add a few additional useful fields

        # Counts
        for f in ['electrodes', 'units']:
            out['number_of_{}'.format(f)] = len(getattr(nwb, f, []) or [])

    return out
