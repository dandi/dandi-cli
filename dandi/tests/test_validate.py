import cv2
import numpy as np
import pytest

from ..validate import validate_file


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
