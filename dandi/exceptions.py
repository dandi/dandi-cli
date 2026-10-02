"""Custom exceptions for DANDI CLI operations.

This module defines exception classes used throughout the DANDI CLI for
handling various error conditions including network errors, validation
failures, and version incompatibilities.
"""

from __future__ import annotations

import requests
from semantic_version import Version


class OrganizeImpossibleError(ValueError):
    """Exception to be raised if given current list of files it is impossible

    E.g. if metadata is not sufficient or conflicting
    """

    pass


class UnknownURLError(ValueError):
    """Given url is not known to correspond to DANDI schema(s)"""

    pass


class NotFoundError(RuntimeError):
    """Online resource which we tried to connect to is not found"""

    pass


class FailedToConnectError(RuntimeError):
    """Failed to connect to online resource"""

    pass


class LockingError(RuntimeError):
    """Failed to lock or unlock a resource"""

    pass


class CliVersionError(RuntimeError):
    """Base class for `CliVersionTooOldError` and `BadCliVersionError`"""

    def __init__(
        self, our_version: Version, minversion: Version, bad_versions: list[Version]
    ) -> None:
        self.our_version = our_version
        self.minversion = minversion
        self.bad_versions = bad_versions

    def server_requirements(self) -> str:
        s = f"Server requires at least version {self.minversion}"
        if self.bad_versions:
            s += f" (but not {', '.join(map(str, self.bad_versions))})"
        return s


class CliVersionTooOldError(CliVersionError):
    def __str__(self) -> str:
        return (
            f"Client version {self.our_version} is too old!  "
            + self.server_requirements()
        )


class BadCliVersionError(CliVersionError):
    def __str__(self) -> str:
        return (
            f"Client version {self.our_version} is rejected by server!  "
            + self.server_requirements()
        )


class SchemaVersionError(Exception):
    pass


class UnknownAssetError(ValueError):
    pass


class HTTP404Error(requests.HTTPError):
    pass


class UploadError(Exception):
    pass


class BlobExistsError(UploadError):
    """
    Raised when the archive reports, via an HTTP 409 from the ``initialize``
    endpoint of a multipart upload, that the blob being uploaded is already
    present.  Only that endpoint identifies the existing blob; a 409 from any
    other point of an upload is an ordinary error and propagates as such.
    """

    def __init__(self, blob_id: str) -> None:
        super().__init__(f"Blob already exists on server with ID {blob_id}")
        #: The ID of the pre-existing blob, from the response's ``Location``
        #: header
        self.blob_id = blob_id


class UploadValidationError(UploadError):
    """An upload could not proceed because an asset failed validation."""

    pass
