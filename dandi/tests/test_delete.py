from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture
import requests

from .fixtures import DandiAPI, SampleDandiset, bulk_delete_supported
from .. import delete as delete_mod
from ..consts import DRAFT, dandiset_metadata_file
from ..dandiapi import RemoteDandiset, RESTFullAPIClient
from ..delete import delete, is_same_url
from ..download import download
from ..exceptions import BulkDeleteUnsupportedError, HTTP404Error, NotFoundError
from ..utils import list_paths


@pytest.mark.parametrize(
    "paths,remainder",
    [
        (
            ["subdir2/coconut.txt"],
            [
                Path("file.txt"),
                Path("subdir1", "apple.txt"),
                Path("subdir2", "banana.txt"),
            ],
        ),
        (["subdir2"], [Path("file.txt"), Path("subdir1", "apple.txt")]),
        (
            ["subdir2", "subdir2/coconut.txt"],
            [Path("file.txt"), Path("subdir1", "apple.txt")],
        ),
        (
            ["dandi://{instance}/{dandiset_id}/subdir2/coconut.txt"],
            [
                Path("file.txt"),
                Path("subdir1", "apple.txt"),
                Path("subdir2", "banana.txt"),
            ],
        ),
        (
            ["dandi://{instance}/{dandiset_id}/subdir2/"],
            [Path("file.txt"), Path("subdir1", "apple.txt")],
        ),
        (
            [
                "dandi://{instance}/{dandiset_id}/subdir2/",
                "dandi://{instance}/{dandiset_id}/subdir2/coconut.txt",
            ],
            [Path("file.txt"), Path("subdir1", "apple.txt")],
        ),
        (
            [
                "subdir1",
                "dandi://{instance}/{dandiset_id}/subdir2/coconut.txt",
            ],
            [Path("file.txt"), Path("subdir2", "banana.txt")],
        ),
    ],
)
def test_delete_paths(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
    tmp_path: Path,
    paths: list[str],
    remainder: list[Path],
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    delete(
        [p.format(instance=instance, dandiset_id=dandiset_id) for p in paths],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
    )
    bulk_delete_spy.assert_called()
    download(text_dandiset.dandiset.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / dandiset_id / f for f in [Path("dandiset.yaml")] + remainder
    ]


@pytest.mark.parametrize("confirm", [True, False])
def test_delete_path_confirm(
    confirm: bool,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    confirm_mock = mocker.patch("click.confirm", return_value=confirm)
    delete(["subdir2/coconut.txt"], dandi_instance=instance, devel_debug=True)
    confirm_mock.assert_called_with(
        f"Delete 1 assets on server from Dandiset {dandiset_id}?"
    )
    if confirm:
        bulk_delete_spy.assert_called()
    else:
        bulk_delete_spy.assert_not_called()


def test_delete_path_pyout(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = text_dandiset.api.instance_id
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    delete(["subdir2/coconut.txt"], dandi_instance=instance, force=True)
    bulk_delete_spy.assert_called()


@pytest.mark.parametrize(
    "paths",
    [
        ["dandi://{instance}/{dandiset_id}"],
        ["dandi://{instance}/{dandiset_id}", "file.txt"],
        ["file.txt", "dandi://{instance}/{dandiset_id}"],
        [
            "dandi://{instance}/{dandiset_id}",
            "dandi://{instance}/{dandiset_id}/subdir2/coconut.txt",
        ],
        [
            "dandi://{instance}/{dandiset_id}/subdir2/coconut.txt",
            "dandi://{instance}/{dandiset_id}",
        ],
    ],
)
def test_delete_dandiset(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
    paths: list[str],
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    delete(
        [p.format(instance=instance, dandiset_id=dandiset_id) for p in paths],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
    )
    delete_spy.assert_called()
    with pytest.raises(NotFoundError):
        text_dandiset.client.get_dandiset(dandiset_id, DRAFT, lazy=False)


@pytest.mark.parametrize("confirm", [True, False])
def test_delete_dandiset_confirm(
    confirm: bool,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    confirm_mock = mocker.patch("click.confirm", return_value=confirm)
    delete(
        [f"dandi://{instance}/{dandiset_id}"], dandi_instance=instance, devel_debug=True
    )
    confirm_mock.assert_called_with(f"Delete Dandiset {dandiset_id}?")
    if confirm:
        delete_spy.assert_called()
    else:
        delete_spy.assert_not_called()


def test_delete_dandiset_mismatch(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    not_dandiset = str(int(dandiset_id) - 1).zfill(6)
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    for paths in [
        [
            "subdir1/apple.txt",
            f"dandi://{instance}/{not_dandiset}/subdir2/coconut.txt",
        ],
        [
            f"dandi://{instance}/{dandiset_id}/subdir1/apple.txt",
            f"dandi://{instance}/{not_dandiset}/subdir2/coconut.txt",
        ],
    ]:
        with pytest.raises(ValueError) as excinfo:
            delete(paths, dandi_instance=instance, devel_debug=True, force=True)
        assert (
            str(excinfo.value) == "Cannot delete assets from multiple Dandisets at once"
        )
        bulk_delete_spy.assert_not_called()


def test_delete_instance_mismatch(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    for paths in [
        [
            "subdir1/apple.txt",
            f"dandi://dandi/{dandiset_id}/subdir2/coconut.txt",
        ],
        [
            f"dandi://{instance}/{dandiset_id}/subdir2/coconut.txt",
            f"dandi://dandi/{dandiset_id}/subdir1/apple.txt",
        ],
    ]:
        with pytest.raises(ValueError) as excinfo:
            delete(paths, dandi_instance=instance, devel_debug=True, force=True)
        assert (
            str(excinfo.value)
            == "Cannot delete assets from multiple API instances at once"
        )
        bulk_delete_spy.assert_not_called()


def test_delete_nonexistent_dandiset(
    local_dandi_api: DandiAPI, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    local_dandi_api.monkeypatch_set_api_key_env(monkeypatch)
    instance = local_dandi_api.instance_id
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    with pytest.raises(NotFoundError) as excinfo:
        delete(
            [f"dandi://{instance}/999999/subdir1/apple.txt"],
            dandi_instance=instance,
            devel_debug=True,
            force=True,
        )
    assert str(excinfo.value) == (
        "No such Dandiset: '999999'. "
        "Verify the Dandiset ID is correct and that you have access. "
    )
    bulk_delete_spy.assert_not_called()


def test_delete_nonexistent_dandiset_skip_missing(
    local_dandi_api: DandiAPI, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    local_dandi_api.monkeypatch_set_api_key_env(monkeypatch)
    instance = local_dandi_api.instance_id
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    delete(
        [f"dandi://{instance}/999999/subdir1/apple.txt"],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
        skip_missing=True,
    )
    bulk_delete_spy.assert_not_called()


def test_delete_nonexistent_asset(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    with pytest.raises(NotFoundError) as excinfo:
        delete(
            [
                f"dandi://{instance}/{dandiset_id}/file.txt",
                f"dandi://{instance}/{dandiset_id}/subdir3/mango.txt",
            ],
            dandi_instance=instance,
            devel_debug=True,
            force=True,
        )
    assert (
        str(excinfo.value)
        == f"No assets found for dandi://{instance}/{dandiset_id}/subdir3/mango.txt"
    )
    bulk_delete_spy.assert_not_called()


def test_delete_nonexistent_asset_skip_missing(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
    tmp_path: Path,
) -> None:
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    delete(
        [
            f"dandi://{instance}/{dandiset_id}/file.txt",
            f"dandi://{instance}/{dandiset_id}/subdir3/mango.txt",
        ],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
        skip_missing=True,
    )
    bulk_delete_spy.assert_called()
    download(text_dandiset.dandiset.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / dandiset_id / "dandiset.yaml",
        tmp_path / dandiset_id / "subdir1" / "apple.txt",
        tmp_path / dandiset_id / "subdir2" / "banana.txt",
        tmp_path / dandiset_id / "subdir2" / "coconut.txt",
    ]


def test_delete_nonexistent_asset_folder(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    with pytest.raises(NotFoundError) as excinfo:
        delete(
            [
                f"dandi://{instance}/{dandiset_id}/subdir1/",
                f"dandi://{instance}/{dandiset_id}/subdir3/",
            ],
            dandi_instance=instance,
            devel_debug=True,
            force=True,
        )
    assert (
        str(excinfo.value)
        == f"No assets found for dandi://{instance}/{dandiset_id}/subdir3/"
    )
    bulk_delete_spy.assert_not_called()


def test_delete_nonexistent_asset_folder_skip_missing(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
    tmp_path: Path,
) -> None:
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = text_dandiset.api.instance_id
    dandiset_id = text_dandiset.dandiset_id
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    delete(
        [
            f"dandi://{instance}/{dandiset_id}/subdir1/",
            f"dandi://{instance}/{dandiset_id}/subdir3/",
        ],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
        skip_missing=True,
    )
    bulk_delete_spy.assert_called()
    download(text_dandiset.dandiset.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / dandiset_id / "dandiset.yaml",
        tmp_path / dandiset_id / "file.txt",
        tmp_path / dandiset_id / "subdir2" / "banana.txt",
        tmp_path / dandiset_id / "subdir2" / "coconut.txt",
    ]


def test_delete_version(
    local_dandi_api: DandiAPI, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    local_dandi_api.monkeypatch_set_api_key_env(monkeypatch)
    instance = local_dandi_api.instance_id
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    with pytest.raises(NotImplementedError) as excinfo:
        delete(
            [f"dandi://{instance}/999999@draft"],
            dandi_instance=instance,
            devel_debug=True,
            force=True,
        )
    assert str(excinfo.value) == (
        "DANDI API server does not support deletion of individual versions of a"
        " dandiset"
    )
    delete_spy.assert_not_called()


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "suffix", ["/acquisition/data_00000_AD0", "/acquisition/data_00000_AD0/"]
)
def test_delete_within_zarr_refused(mocker: MockerFixture, suffix: str) -> None:
    """A URL inside a Zarr asset must not delete the whole asset.

    `AssetZarrEntryURL.get_assets()` yields the Zarr asset itself, so without
    a guard the deletion would take every entry, not the named ones.
    """
    post_spy = mocker.spy(RESTFullAPIClient, "post")
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    with pytest.raises(NotImplementedError) as excinfo:
        delete(
            [f"dandi://dandi/000108/sub-1/file.ome.zarr{suffix}"],
            dandi_instance="dandi",
            devel_debug=True,
            force=True,
        )
    assert "Cannot delete individual entries within a Zarr asset" in str(excinfo.value)
    post_spy.assert_not_called()
    delete_spy.assert_not_called()


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "url",
    [
        "dandi://dandi/000108@0.210812.1448/sub-1/file.nwb",
        "dandi://dandi/000108@0.210812.1448/sub-1/",
        "https://api.dandiarchive.org/api/dandisets/000108/versions/0.210812.1448"
        "/assets/9e1a4a8d-fb5d-4a0f-9a0d-6d6ec5bc4b61/",
        "https://api.dandiarchive.org/api/dandisets/000108/versions/0.210812.1448"
        "/assets/?path=sub-1",
    ],
)
def test_delete_published_version_assets_refused(
    mocker: MockerFixture, url: str
) -> None:
    """Asset URLs naming a published version are rejected before any request.

    Published versions share asset IDs with the draft, so deleting the assets
    found in the published version would remove them from the draft.
    """
    request_spy = mocker.spy(RESTFullAPIClient, "request")
    with pytest.raises(NotImplementedError) as excinfo:
        delete([url], dandi_instance="dandi", devel_debug=True, force=True)
    assert str(excinfo.value) == (
        "Cannot delete assets from published version 0.210812.1448 of Dandiset"
        " 000108; only the draft version can be modified.  Use a URL for the"
        " draft version or one without a version."
    )
    request_spy.assert_not_called()


@pytest.mark.ai_generated
def test_delete_non_draft_assets_not_deleted(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    text_dandiset: SampleDandiset,
) -> None:
    """`Deleter.process_assets()` never sends a non-draft asset's ID to the
    draft; it reports an error for it and still deletes the other assets."""
    dandiset = text_dandiset.dandiset
    deleter = delete_mod.Deleter(client=dandiset.client, dandiset=dandiset)
    published = dandiset.get_asset_by_path("file.txt").model_copy(
        update={"version_id": "0.210812.1448"}
    )
    other = dandiset.get_asset_by_path("subdir1/apple.txt")
    deleter.add_asset(published)
    deleter.add_asset(other)
    post_spy = mocker.spy(RESTFullAPIClient, "post")
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    records = {r["path"]: r for r in deleter.process_assets()}
    assert records == {
        "file.txt": {
            "path": "file.txt",
            "status": "Error",
            "message": (
                f"Asset belongs to {dandiset.identifier}/0.210812.1448,"
                f" not {dandiset.identifier}/{DRAFT}"
            ),
        },
        "subdir1/apple.txt": {"path": "subdir1/apple.txt", "status": "Deleted"},
    }
    sent_ids = [
        aid for c in post_spy.call_args_list for aid in c.kwargs["json"]["asset_ids"]
    ] + [c.args[1].rstrip("/").rsplit("/", 1)[-1] for c in delete_spy.call_args_list]
    assert published.identifier not in sent_ids
    assert other.identifier in sent_ids
    assert {a.path for a in dandiset.get_assets()} == {
        "file.txt",
        "subdir2/banana.txt",
        "subdir2/coconut.txt",
    }


@pytest.mark.ai_generated
@pytest.mark.parametrize("suffix", ["", "/"])
def test_delete_zarr_url_at_boundary(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    zarr_dandiset: SampleDandiset,
    tmp_path: Path,
    suffix: str,
) -> None:
    """A URL ending *at* a Zarr deletes the asset, with or without a slash.

    The trailing-slash spelling used to fail with `NotFoundError`, since
    `AssetFolderURL` could never match the asset's own slash-less path.  It now
    names the asset, like the slash-less spelling always has -- including for
    the GUI's "browse to this Zarr" URL, whose trailing slash the parser adds.
    """
    zarr_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = zarr_dandiset.api.instance_id
    # The asset is deleted with a bulk deletion request, or with a single-asset
    # deletion request on servers without bulk deletion
    post_spy = mocker.spy(RESTFullAPIClient, "post")
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    delete(
        [f"dandi://{instance}/{zarr_dandiset.dandiset_id}/sample.zarr{suffix}"],
        dandi_instance=instance,
        devel_debug=True,
        force=True,
    )
    assert post_spy.called or delete_spy.called
    download(zarr_dandiset.dandiset.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / zarr_dandiset.dandiset_id / "dandiset.yaml"
    ]


def test_delete_no_dandiset(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    with pytest.raises(RuntimeError) as excinfo:
        delete(
            ["dir/file.txt"],
            dandi_instance="dandi",
            devel_debug=True,
            force=True,
        )
    assert str(excinfo.value) == (
        f"Found no {dandiset_metadata_file} anywhere.  "
        "Use 'dandi download' or 'organize' first"
    )
    bulk_delete_spy.assert_not_called()


def test_delete_zarr_path(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    zarr_dandiset: SampleDandiset,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(zarr_dandiset.dspath)
    zarr_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    instance = zarr_dandiset.api.instance_id
    bulk_delete_spy = mocker.spy(RESTFullAPIClient, "post")
    delete(["sample.zarr"], dandi_instance=instance, devel_debug=True, force=True)
    bulk_delete_spy.assert_called()
    download(zarr_dandiset.dandiset.version_api_url, tmp_path)
    assert list_paths(tmp_path) == [
        tmp_path / zarr_dandiset.dandiset_id / "dandiset.yaml"
    ]


def _debug_records(output: str) -> dict[str, dict]:
    """Parse the status records printed by ``delete(..., devel_debug=True)``"""
    records = [ast.literal_eval(line) for line in output.splitlines() if line]
    return {r["path"]: r for r in records}


@pytest.mark.ai_generated
def test_delete_multiple_batches(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    monkeypatch.setattr(delete_mod, "BULK_DELETE_BATCH_SIZE", 2)
    supported = bulk_delete_supported(text_dandiset.dandiset)
    post_spy = mocker.spy(RESTFullAPIClient, "post")
    delete_spy = mocker.spy(RESTFullAPIClient, "delete")
    # Discard output from setting up the Dandiset
    capsys.readouterr()
    delete(
        ["file.txt", "subdir1", "subdir2"],
        dandi_instance=text_dandiset.api.instance_id,
        devel_debug=True,
        force=True,
    )
    bulk_calls = [c for c in post_spy.call_args_list if "/bulk-delete/" in c.args[1]]
    if supported:
        # One bulk deletion request per batch
        assert len(bulk_calls) == 2
        assert delete_spy.call_count == 0
    else:
        # The bulk deletion endpoint is only tried for the first batch, after
        # which the assets are deleted one at a time
        assert len(bulk_calls) == 1
        assert delete_spy.call_count == 4
    records = _debug_records(capsys.readouterr().out)
    assert {p: r["status"] for p, r in records.items()} == {
        "file.txt": "Deleted",
        "subdir1/apple.txt": "Deleted",
        "subdir2/banana.txt": "Deleted",
        "subdir2/coconut.txt": "Deleted",
    }
    assert list(text_dandiset.dandiset.get_assets()) == []


@pytest.mark.ai_generated
def test_delete_asset_deleted_concurrently(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    gone = text_dandiset.dandiset.get_asset_by_path("subdir2/banana.txt")

    def confirm(_msg: str) -> bool:
        # Confirmation is requested after the assets have been looked up and
        # before any are deleted, so delete one of them in the meantime
        gone.delete()
        return True

    mocker.patch("click.confirm", side_effect=confirm)
    # Discard output from setting up the Dandiset
    capsys.readouterr()
    delete(["subdir2"], dandi_instance=text_dandiset.api.instance_id, devel_debug=True)
    records = _debug_records(capsys.readouterr().out)
    assert records == {
        "subdir2/banana.txt": {
            "path": "subdir2/banana.txt",
            "status": "Skipped",
            "message": "already absent",
        },
        "subdir2/coconut.txt": {"path": "subdir2/coconut.txt", "status": "Deleted"},
    }
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert sorted(a.path for a in text_dandiset.dandiset.get_assets()) == [
        "file.txt",
        "subdir1/apple.txt",
    ]


@pytest.mark.ai_generated
def test_delete_failed_batch_continues(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    monkeypatch.setattr(delete_mod, "BULK_DELETE_BATCH_SIZE", 2)
    real_delete_asset_batch = RemoteDandiset._delete_asset_batch
    calls = 0

    def flaky_delete_asset_batch(
        self: RemoteDandiset, *args: Any, **kwargs: Any
    ) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        return real_delete_asset_batch(self, *args, **kwargs)

    monkeypatch.setattr(RemoteDandiset, "_delete_asset_batch", flaky_delete_asset_batch)
    # Discard output from setting up the Dandiset
    capsys.readouterr()
    delete(
        ["file.txt", "subdir1", "subdir2"],
        dandi_instance=text_dandiset.api.instance_id,
        devel_debug=True,
        force=True,
    )
    records = _debug_records(capsys.readouterr().out)
    assert {p: (r["status"], r.get("message")) for p, r in records.items()} == {
        "file.txt": ("Error", "RuntimeError: boom"),
        "subdir1/apple.txt": ("Error", "RuntimeError: boom"),
        "subdir2/banana.txt": ("Deleted", None),
        "subdir2/coconut.txt": ("Deleted", None),
    }
    assert sorted(a.path for a in text_dandiset.dandiset.get_assets()) == [
        "file.txt",
        "subdir1/apple.txt",
    ]


@pytest.mark.ai_generated
def test_delete_bulk_reports_per_asset(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    # Emulate a server with the bulk deletion endpoint, whatever the server
    # actually is, so that reporting the results of successful bulk deletion
    # requests is always exercised
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    monkeypatch.setattr(delete_mod, "BULK_DELETE_BATCH_SIZE", 2)

    def fake_bulk_delete_assets(
        self: RemoteDandiset, asset_ids: list[str]
    ) -> list[str]:
        # Delete those of the assets that belong to the version and return
        # their IDs, as the endpoint does
        removed = []
        for aid in asset_ids:
            try:
                self.client.delete(
                    f"{self.version_api_path}assets/{aid}/", quiet_statuses=[404]
                )
            except HTTP404Error:
                continue
            removed.append(aid)
        return removed

    bulk_delete = mocker.patch.object(
        RemoteDandiset,
        "_bulk_delete_assets",
        autospec=True,
        side_effect=fake_bulk_delete_assets,
    )
    dandiset = text_dandiset.dandiset
    gone = dandiset.get_asset_by_path("subdir1/apple.txt")

    def confirm(_msg: str) -> bool:
        # Confirmation is requested after the assets have been looked up and
        # before any are deleted, so delete one of them in the meantime
        dandiset.client.delete(f"{dandiset.version_api_path}assets/{gone.identifier}/")
        return True

    mocker.patch("click.confirm", side_effect=confirm)
    # Discard output from setting up the Dandiset
    capsys.readouterr()
    delete(
        ["file.txt", "subdir1", "subdir2"],
        dandi_instance=text_dandiset.api.instance_id,
        devel_debug=True,
    )
    assert bulk_delete.call_count == 2
    records = _debug_records(capsys.readouterr().out)
    assert {p: (r["status"], r.get("message")) for p, r in records.items()} == {
        "file.txt": ("Deleted", None),
        "subdir1/apple.txt": ("Skipped", "already absent"),
        "subdir2/banana.txt": ("Deleted", None),
        "subdir2/coconut.txt": ("Deleted", None),
    }
    assert list(dandiset.get_assets()) == []


@pytest.mark.ai_generated
def test_delete_fallback_reports_per_asset(
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    text_dandiset: SampleDandiset,
) -> None:
    monkeypatch.chdir(text_dandiset.dspath)
    text_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    monkeypatch.setattr(delete_mod, "BULK_DELETE_BATCH_SIZE", 2)
    # Simulate a server that does not support bulk deletion
    bulk_delete = mocker.patch.object(
        RemoteDandiset,
        "_bulk_delete_assets",
        side_effect=BulkDeleteUnsupportedError("no bulk deletion"),
    )
    dandiset = text_dandiset.dandiset
    gone = dandiset.get_asset_by_path("subdir2/banana.txt")
    failing = dandiset.get_asset_by_path("file.txt")
    real_delete = RESTFullAPIClient.delete

    def flaky_delete(self: RESTFullAPIClient, path: str, **kwargs: Any) -> Any:
        if path.endswith(f"/assets/{failing.identifier}/"):
            raise requests.HTTPError("boom")
        return real_delete(self, path, **kwargs)

    monkeypatch.setattr(RESTFullAPIClient, "delete", flaky_delete)

    def confirm(_msg: str) -> bool:
        # Confirmation is requested after the assets have been looked up and
        # before any are deleted, so delete one of them in the meantime
        dandiset.client.delete(f"{dandiset.version_api_path}assets/{gone.identifier}/")
        return True

    mocker.patch("click.confirm", side_effect=confirm)
    # Discard output from setting up the Dandiset
    capsys.readouterr()
    delete(
        ["file.txt", "subdir1", "subdir2"],
        dandi_instance=text_dandiset.api.instance_id,
        devel_debug=True,
    )
    # The bulk deletion endpoint is only tried for the first batch
    assert bulk_delete.call_count == 1
    records = _debug_records(capsys.readouterr().out)
    # A failure only affects the asset concerned, even within the first batch
    assert {p: (r["status"], r.get("message")) for p, r in records.items()} == {
        "file.txt": ("Error", "HTTPError: boom"),
        "subdir1/apple.txt": ("Deleted", None),
        "subdir2/banana.txt": ("Skipped", "already absent"),
        "subdir2/coconut.txt": ("Deleted", None),
    }
    assert [a.path for a in dandiset.get_assets()] == ["file.txt"]


@pytest.mark.parametrize(
    "url1,url2,r",
    [
        ("https://example.com/api", "https://example.com/api/", True),
        ("https://example.com/api", "http://example.com/api", False),
        ("https://example.com/api", "HTTPS://EXAMPLE.COM/api", True),
        ("https://example.珠宝/api", "https://example.xn--pbt977c/api", True),
    ],
)
def test_is_same_url(url1: str, url2: str, r: bool) -> None:
    assert is_same_url(url1, url2) is r
