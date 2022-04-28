import os
import shutil
import subprocess

import pytest

from ...utils import on_windows


# Process substitution is apparently broken on certain older versions of Bash
# on Windows, which includes the version used by conda-forge as of 2021-07-08,
# so we need to skip this test entirely on Windows.
@pytest.mark.skipif(
    shutil.which("bash") is None or on_windows, reason="Bash on POSIX required"
)
def test_shell_completion_sourceable():
    subprocess.run(
        ["bash", "-c", "source <(dandi shell-completion)"],
        check=True,
        # When testing for conda-forge on Windows, SHELL doesn't seem to be
        # set, so we need to set it ourselves:
        env={**os.environ, "SHELL": shutil.which("bash")},
    )
