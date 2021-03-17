import pytest

from ..dandietag import DandiETag, mb, tb


@pytest.mark.parametrize(
    "file_size,initial_part_size,final_part_size,part_count",
    [
        (mb(64), mb(64), mb(64), 1),
        (mb(50), mb(50), mb(50), 1),
        (mb(70), mb(64), mb(6), 2),
        (mb(140), mb(64), mb(12), 3),
        (tb(5), 549755814, 549754694, 10000),
    ],
)
def test_gen_part_sizes(file_size, initial_part_size, final_part_size, part_count):
    sizes = DandiETag.gen_part_sizes(file_size)
    assert len(sizes) == part_count
    assert all(sz == initial_part_size for sz in sizes[:-1])
    assert sizes[-1] == final_part_size
