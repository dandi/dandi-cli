from enum import Enum

import click
from click.testing import CliRunner
import pytest

from ..base import EnumChoice


class _Existing(str, Enum):
    ERROR = "error"
    SKIP = "skip"
    OVERWRITE = "overwrite-different"

    def __str__(self) -> str:
        return self.value


def _make_command(**option_kwargs):
    @click.command()
    @click.option("--existing", type=EnumChoice(_Existing), **option_kwargs)
    def cmd(existing):
        click.echo(f"{type(existing).__name__}:{existing!r}")

    return cmd


@pytest.mark.ai_generated
def test_enum_choice_accepts_member_value():
    captured = {}

    @click.command()
    @click.option("--existing", type=EnumChoice(_Existing), default="error")
    def cmd(existing):
        captured["existing"] = existing

    r = CliRunner().invoke(cmd, ["--existing", "overwrite-different"])
    assert r.exit_code == 0, r.output
    assert captured["existing"] is _Existing.OVERWRITE


@pytest.mark.ai_generated
def test_enum_choice_rejects_member_name():
    r = CliRunner().invoke(_make_command(default="error"), ["--existing", "SKIP"])
    assert r.exit_code != 0
    assert "'SKIP' is not one of" in r.output


@pytest.mark.ai_generated
def test_enum_choice_none_default_passes_through():
    captured = {}

    @click.command()
    @click.option("--existing", type=EnumChoice(_Existing), default=None)
    def cmd(existing):
        captured["existing"] = existing

    r = CliRunner().invoke(cmd, [])
    assert r.exit_code == 0, r.output
    assert captured["existing"] is None


@pytest.mark.ai_generated
def test_enum_choice_string_default_converted_to_member():
    captured = {}

    @click.command()
    @click.option("--existing", type=EnumChoice(_Existing), default="skip")
    def cmd(existing):
        captured["existing"] = existing

    r = CliRunner().invoke(cmd, [])
    assert r.exit_code == 0, r.output
    assert captured["existing"] is _Existing.SKIP
