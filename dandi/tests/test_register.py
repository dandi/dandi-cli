import re

import yaml

from ..consts import dandiset_identifier_regex, dandiset_metadata_file
from ..register import register


def yaml_load(s):
    obj = yaml.load(s, Loader=yaml.BaseLoader)
    return obj


def test_smoke_metadata_present(local_docker_compose_env, monkeypatch, tmp_path):
    (tmp_path / dandiset_metadata_file).write_text("{}\n")
    assert (
        register(
            "Dandiset Name",
            "Dandiset Description",
            dandiset_path=tmp_path,
            dandi_instance=local_docker_compose_env["instance_id"],
        )
        is None
    )
    with (tmp_path / dandiset_metadata_file).open() as fp:
        metadata = yaml_load(fp.read())
    assert metadata
    assert metadata["name"] == "Dandiset Name"
    assert metadata["description"] == "Dandiset Description"
    assert re.match(dandiset_identifier_regex, metadata["identifier"])
    # TODO: Check that a Dandiset exists in the local-docker-tests instance
    # with the given identifier


def test_smoke_metadata_not_present(local_docker_compose_env, monkeypatch, tmp_path):
    assert (
        register(
            "Dandiset Name",
            "Dandiset Description",
            dandiset_path=tmp_path,
            dandi_instance=local_docker_compose_env["instance_id"],
        )
        is None
    )
    with (tmp_path / dandiset_metadata_file).open() as fp:
        metadata = yaml_load(fp.read())
    assert metadata
    assert metadata["name"] == "Dandiset Name"
    assert metadata["description"] == "Dandiset Description"
    assert re.match(dandiset_identifier_regex, metadata["identifier"])
    # TODO: Check that a Dandiset exists in the local-docker-tests instance
    # with the given identifier
