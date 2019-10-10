import pynwb

from ..pynwb_utils import get_metadata, metadata_subject_fields


def test_get_metadata(simple1_nwb, simple1_nwb_metadata):
    target_metadata = simple1_nwb_metadata.copy()
    # we will also get some counts
    target_metadata["number_of_electrodes"] = 0
    target_metadata["number_of_units"] = 0
    target_metadata["number_of_units"] = 0
    # we do not populate any subject fields in our simple1_nwb
    for f in metadata_subject_fields:
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
