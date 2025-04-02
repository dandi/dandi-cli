from typing import Any

from pydantic import RootModel


class BidsValidationResult(RootModel):
    root: dict[str, Any]
