from pathlib import Path
from shutil import copyfile

import pytest
import yaml

from .. import girder
from ..consts import collection_drafts, dandiset_metadata_file
from ..register import register
from ..upload import upload

DANDIFILES_DIR = Path(__file__).with_name("data") / "dandifiles"


def test_upload(local_docker_compose_env, monkeypatch, tmp_path):
    DIRNAME1 = "sub-anm369963"
    FILENAME1 = "sub-anm369963_ses-20170228.nwb"
    DIRNAME2 = "sub-anm372793"
    FILENAME2 = "sub-anm372793_ses-20170508.nwb"

    dandi_instance_id = local_docker_compose_env["instance_id"]

    for dirname, filename in [(DIRNAME1, FILENAME1), (DIRNAME2, FILENAME2)]:
        (tmp_path / dirname).mkdir(exist_ok=True, parents=True)
        copyfile(DANDIFILES_DIR / dirname / filename, tmp_path / dirname / filename)

    register(
        "Upload Test",
        "Upload Test Description",
        dandiset_path=tmp_path,
        dandi_instance=dandi_instance_id,
    )
    with (tmp_path / dandiset_metadata_file).open() as fp:
        metadata = yaml.safe_load(fp)
    dandi_id = metadata["identifier"]

    client = girder.get_client(local_docker_compose_env["instance"].girder)
    for dirname in [DIRNAME1, DIRNAME2]:
        with pytest.raises(girder.GirderNotFound):
            girder.lookup(client, collection_drafts, path=f"{dandi_id}/{dirname}")

    monkeypatch.chdir(tmp_path)
    upload(paths=[DIRNAME1], dandi_instance=dandi_instance_id, devel_debug=True)

    girder.lookup(client, collection_drafts, path=f"{dandi_id}/{DIRNAME1}/{FILENAME1}")
    with pytest.raises(girder.GirderNotFound):
        girder.lookup(client, collection_drafts, path=f"{dandi_id}/{DIRNAME2}")


def test_upload_existing_error(local_docker_compose_env, monkeypatch, tmp_path):
    DIRNAME = "sub-anm369963"
    FILENAME = "sub-anm369963_ses-20170228.nwb"
    dandi_instance_id = local_docker_compose_env["instance_id"]
    (tmp_path / DIRNAME).mkdir(exist_ok=True, parents=True)
    copyfile(DANDIFILES_DIR / DIRNAME / FILENAME, tmp_path / DIRNAME / FILENAME)
    register(
        "Upload Test",
        "Upload Test Description",
        dandiset_path=tmp_path,
        dandi_instance=dandi_instance_id,
    )
    monkeypatch.chdir(tmp_path)
    upload(
        paths=[DIRNAME],
        dandi_instance=dandi_instance_id,
        devel_debug=True,
        existing="error",
    )
    with pytest.raises(FileExistsError):
        upload(
            paths=[DIRNAME],
            dandi_instance=dandi_instance_id,
            devel_debug=True,
            existing="error",
        )
