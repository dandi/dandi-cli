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


def test_smoke(local_docker):
    runner = CliRunner(mix_stderr=False)
    with runner.isolated_filesystem():
        Path(dandiset_metadata_file).write_text("{}\n")
        r = runner.invoke(
            register,
            [
                "-i",
                "local-docker",
                "--name",
                "Dandiset Name",
                "--description",
                "Dandiset Description",
            ],
            env={"DANDI_API_KEY": local_docker["api_key"]},
        )
        assert r.exit_code == 0, show_result(r)
        with open(dandiset_metadata_file) as fp:
            metadata = yaml_load(fp.read())
    assert metadata
    assert metadata["name"] == "Dandiset Name"
    assert metadata["description"] == "Dandiset Description"
    assert re.match(dandiset_identifier_regex, metadata["identifier"])
    # TODO: Check that a Dandiset exists in the local-docker instance with the
    # given identifier
