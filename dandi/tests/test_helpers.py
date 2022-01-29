from operator import attrgetter
from pathlib import Path


# This needs to be in a file named "test_*.py" so that pytest performs its
# assertion rewriting on it.
def assert_dirtrees_eq(tree1: Path, tree2: Path) -> None:
    """Assert that the file trees at the given paths are equal"""
    assert sorted(map(attrgetter("name"), tree1.iterdir())) == sorted(
        map(attrgetter("name"), tree2.iterdir())
    )
    for p1 in tree1.iterdir():
        p2 = tree2 / p1.name
        assert p1.is_dir() == p2.is_dir()
        if p1.is_dir():
            assert_dirtrees_eq(p1, p2)
        # TODO: Considering using the identify library to test for binary-ness.
        # (We can't use mimetypes, as .json maps to application/json instead of
        # text/json.)
        elif p1.suffix in {".txt", ".py", ".json"}:
            assert p1.read_text() == p2.read_text()
        else:
            assert p1.read_bytes() == p2.read_bytes()
