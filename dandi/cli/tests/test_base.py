from enum import StrEnum
import os
from pathlib import Path

import click
from click.testing import CliRunner
import pytest

from ..base import EnumChoice, LinkAwarePath


class _Existing(StrEnum):
    ERROR = "error"
    SKIP = "skip"
    OVERWRITE = "overwrite-different"


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


@pytest.mark.ai_generated
def test_path_lexists_rejects_resolve_path():
    with pytest.raises(ValueError, match="resolve_path"):
        LinkAwarePath(lexists=True, resolve_path=True)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "kwargs,broken_ok",
    [
        ({"lexists": True}, True),
        ({"lexists": True, "exists": True}, False),
        ({"exists": True}, False),
    ],
)
def test_path_lexists(tmp_path: Path, kwargs: dict, broken_ok: bool) -> None:
    @click.command()
    @click.argument("path", type=LinkAwarePath(allow_dash=True, **kwargs))
    def cmd(path):
        click.echo(f"got:{path}")

    (tmp_path / "file.txt").write_text("content")
    broken = tmp_path / "broken"
    try:
        os.symlink(tmp_path / "missing", broken)
    except OSError:
        pytest.skip("symlinks are not supported here")
    for ok in [str(tmp_path / "file.txt"), "-"] + ([str(broken)] if broken_ok else []):
        r = CliRunner().invoke(cmd, [ok])
        assert r.exit_code == 0, r.output
        assert r.output == f"got:{ok}\n"
    for bad in [str(tmp_path / "missing")] + ([] if broken_ok else [str(broken)]):
        r = CliRunner().invoke(cmd, [bad])
        assert r.exit_code == 2
        assert f"Path {bad!r} does not exist." in r.output
