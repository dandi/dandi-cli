import os
import shutil
import subprocess

import pytest

# In GitHub Actions' Windows environments, Bash is nominally present in the
# PATH, but it doesn't actually work when run, so we need to check for more
# than just `which`-ability.
if shutil.which("bash") is None:
    bash_works = False
else:
    r = subprocess.run(["bash", "--version"], capture_output=True, text=True)
    bash_works = r.returncode == 0 and "GNU" in r.stdout


@pytest.mark.skipif(not bash_works, reason="Bash required")
def test_shell_completion_sourceable():
    subprocess.run(
        ["bash", "-c", "source <(dandi shell-completion)"],
        check=True,
        # When testing for conda-forge on Windows, SHELL doesn't seem to be
        # set, so we need to set it ourselves:
        env={**os.environ, "SHELL": shutil.which("bash")},
    )
