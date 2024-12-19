"""
This module provides functionality for parsing URLs and other resource
identifiers for Dandisets & assets on DANDI instances and for fetching
the objects to which the URLs refer.  See :ref:`resource_ids` for a list of
accepted URL formats.

Basic operation begins by calling `parse_dandi_url()` on a URL in order to
acquire a `ParsedDandiURL` instance, which can then be used to obtain the
Dandiset and/or assets specified in the URL.  Call an instance's
`~ParsedDandiURL.get_dandiset()` and/or `~ParsedDandiURL.get_assets()` to get
the assets, passing in a `~dandi.dandiapi.DandiAPIClient` for the appropriate
DANDI API instance; an unauthenticated client pointing to the correct
instance can be acquired via the `~ParsedDandiURL.get_client()` method.  As a
convenience, one can acquire a client, the Dandiset, and an iterator of all
assets by using the `~ParsedDandiAPI.navigate()` context manager like so:

.. code:: python

    parsed_url = parse_dandi_url("https://...")
    with parsed_url.navigate() as (client, dandiset, assets):
        ...
    # The client's session is closed when the context manager exits.

As a further convenience, a URL can be parsed and navigated in one fell swoop
using the `navigate_url()` function.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
import posixpath
import re
from time import sleep
from typing import Any
from urllib.parse import unquote as urlunquote

from pydantic import AnyHttpUrl, TypeAdapter
import requests

from . import get_logger
from .consts import (
    DANDISET_ID_REGEX,
    PUBLISHED_VERSION_REGEX,
    RETRY_STATUSES,
    VERSION_REGEX,
    DandiInstance,
    known_instances,
)
from .dandiapi import BaseRemoteAsset, DandiAPIClient, RemoteDandiset
from .exceptions import FailedToConnectError, NotFoundError, UnknownURLError
from .utils import get_instance

lgr = get_logger()


@dataclass
class ParsedDandiURL(ABC):
    """
    Parsed representation of a URL pointing to a DANDI resource
    (Dandiset or asset(s)).  Subclasses must implement `get_assets()`.

    Most methods take a ``client: DandiAPIClient`` argument, which must be a
    `~dandi.dandiapi.DandiAPIClient` object for querying `instance` (This is
    not checked).  Such a client instance can be obtained by calling
    `get_client()`, or an appropriate pre-existing client instance can be
    passed instead.
    """

    #: The DANDI instance that the URL points to
    instance: DandiInstance
    #: The ID of the Dandiset given in the URL
    dandiset_id: str | None
    #: The version of the Dandiset, if specified.  If this is not set, the
    #: version will be defaulted using the rules described under
    #: `DandiAPIClient.get_dandiset()`.
    version_id: str | None

    @property
    def api_url(self) -> AnyHttpUrl:
        """The base URL of the DANDI API service, without a trailing slash"""
        # Kept for backwards compatibility
        adapter = TypeAdapter(AnyHttpUrl)
        return adapter.validate_python(self.instance.api.rstrip("/"))

    def get_client(self) -> DandiAPIClient:
        """
        Returns an unauthenticated `~dandi.dandiapi.DandiAPIClient` for
        `instance`
        """
        return DandiAPIClient(dandi_instance=self.instance)

    def get_dandiset(
        self, client: DandiAPIClient, lazy: bool = True
    ) -> RemoteDandiset | None:
        """
        Returns information about the specified (or default) version of the
        specified Dandiset.  Returns `None` if the URL did not contain a
        Dandiset identifier.

        If ``lazy`` is true, a "lazy" `RemoteDandiset` instance is returned,
        with no requests made until any data is actually required.
        """
        if self.dandiset_id is not None:
            return client.get_dandiset(self.dandiset_id, self.version_id, lazy=lazy)
        else:
            return None

    @abstractmethod
    def get_assets(
        self, client: DandiAPIClient, order: str | None = None, strict: bool = False
    ) -> Iterator[BaseRemoteAsset]:
        """
        Returns an iterator of asset structures for the assets referred to by
        or associated with the URL.  For a URL pointing to just a Dandiset,
        this is the set of all assets in the given or default version of the
        Dandiset.  For a URL that specifies a specific asset or collection of
        assets in a Dandiset, this is all of those assets.

        When multiple assets are returned, they can be sorted by a given field
        by passing the name of that field as the ``order`` parameter.  The
        accepted field names are ``"created"``, ``"modified"``, and ``"path"``.
        Prepend a hyphen to the field name to reverse the sort order.

        If ``strict`` is true, then fetching assets for a URL that refers to a
        nonexistent resource will raise a `NotFoundError`; if it is false, the
        method will instead return an empty iterator.
        """
        ...

    def get_asset_ids(self, client: DandiAPIClient) -> Iterator[str]:
        """
        Returns an iterator of IDs of the assets referred to by or associated
        with the URL
        """
        for a in self.get_assets(client):
            yield a.identifier

    @contextmanager
    def navigate(
        self, *, strict: bool = False, authenticate: bool | None = None
    ) -> Iterator[
        tuple[DandiAPIClient, RemoteDandiset | None, Iterable[BaseRemoteAsset]]
    ]:
        """
        A context manager that returns a triple of a
        `~dandi.dandiapi.DandiAPIClient` (with an open session that is closed
        when the context manager closes), the return value of `get_dandiset()`,
        and the return value of `get_assets()`.

        If ``strict`` is true, then `get_dandiset()` is called with
        ``lazy=False`` and `get_assets()` is called with ``strict=True``; if
        ``strict`` is false, the opposite occurs.

        If ``authenticate`` is true, then
        `~dandi.dandiapi.DandiAPIClient.dandi_authenticate()` will be called on
        the client before returning it.  If it is `None` (the default), the
        method will only be called if the URL requires authentication (e.g., if
        the resource(s) are embargoed).

        .. versionchanged:: 0.35.0
            ``authenticate`` added
        """
        with self.get_client() as client:
            if authenticate:
                client.dandi_authenticate()
            try:
                dandiset = self.get_dandiset(client, lazy=not strict)
            except requests.HTTPError as e:
                if (
                    e.response is not None
                    and e.response.status_code == 401
                    and authenticate is not False
                ):
                    lgr.info("Resource requires authentication; authenticating ...")
                    client.dandi_authenticate()
                    dandiset = self.get_dandiset(client, lazy=not strict)
                else:
                    raise
            assets = self.get_assets(client, strict=strict)
            yield (client, dandiset, assets)

    @abstractmethod
    def get_asset_download_path(
        self, asset: BaseRemoteAsset, preserve_tree: bool
    ) -> str:
        """
        Returns the path (relative to the base download directory) at which the
        asset ``asset`` (assumed to have been returned by this object's
        `get_assets()` method) should be downloaded.

        If ``preserve_tree`` is `True`, then the download is being performed
        with ``--download tree`` option, and the method's return value should
        be adjusted accordingly.

        :meta private:
        """
        ...

    @abstractmethod
    def is_under_download_path(self, path: str) -> bool:
        """
        Returns `True` iff `path` (a forward-slash-separated path to a file
        relative to a base download directory) is a location to which an asset
        returned by this URL could be downloaded.

        For example, for an `AssetFolderURL` with a path of ``"foo/bar/"``, all
        assets returned by the URL will have their `get_asset_download_path()`
        return value start with ``"bar/"``, and so this method will return true
        for ``"bar/apple.txt"`` but not ``"foo/bar/apple.txt"``.

        Technically, this method should only be called on `DandisetURL` and
        `MultiAssetURL` instances, not on `SingleAssetURL` instances, but
        defining it on `ParsedDandiURL` instead of the first two classes lets
        us call it on a `ParsedDandiURL` we know to be non-`SingleAssetURL`
        without mypy complaining.

        :meta private:
        """
        ...


@dataclass
class DandisetURL(ParsedDandiURL):
    """
    Parsed from a URL that only refers to a Dandiset (possibly with a version)
    """

    def get_assets(
        self, client: DandiAPIClient, order: str | None = None, strict: bool = False
    ) -> Iterator[BaseRemoteAsset]:
        """Returns all assets in the Dandiset"""
        with _maybe_strict(strict):
            d = self.get_dandiset(client, lazy=not strict)
            assert d is not None
            yield from d.get_assets(order=order)

    def get_asset_download_path(
        self, asset: BaseRemoteAsset, preserve_tree: bool
    ) -> str:
        return asset.path.lstrip("/")

    def is_under_download_path(self, path: str) -> bool:
        return True


@dataclass
class SingleAssetURL(ParsedDandiURL):
    """Superclass for parsed URLs that refer to a single asset"""

    def get_asset_download_path(
        self, asset: BaseRemoteAsset, preserve_tree: bool
    ) -> str:
        path = asset.path.lstrip("/")
        if preserve_tree:
            return path
        else:
            return posixpath.basename(path)

    def is_under_download_path(self, path: str) -> bool:
        return False


@dataclass
class MultiAssetURL(ParsedDandiURL):
    """Superclass for parsed URLs that refer to multiple assets"""

    path: str

    def get_asset_download_path(
        self, asset: BaseRemoteAsset, preserve_tree: bool
    ) -> str:
        path = asset.path.lstrip("/")
        if preserve_tree:
            return path
        else:
            return multiasset_target(self.path, path)

    def is_under_download_path(self, path: str) -> bool:
        prefix = posixpath.dirname(self.path.strip("/"))
        if prefix:
            return path.startswith(prefix + "/")
        else:
            return path.startswith(self.path)


@dataclass
# The below `type: ignore[override]` prevents mypy under Python 3.13+ from
# complaining about problems caused by overriding the types of `dandiset_id`
# and `version_id` from what they are in ParsedDandiURL.
class BaseAssetIDURL(SingleAssetURL):  # type: ignore[override]
    """
    Parsed from a URL that refers to an asset by ID and does not include the
    Dandiset ID
    """

    dandiset_id: None = field(init=False, default=None)
    version_id: None = field(init=False, default=None)
    asset_id: str

    def get_assets(
        self, client: DandiAPIClient, order: str | None = None, strict: bool = False
    ) -> Iterator[BaseRemoteAsset]:
        """
        Yields the asset with the given ID.  If the asset does not exist, then
        a `NotFoundError` is raised if ``strict`` is true, and nothing is
        yielded if ``strict`` is false.
        """
        with _maybe_strict(strict):
            yield client.get_asset(self.asset_id)

    def get_asset_ids(self, client: DandiAPIClient) -> Iterator[str]:
        """Yields the ID of the asset (regardless of whether it exists)"""
        yield self.asset_id

    @contextmanager
    def navigate(
        self, *, strict: bool = False, authenticate: bool | None = None
    ) -> Iterator[
        tuple[DandiAPIClient, RemoteDandiset | None, Iterable[BaseRemoteAsset]]
    ]:
        with self.get_client() as client:
            if authenticate:
                client.dandi_authenticate()
            dandiset = self.get_dandiset(client, lazy=not strict)
            try:
                assets = list(self.get_assets(client, strict=strict))
            except requests.HTTPError as e:
                if (
                    e.response is not None
                    and e.response.status_code == 401
                    and authenticate is not False
                ):
                    lgr.info("Resource requires authentication; authenticating ...")
                    client.dandi_authenticate()
                    assets = list(self.get_assets(client, strict=strict))
                else:
                    raise
            yield (client, dandiset, assets)


@dataclass
class AssetIDURL(SingleAssetURL):
    """
    Parsed from a URL that refers to an asset by ID and includes the Dandiset ID
    """

    asset_id: str

    def get_assets(
        self, client: DandiAPIClient, order: str | None = None, strict: bool = False
    ) -> Iterator[BaseRemoteAsset]:
        """
        Yields the asset with the given ID.  If the Dandiset or asset does not
        exist, then a `NotFoundError` is raised if ``strict`` is true, and
        nothing is yielded if ``strict`` is false.
        """
        with _maybe_strict(strict):
            d = self.get_dandiset(client, lazy=not strict)
            assert d is not None
            yield d.get_asset(self.asset_id)

    def get_asset_ids(self, client: DandiAPIClient) -> Iterator[str]:
        """Yields the ID of the asset (regardless of whether it exists)"""
        yield self.asset_id


@dataclass
class AssetPathPrefixURL(MultiAssetURL):
    """
    Parsed from a URL that refers to a collection of assets by path prefix
    """

    def get_assets(
        self, client: DandiAPIClient, order: str | None = None, strict: bool = False
    ) -> Iterator[BaseRemoteAsset]:
        """
        Returns the assets whose paths start with `path`.  If `strict` is true
        and there are no such assets, raises `NotFoundError`.

        .. versionchanged:: 0.54.0

            `NotFoundError` will now be raised if `strict` is true and there
            are no such assets.
        """
        any_assets = False
        with _maybe_strict(strict):
            d = self.get_dandiset(client, lazy=not strict)
            assert d is not None
            for a in d.get_assets_with_path_prefix(self.path, order=order):
                any_assets = True
                yield a
        if strict and not any_assets:
            raise NotFoundError(f"No assets found with path prefix {self.path!r}")


@dataclass
class AssetItemURL(SingleAssetURL):
    """Parsed from a URL that refers to a specific asset by path"""

    path: str

    def get_assets(
        self, client: DandiAPIClient, order: str | None = None, strict: bool = False
    ) -> Iterator[BaseRemoteAsset]:
        """
        Yields the asset whose path equals `path`.  If there is no such asset:

        - If ``strict`` is true, a `NotFoundError` is raised.
        - If ``strict`` is false and the path happens to be the path to an
          asset directory, a `ValueError` is raised indicating that the user
          left off a trailing slash.
        - Otherwise, nothing is yielded.
        """
        try:
            dandiset = self.get_dandiset(client, lazy=not strict)
            assert dandiset is not None
            # Force evaluation of the version here instead of when
            # get_asset_by_path() is called so we don't get nonexistent
            # dandisets with unspecified versions mixed up with nonexistent
            # assets.
            dandiset.version_id
        except NotFoundError:
            if strict:
                raise
            else:
                return
        try:
            yield dandiset.get_asset_by_path(self.path)
        except NotFoundError:
            if strict:
                raise
            try:
                next(dandiset.get_assets_with_path_prefix(self.path + "/"))
            except NotFoundError:
                # Dandiset has explicit version that doesn't exist.
                return
            except StopIteration:
                pass
            else:
                raise ValueError(
                    f"Asset path {self.path!r} points to a directory but lacks trailing /"
                )


@dataclass
class AssetFolderURL(MultiAssetURL):
    """
    Parsed from a URL that refers to a collection of assets by folder path
    """

    def get_assets(
        self, client: DandiAPIClient, order: str | None = None, strict: bool = False
    ) -> Iterator[BaseRemoteAsset]:
        """
        Returns all assets under the folder at `path`.  If the folder does not
        exist and `strict` is true, raises `NotFoundError`; otherwise, if the
        folder does not exist and `strict` is false, yields nothing.

        .. versionchanged:: 0.54.0

            `NotFoundError` will now be raised if `strict` is true and there
            is no such folder.
        """
        path = self.path
        if not path.endswith("/"):
            path += "/"
        any_assets = False
        with _maybe_strict(strict):
            d = self.get_dandiset(client, lazy=not strict)
            assert d is not None
            for a in d.get_assets_with_path_prefix(path, order=order):
                any_assets = True
                yield a
        if strict and not any_assets:
            raise NotFoundError(f"No assets found under folder {path!r}")


@dataclass
class AssetGlobURL(MultiAssetURL):
    """
    .. versionadded:: 0.54.0

    Parsed from a URL that refers to a collection of assets by a path glob
    """

    def get_assets(
        self, client: DandiAPIClient, order: str | None = None, strict: bool = False
    ) -> Iterator[BaseRemoteAsset]:
        """
        Returns all assets whose paths match the glob pattern `path`.  If
        `strict` is true and there are no such assets, raises `NotFoundError`.

        .. versionchanged:: 0.54.0

            `NotFoundError` will now be raised if `strict` is true and there
            are no such assets.
        """
        any_assets = False
        with _maybe_strict(strict):
            d = self.get_dandiset(client, lazy=not strict)
            assert d is not None
            for a in d.get_assets_by_glob(self.path, order=order):
                any_assets = True
                yield a
        if strict and not any_assets:
            raise NotFoundError(f"No assets found matching glob {self.path!r}")

    def get_asset_download_path(
        self, asset: BaseRemoteAsset, preserve_tree: bool
    ) -> str:
        return asset.path.lstrip("/")

    def is_under_download_path(self, path: str) -> bool:
        # cf. <https://github.com/dandi/dandi-archive/blob/185a583b505bcb0ca990758b26210cd09228e81b/dandiapi/api/views/asset.py#L403-L409>  # noqa: E501
        return bool(
            re.fullmatch(re.escape(self.path).replace(r"\*", ".*"), path, flags=re.I)
        )


@contextmanager
def _maybe_strict(strict: bool) -> Iterator[None]:
    try:
        yield
    except NotFoundError:
        if strict:
            raise


@contextmanager
def navigate_url(
    url: str, *, strict: bool = False, authenticate: bool | None = None
) -> Iterator[tuple[DandiAPIClient, RemoteDandiset | None, Iterable[BaseRemoteAsset]]]:
    """
    A context manager that takes a URL pointing to a DANDI Archive and
    returns a triple of a `~dandi.dandiapi.DandiAPIClient` (with an open
    session that is closed when the context manager closes), the Dandiset
    identified in the URL (if any), and the assets specified by the URL (or, if
    no specific assets were specified, all assets in the Dandiset).

    .. versionchanged:: 0.35.0
        ``authenticate`` added

    :param str url: URL which might point to a Dandiset, folder, or asset(s)
    :param bool strict:
        If true, then `get_dandiset()` is called with ``lazy=False`` and
        `get_assets()` is called with ``strict=True``; if false, the opposite
        occurs.
    :param authenticate:
        If true, then `~dandi.dandiapi.DandiAPIClient.dandi_authenticate()`
        will be called on the client before returning it.  If `None` (the
        default), the method will only be called if the URL requires
        authentication (e.g., if the resource(s) are embargoed).
    :returns: Context manager that yields a ``(client, dandiset, assets)``
        tuple; ``client`` will have a session established for the duration of
        the context
    """
    parsed_url = parse_dandi_url(url)
    with parsed_url.navigate(strict=strict, authenticate=authenticate) as (
        client,
        dandiset,
        assets,
    ):
        yield (client, dandiset, assets)


class _dandi_url_parser:
    # Defining as a class with all the attributes to not leak all the variables
    # etc into module space, and later we might end up with classes for those
    # anyways
    dandiset_id_grp = f"(?P<dandiset_id>{DANDISET_ID_REGEX})"
    # Should absorb port and "api/":
    server_grp = "(?P<server>(?P<protocol>https?)://(?P<hostname>[^/]+)/(api/)?)"
    known_urls: list[tuple[re.Pattern[str], dict[str, Any], str]] = [
        # List of (regex, settings, display string) triples
        #
        # Settings:
        # - handle_redirect:
        #   - 'pass' - would continue with original url if no redirect happen
        #   - 'only' - would interrupt if no redirection happens
        # - rewrite:
        #   - callable -- which would rewrite that "URI"
        # - map_instance
        #
        # Those we first redirect and then handle the redirected URL
        # TODO: Later should better conform to our API, so we could allow
        #       for not only "dandiarchive.org" URLs
        (
            re.compile(
                rf"(?P<instance_name>DANDI):"
                rf"{dandiset_id_grp}"
                rf"(/(?P<version>{VERSION_REGEX}))?",
                flags=re.I,
            ),
            {},
            "DANDI:<dandiset id>[/<version>]",
        ),
        (
            re.compile(r"https?://gui\.dandiarchive\.org/.*"),
            {"handle_redirect": "pass"},
            "https://gui.dandiarchive.org/...",
        ),
        (
            re.compile(
                rf"https?://identifiers\.org/DANDI:{DANDISET_ID_REGEX}"
                rf"(?:/{PUBLISHED_VERSION_REGEX})?",
                flags=re.I,
            ),
            {"handle_redirect": "pass"},
            "https://identifiers.org/DANDI:<dandiset id>[/<version id>]"
            " (<version id> cannot be 'draft')",
        ),
        (
            re.compile(
                rf"{server_grp}(#/)?(?P<asset_type>dandiset)/{dandiset_id_grp}"
                rf"(/(?P<version>{VERSION_REGEX}))?"
                r"(/(files(\?location=(?P<location_folder>.*)?)?)?)?"
            ),
            {},
            "https://<server>[/api]/[#/]dandiset/<dandiset id>[/<version>]"
            "[/files[?location=<path>]]",
        ),
        # PRs are also on netlify - so above takes precedence. TODO: make more
        # specific?
        (
            re.compile(r"https?://[^/]*dandiarchive-org\.netlify\.app/.*"),
            {"map_instance": "dandi"},
            "https://*dandiarchive-org.netlify.app/...",
        ),
        # Direct urls to our new API
        (
            re.compile(
                rf"{server_grp}(?P<asset_type>dandiset)s/{dandiset_id_grp}"
                rf"(/(versions(/(?P<version>{VERSION_REGEX}))?/?)?)?"
            ),
            {},
            "https://<server>[/api]/dandisets/<dandiset id>[/versions[/<version>]]",
        ),
        (
            re.compile(
                rf"{server_grp}(?P<asset_type>asset)s/(?P<asset_id>[^?/]+)(/(download/?)?)?"
            ),
            {},
            "https://<server>[/api]/assets/<asset id>[/download]",
        ),
        (
            re.compile(
                rf"{server_grp}(?P<asset_type>dandiset)s/{dandiset_id_grp}"
                rf"/versions/(?P<version>{VERSION_REGEX})"
                r"/assets/(?P<asset_id>[^?/]+)(/(download/?)?)?"
            ),
            {},
            "https://<server>[/api]/dandisets/<dandiset id>/versions/<version>"
            "/assets/<asset id>[/download]",
        ),
        (
            re.compile(
                rf"{server_grp}(?P<asset_type>dandiset)s/{dandiset_id_grp}"
                rf"/versions/(?P<version>{VERSION_REGEX})"
                r"/assets/\?path=(?P<path>[^&]+)",
            ),
            {},
            "https://<server>[/api]/dandisets/<dandiset id>/versions/<version>"
            "/assets/?path=<path>",
        ),
        (
            re.compile(
                rf"{server_grp}(?P<asset_type>dandiset)s/{dandiset_id_grp}"
                rf"/versions/(?P<version>{VERSION_REGEX})"
                r"/assets/\?glob=(?P<glob>[^&]+)",
            ),
            {},
            "https://<server>[/api]/dandisets/<dandiset id>/versions/<version>"
            "/assets/?glob=<glob>",
        ),
        # ad-hoc explicitly pointing within URL to the specific instance to use
        # and otherwise really simple:
        # dandi://INSTANCE/DANDISET_ID[@VERSION][/PATH]
        # For now to not be promoted to the users, and primarily for internal
        # use
        (
            re.compile(
                rf"dandi://(?P<instance_name>[-\w._]+)"
                rf"/{dandiset_id_grp}"
                rf"(@(?P<version>{VERSION_REGEX}))?"
                rf"(/(?P<location>.*)?)?"
            ),
            {},
            "dandi://<instance name>/<dandiset id>[@<version>][/<path>]",
        ),
        # https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000006/draft
        # (no API yet)
        (
            re.compile(r"https?://.*"),
            {"handle_redirect": "only"},
            "https://<server>/...",
        ),
    ]
    resource_identifier_primer = """RESOURCE ID/URLS:\n
 dandi commands accept URLs and URL-like identifiers called <resource
 ids> in the following formats for identifying Dandisets, assets, and
 asset collections.

 Text in [brackets] is optional.  A server field is a base API or GUI URL
 for a DANDI Archive instance.  If an optional ``version`` field is
 omitted from a URL, the given Dandiset's most recent published version
 will be used if it has one, and its draft version will be used otherwise.
"""
    known_patterns = "Accepted resource identifier patterns:" + "\n - ".join(
        [""] + [display for _, _, display in known_urls]
    )

    @classmethod
    def parse(
        cls, url: str, *, map_instance: bool = True, glob: bool = False
    ) -> ParsedDandiURL:
        """
        Parse a DANDI instance URL and return a `ParsedDandiURL` instance.  See
        :ref:`resource_ids` for the supported URL formats.

        .. versionadded:: 0.54.0

            ``glob`` parameter added

        :param bool glob:
            if true, certain URL formats will be parsed into `AssetGlobURL`
            instances
        :raises UnknownURLError: if the URL is not one of the above
        """

        lgr.debug("Parsing url %s", url)

        # Loop through known url regexes and stop as soon as one is matching
        match = None
        for regex, settings, _ in cls.known_urls:
            match = regex.fullmatch(url)
            if not match:
                continue
            groups = match.groupdict()
            if "instance_name" in groups:
                # map to lower case so we could immediately map DANDI: into "dandi" instance
                groups["instance_name"] = groups["instance_name"].lower()
            lgr.log(5, "Matched %r into %s", url, groups)
            rewrite = settings.get("rewrite", False)
            handle_redirect = settings.get("handle_redirect", False)
            if rewrite:
                assert not handle_redirect
                assert not settings.get("map_instance")
                new_url = rewrite(url)
                return cls.parse(new_url, map_instance=map_instance, glob=glob)
            elif handle_redirect:
                assert handle_redirect in ("pass", "only")
                new_url = cls.follow_redirect(url)
                if new_url != url:
                    return cls.parse(new_url, map_instance=map_instance, glob=glob)
                if handle_redirect == "pass":
                    # We used to issue warning in such cases, but may be it got implemented
                    # now via reverse proxy and we had added a new regex? let's just
                    # continue with a debug msg
                    lgr.debug("Redirection did not happen for %s", url)
                else:
                    raise RuntimeError(
                        f"{url} did not redirect to another location which dandi client would"
                        f" know how to handle."
                    )
            elif settings.get("map_instance"):
                if map_instance:
                    parsed_url = cls.parse(url, map_instance=False, glob=glob)
                    if settings["map_instance"] not in known_instances:
                        raise ValueError(
                            "Unknown instance {}. Known are: {}".format(
                                settings["map_instance"], ", ".join(known_instances)
                            )
                        )
                    parsed_url.instance = get_instance(settings["map_instance"])
                continue  # in this run we ignore and match further
            elif "instance_name" in groups:
                try:
                    known_instance = get_instance(groups["instance_name"])
                except KeyError:
                    raise UnknownURLError(
                        f"Unknown instance {groups['instance_name']!r}.  Valid instances: "
                        + ", ".join(sorted(known_instances))
                    )
                assert known_instance.api  # must be defined
                groups["server"] = known_instance.api
                # could be overloaded later depending if location is provided
                groups["asset_type"] = "dandiset"
                break
            else:
                break
        if not match:
            # TODO: may be make use of etelemetry and report if newer client
            # which might know is available?
            raise UnknownURLError(
                f"We do not know how to map URL {url} to our servers.\n"
                f"{cls.known_patterns}"
            )

        url_server = groups["server"].rstrip("/")
        if re.fullmatch(
            r"https?://deploy-preview-.*--gui-dandiarchive-org\.netlify\.app",
            url_server,
        ):
            url_server = "https://gui-staging.dandiarchive.org"
        instance = get_instance(url_server)
        # asset_type = groups.get("asset_type")
        dandiset_id = groups.get("dandiset_id")
        version_id = groups.get("version")
        location: str
        if groups.get("location_folder") is not None:
            assert "location" not in groups
            location = urlunquote(groups["location_folder"])
            if not location.endswith("/") and not glob:
                location += "/"
        else:
            location = urlunquote(groups.get("location") or "")
        asset_id = groups.get("asset_id")
        path = groups.get("path")
        glob_param = groups.get("glob")
        if location:
            # ATM carries leading '/' which IMHO is not needed/misguiding
            # somewhat, so I will just strip it
            location = location.lstrip("/")
        # if location is not degenerate -- it would be a folder or a file
        if location:
            if glob:
                parsed_url = AssetGlobURL(
                    instance=instance,
                    dandiset_id=dandiset_id,
                    version_id=version_id,
                    path=location,
                )
            elif location.endswith("/"):
                parsed_url = AssetFolderURL(
                    instance=instance,
                    dandiset_id=dandiset_id,
                    version_id=version_id,
                    path=location,
                )
            else:
                parsed_url = AssetItemURL(
                    instance=instance,
                    dandiset_id=dandiset_id,
                    version_id=version_id,
                    path=location,
                )
        elif asset_id:
            if dandiset_id is None:
                parsed_url = BaseAssetIDURL(instance=instance, asset_id=asset_id)
            else:
                parsed_url = AssetIDURL(
                    instance=instance,
                    dandiset_id=dandiset_id,
                    version_id=version_id,
                    asset_id=asset_id,
                )
        elif path:
            parsed_url = AssetPathPrefixURL(
                instance=instance,
                dandiset_id=dandiset_id,
                version_id=version_id,
                path=path,
            )
        elif glob_param:
            parsed_url = AssetGlobURL(
                instance=instance,
                dandiset_id=dandiset_id,
                version_id=version_id,
                path=glob_param,
            )
        else:
            parsed_url = DandisetURL(
                instance=instance,
                dandiset_id=dandiset_id,
                version_id=version_id,
            )
        lgr.debug("Parsed into %r", parsed_url)
        return parsed_url

    @staticmethod
    def follow_redirect(url: str) -> str:
        """
        Resolve the given URL by following all redirects.

        :raises NotFoundError: if a 404 response is returned
        :raises FailedToConnectError: if a response other than 200, 400, 404,
            or one of the statuses in `~dandi.consts.RETRY_STATUSES` is returned
        """
        i = 0
        while True:
            r = requests.head(url, allow_redirects=True)
            if r.status_code in RETRY_STATUSES and i < 4:
                delay = 0.1 * 10**i
                lgr.warning(
                    "HEAD request to %s returned %d; sleeping for %f seconds and then retrying...",
                    url,
                    r.status_code,
                    delay,
                )
                sleep(delay)
                i += 1
                continue
            elif r.status_code == 404:
                raise NotFoundError(url)
            elif r.status_code != 200:
                raise FailedToConnectError(
                    f"Response for getting {url} to redirect returned {r.status_code}."
                    f" Please verify that it is a URL related to dandiarchive and"
                    f" supported by dandi client"
                )
            elif r.url != url:
                return r.url
            assert isinstance(url, str)
            return url


# convenience binding
parse_dandi_url = _dandi_url_parser.parse
follow_redirect = _dandi_url_parser.follow_redirect


def multiasset_target(url_path: str, asset_path: str) -> str:
    """
    When downloading assets for a non-glob `MultiAssetURL` with
    `~MultiAssetURL.path` equal to ``url_path``, calculate the path (relative
    to the output path) at which to save the asset with path ``asset_path``.

    :meta private:
    """
    prefix = posixpath.dirname(url_path.strip("/"))
    if prefix:
        prefix += "/"
    assert asset_path.startswith(prefix)
    return asset_path[len(prefix) :]
