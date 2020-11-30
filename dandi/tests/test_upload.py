import os
import re
import pytest

from .. import girder
from ..consts import collection_drafts, dandiset_metadata_file
from ..dandiset import Dandiset
from ..download import download
from ..register import register
from ..upload import upload
from ..utils import yaml_load


def test_upload(local_docker_compose_env, monkeypatch, organized_nwb_dir2):
    nwb_files = list(organized_nwb_dir2.glob(f"*{os.sep}*.nwb"))
    assert len(nwb_files) == 2
    dirname1 = nwb_files[0].parent.name
    filename1 = nwb_files[0].name
    dirname2 = nwb_files[1].parent.name
    assert dirname1 != dirname2

    dandi_instance_id = local_docker_compose_env["instance_id"]

    register(
        "Upload Test",
        "Upload Test Description",
        dandiset_path=organized_nwb_dir2,
        dandi_instance=dandi_instance_id,
    )
    with (organized_nwb_dir2 / dandiset_metadata_file).open() as fp:
        metadata = yaml_load(fp, typ="safe")
    dandi_id = metadata["identifier"]

    client = girder.get_client(local_docker_compose_env["instance"].girder)
    for dname in [dirname1, dirname2]:
        with pytest.raises(girder.GirderNotFound):
            girder.lookup(client, collection_drafts, path=f"{dandi_id}/{dname}")

    monkeypatch.chdir(organized_nwb_dir2)
    upload(paths=[dirname1], dandi_instance=dandi_instance_id, devel_debug=True)

    girder.lookup(client, collection_drafts, path=f"{dandi_id}/{dirname1}/{filename1}")
    with pytest.raises(girder.GirderNotFound):
        girder.lookup(client, collection_drafts, path=f"{dandi_id}/{dirname2}")


def test_upload_existing_error(
    local_docker_compose_env, monkeypatch, organized_nwb_dir
):
    dandi_instance_id = local_docker_compose_env["instance_id"]
    register(
        "Upload Test",
        "Upload Test Description",
        dandiset_path=organized_nwb_dir,
        dandi_instance=dandi_instance_id,
    )
    monkeypatch.chdir(organized_nwb_dir)
    upload(
        paths=[], dandi_instance=dandi_instance_id, devel_debug=True, existing="error"
    )
    with pytest.raises(FileExistsError):
        upload(
            paths=[],
            dandi_instance=dandi_instance_id,
            devel_debug=True,
            existing="error",
        )


def test_upload_locks(local_docker_compose_env, mocker, monkeypatch, organized_nwb_dir):
    nwb_file, = organized_nwb_dir.glob(f"*{os.sep}*.nwb")
    dirname = nwb_file.parent.name
    dandi_instance_id = local_docker_compose_env["instance_id"]
    register(
        "Upload Test",
        "Upload Test Description",
        dandiset_path=organized_nwb_dir,
        dandi_instance=dandi_instance_id,
    )
    monkeypatch.chdir(organized_nwb_dir)
    lockmock = mocker.patch.object(girder.GirderCli, "lock_dandiset")
    upload(
        paths=[dirname],
        dandi_instance=dandi_instance_id,
        devel_debug=True,
        existing="error",
    )
    lockmock.assert_called()
    lockmock.return_value.__enter__.assert_called()
    lockmock.return_value.__exit__.assert_called()


def test_upload_unregistered(local_docker_compose_env, monkeypatch, organized_nwb_dir):
    nwb_file, = organized_nwb_dir.glob(f"*{os.sep}*.nwb")
    dirname = nwb_file.parent.name
    dandi_instance_id = local_docker_compose_env["instance_id"]
    (organized_nwb_dir / dandiset_metadata_file).write_text("identifier: '999999'\n")
    monkeypatch.chdir(organized_nwb_dir)
    with pytest.raises(ValueError) as excinfo:
        upload(paths=[dirname], dandi_instance=dandi_instance_id, devel_debug=True)
    assert str(excinfo.value) == (
        f"There is no 999999 in {collection_drafts}. Did you use 'dandi register'?"
    )


def test_upload_path_not_in_dandiset_path(
    local_docker_compose_env, organized_nwb_dir, organized_nwb_dir2
):
    (organized_nwb_dir / dandiset_metadata_file).write_text("identifier: '000001'\n")
    with pytest.raises(ValueError) as excinfo:
        upload(
            paths=[str(organized_nwb_dir2)],
            dandiset_path=organized_nwb_dir,
            dandi_instance=local_docker_compose_env["instance_id"],
        )
    assert re.fullmatch(
        rf"{re.escape(str(organized_nwb_dir2))}\S* is not under "
        rf"{re.escape(str(organized_nwb_dir))}",
        str(excinfo.value),
    )


def test_upload_nonexistent_path(local_docker_compose_env, organized_nwb_dir):
    # This is currently just a smoke test to cover the "except
    # FileNotFoundError:" block in process_path().
    (organized_nwb_dir / dandiset_metadata_file).write_text("identifier: '000001'\n")
    upload(
        paths=[str(organized_nwb_dir / "nonexistent.nwb")],
        dandiset_path=organized_nwb_dir,
        dandi_instance=local_docker_compose_env["instance_id"],
    )


def test_upload_stat_failure(local_docker_compose_env, organized_nwb_dir):
    # This is currently just a smoke test to cover the "except Exception:"
    # block in process_path().
    (organized_nwb_dir / dandiset_metadata_file).write_text("identifier: '000001'\n")
    baddir = organized_nwb_dir / "bad"
    baddir.mkdir(mode=0o444)
    try:
        upload(
            paths=[str(baddir / "nonexistent.nwb")],
            dandiset_path=organized_nwb_dir,
            dandi_instance=local_docker_compose_env["instance_id"],
        )
    finally:
        baddir.rmdir()


def test_upload_external_download(local_docker_compose_env, monkeypatch, tmp_path):
    download("https://dandiarchive.org/dandiset/000027", tmp_path)
    dandiset_path = tmp_path / "000027"
    dandi_instance_id = local_docker_compose_env["instance_id"]
    dandiset = Dandiset(dandiset_path)

    # Since identifier is instance-specific and locking requires dandiset to exist
    # we cannot just upload.  We need first to register a new one and have identifier updated.
    # To minimize any programmatic changes, we will not point register to the dandiset
    # but just will use its  "identifier"  in the simplest .replace
    rec = register(
        dandiset.metadata["name"],
        dandiset.metadata["description"],
        dandi_instance=dandi_instance_id,
    )
    dandiset_yaml = dandiset_path / dandiset_metadata_file
    new_dandiset_yaml = dandiset_yaml.read_text().replace("000027", rec["identifier"])
    dandiset_yaml.write_text(new_dandiset_yaml)

    monkeypatch.chdir(dandiset_path)
    upload(paths=[], dandi_instance=dandi_instance_id, devel_debug=True)
