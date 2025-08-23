# Largely a helper to quickly trigger fixtures to smoke test them
# and possibly go through their internal asserts

from pathlib import Path

from .xfail import mark_xfail_windows_python313_posixsubprocess


def test_organized_nwb_dir(organized_nwb_dir: Path) -> None:
    pass  # Just a smoke test to trigger fixture's asserts


@mark_xfail_windows_python313_posixsubprocess
def test_organized_nwb_dir2(organized_nwb_dir2: Path) -> None:
    pass  # Just a smoke test to trigger fixture's asserts
