from abc import ABC, abstractmethod
from contextlib import contextmanager
import re
from time import sleep
from typing import Iterator, Optional, Tuple
from urllib.parse import unquote as urlunquote

from pydantic import AnyHttpUrl, BaseModel, parse_obj_as, validator
import requests

from . import get_logger
from .consts import VERSION_REGEX, known_instances
from .dandiapi import BaseRemoteAsset, DandiAPIClient, RemoteDandiset
from .exceptions import FailedToConnectError, NotFoundError, UnknownURLError
from .utils import get_instance

lgr = get_logger()


class ParsedDandiURL(ABC, BaseModel):
    """
    Parsed representation of a URL pointing to a Dandi Archive resource
    (Dandiset or asset(s)).  Subclasses must implement `get_assets()`.

    Most methods take a ``client: DandiAPIClient`` argument, which must be a
    `DandiAPIClient` object for querying `api_url` (This is not checked).  Such
    a client instance can be obtained by calling `get_client()`, or an
    appropriate pre-existing client instance can be passed instead.
    """

    #: The base URL of the Dandi API service, without a trailing slash
    api_url: AnyHttpUrl
    #: The ID of the Dandiset given in the URL
    dandiset_id: Optional[str]
    #: The version of the Dandiset, if specified.  If this is not set, methods
    #: that need the Dandiset version will call `get_version_id()` to get an
    #: appropriate default value.
    version_id: Optional[str] = None

    @validator("api_url")
    def _validate_api_url(cls, v: AnyHttpUrl) -> AnyHttpUrl:
        return parse_obj_as(AnyHttpUrl, v.rstrip("/"))

    def get_client(self) -> DandiAPIClient:
        """Returns an unauthenticated `DandiAPIClient` for `api_url`"""
        return DandiAPIClient(self.api_url)

    def get_dandiset(self, client: DandiAPIClient) -> Optional[RemoteDandiset]:
        """
        Returns information about the specified (or default) version of the
        specified Dandiset
        """
        if self.dandiset_id is not None:
            return client.get_dandiset(self.dandiset_id, self.get_version_id(client))
        else:
            return None

    def get_version_id(self, client: DandiAPIClient) -> str:
        """
        Returns `version_id` or determines a default value if unset.

        If `version_id` is non-`None`, returns it.  Otherwise, the ID of the
        most recent published version of the Dandiset is returned, if any,
        otherwise the ID of the draft version is returned.
        """
        if self.dandiset_id is None:
            raise ValueError("Cannot get version for Dandiset-less URL")
        elif self.version_id is None:
            r = client.get(f"/dandisets/{self.dandiset_id}/")
            version = r["most_recent_published_version"] or r["draft_version"]
            return version["version"]
        else:
            return self.version_id

    @abstractmethod
    def get_assets(self, client: DandiAPIClient) -> Iterator[BaseRemoteAsset]:
        """
        Returns an iterator of asset structures for the assets referred to by
        or associated with the URL.  For a URL pointing to just a Dandiset,
        this is the set of all assets in the given or default version of the
        Dandiset.  For a URL that specifies a specific asset or collection of
        assets in a Dandiset, this is all of those assets.
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
        self,
    ) -> Iterator[
        Tuple[DandiAPIClient, Optional[RemoteDandiset], Iterator[BaseRemoteAsset]]
    ]:
        """
        A context manager that returns a triple of a `DandiAPIClient` (with an
        open session that is closed when the context manager closes), the
        return value of `get_dandiset()`, and the return value of
        `get_assets()`
        """
        # We could later try to "dandi_authenticate" if run into permission
        # issues.  May be it could be not just boolean but the "id" to be used?
        with self.get_client() as client:
            yield (client, self.get_dandiset(client), self.get_assets(client))


class DandisetURL(ParsedDandiURL):
    """
    Parsed from a URL that only refers to a Dandiset (possibly with a version)
    """

    def get_assets(self, client: DandiAPIClient) -> Iterator[BaseRemoteAsset]:
        """Returns all assets in the Dandiset"""
        return self.get_dandiset(client).get_assets()


class SingleAssetURL(ParsedDandiURL):
    """Superclass for parsed URLs that refer to a single asset"""

    pass


class MultiAssetURL(ParsedDandiURL):
    """Superclass for parsed URLs that refer to multiple assets"""

    path: str


class BaseAssetIDURL(SingleAssetURL):
    """
    Parsed from a URL that refers to an asset by ID and does not include the
    Dandiset ID
    """

    asset_id: str

    def get_assets(self, client: DandiAPIClient) -> Iterator[BaseRemoteAsset]:
        """
        Yields the asset with the given ID.  Yields nothing if the asset does
        not exist.
        """
        try:
            yield client.get_asset(self.asset_id)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return
            else:
                raise

    def get_asset_ids(self, client: DandiAPIClient) -> Iterator[str]:
        """Yields the ID of the asset (regardless of whether it exists)"""
        yield self.asset_id


class AssetIDURL(SingleAssetURL):
    """
    Parsed from a URL that refers to an asset by ID and includes the Dandiset ID
    """

    asset_id: str

    def get_assets(self, client: DandiAPIClient) -> Iterator[BaseRemoteAsset]:
        """
        Yields the asset with the given ID.  Yields nothing if the asset does
        not exist.
        """
        try:
            yield self.get_dandiset(client).get_asset(self.asset_id)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return
            else:
                raise

    def get_asset_ids(self, client: DandiAPIClient) -> Iterator[str]:
        """Yields the ID of the asset (regardless of whether it exists)"""
        yield self.asset_id


class AssetPathPrefixURL(MultiAssetURL):
    """
    Parsed from a URL that refers to a collection of assets by path prefix
    """

    def get_assets(self, client: DandiAPIClient) -> Iterator[BaseRemoteAsset]:
        """Returns the assets whose paths start with `path`"""
        return self.get_dandiset(client).get_assets_with_path_prefix(self.path)


class AssetItemURL(SingleAssetURL):
    """Parsed from a URL that refers to a specific asset by path"""

    path: str

    def get_assets(self, client: DandiAPIClient) -> Iterator[BaseRemoteAsset]:
        """
        Yields the asset whose path equals `path`.  If there is no such asset,
        this method yields nothing, unless the path happens to be the path to
        an asset directory, in which case an error is raised indicating that
        the user left off a trailing slash.
        """
        d = self.get_dandiset(client)
        try:
            asset = d.get_asset_by_path(self.path)
        except NotFoundError:
            try:
                next(d.get_assets_with_path_prefix(self.path + "/"))
            except StopIteration:
                pass
            else:
                raise ValueError(
                    f"Asset path {self.path!r} points to a directory but lacks trailing /"
                )
        else:
            yield asset


class AssetFolderURL(MultiAssetURL):
    """
    Parsed from a URL that refers to a collection of assets by folder path
    """

    path: str

    def get_assets(self, client: DandiAPIClient) -> Iterator[BaseRemoteAsset]:
        """
        Returns all assets under the folder at `path`.  Yields nothing if the
        folder does not exist.
        """
        path = self.path
        if not path.endswith("/"):
            path += "/"
        return self.get_dandiset(client).get_assets_with_path_prefix(path)


@contextmanager
def navigate_url(url):
    """Context manager to 'navigate' URL pointing to DANDI archive.

    :param str url: URL which might point to a dandiset, a folder, or an
        asset(s)

    :returns: Generator of one ``(client, dandiset, assets)``; ``client`` will
        have established a session for the duration of the context
    """
    parsed_url = parse_dandi_url(url)
    with parsed_url.navigate() as (client, dandiset, assets):
        yield (client, dandiset, assets)


class _dandi_url_parser:
    # Defining as a class with all the attributes to not leak all the variables
    # etc into module space, and later we might end up with classes for those
    # anyways
    dandiset_id_grp = "(?P<dandiset_id>[0-9]{6})"
    # Should absorb port and "api/":
    server_grp = "(?P<server>(?P<protocol>https?)://(?P<hostname>[^/]+)/(api/)?)"
    known_urls = [
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
            re.compile(r"DANDI:.*"),
            {"rewrite": lambda x: "https://identifiers.org/" + x},
            "DANDI:<dandiset id>",
        ),
        (
            re.compile(r"https?://dandiarchive\.org/.*"),
            {"handle_redirect": "pass"},
            "https://dandiarchive.org/...",
        ),
        (
            re.compile(r"https?://identifiers\.org/DANDI:.*"),
            {"handle_redirect": "pass"},
            "https://identifiers.org/DANDI:<dandiset id>",
        ),
        (
            re.compile(
                rf"{server_grp}(#/)?(?P<asset_type>dandiset)/{dandiset_id_grp}"
                rf"(/(?P<version>{VERSION_REGEX}))?"
                r"(/(files(\?location=(?P<location>.*)?)?)?)?"
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
            "https://*dandiarchive-org.netflify.app/...",
        ),
        # Direct urls to our new API
        (
            re.compile(
                rf"{server_grp}(?P<asset_type>dandiset)s/{dandiset_id_grp}"
                rf"(/(versions(/(?P<version>{VERSION_REGEX}))?)?)?"
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
        # ad-hoc explicitly pointing within URL to the specific instance to use
        # and otherwise really simple:
        # dandi://INSTANCE/DANDISET_ID[@VERSION][/PATH]
        # For now to not be promoted to the users, and primarily for internal
        # use
        (
            re.compile(
                rf"dandi://(?P<instance_name>({'|'.join(known_instances)}))"
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
    known_patterns = "Patterns for known setups:" + "\n - ".join(
        [""] + [display for _, _, display in known_urls]
    )
    map_to = {}
    for (gui, redirector, api) in known_instances.values():
        for h in (gui, redirector):
            if h and api:
                map_to[h] = api

    @classmethod
    def parse(cls, url, *, map_instance=True):
        """
        Parse url like and return server (address), asset_id and/or directory

        Example URLs (as of 20210428):

        - Dataset landing page metadata:
          https://gui.dandiarchive.org/#/dandiset/000003

        Individual and multiple files:

        - dandi???

        Multiple selected files + folders -- we do not support ATM, then further
        RFing would be due, probably making this into a generator or returning a
        list of entries.

        "Features":

        - uses some of `known_instances` to map some urls, e.g. from
          gui.dandiarchive.org ones into girder.

        :rtype: ParsedDandiURL
        """
        lgr.debug("Parsing url %s", url)

        # Loop through known url regexes and stop as soon as one is matching
        match = None
        for regex, settings, _ in cls.known_urls:
            match = regex.fullmatch(url)
            if not match:
                continue
            groups = match.groupdict()
            lgr.log(5, "Matched %r into %s", url, groups)
            rewrite = settings.get("rewrite", False)
            handle_redirect = settings.get("handle_redirect", False)
            if rewrite:
                assert not handle_redirect
                assert not settings.get("map_instance")
                new_url = rewrite(url)
                return cls.parse(new_url)
            elif handle_redirect:
                assert handle_redirect in ("pass", "only")
                new_url = cls.follow_redirect(url)
                if new_url != url:
                    return cls.parse(new_url)
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
                    parsed_url = cls.parse(url, map_instance=False)
                    if settings["map_instance"] not in known_instances:
                        raise ValueError(
                            "Unknown instance {}. Known are: {}".format(
                                settings["map_instance"], ", ".join(known_instances)
                            )
                        )
                    known_instance = get_instance(settings["map_instance"])
                    parsed_url.api_url = known_instance.api
                continue  # in this run we ignore and match further
            elif "instance_name" in groups:
                known_instance = get_instance(groups["instance_name"])
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
        server = cls.map_to.get(url_server, url_server)
        # asset_type = groups.get("asset_type")
        dandiset_id = groups.get("dandiset_id")
        version_id = groups.get("version")
        location = groups.get("location")
        asset_id = groups.get("asset_id")
        path = groups.get("path")
        if location:
            location = urlunquote(location)
            # ATM carries leading '/' which IMHO is not needed/misguiding somewhat, so
            # I will just strip it
            location = location.lstrip("/")

        # if location is not degenerate -- it would be a folder or a file
        if location:
            if location.endswith("/"):
                parsed_url = AssetFolderURL(
                    api_url=server,
                    dandiset_id=dandiset_id,
                    version_id=version_id,
                    path=location,
                )
            else:
                parsed_url = AssetItemURL(
                    api_url=server,
                    dandiset_id=dandiset_id,
                    version_id=version_id,
                    path=location,
                )
        elif asset_id:
            if dandiset_id is None:
                parsed_url = BaseAssetIDURL(api_url=server, asset_id=asset_id)
            else:
                parsed_url = AssetIDURL(
                    api_url=server,
                    dandiset_id=dandiset_id,
                    version_id=version_id,
                    asset_id=asset_id,
                )
        elif path:
            parsed_url = AssetPathPrefixURL(
                api_url=server,
                dandiset_id=dandiset_id,
                version_id=version_id,
                path=path,
            )
        else:
            parsed_url = DandisetURL(
                api_url=server,
                dandiset_id=dandiset_id,
                version_id=version_id,
            )
        lgr.debug("Parsed into %r", parsed_url)
        return parsed_url

    @staticmethod
    def follow_redirect(url):
        i = 0
        while True:
            r = requests.head(url, allow_redirects=True)
            if r.status_code == 404:
                if i < 3:
                    sleep(0.1 * 10 ** i)
                    i += 1
                    continue
                else:
                    raise NotFoundError(url)
            elif r.status_code != 200:
                raise FailedToConnectError(
                    f"Response for getting {url} to redirect returned {r.status_code}."
                    f" Please verify that it is a URL related to dandiarchive and"
                    f" supported by dandi client"
                )
            elif r.url != url:
                return r.url
            return url


# convenience binding
parse_dandi_url = _dandi_url_parser.parse
follow_redirect = _dandi_url_parser.follow_redirect
