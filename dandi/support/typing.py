import sys

if sys.version_info >= (3, 8):
    from typing import Literal, TypedDict  # noqa: F401
else:
    from typing_extensions import Literal, TypedDict  # noqa: F401
