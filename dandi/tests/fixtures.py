from datetime import datetime
import logging
import os
from pathlib import Path
import re
import shutil
from subprocess import DEVNULL, check_output, run
import tempfile
from time import sleep
from uuid import uuid4

from dandischema.consts import DANDI_SCHEMA_VERSION
from dateutil.tz import tzutc
import pynwb
import pytest
import requests

from .skip import skipif
from .. import get_logger
from ..cli.command import organize
from ..consts import dandiset_metadata_file, known_instances
from ..dandiapi import DandiAPIClient
from ..pynwb_utils import make_nwb_file, metadata_nwb_file_fields
from ..upload import upload

lgr = get_logger()


@pytest.fixture(autouse=True)
def capture_all_logs(caplog):
    caplog.set_level(logging.DEBUG, logger="dandi")


# TODO: move into some common fixtures.  We might produce a number of files
#       and also carry some small ones directly in git for regression testing
@pytest.fixture(scope="session")
def simple1_nwb_metadata(tmpdir_factory):
    # very simple assignment with the same values as the key with 1 as suffix
    metadata = {f: "{}1".format(f) for f in metadata_nwb_file_fields}
    metadata["identifier"] = uuid4().hex
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
            date_of_birth=datetime(2016, 12, 1, tzinfo=tzutc()),
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
            date_of_birth=datetime(2016, 12, 1, tzinfo=tzutc()),
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


def get_gitrepo_fixture(url, committish=None, scope="session"):

    if committish:
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
def docker_compose_setup():
    skipif.no_network()
    skipif.no_docker_engine()

    # Check that we're running on a Unix-based system (Linux or macOS), as the
    # Docker images don't work on Windows.
    if os.name != "posix":
        pytest.skip("Docker images require Unix host")

    persist = os.environ.get("DANDI_TESTS_PERSIST_DOCKER_COMPOSE")

    create = (
        persist is None
        or run(
            ["docker", "inspect", f"{LOCAL_DOCKER_ENV}_django_1"],
            stdout=DEVNULL,
            stderr=DEVNULL,
        ).returncode
        != 0
    )

    # TODO: Delete this after <https://github.com/dandi/dandi-api/pull/251> is
    # merged:
    env = dict(os.environ)
    env["DJANGO_DANDI_GIRDER_API_URL"] = "http://localhost:8080/api/v1"
    env["DJANGO_DANDI_GIRDER_API_KEY"] = "abc123"
    env["DJANGO_DANDI_SCHEMA_VERSION"] = DANDI_SCHEMA_VERSION

    try:
        if create:
            run(
                ["docker-compose", "run", "--rm", "django", "./manage.py", "migrate"],
                cwd=str(LOCAL_DOCKER_DIR),
                env=env,
                check=True,
            )
            run(
                [
                    "docker-compose",
                    "run",
                    "--rm",
                    "-e",
                    "DJANGO_SUPERUSER_PASSWORD=nsNc48DBiS",
                    "django",
                    "./manage.py",
                    "createsuperuser",
                    "--no-input",
                    "--username",
                    "admin",
                    "--email",
                    "nil@nil.nil",
                ],
                cwd=str(LOCAL_DOCKER_DIR),
                env=env,
                check=True,
            )

        r = check_output(
            [
                "docker-compose",
                "run",
                "--rm",
                "django",
                "./manage.py",
                "drf_create_token",
                "admin",
            ],
            cwd=str(LOCAL_DOCKER_DIR),
            env=env,
            universal_newlines=True,
        )
        m = re.search(r"^Generated token (\w+) for user admin$", r, flags=re.M)
        if not m:
            raise RuntimeError(
                f"Could not extract Django auth token from drf_create_token output: {r!r}"
            )
        django_api_key = m[1]

        if create:
            run(
                ["docker-compose", "up", "-d", "django", "celery", "redirector"],
                cwd=str(LOCAL_DOCKER_DIR),
                env=env,
                check=True,
            )
            API_URL = known_instances["dandi-api-local-docker-tests"].api
            for _ in range(10):
                try:
                    requests.get(f"{API_URL}/dandisets/")
                except requests.ConnectionError:
                    sleep(1)
                else:
                    break
            else:
                raise RuntimeError("Django container did not start up in time")
        yield {"django_api_key": django_api_key}
    finally:
        if persist in (None, "0"):
            run(["docker-compose", "down", "-v"], cwd=str(LOCAL_DOCKER_DIR), check=True)


@pytest.fixture(scope="session")
def local_dandi_api(docker_compose_setup):
    instance_id = "dandi-api-local-docker-tests"
    instance = known_instances[instance_id]
    api_key = docker_compose_setup["django_api_key"]
    with DandiAPIClient(api_url=instance.api, token=api_key) as client:
        yield {
            "api_key": api_key,
            "client": client,
            "instance": instance,
            "instance_id": instance_id,
        }


@pytest.fixture()
def text_dandiset(local_dandi_api, monkeypatch, tmp_path_factory):
    d = local_dandi_api["client"].create_dandiset(
        "Text Dandiset",
        {
            "schemaKey": "Dandiset",
            "name": "Text Dandiset",
            "description": "A test text Dandiset",
            "contributor": [
                {
                    "schemaKey": "Person",
                    "name": "Wodder, John",
                    "roleName": ["dcite:Author", "dcite:ContactPerson"],
                }
            ],
            "license": ["spdx:CC0-1.0"],
            "manifestLocation": ["https://github.com/dandi/dandi-cli"],
        },
    )
    dandiset_id = d.identifier
    dspath = tmp_path_factory.mktemp("text_dandiset")
    (dspath / dandiset_metadata_file).write_text(f"identifier: '{dandiset_id}'\n")
    (dspath / "file.txt").write_text("This is test text.\n")
    (dspath / "subdir1").mkdir()
    (dspath / "subdir1" / "apple.txt").write_text("Apple\n")
    (dspath / "subdir2").mkdir()
    (dspath / "subdir2" / "banana.txt").write_text("Banana\n")
    (dspath / "subdir2" / "coconut.txt").write_text("Coconut\n")

    def upload_dandiset(paths=None, **kwargs):
        with monkeypatch.context() as m:
            m.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
            upload(
                paths=paths or [],
                dandiset_path=dspath,
                dandi_instance=local_dandi_api["instance_id"],
                devel_debug=True,
                allow_any_path=True,
                validation="skip",
                **kwargs,
            )

    upload_dandiset()
    return {
        "client": local_dandi_api["client"],
        "dspath": dspath,
        "dandiset": d,
        "dandiset_id": dandiset_id,
        "reupload": upload_dandiset,
    }
