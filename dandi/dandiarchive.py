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
    # TODO: remove whenever API starts to support drafts in an unknown version
    if server_type == "api" and asset_id.get("version") == "draft":
        asset_id, asset_type, client, server_type = _map_to_girder(url)
        args = asset_id, asset_type
    elif server_type == "girder":
        client = girder.get_client(
            server_url, authenticate=False, progressbars=True  # TODO: redo all this
        )
        args = asset_id, asset_type
    elif server_type == "api":
        client = DandiAPIClient(server_url)
        args = (asset_id["dandiset_id"], asset_id["version"], asset_id.get("location"))
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
    "draft" datasets are not yet supported through our DANDI API. So we need to
    perform special handling for now: discover girder_id for it and then proceed
    with girder
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
    server_grp = "(?P<server>(?P<protocol>https?)://(?P<hostname>[^/]+)/)"
    known_urls = {
        # Those we first redirect and then handle the redirected URL
        # TODO: Later should better conform to our API, so we could allow
        #       for not only "dandiarchive.org" URLs
        # handle_redirect:
        #   - 'pass' - would continue with original url if no redirect happen
        #   - 'only' - would interrupt if no redirection happens
        # server_type:
        #   - 'girder' - the default/old
        #   - 'api' - the "new" (as of 20200715 state of various PRs)
        # rewrite:
        #   - callable -- which would rewrite that "URI"
        "DANDI:": {"rewrite": lambda x: "https://identifiers.org/" + x},
        "https?://dandiarchive.org/.*": {"handle_redirect": "pass"},
        "https?://identifiers.org/DANDI:.*": {"handle_redirect": "pass"},
        "https?://[^/]*dandiarchive-org.netlify.app/.*": {"map_instance": "dandi"},
        # Girder-inflicted urls to folders etc based on the IDs
        # For those we will completely ignore domain - it will be "handled"
        f"{server_grp}#.*/(?P<asset_type>folder|collection|dandiset)/{id_grp}$": {},
        # Nothing special
        # Multiple items selected - will need custom handling of 'multiitem'
        f"{server_grp}#/folder/{id_regex}/selected(?P<multiitem>(/item\\+{id_grp})+)$": {},
        # Direct girder urls to items
        f"{server_grp}api/v1/(?P<asset_type>item)/{id_grp}/download$": {},
        # New DANDI API
        # https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000006/0.200714.1807
        # https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000006/0.200714.1807/files
        # https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000006/0.200714.1807/files?location=%2Fsub-anm369962%2F
        # But for drafts files navigator it is a different beast:
        # https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000027/draft/files?_id=5f176583f63d62e1dbd06943&_modelType=folder
        f"{server_grp}#.*/(?P<asset_type>dandiset)/{dandiset_id_grp}"
        "/(?P<version>([.0-9]{5,}|draft))"
        "(/files(\\?location=(?P<location>.*)?)?)?"
        f"(/files(\\?_id={id_grp}(&_modelType=folder)?)?)?"
        "$": {"server_type": "api"},
        # https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000006/draft
        # (no API yet)
        "https?://.*": {"handle_redirect": "only"},
    }
    # We might need to remap some assert_types
    map_asset_types = {"dandiset": "folder"}
    # And lets create our mapping into girder instances from known_instances:
    map_to = {"girder": {}, "api": {}}
    for girder, gui, redirector, api in known_instances.values():  # noqa: F402
        for h in (gui, redirector):
            if h:
                map_to["girder"][h] = girder
                map_to["api"][h] = api

    @classmethod
    def parse(cls, url, *, map_instance=True):
        """Parse url like and return server (address), asset_id and/or directory

        Example URLs (as of 20200310):
        - User public: (Users -> bendichter/Public/Tolias2020)
          [seems to be visible only if logged in]
          https://gui.dandiarchive.org/#/folder/5e5593cc1a343161ff7c5a92
          https://girder.dandiarchive.org/#user/5da4b8fe51c340795cb18fd0/folder/5e5593cc1a343161ff7c5a92
        - Collection top level (Collections -> yarik):
          https://gui.dandiarchive.org/#/collection/5daa5ca7e3489855a3027682
          https://girder.dandiarchive.org/#collection/5daa5ca7e3489855a3027682
        - Collections: (Collections -> yarik/svoboda)
          https://gui.dandiarchive.org/#/folder/5dab0830f377535c7d96c2b4
          https://girder.dandiarchive.org/#collection/5daa5ca7e3489855a3027682/folder/5dab0830f377535c7d96c2b4
        - Dataset landing page metadata
          https://gui.dandiarchive.org/#/dandiset/5e6d5c6976569eb93f451e4f

        Individual and multiple files:
          - dandi???
          - girder -- we don't support:
            https://girder.dandiarchive.org/api/v1/item/5dab0972f377535c7d96c392/download
          - gui.: support single or multiple
            # if there is a selection, we could get multiple items
            https://gui.dandiarchive.org/#/folder/5e60c14f81bc3e47d94aa012/selected/item+5e60c19381bc3e47d94aa014

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

        if server_type == "girder":
            if "multiitem" not in groups:
                # we must be all set
                asset_ids = [groups["id"]]
                asset_type = groups["asset_type"]
                asset_type = cls.map_asset_types.get(asset_type, asset_type)
            else:
                # we need to split/parse them and return a list
                asset_ids = [
                    i.split("+")[1] for i in groups["multiitem"].split("/") if i
                ]
                asset_type = "item"
        elif server_type == "api":
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
                raise NotImplementedError(
                    f"{url} does not point to a specific version (or draft). DANDI ppl should "
                    f"decide what should be a behavior in such cases"
                )
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
        else:
            raise RuntimeError(f"must not happen. We got {server_type}")
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
