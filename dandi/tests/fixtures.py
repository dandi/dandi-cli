from datetime import datetime
import os
from pathlib import Path
from subprocess import run
import shutil
import tempfile

from dateutil.tz import tzutc
import pynwb
import pytest
import requests

from .skip import skipif
from .. import get_logger
from ..cli.command import organize
from ..consts import dandiset_metadata_file, known_instances
from ..pynwb_utils import make_nwb_file, metadata_nwb_file_fields


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
            date_of_birth=datetime(2019, 12, 1, tzinfo=tzutc()),
            sex="M",
            species="mouse",
        ),
        **simple1_nwb_metadata,
    )


@pytest.fixture(scope="session")
def organized_nwb_dir(simple2_nwb, tmp_path_factory, clirunner):
    tmp_path = tmp_path_factory.mktemp("dandiset")
    (tmp_path / dandiset_metadata_file).write_text("{}\n")
    r = clirunner.invoke(
        organize, ["-f", "copy", "--dandiset-path", str(tmp_path), str(simple2_nwb)]
    )
    assert r.exit_code == 0, r.stdout
    return tmp_path


@pytest.fixture(scope="session")
def organized_nwb_dir2(simple1_nwb_metadata, simple2_nwb, tmp_path_factory, clirunner):
    tmp_path = tmp_path_factory.mktemp("dandiset")

    # need to copy first and then use -f move since we will create one more
    # file to be "organized"
    shutil.copy(str(simple2_nwb), str(tmp_path))
    make_nwb_file(
        str(tmp_path / "simple3.nwb"),
        subject=pynwb.file.Subject(
            subject_id="lizard001",
            date_of_birth=datetime(2019, 12, 1, tzinfo=tzutc()),
            sex="F",
            species="Gekko gecko",
        ),
        **simple1_nwb_metadata,
    )
    (tmp_path / dandiset_metadata_file).write_text("{}\n")
    r = clirunner.invoke(organize, ["-f", "move", "--dandiset-path", str(tmp_path)])
    assert r.exit_code == 0, r.stdout
    assert sum(p.is_dir() for p in tmp_path.iterdir()) == 2
    return tmp_path


@pytest.fixture(scope="session")
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


LOCAL_DOCKER_DIR = Path(__file__).with_name("data") / "dandiarchive-docker"
LOCAL_DOCKER_ENV = LOCAL_DOCKER_DIR.name


@pytest.fixture(scope="session")
def local_docker_compose():
    instance_id = "local-docker-tests"
    instance = known_instances[instance_id]

    # if api_key is specified, we are reusing some already running instance
    # so we would not bother starting/stopping a new one here
    api_key = os.environ.get('DANDI_REUSE_LOCAL_DOCKER_TESTS_API_KEY')
    if api_key:
        yield {"api_key": api_key, "instance": instance, "instance_id": instance_id}
        return

    skipif.no_network()
    skipif.no_docker_engine()

    # Check that we're running on a Unix-based system (Linux or macOS), as the
    # Docker images don't work on Windows.
    if os.name != "posix":
        pytest.skip("Docker images require Unix host")

    run(["docker-compose", "up", "-d"], cwd=str(LOCAL_DOCKER_DIR), check=True)
    try:
        run(["docker", "wait", f"{LOCAL_DOCKER_ENV}_provision_1"], check=True)

        # Should we check that the output of `docker wait` is 0?
        r = requests.get(
            f"{instance.girder}/api/v1/user/authentication", auth=("admin", "letmein")
        )
        r.raise_for_status()
        initial_api_key = r.json()["authToken"]["token"]

        # Get an unscoped/full permissions API key that can be used for
        # uploading:
        r = requests.post(
            f"{instance.girder}/api/v1/api_key",
            params={"name": "testkey", "tokenDuration": 1},
            headers={"Girder-Token": initial_api_key},
        )
        r.raise_for_status()
        api_key = r.json()["key"]

        yield {"api_key": api_key, "instance": instance, "instance_id": instance_id}
    finally:
        run(["docker-compose", "down", "-v"], cwd=str(LOCAL_DOCKER_DIR), check=True)


@pytest.fixture()
def local_docker_compose_env(local_docker_compose, monkeypatch):
    monkeypatch.setenv("DANDI_API_KEY", local_docker_compose["api_key"])
    return local_docker_compose
