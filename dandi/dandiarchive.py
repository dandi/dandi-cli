"""
Interactions with DANDI archive ATM go either through Girder or through DANDI API.

This module provides helpers to decide on which API Client to use and/or
abstract higher level code from specifics of any particular client.

Eventually it is largely to be "dissolved" whenever we stop talking to girder.
"""

import re
from urllib.parse import unquote as urlunquote
from contextlib import contextmanager

import requests

from .consts import known_instances, known_instances_rev
from .exceptions import UnknownURLError, NotFoundError, FailedToConnectError
from .utils import get_instance
from .dandiapi import DandiAPIClient
from . import girder, get_logger


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
    if server_type == "girder":
        asset_id, asset_type, client, server_type = _map_to_girder(url)
        args = asset_id, asset_type
    elif server_type == "api":
        client = DandiAPIClient(server_url)
        args = (asset_id["dandiset_id"], asset_id["version"])
        if asset_id.get("location"):
            # API interface was RFed in 6ba45daf7c00d6cbffd33aed91a984ad28419f56
            # and no longer takes "location" kwarg. There is `get_dandiset_assets`
            # but it doesn't provide dandiset... review the use of navigate_url
            # to see if we should keep its interface as is and provide dandiset...
            raise NotImplementedError(
                "No support for path specific handling via API yet"
            )
    else:
        raise NotImplementedError(
            f"Download from server of type {server_type} is not yet implemented"
        )

    with client.session():
        dandiset, assets = client.get_dandiset_and_assets(
            *args
        )  # , recursive=recursive)
        yield client, dandiset, assets


def _map_to_girder(url):
    """
    discover girder_id for a draft dataset
    """
    # This is a duplicate call from above but it is cheap, so decided to just redo
    # it here instead of passing all the variables + url
    server_type, server_url, asset_type, asset_id = parse_dandi_url(url)
    server_url = known_instances[known_instances_rev[server_url.rstrip("/")]].girder
    client = girder.get_client(server_url, authenticate=False, progressbars=True)
    # TODO: RF if https://github.com/dandi/dandiarchive/issues/316 gets addressed
    # A hybrid UI case not yet adjusted for drafts API.
    # TODO: remove whenever it is gone in an unknown version
    if asset_id.get("folder_id"):
        asset_type = "folder"
        asset_id = [asset_id.get("folder_id")]
    else:
        girder_path = "{}/{}".format("drafts", asset_id["dandiset_id"])
        asset_type = "folder"
        if asset_id.get("location"):
            # Not implemented by UI ATM but might come
            girder_path = "{}/{}".format(girder_path, asset_id["location"])
        try:
            girder_rec = girder.lookup(client, girder_path)
        except BaseException:
            lgr.warning(f"Failed to lookup girder information for {girder_path}")
            girder_rec = None
        if not girder_rec:
            raise RuntimeError(f"Cannot download from {url}")
        asset_id = girder_rec.get("_id")
    return asset_id, asset_type, client, "girder"


class _dandi_url_parser:
    # Defining as a class with all the attributes to not leak all the variables etc
    # into module space, and later we might end up with classes for those anyways
    id_regex = "[a-f0-9]{24}"
    id_grp = f"(?P<id>{id_regex})"
    dandiset_id_grp = "(?P<dandiset_id>[0-9]{6})"
    server_grp = (
        "(?P<server>(?P<protocol>https?)://(?P<hostname>[^/]+)/(api/)?)"
    )  # should absorb port and api/
    known_urls = {
        # Those we first redirect and then handle the redirected URL
        # TODO: Later should better conform to our API, so we could allow
        #       for not only "dandiarchive.org" URLs
        # handle_redirect:
        #   - 'pass' - would continue with original url if no redirect happen
        #   - 'only' - would interrupt if no redirection happens
        # server_type:
        #   - 'girder' - underlying requests should go to girder server
        #   - 'api' - the "new" API service
        # rewrite:
        #   - callable -- which would rewrite that "URI"
        "DANDI:": {"rewrite": lambda x: "https://identifiers.org/" + x},
        "https?://dandiarchive.org/.*": {"handle_redirect": "pass"},
        "https?://identifiers.org/DANDI:.*": {"handle_redirect": "pass"},
        # New DANDI API, ATM can be reached only via enable('DJANGO_API')  in browser console
        # https://gui.dandiarchive.org/#/dandiset/000001/0.201104.2302/files
        # TODO: upload something to any dandiset to see what happens when there are files
        # and adjust for how path is provided (if not ?location=)
        f"(?P<server>(?P<protocol>https?)://(?P<hostname>gui-beta-dandiarchive-org.netlify.app)/)"
        f"#/(?P<asset_type>dandiset)/{dandiset_id_grp}"
        "(/(?P<version>([.0-9]{5,}|draft)))?"
        f"(/files(\\?location=(?P<location>.*)?)?)?"
        "$": {"server_type": "api"},
        #
        # PRs are also on netlify - so above takes precedence. TODO: make more specific?
        "https?://[^/]*dandiarchive-org.netlify.app/.*": {"map_instance": "dandi"},
        #
        # Direct urls to our new API
        f"{server_grp}"
        f"(?P<asset_type>dandiset)s/{dandiset_id_grp}/?"
        "(versions(/(?P<version>([.0-9]{5,}|draft)))?)?"
        "$": {"server_type": "api"},
        # But for drafts files navigator it is a bit different beast and there
        # could be no versions, only draft
        # https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000027/draft/files?_id=5f176583f63d62e1dbd06943&_modelType=folder
        f"{server_grp}"
        f"#/(?P<asset_type>dandiset)/{dandiset_id_grp}"
        "(/(?P<version>draft))?"
        f"(/files(\\?_id={id_grp}(&_modelType=folder)?)?)?"
        "$": {"server_type": "girder"},
        # https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000006/draft
        # (no API yet)
        "https?://.*": {"handle_redirect": "only"},
    }
    # We might need to remap some assert_types
    map_asset_types = {"dandiset": "folder"}
    # And lets create our mapping into girder instances from known_instances:
    map_to = {"girder": {}, "api": {}}
    for (
        metadata_version,
        girder,  # noqa: F402
        gui,
        redirector,
        api,
    ) in known_instances.values():
        for h in (gui, redirector):
            if h:
                if girder:
                    map_to["girder"][h] = girder
                if api:
                    map_to["api"][h] = api

    @classmethod
    def parse(cls, url, *, map_instance=True):
        """Parse url like and return server (address), asset_id and/or directory

        Example URLs (as of 20200310):
        - User public: (Users -> bendichter/Public/Tolias2020)
          [seems to be visible only if logged in]
          old (girder inflicted): https://gui.dandiarchive.org/#/folder/5e5593cc1a343161ff7c5a92
        - Collection top level (Collections -> yarik):
          https://gui.dandiarchive.org/#/collection/5daa5ca7e3489855a3027682
        - Collections: (Collections -> yarik/svoboda)
          old (girder inflicted): https://gui.dandiarchive.org/#/folder/5dab0830f377535c7d96c2b4
        - Dataset landing page metadata
          old (girder inflicted): https://gui.dandiarchive.org/#/dandiset/5e6d5c6976569eb93f451e4f
          now (20210119): https://gui.dandiarchive.org/#/dandiset/000003

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
        for regex, settings in cls.known_urls.items():
            match = re.match(regex, url)
            if not match:
                continue
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
            else:
                server_type = settings.get("server_type", "girder")
                break

        if not match:
            known_regexes = "\n - ".join([""] + list(cls.known_urls))
            # TODO: may be make use of etelemetry and report if newer client
            # which might know is available?
            raise UnknownURLError(
                f"We do not know how to map URL {url} to girder.\n"
                f"Regular expressions for known setups:"
                f"{known_regexes}"
            )

        groups = match.groupdict()
        url_server = groups["server"]
        server = cls.map_to[server_type].get(url_server.rstrip("/"), url_server)

        if not server.endswith("/"):
            server += "/"  # we expected '/' to be there so let it be

        asset_type = groups.get("asset_type")
        dandiset_id = groups.get("dandiset_id")
        version = groups.get("version")
        location = groups.get("location")
        if location:
            location = urlunquote(location)
            # ATM carries leading '/' which IMHO is not needed/misguiding somewhat, so
            # I will just strip it
            location = location.lstrip("/")
        if not (asset_type == "dandiset" and dandiset_id):
            raise ValueError(f"{url} does not point to a dandiset")
        if not version:
            version = "draft"
            # TODO: verify since web UI might have different opinion: it does show e.g.
            # released version for 000001 now, but that one could be produced only from draft
            # so we should be ok.  Otherwise we should always then query "dandiset_read" endpoint
            # to figure out what is the "most recent one"
        # Let's just return a structured record for the requested asset
        asset_ids = {"dandiset_id": dandiset_id, "version": version}
        # if location is not degenerate -- it would be a folder or a file
        if location:
            if location.endswith("/"):
                asset_type = "folder"
            else:
                asset_type = "item"
            asset_ids["location"] = location
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
