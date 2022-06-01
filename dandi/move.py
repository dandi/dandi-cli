from pathlib import Path
from typing import Union


def move(
    *srcs: str,
    dest: str,
    regex: bool = False,
    existing: str = "error",
    dandi_instance: str = "dandi",
    dandiset: Union[Path, str, None] = None,
    work_on: str = "auto",
) -> None:
    ...
