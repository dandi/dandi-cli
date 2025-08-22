# Largely a helper to quickly trigger fixtures to smoke test them
# and possibly go through their internal asserts

from pathlib import Path
import sys

import pytest


def test_organized_nwb_dir(organized_nwb_dir: Path) -> None:
    pass  # Just a smoke test to trigger fixture's asserts


@pytest.mark.xfail(
    condition=sys.platform == "win32" and sys.version_info >= (3, 13),
    reason="Fails on Windows with Python 3.13 due to _posixsubprocess module error",
    raises=AssertionError,
    strict=False,
)
def test_organized_nwb_dir2(organized_nwb_dir2: Path) -> None:
    pass  # Just a smoke test to trigger fixture's asserts
