import sys

if sys.version_info >= (3, 8):
    from typing import Literal, Protocol, TypedDict  # noqa: F401
else:
    from typing_extensions import Literal, Protocol, TypedDict  # noqa: F401
