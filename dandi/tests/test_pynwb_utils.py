from datetime import (
    datetime,
)
from dateutil.tz import tzutc

import pytz

import pynwb

from ..pynwb_utils import (
    get_metadata,
    metadata_fields,
)

import pytest


# TODO: move into some common fixtures.  We might produce a number of files
#       and also carry some small ones directly in git for regression testing
@pytest.fixture(scope='session')
def simple1_nwb_metadata(tmpdir_factory):
    # very simple assignment with the same values as the key with 1 as suffix
    metadata = {f: "{}1".format(f) for f in metadata_fields}
    # tune specific ones:
    # Needs an explicit time zone since otherwise pynwb would add one
    # But then comparison breaks anyways any ways yoh have tried to set it
    # for datetime.now.  Taking example from pynwb tests
    metadata['session_start_time'] = datetime(2017, 4, 15, 12, tzinfo=tzutc())
    metadata['keywords'] = ['keyword1', 'keyword 2']
    return metadata


@pytest.fixture(scope='session')
def simple1_nwb(simple1_nwb_metadata, tmpdir_factory):
    filename = str(tmpdir_factory.mktemp('data').join('simple1.nwb'))
    nwbfile = pynwb.NWBFile(**simple1_nwb_metadata)
    with pynwb.NWBHDF5IO(filename, 'w') as io:
        io.write(nwbfile, cache_spec=False)
    return filename


def test_get_metadata(simple1_nwb, simple1_nwb_metadata):
    target_metadata = simple1_nwb_metadata.copy()
    # we will also get some counts
    target_metadata['number_of_electrodes'] = 0
    target_metadata['number_of_units'] = 0
    # subject_id is also nohow specified in that file yet
    target_metadata['subject_id'] = None
    assert target_metadata == get_metadata(str(simple1_nwb))


def test_pynwb_io(simple1_nwb):
    # To verify that our dependencies spec is sufficient to avoid
    # stepping into known pynwb/hdmf issues
    with pynwb.NWBHDF5IO(str(simple1_nwb), 'r', load_namespaces=True) as reader:
        nwbfile = reader.read()
    assert repr(nwbfile)
    assert str(nwbfile)
