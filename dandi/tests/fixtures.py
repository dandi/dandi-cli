from datetime import datetime
from dateutil.tz import tzutc
from subprocess import run
import shutil
import tempfile

import pynwb
from ..pynwb_utils import make_nwb_file, metadata_nwb_file_fields

import pytest

from .. import get_logger


lgr = get_logger()

# TODO: move into some common fixtures.  We might produce a number of files
#       and also carry some small ones directly in git for regression testing
@pytest.fixture(scope="session")
def simple1_nwb_metadata(tmpdir_factory):
    # very simple assignment with the same values as the key with 1 as suffix
    metadata = {f: "{}1".format(f) for f in metadata_nwb_file_fields}
    # subject_fields

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
    return make_nwb_file(
        str(tmpdir_factory.mktemp("data").join("simple1.nwb")), **simple1_nwb_metadata
    )


@pytest.fixture(scope="session")
def simple2_nwb(simple1_nwb_metadata, tmpdir_factory):
    """With a subject"""
    return make_nwb_file(
        str(tmpdir_factory.mktemp("data").join("simple2.nwb")),
        subject=pynwb.file.Subject(
            subject_id="mouse001",
            date_of_birth=datetime(2019, 12, 1),
            sex="M",
            species="mouse",
        ),
        **simple1_nwb_metadata,
    )


@pytest.fixture()
def clirunner():
    """A shortcut to get a click.runner to run a command"""
    from click.testing import CliRunner

    yield CliRunner()


def get_gitrepo_fixture(url, commitish=None, scope="session"):

    if commitish:
        raise NotImplementedError()

    @pytest.fixture(scope=scope)
    def fixture():
        # TODO: adapt reproman.tests.skip collection of skipif conditions
        # skipif.no_network()
        # skipif.no_git()

        path = tempfile.mktemp()  # not using pytest's tmpdir fixture to not
        # collide in different scopes etc. But we
        # would need to remove it ourselves
        lgr.debug("Cloning %r into %r", url, path)
        try:
            runout = run(["git", "clone", url, path])
            if runout.returncode:
                raise RuntimeError(f"Failed to clone {url} into {path}")
            yield path
        finally:
            try:
                shutil.rmtree(path)
            except BaseException as exc:
                lgr.warning("Failed to remove %s - using Windows?: %s", path, exc)

    return fixture


nwb_test_data = get_gitrepo_fixture("http://github.com/dandi-datasets/nwb_test_data")
