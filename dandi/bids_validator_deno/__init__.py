"""Package providing an interface to the deno-compiled BIDS validator"""

from ._validator import bids_validate, get_version

__all__ = ["bids_validate", "get_version"]


def __dir__() -> list[str]:
    return list(__all__)  # return a copy of `__all__` to avoid modifying the original
