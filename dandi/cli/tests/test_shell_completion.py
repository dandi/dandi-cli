import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which("bash") is None, reason="Bash required")
def test_shell_completion_sourceable():
    subprocess.run(["bash", "-c", "source <(dandi shell-completion)"], check=True)
