import os
from pathlib import Path

import click
from click.testing import CliRunner
import pytest

from ..command import download
from ...consts import dandiset_metadata_file


def test_download_defaults(mocker):
    mock_download = mocker.patch("dandi.download.download")
    r = CliRunner().invoke(download)
    assert r.exit_code == 0
    mock_download.assert_called_once_with(
        (),
        os.curdir,
        existing="refresh",
        format="pyout",
        jobs=6,
        get_metadata=True,
        get_assets=True,
    )


def test_download_all_types(mocker):
    mock_download = mocker.patch("dandi.download.download")
    r = CliRunner().invoke(download, ["--download", "all"])
    assert r.exit_code == 0
    mock_download.assert_called_once_with(
        (),
        os.curdir,
        existing="refresh",
        format="pyout",
        jobs=6,
        get_metadata=True,
        get_assets=True,
    )


def test_download_metadata_only(mocker):
    mock_download = mocker.patch("dandi.download.download")
    r = CliRunner().invoke(download, ["--download", "dandiset.yaml"])
    assert r.exit_code == 0
    mock_download.assert_called_once_with(
        (),
        os.curdir,
        existing="refresh",
        format="pyout",
        jobs=6,
        get_metadata=True,
        get_assets=False,
    )


def test_download_assets_only(mocker):
    mock_download = mocker.patch("dandi.download.download")
    r = CliRunner().invoke(download, ["--download", "assets"])
    assert r.exit_code == 0
    mock_download.assert_called_once_with(
        (),
        os.curdir,
        existing="refresh",
        format="pyout",
        jobs=6,
        get_metadata=False,
        get_assets=True,
    )


def test_download_bad_type(mocker):
    mock_download = mocker.patch("dandi.download.download")
    r = CliRunner().invoke(download, ["--download", "foo"], standalone_mode=False)
    assert r.exit_code != 0
    assert isinstance(r.exception, click.UsageError)
    assert str(r.exception) == "'foo': invalid value"
    mock_download.assert_not_called()


@pytest.mark.skipif(
    not os.environ.get("DANDI_DEVEL"), reason="DANDI_DEVEL required to run"
)
def test_download_gui_instance_in_dandiset(mocker):
    mock_download = mocker.patch("dandi.download.download")
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path(dandiset_metadata_file).write_text("identifier: '123456'\n")
        r = runner.invoke(download, ["-i", "dandi"])
    assert r.exit_code == 0
    mock_download.assert_called_once_with(
        ["https://gui.dandiarchive.org/#/dandiset/123456/draft"],
        os.curdir,
        existing="refresh",
        format="pyout",
        jobs=6,
        get_metadata=True,
        get_assets=True,
    )


@pytest.mark.skipif(
    not os.environ.get("DANDI_DEVEL"), reason="DANDI_DEVEL required to run"
)
def test_download_api_instance_in_dandiset(mocker):
    mock_download = mocker.patch("dandi.download.download")
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path(dandiset_metadata_file).write_text("identifier: '123456'\n")
        r = runner.invoke(download, ["-i", "dandi-api-local-docker-tests"])
    assert r.exit_code == 0
    mock_download.assert_called_once_with(
        ["http://localhost:8000/api/dandisets/123456/"],
        os.curdir,
        existing="refresh",
        format="pyout",
        jobs=6,
        get_metadata=True,
        get_assets=True,
    )


@pytest.mark.skipif(
    not os.environ.get("DANDI_DEVEL"), reason="DANDI_DEVEL required to run"
)
def test_download_url_instance_match(mocker):
    mock_download = mocker.patch("dandi.download.download")
    r = CliRunner().invoke(
        download,
        [
            "-i",
            "dandi-api-local-docker-tests",
            "http://localhost:8000/api/dandisets/123456/",
        ],
    )
    assert r.exit_code == 0
    mock_download.assert_called_once_with(
        ("http://localhost:8000/api/dandisets/123456/",),
        os.curdir,
        existing="refresh",
        format="pyout",
        jobs=6,
        get_metadata=True,
        get_assets=True,
    )


@pytest.mark.skipif(
    not os.environ.get("DANDI_DEVEL"), reason="DANDI_DEVEL required to run"
)
def test_download_url_instance_conflict(mocker):
    mock_download = mocker.patch("dandi.download.download")
    r = CliRunner().invoke(
        download,
        ["-i", "dandi", "http://localhost:8000/api/dandisets/123456/"],
        standalone_mode=False,
    )
    assert r.exit_code != 0
    assert isinstance(r.exception, click.UsageError)
    assert (
        str(r.exception)
        == "http://localhost:8000/api/dandisets/123456/ does not point to 'dandi' instance"
    )
    mock_download.assert_not_called()
