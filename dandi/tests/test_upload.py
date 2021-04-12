import os
from pathlib import Path
import random
import re

import pytest
import responses

from ..consts import collection_drafts, dandiset_metadata_file
from ..dandiapi import DandiAPIClient
from ..dandiset import Dandiset
from ..download import download
from .. import girder
from ..register import register
from ..upload import upload
from ..utils import find_files, yaml_load


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
    (nwb_file,) = organized_nwb_dir.glob(f"*{os.sep}*.nwb")
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
    (nwb_file,) = organized_nwb_dir.glob(f"*{os.sep}*.nwb")
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


def test_upload_size_mismatch(
    capsys, local_docker_compose_env, monkeypatch, organized_nwb_dir
):
    (nwb_file,) = organized_nwb_dir.glob(f"*{os.sep}*.nwb")
    dirname = nwb_file.parent.name
    dandi_instance_id = local_docker_compose_env["instance_id"]
    register(
        "Upload Test",
        "Upload Test Description",
        dandiset_path=organized_nwb_dir,
        dandi_instance=dandi_instance_id,
    )
    monkeypatch.chdir(organized_nwb_dir)
    with responses.RequestsMock() as rsps:
        rsps.add_passthru(re.compile(r".+"))
        rsps.add(
            responses.GET,
            re.compile(
                r"^{}/api/v1/file/[^/]+/download$".format(
                    re.escape(local_docker_compose_env["instance"].girder)
                )
            ),
            body="Disregard this.",
            headers={"Content-Length": "42"},
            stream=True,
        )
        upload(paths=[dirname], dandi_instance=dandi_instance_id, devel_debug=True)
    assert (
        repr(
            {
                "status": "skipped",
                "message": "File size on server does not match local file",
            }
        )
        in capsys.readouterr().out
    )


@pytest.mark.skipif(
    not os.environ.get("DANDI_DEVEL"), reason="Only run when DANDI_DEVEL is set"
)
def test_enormous_upload_breaks_girder(
    capsys, local_docker_compose_env, monkeypatch, tmp_path
):
    dandi_instance_id = local_docker_compose_env["instance_id"]
    register(
        "Enormous File Upload Test",
        "Enormous File Upload Test Description",
        dandiset_path=tmp_path,
        dandi_instance=dandi_instance_id,
    )
    bigfile = tmp_path / "blob.dat"
    meg = bytes(random.choices(range(256), k=1 << 20))
    try:
        with bigfile.open("wb") as fp:
            for _ in range(66 * 1024):
                fp.write(meg)
        monkeypatch.chdir(tmp_path)
        upload(
            paths=[str(bigfile)],
            dandi_instance=dandi_instance_id,
            allow_any_path=True,
            devel_debug=True,
        )
        assert "'status': 'skipped'" in capsys.readouterr().out
    finally:
        try:
            bigfile.unlink()
        except FileNotFoundError:
            pass


def test_new_upload_download(local_dandi_api, monkeypatch, organized_nwb_dir, tmp_path):
    r = local_dandi_api["client"].create_dandiset("Test Dandiset", {})
    dandiset_id = r["identifier"]
    (nwb_file,) = organized_nwb_dir.glob(f"*{os.sep}*.nwb")
    (organized_nwb_dir / dandiset_metadata_file).write_text(
        f"identifier: '{dandiset_id}'\n"
    )
    monkeypatch.chdir(organized_nwb_dir)
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    upload(paths=[], dandi_instance=local_dandi_api["instance_id"], devel_debug=True)
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/draft",
        tmp_path,
    )
    (nwb_file2,) = tmp_path.glob(f"{dandiset_id}{os.sep}*{os.sep}*.nwb")
    assert nwb_file.name == nwb_file2.name
    assert nwb_file.parent.name == nwb_file2.parent.name

    #
    # test updating dandiset metadata record while at it
    # For now let's "manually" populate dandiset.yaml in that downloaded location
    # which is missing due to https://github.com/dandi/dandi-api/issues/63
    from ..dandiset import APIDandiset
    from ..utils import yaml_dump

    ds_orig = APIDandiset(organized_nwb_dir)
    ds_metadata = ds_orig.metadata
    ds_metadata["description"] = "very long"
    ds_metadata["name"] = "shorty"

    monkeypatch.chdir(tmp_path / dandiset_id)
    Path(dandiset_metadata_file).write_text(yaml_dump(ds_metadata))
    upload(
        paths=[dandiset_metadata_file],
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        upload_dandiset_metadata=True,
    )

    r = local_dandi_api["client"].get_dandiset(dandiset_id, "draft")
    assert r["metadata"]["name"] == "shorty"


def test_new_upload_extant_existing(mocker, text_dandiset):
    iter_upload_spy = mocker.spy(DandiAPIClient, "iter_upload")
    with pytest.raises(FileExistsError):
        text_dandiset["reupload"](existing="error")
    iter_upload_spy.assert_not_called()


def test_new_upload_extant_skip(mocker, text_dandiset):
    iter_upload_spy = mocker.spy(DandiAPIClient, "iter_upload")
    text_dandiset["reupload"](existing="skip")
    iter_upload_spy.assert_not_called()


@pytest.mark.parametrize("existing", ["overwrite", "refresh"])
def test_new_upload_extant_eq_overwrite(existing, mocker, text_dandiset):
    iter_upload_spy = mocker.spy(DandiAPIClient, "iter_upload")
    text_dandiset["reupload"](existing=existing)
    iter_upload_spy.assert_not_called()


@pytest.mark.parametrize("existing", ["overwrite", "refresh"])
def test_new_upload_extant_neq_overwrite(
    existing, local_dandi_api, mocker, text_dandiset, tmp_path
):
    dandiset_id = text_dandiset["dandiset_id"]
    (text_dandiset["dspath"] / "file.txt").write_text("This is different text.\n")
    iter_upload_spy = mocker.spy(DandiAPIClient, "iter_upload")
    text_dandiset["reupload"](existing=existing)
    iter_upload_spy.assert_called()
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/draft",
        tmp_path,
    )
    assert (
        tmp_path / dandiset_id / "file.txt"
    ).read_text() == "This is different text.\n"


def test_new_upload_extant_old_refresh(mocker, text_dandiset):
    (text_dandiset["dspath"] / "file.txt").write_text("This is different text.\n")
    os.utime(text_dandiset["dspath"] / "file.txt", times=(0, 0))
    iter_upload_spy = mocker.spy(DandiAPIClient, "iter_upload")
    text_dandiset["reupload"](existing="refresh")
    iter_upload_spy.assert_not_called()


def test_new_upload_extant_force(mocker, text_dandiset):
    iter_upload_spy = mocker.spy(DandiAPIClient, "iter_upload")
    text_dandiset["reupload"](existing="force")
    iter_upload_spy.assert_called()


def test_new_upload_extant_bad_existing(mocker, text_dandiset):
    iter_upload_spy = mocker.spy(DandiAPIClient, "iter_upload")
    text_dandiset["reupload"](existing="foobar")
    iter_upload_spy.assert_not_called()


@pytest.mark.parametrize(
    "contents",
    [
        pytest.param(
            b"",
            marks=pytest.mark.xfail(
                reason="https://github.com/dandi/dandi-api/issues/168"
            ),
        ),
        b"x",
    ],
)
def test_upload_download_small_file(contents, local_dandi_api, monkeypatch, tmp_path):
    client = local_dandi_api["client"]
    dandiset_id = client.create_dandiset("Small Dandiset", {})["identifier"]
    dspath = tmp_path / "upload"
    dspath.mkdir()
    (dspath / dandiset_metadata_file).write_text(f"identifier: '{dandiset_id}'\n")
    (dspath / "file.txt").write_bytes(contents)
    monkeypatch.setenv("DANDI_API_KEY", local_dandi_api["api_key"])
    upload(
        paths=[],
        dandiset_path=dspath,
        dandi_instance=local_dandi_api["instance_id"],
        devel_debug=True,
        allow_any_path=True,
        validation="skip",
    )
    download_dir = tmp_path / "download"
    download_dir.mkdir()
    download(
        f"{local_dandi_api['instance'].api}/dandisets/{dandiset_id}/versions/draft",
        download_dir,
    )
    files = sorted(map(Path, find_files(r".*", paths=[download_dir])))
    assert files == [
        download_dir / dandiset_id / dandiset_metadata_file,
        download_dir / dandiset_id / "file.txt",
    ]
    assert files[1].read_bytes() == contents
