from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from dandischema.models import DigestType


@dataclass
class Digest:
    """A computed digest for a file or directory"""

    #: The digest algorithm used
    algorithm: DigestType

    #: The digest itself
    value: str

    @classmethod
    def dandi_etag(cls, value: str) -> Digest:
        """
        Construct a `Digest` with the given value and a ``algorithm`` of
        ``DigestType.dandi_etag``
        """
        return cls(algorithm=DigestType.dandi_etag, value=value)

    @classmethod
    def dandi_zarr(cls, value: str) -> Digest:
        """
        Construct a `Digest` with the given value and a ``algorithm`` of
        ``DigestType.dandi_zarr_checksum``
        """
        return cls(algorithm=DigestType.dandi_zarr_checksum, value=value)

    def asdict(self) -> Dict[DigestType, str]:
        """
        Convert the instance to a single-item `dict` mapping the digest
        algorithm to the digest value
        """
        return {self.algorithm: self.value}


DUMMY_DIGEST = Digest(algorithm=DigestType.dandi_etag, value=32 * "d" + "-1")
