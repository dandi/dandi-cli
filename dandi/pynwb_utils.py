from pynwb import NWBHDF5IO

metadata_list = ('related_publications', 'lab', 'experimenter', 'keywords', 'session_start_time',
                 'institution', 'session_description', 'session_id', 'experiment_description')


def get_metadata(filepath):
    out = dict()
    with NWBHDF5IO(filepath, 'r') as io:
        nwb = io.read()
        for key in metadata_list:
            out[key] = getattr(nwb, key)
        out['subject_id'] = nwb.subject.subject_id
        if hasattr(nwb, 'electrodes') and nwb.electrodes is not None:
            out['number_of_electrodes'] = len(nwb.electrodes)
        else:
            out['number_of_electrodes'] = 0

        if hasattr(nwb, 'units') and nwb.units is not None:
            out['number_of_units'] = len(nwb.units)
        else:
            out['number_of_units'] = 0

    return out