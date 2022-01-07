from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from dandischema.models import DigestType


@dataclass
class Digest:
    algorithm: DigestType
    value: str

    @classmethod
    def dandi_etag(cls, value: str) -> Digest:
        return cls(algorithm=DigestType.dandi_etag, value=value)

    def asdict(self) -> Dict[DigestType, str]:
        return {self.algorithm: self.value}


DUMMY_DIGEST = Digest(algorithm=DigestType.dandi_etag, value=32 * "d" + "-1")
