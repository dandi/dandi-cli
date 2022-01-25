import cv2
from dandischema.models import get_schema_version
import numpy as np
import pytest

from ..validate import validate_file


def test_validate_simple1(simple1_nwb):
    # this file should be ok
    errors = validate_file(simple1_nwb, schema_version=get_schema_version())
    assert not errors


def test_validate_simple2(simple2_nwb):
    # this file should be ok
    errors = validate_file(simple2_nwb)
    assert not errors


def test_validate_simple2_new(simple2_nwb):
    # this file should be ok
    errors = validate_file(simple2_nwb, schema_version=get_schema_version())
    assert not errors


def test_validate_bogus(tmp_path):
    path = tmp_path / "wannabe.nwb"
    path.write_text("not really nwb")
    # intended to produce use-case for https://github.com/dandi/dandi-cli/issues/93
    # but it would be tricky, so it is more of a smoke test that
    # we do not crash
    errors = validate_file(str(path))
    # ATM we would get 2 errors -- since could not be open in two places,
    # but that would be too rigid to test. Let's just see that we have expected errors
    assert any(e.startswith("Failed to read metadata") for e in errors)


@pytest.mark.parametrize("no_frames", [10, 0])
def test_validate_movie(tmp_path, no_frames):
    frame_size = (10, 10)
    movie_loc = tmp_path / "movie.avi"
    writer1 = cv2.VideoWriter(
        filename=str(movie_loc),
        apiPreference=None,
        fourcc=cv2.VideoWriter_fourcc(*"DIVX"),
        fps=25,
        frameSize=frame_size,
        params=None,
    )
    for i in range(no_frames):
        writer1.write(np.random.randint(0, 255, (*frame_size, 3)).astype("uint8"))
    writer1.release()
    errors = validate_file(movie_loc)
    if no_frames == 0:
        assert errors[0] == f"no frames in video file {movie_loc}"
    else:
        assert not errors
