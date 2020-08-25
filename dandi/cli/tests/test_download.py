import os
import click
from click.testing import CliRunner
from ..command import download


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
