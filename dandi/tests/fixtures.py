from datetime import datetime
from dateutil.tz import tzutc

import pynwb
from ..pynwb_utils import metadata_fields

import pytest

# TODO: move into some common fixtures.  We might produce a number of files
#       and also carry some small ones directly in git for regression testing
@pytest.fixture(scope="session")
def simple1_nwb_metadata(tmpdir_factory):
    # very simple assignment with the same values as the key with 1 as suffix
    metadata = {f: "{}1".format(f) for f in metadata_fields}
    # tune specific ones:
    # Needs an explicit time zone since otherwise pynwb would add one
    # But then comparison breaks anyways any ways yoh have tried to set it
    # for datetime.now.  Taking example from pynwb tests
    metadata["session_start_time"] = datetime(2017, 4, 15, 12, tzinfo=tzutc())
    metadata["keywords"] = ["keyword1", "keyword 2"]
    # since NWB 2.1.0 some fields values become "arrays" which are
    # then reloaded as tuples, so we force them being tuples here
    # See e.g. https://github.com/NeurodataWithoutBorders/pynwb/issues/1091
    for f in "related_publications", "experimenter":
        metadata[f] = (metadata[f],)
    return metadata


@pytest.fixture(scope="session")
def simple1_nwb(simple1_nwb_metadata, tmpdir_factory):
    filename = str(tmpdir_factory.mktemp("data").join("simple1.nwb"))
    nwbfile = pynwb.NWBFile(**simple1_nwb_metadata)
    with pynwb.NWBHDF5IO(filename, "w") as io:
        io.write(nwbfile, cache_spec=False)
    return filename
