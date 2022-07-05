from click.testing import CliRunner
import pytest

from dandi.tests.fixtures import SampleDandiset

from ..command import service_scripts


def test_cancel_zarr_upload(
    monkeypatch: pytest.MonkeyPatch, new_dandiset: SampleDandiset
) -> None:
    client = new_dandiset.client
    asset_path = "foo/bar/baz.zarr"
    r = client.post(
        "/zarr/", json={"name": asset_path, "dandiset": new_dandiset.dandiset_id}
    )
    zarr_id = r["zarr_id"]
    client.post(
        f"{new_dandiset.dandiset.version_api_path}assets/",
        json={"metadata": {"path": asset_path}, "zarr_id": zarr_id},
    )
    client.post(
        f"/zarr/{zarr_id}/upload/",
        json=[
            {"path": "0.dat", "etag": "0" * 32},
            {"path": "1.dat", "etag": "1" * 32},
        ],
    )
    r = client.get(f"/zarr/{zarr_id}/")
    assert r["upload_in_progress"] is True

    (new_dandiset.dspath / "foo").mkdir()
    monkeypatch.chdir(new_dandiset.dspath / "foo")
    monkeypatch.setenv("DANDI_API_KEY", new_dandiset.api.api_key)

    r = CliRunner().invoke(
        service_scripts,
        ["cancel-zarr-upload", "-i", new_dandiset.api.instance_id, "bar/baz.zarr"],
    )
    assert r.exit_code == 0

    r = client.get(f"/zarr/{zarr_id}/")
    assert r["upload_in_progress"] is False
