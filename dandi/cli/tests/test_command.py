import os
import re
from subprocess import PIPE, Popen
import sys

from click.testing import CliRunner
import pytest

from ..command import __all_commands__, ls, validate


@pytest.mark.parametrize("command", (ls, validate))
def test_smoke(simple2_nwb, command):
    runner = CliRunner()
    r = runner.invoke(command, [simple2_nwb])
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    assert r.stdout, "There were no output whatsoever"

    # empty invocation should not crash
    # But we must cd to the temp directory since current directory could
    # have all kinds of files which could trip the command, e.g. validate
    # could find some broken test files in the code base
    with runner.isolated_filesystem():
        r = runner.invoke(command, [])
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"


@pytest.mark.parametrize("command", __all_commands__)
def test_smoke_help(command):
    runner = CliRunner()
    r = runner.invoke(command, ["--help"])
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    assert r.stdout, "There were no output whatsoever"

    assert re.match("Usage: .*Options:.*--help", r.stdout, flags=re.DOTALL) is not None


def test_no_heavy_imports():
    # Timing --version for being fast is unreliable, so we will verify that
    # no h5py or numpy (just in case) module is imported upon import of the
    # command
    heavy_modules = {"pynwb", "h5py", "numpy"}
    env = os.environ.copy()
    env["NO_ET"] = "1"
    p = Popen(
        [
            sys.executable,
            "-c",
            "import sys; "
            "import dandi.cli.command; "
            "print(','.join(set(m.split('.')[0] for m in sys.modules)));",
        ],
        env=env,
        stdout=PIPE,
        stderr=PIPE,
    )
    stdout, stderr = p.communicate()
    modules = stdout.decode().split(",")
    loaded_heavy = set(modules).intersection(heavy_modules)

    assert not loaded_heavy
    assert not stderr or b"Failed to check" in stderr or b"dandi version" in stderr
    assert not p.wait()
