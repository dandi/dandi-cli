from __future__ import annotations

from typing import Any

import click
from click.testing import CliRunner
import pytest
from pytest_mock import MockerFixture

from ..command import move


@pytest.mark.parametrize(
    "cmdline,srcs,kwargs",
    [
        (
            ["src.txt", "dest/"],
            ["src.txt"],
            {
                "dest": "dest/",
                "dandiset": None,
                "dry_run": False,
                "existing": "error",
                "jobs": None,
                "regex": False,
                "work_on": "auto",
                "dandi_instance": "dandi",
                "devel_debug": False,
            },
        ),
        (
            ["src.txt", "other.txt", "dest/"],
            ["src.txt", "other.txt"],
            {
                "dest": "dest/",
                "dandiset": None,
                "dry_run": False,
                "existing": "error",
                "jobs": None,
                "regex": False,
                "work_on": "auto",
                "dandi_instance": "dandi",
                "devel_debug": False,
            },
        ),
        (
            [
                "-d",
                "DANDI:000027",
                "--existing=skip",
                "--dry-run",
                "--jobs",
                "5",
                "--regex",
                "--work-on=remote",
                "--dandi-instance",
                "dandi-staging",
                "src.txt",
                "dest/",
            ],
            ["src.txt"],
            {
                "dest": "dest/",
                "dandiset": "DANDI:000027",
                "dry_run": True,
                "existing": "skip",
                "jobs": 5,
                "regex": True,
                "work_on": "remote",
                "dandi_instance": "dandi-staging",
                "devel_debug": False,
            },
        ),
    ],
)
def test_move_command(
    mocker: MockerFixture, cmdline: list[str], srcs: list[str], kwargs: dict[str, Any]
) -> None:
    mock_move = mocker.patch("dandi.move.move")
    r = CliRunner().invoke(move, cmdline)
    assert r.exit_code == 0
    mock_move.assert_called_once_with(*srcs, **kwargs)


def test_move_command_too_few_paths(mocker: MockerFixture) -> None:
    mock_move = mocker.patch("dandi.move.move")
    r = CliRunner().invoke(move, ["foo"], standalone_mode=False)
    assert r.exit_code != 0
    # This is a ClickException when map_to_click_exceptions is in effect and a
    # ValueError when it's not (which happens when DANDI_DEVEL is set).
    assert isinstance(r.exception, (click.ClickException, ValueError))
    assert str(r.exception) == "At least two paths are required"
    mock_move.assert_not_called()
