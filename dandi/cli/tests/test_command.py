import sys
from subprocess import Popen, PIPE

from ..command import ls, validate

from click.testing import CliRunner
import pytest


@pytest.mark.parametrize("command", (ls, validate))
def test_smoke(simple1_nwb, command):
    runner = CliRunner()
    r = runner.invoke(command, [simple1_nwb])
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    assert r.stdout, "There were no output whatsoever"

    # empty invocation should not crash
    r = runner.invoke(command, [])
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"


def test_no_heavy_imports():
    # Timing --version for being fast is unreliable, so we will verify that
    # no h5py or numpy (just in case) module is imported upon import of the
    # command
    heavy_modules = {"pynwb", "h5py", "numpy"}
    p = Popen(
        [
            sys.executable,
            "-c",
            "import sys; "
            "import dandi.cli.command; "
            "print(','.join(set(m.split('.')[0] for m in sys.modules)));",
        ],
        stdout=PIPE,
        stderr=PIPE,
    )
    stdout, stderr = p.communicate()
    modules = stdout.decode().split(",")
    loaded_heavy = set(modules).intersection(heavy_modules)

    assert not loaded_heavy
    assert not stderr
    assert not p.wait()
