import re
import pynwb

from ..pynwb_utils import metadata_nwb_subject_fields, _sanitize_nwb_version, nwbfile_to_metadata_dict
from ..metadata import get_metadata


def test_get_metadata(simple1_nwb, simple1_nwb_metadata):
    target_metadata = simple1_nwb_metadata.copy()
    # we will also get some counts
    target_metadata["number_of_electrodes"] = 0
    target_metadata["number_of_units"] = 0
    target_metadata["number_of_units"] = 0
    # We also populate with nd_types now, although here they would be empty
    target_metadata["nd_types"] = []
    # we do not populate any subject fields in our simple1_nwb
    for f in metadata_nwb_subject_fields:
        target_metadata[f] = None
    metadata = get_metadata(str(simple1_nwb))
    # we also load nwb_version field, so it must not be degenerate and ATM
    # it is 2.X.Y. And since I don't know how to query pynwb on what
    # version it currently "supports", we will just pop it
    assert metadata.pop("nwb_version").startswith("2.")
    assert target_metadata == metadata


def test_pynwb_io(simple1_nwb):
    # To verify that our dependencies spec is sufficient to avoid
    # stepping into known pynwb/hdmf issues
    with pynwb.NWBHDF5IO(str(simple1_nwb), "r", load_namespaces=True) as reader:
        nwbfile = reader.read()
    assert repr(nwbfile)
    assert str(nwbfile)


def test_sanitize_nwb_version():
    def _nocall(*args):
        raise AssertionError(f"Should have not been called. Was called with {args}")

    def assert_regex(regex):
        def search(v):
            assert re.search(regex, v)

        return search

    assert _sanitize_nwb_version("1.0.0", log=_nocall) == "1.0.0"
    assert _sanitize_nwb_version("NWB-1.0.0", log=_nocall) == "1.0.0"
    assert _sanitize_nwb_version("NWB-2.0.0", log=_nocall) == "2.0.0"
    assert (
        _sanitize_nwb_version(
            "NWB-2.1.0",
            log=assert_regex("^nwb_version 'NWB-2.1.0' starts with NWB- prefix,"),
        )
        == "2.1.0"
    )
    assert (
        _sanitize_nwb_version(
            "NWB-2.1.0",
            filename="/bu",
            log=assert_regex(
                "^File /bu: nwb_version 'NWB-2.1.0' starts with NWB- prefix,"
            ),
        )
        == "2.1.0"
    )


def test_nwbfile_to_dict(simple1_nwb):
    assert nwbfile_to_metadata_dict(simple1_nwb) == {'attributes': {'namespace': 'core', 'neurodata_type': 'NWBFile', 'nwb_version': '2.2.2', 'object_id': 'f852e236-37db-4e2b-81ef-37f22ba20bb4'}, 'datasets': {'file_create_date': {'data': '<HDF5 dataset "file_create_date": shape (1,), type "|O">'}, 'identifier': {'data': 'identifier1'}, 'session_description': {'data': 'session_description1'}, 'session_start_time': {'data': '2017-04-15T12:00:00+00:00'}, 'timestamps_reference_time': {'data': '2017-04-15T12:00:00+00:00'}}, 'groups': {'general': {'datasets': {'experiment_description': {'data': 'experiment_description1'}, 'experimenter': {'data': '<HDF5 dataset "experimenter": shape (1,), type "|O">'}, 'institution': {'data': 'institution1'}, 'keywords': {'data': '<HDF5 dataset "keywords": shape (2,), type "|O">'}, 'lab': {'data': 'lab1'}, 'related_publications': {'data': '<HDF5 dataset "related_publications": shape (1,), type "|O">'}, 'session_id': {'data': 'session_id1'}}}, 'stimulus': {'groups': {}}}}