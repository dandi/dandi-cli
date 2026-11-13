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


class AssetsNotFoundError(HTTP404Error):
    """
    An asset deletion request named assets that do not belong to the Dandiset
    version.  Other assets in the request may still have been deleted; see
    ``deleted_asset_ids``.

    Unlike with other HTTP errors, its ``response`` is always `None`:
    the bulk deletion endpoint reports missing assets in a successful
    response, and a single-asset deletion request may have been followed by
    others.
    """

    def __init__(
        self,
        msg: str,
        missing_asset_ids: set[str],
        deleted_asset_ids: list[str] | None = None,
    ) -> None:
        super().__init__(msg)
        #: The IDs of the requested assets that do not belong to the version
        self.missing_asset_ids = missing_asset_ids
        #: The IDs of the other assets in the same batch that were deleted
        #: before the error was raised
        self.deleted_asset_ids = (
            list(deleted_asset_ids) if deleted_asset_ids is not None else []
        )


class BulkDeleteUnsupportedError(HTTP404Error):
    """
    A bulk asset deletion request returned a 404, most likely because the
    server predates the bulk deletion endpoint
    """

    pass


class UploadError(Exception):
    pass


class UploadValidationError(UploadError):
    """An upload could not proceed because an asset failed validation."""

    pass
