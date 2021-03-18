import pytest

from ..dandietag import Part, PartGenerator, mb, tb


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
def test_part_generator(file_size, initial_part_size, final_part_size, part_count):
    pg = PartGenerator.for_file_size(file_size)
    assert pg == PartGenerator(part_count, initial_part_size, final_part_size)
    assert len(pg) == part_count
    parts = list(pg)
    assert [p.number for p in parts] == list(range(1, part_count + 1))
    assert all(p.size == initial_part_size for p in parts[:-1])
    assert parts[-1].size == final_part_size
    offset = 0
    for p in parts:
        assert p.offset == offset
        offset += p.size
    assert pg[1] == Part(1, 0, initial_part_size)
    assert pg[part_count] == Part(
        part_count, initial_part_size * (part_count - 1), final_part_size
    )
