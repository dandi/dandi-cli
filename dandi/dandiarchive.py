"""
Interactions with DANDI archive ATM go either through Girder or through DANDI API.

This module provides helpers to decide on which API Client to use and/or
abstract higher level code from specifics of any particular client.

Eventually it is largely to be "dissolved" whenever we stop talking to girder.
"""

from contextlib import contextmanager
import re
from urllib.parse import unquote as urlunquote

import requests

from .consts import known_instances, known_instances_rev
from .dandiapi import DandiAPIClient
from .exceptions import FailedToConnectError, NotFoundError, UnknownURLError
from . import get_logger
from .utils import get_instance

lgr = get_logger()


@contextmanager
def navigate_url(url):
    """Context manager to 'navigate' URL pointing to DANDI archive.

    Parameters
    ----------
    url: str
      URL which might point to a dandiset, a folder, or an asset(s)

    Yields
    ------
    client, dandiset, assets (generator)
      `client` will have established a session for the duration of the context
    """
    server_type, server_url, asset_type, asset_id = parse_dandi_url(url)
    # We could later try to "dandi_authenticate" if run into permission issues.
    # May be it could be not just boolean but the "id" to be used?
    assert server_type == "api"
    client = DandiAPIClient(server_url)
    with client.session():
        if asset_id["version"] is None:
            r = client.get(f"/dandisets/{asset_id['dandiset_id']}/")
            published_version = r["most_recent_published_version"]
            if published_version:
                asset_id["version"] = published_version["version"]
            else:
                asset_id["version"] = r["draft_version"]["version"]
        args = (asset_id["dandiset_id"], asset_id["version"])
        if asset_id.get("location") or asset_id.get("asset_id"):
            dandiset = client.get_dandiset(*args)
            if asset_type == "folder":
                assets = client.get_dandiset_assets(*args, path=asset_id["location"])
            elif asset_type == "item":
                if "location" in asset_id:
                    asset = client.get_asset_bypath(*args, asset_id["location"])
                    assets = [asset] if asset is not None else []
                else:
                    assets = [client.get_asset(*args, asset_id["asset_id"])]
            else:
                raise NotImplementedError(
                    f"Do not know how to handle asset type {asset_type} with location"
                )
        else:
            dandiset, assets = client.get_dandiset_and_assets(
                *args, include_metadata=True
            )
        yield client, dandiset, assets


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
        # - server_type:
        #   - 'api' - the "new" API service
        #   - 'redirect' - use redirector's server-info
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
                rf"{server_grp}#/(?P<asset_type>dandiset)/{dandiset_id_grp}"
                r"(/(?P<version>[.0-9]{5,}|draft))?"
                r"(/files(\?location=(?P<location>.*)?)?)?"
            ),
            {"server_type": "api"},
            "https://<server>[/api]/#/dandiset/<dandiset id>[/<version>]"
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
                r"(/(versions(/(?P<version>[.0-9]{5,}|draft))?)?)?"
            ),
            {"server_type": "api"},
            "https://<server>[/api]/dandisets/<dandiset id>[/versions[/<version>]]",
        ),
        (
            re.compile(
                rf"{server_grp}(?P<asset_type>dandiset)s/{dandiset_id_grp}"
                r"/versions/(?P<version>[.0-9]{5,}|draft)"
                r"/assets/(?P<asset_id>[^?/]+)(/(download/?)?)?"
            ),
            {"server_type": "api"},
            "https://<server>[/api]/dandisets/<dandiset id>/versions/<version>"
            "/assets/<asset id>[/download]",
        ),
        (
            re.compile(
                rf"{server_grp}(?P<asset_type>dandiset)s/{dandiset_id_grp}"
                r"/versions/(?P<version>[.0-9]{5,}|draft)"
                r"/assets/\?path=(?P<path>[^&]+)",
            ),
            {"server_type": "api"},
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
                r"(@(?P<version>[.0-9]{5,}|draft))?"
                rf"(/(?P<location>.*)?)?"
            ),
            {"server_type": "api"},
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
        """Parse url like and return server (address), asset_id and/or directory

        Example URLs (as of 20210428):
        - Dataset landing page metadata:
          https://gui.dandiarchive.org/#/dandiset/000003

        Individual and multiple files:
          - dandi???

        Multiple selected files + folders -- we do not support ATM, then further
        RFing would be due, probably making this into a generator or returning a
        list of entries.

        "Features":

        - uses some of `known_instance`s to map some urls, e.g. from
          gui.dandiarchive.org ones into girder.

        Returns
        -------
        server_type, server, asset_type, asset_id
          asset_type is either asset_id or folder ATM. asset_id might be a list
          in case of multiple files

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
                    server_type, server, *_ = cls.parse(url, map_instance=False)
                    if settings["map_instance"] not in known_instances:
                        raise ValueError(
                            "Unknown instance {}. Known are: {}".format(
                                settings["map_instance"], ", ".join(known_instances)
                            )
                        )
                    known_instance = get_instance(settings["map_instance"])
                    # for consistency, add
                    server = getattr(known_instance, server_type)
                    if not server.endswith("/"):
                        server += "/"
                    return (server_type, server) + tuple(_)
                continue  # in this run we ignore an match further
            elif "instance_name" in groups:
                known_instance = get_instance(groups["instance_name"])
                server_type = "api"
                assert known_instance.api  # must be defined
                groups["server"] = known_instance.api
                # could be overloaded later depending if location is provided
                groups["asset_type"] = "dandiset"
                break
            else:
                server_type = settings.get("server_type", "api")
                break
        if not match:
            # TODO: may be make use of etelemetry and report if newer client
            # which might know is available?
            raise UnknownURLError(
                f"We do not know how to map URL {url} to our servers.\n"
                f"{cls.known_patterns}"
            )

        url_server = groups["server"]
        if server_type == "redirect":
            try:
                instance_name = known_instances_rev[url_server.rstrip("/")]
            except KeyError:
                raise UnknownURLError(f"{url} does not map to a known instance")
            instance = get_instance(instance_name)
            server_type = "api"
            assert known_instance.api  # must be defined
            server = instance.api
        else:
            server = cls.map_to.get(url_server.rstrip("/"), url_server)

        if not server.endswith("/"):
            server += "/"  # we expected '/' to be there so let it be

        asset_type = groups.get("asset_type")
        dandiset_id = groups.get("dandiset_id")
        version = groups.get("version")
        location = groups.get("location")
        asset_key = groups.get("asset_id")
        path = groups.get("path")
        if location:
            location = urlunquote(location)
            # ATM carries leading '/' which IMHO is not needed/misguiding somewhat, so
            # I will just strip it
            location = location.lstrip("/")
        if not (asset_type == "dandiset" and dandiset_id):
            raise ValueError(f"{url} does not point to a dandiset")
        # Let's just return a structured record for the requested asset
        asset_ids = {"dandiset_id": dandiset_id, "version": version}
        # if location is not degenerate -- it would be a folder or a file
        if location:
            if location.endswith("/"):
                asset_type = "folder"
            else:
                asset_type = "item"
            asset_ids["location"] = location
        elif asset_key:
            asset_type = "item"
            asset_ids["asset_id"] = asset_key
        elif path:
            asset_type = "folder"
            asset_ids["location"] = path
        # TODO: remove whenever API supports "draft" and this type of url
        if groups.get("id"):
            assert version == "draft"
            asset_ids["folder_id"] = groups["id"]
            asset_type = "folder"

        ret = server_type, server, asset_type, asset_ids
        lgr.debug("Parsed into %s", ret)
        return ret

    @staticmethod
    def follow_redirect(url):
        r = requests.head(url, allow_redirects=True)
        if r.status_code == 404:
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
