import re

import pytest

from ..consts import dandiset_identifier_regex, dandiset_metadata_file
from ..register import register
from ..utils import yaml_load


@pytest.mark.parametrize("present", [True, False])
def test_smoke_register(local_docker_compose_env, tmp_path, present):
    if present:
        (tmp_path / dandiset_metadata_file).write_text("{}\n")
    dandiset_metadata = register(
        "Dandiset Name",
        "Dandiset Description",
        dandiset_path=tmp_path,
        dandi_instance=local_docker_compose_env["instance_id"],
    )
    assert dandiset_metadata
    assert dandiset_metadata["name"] == "Dandiset Name"
    assert dandiset_metadata["description"] == "Dandiset Description"
    assert re.match(dandiset_identifier_regex, dandiset_metadata["identifier"])

    # Verify that dandiset.yaml was updated or generated
    with (tmp_path / dandiset_metadata_file).open() as fp:
        metadata = yaml_load(fp, typ="base")
    assert metadata == dandiset_metadata

    # TODO: Check that a Dandiset exists in the local-docker-tests instance
    # with the given identifier
