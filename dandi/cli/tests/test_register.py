import re
from os.path import dirname
from pathlib import Path
from traceback import format_exception

from click.testing import CliRunner
import pytest
import yaml

from ..command import register
from ...consts import dandiset_identifier_regex, dandiset_metadata_file


def yaml_load(s):
    obj = yaml.load(s, Loader=yaml.BaseLoader)
    return obj


def show_result(r):
    if r.exception is not None:
        return "".join(format_exception(*r.exc_info))
    else:
        return r.output


def test_smoke_metadata_present(local_docker_compose):
    runner = CliRunner(mix_stderr=False)
    with runner.isolated_filesystem():
        Path(dandiset_metadata_file).write_text("{}\n")
        r = runner.invoke(
            register,
            [
                "-i",
                "local-docker-tests",
                "--name",
                "Dandiset Name",
                "--description",
                "Dandiset Description",
            ],
            env={"DANDI_API_KEY": local_docker_compose["api_key"]},
        )
        assert r.exit_code == 0, show_result(r)
        assert r.stdout == ""
        with open(dandiset_metadata_file) as fp:
            metadata = yaml_load(fp.read())
    assert metadata
    assert metadata["name"] == "Dandiset Name"
    assert metadata["description"] == "Dandiset Description"
    assert re.match(dandiset_identifier_regex, metadata["identifier"])
    # TODO: Check that a Dandiset exists in the local-docker-tests instance
    # with the given identifier


def test_smoke_metadata_not_present(local_docker_compose):
    runner = CliRunner(mix_stderr=False)
    with runner.isolated_filesystem():
        r = runner.invoke(
            register,
            [
                "-i",
                "local-docker-tests",
                "--name",
                "Dandiset Name",
                "--description",
                "Dandiset Description",
            ],
            env={"DANDI_API_KEY": local_docker_compose["api_key"]},
        )
        assert r.exit_code == 0, show_result(r)
        assert r.stdout != ""
        assert not Path(dandiset_metadata_file).exists()
        metadata = yaml_load(r.stdout)
    assert metadata
    assert metadata["name"] == "Dandiset Name"
    assert metadata["description"] == "Dandiset Description"
    assert re.match(dandiset_identifier_regex, metadata["identifier"])
    # TODO: Check that a Dandiset exists in the local-docker-tests instance
    # with the given identifier
