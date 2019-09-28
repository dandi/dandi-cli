from pynwb import NWBHDF5IO


def get_metadata(filepath):
    out = dict()
    with NWBHDF5IO(filepath, 'r') as io:
        nwb = io.read()
        out['publications'] = nwb.related_publications
        out['lab'] = nwb.lab
        out['experimenters'] = nwb.experimenter
        out['keywords'] = nwb.keywords
        out['date'] = nwb.session_start_time
        out['subject_id'] = nwb.subject.subject_id
        out['institution'] = nwb.institution

    return out
