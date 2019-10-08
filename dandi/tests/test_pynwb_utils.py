import pynwb

from ..pynwb_utils import get_metadata


def test_get_metadata(simple1_nwb, simple1_nwb_metadata):
    target_metadata = simple1_nwb_metadata.copy()
    # we will also get some counts
    target_metadata["number_of_electrodes"] = 0
    target_metadata["number_of_units"] = 0
    # subject_id is also nohow specified in that file yet
    target_metadata["subject_id"] = None
    assert target_metadata == get_metadata(str(simple1_nwb))


def test_pynwb_io(simple1_nwb):
    # To verify that our dependencies spec is sufficient to avoid
    # stepping into known pynwb/hdmf issues
    with pynwb.NWBHDF5IO(str(simple1_nwb), "r", load_namespaces=True) as reader:
        nwbfile = reader.read()
    assert repr(nwbfile)
    assert str(nwbfile)
