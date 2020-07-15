import os.path as op
import re
import requests

from . import girder, get_logger
from .consts import dandiset_metadata_file, known_instances, metadata_digests
from .exceptions import FailedToConnectError, NotFoundError, UnknownURLError
from .utils import flatten, flattened, Parallel, delayed

lgr = get_logger()


class _dandi_url_parser:
    # Defining as a class with all the attributes to not leak all the variables etc
    # into module space, and later we might end up with classes for those anyways
    id_regex = "[a-f0-9]{24}"
    id_grp = f"(?P<id>{id_regex})"
    server_grp = "(?P<server>(?P<protocol>https?)://(?P<hostname>[^/]+)/)"
    known_urls = {
        # Those we first redirect and then handle the redirected URL
        # TODO: Later should better conform to our API, so we could allow
        #       for not only "dandiarchive.org" URLs
        # handle_redirect:
        #   - 'pass' - would continue with original url if no redirect happen
        #   - 'only' - would interrupt if no redirection happens
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
        "https?://.*": {"handle_redirect": "only"},
    }
    # We might need to remap some assert_types
    map_asset_types = {"dandiset": "folder"}
    # And lets create our mapping into girder instances from known_instances:
    map_to_girder = {}
    for girder, *_ in known_instances.values():  # noqa: F402
        for h in _:
            if h:
                map_to_girder[h] = girder

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
        server, asset_type, asset_id
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
            handle_redirect = settings.get("handle_redirect", False)
            if handle_redirect:
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
                    server, *_ = cls.parse(url, map_instance=False)
                    if settings["map_instance"] not in known_instances:
                        raise ValueError(
                            "Unknown instance {}. Known are: {}".format(
                                settings["map_instance"], ", ".join(known_instances)
                            )
                        )
                    return (known_instances[settings["map_instance"]].girder,) + tuple(
                        _
                    )
                continue  # in this run we ignore an match further
            else:
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
        girder_server = cls.map_to_girder.get(
            groups["server"].rstrip("/"), groups["server"]
        )
        if not girder_server.endswith("/"):
            girder_server += "/"  # we expected '/' to be there so let it be

        if "multiitem" not in groups:
            # we must be all set
            asset_ids = [groups["id"]]
            asset_type = groups["asset_type"]
            asset_type = cls.map_asset_types.get(asset_type, asset_type)
        else:
            # we need to split/parse them and return a list
            asset_ids = [i.split("+")[1] for i in groups["multiitem"].split("/") if i]
            asset_type = "item"
        ret = girder_server, asset_type, asset_ids
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


def download(
    urls, output_dir, *, existing="error", jobs=6, develop_debug=False, recursive=True
):
    """Download a file or entire folder from DANDI"""
    urls = flattened([urls])
    if len(urls) > 1:
        raise NotImplementedError("multiple URLs not supported")
    if not urls:
        # if no paths provided etc, we will download dandiset path
        # we are at, BUT since we are not git -- we do not even know
        # on which instance it exists!  Thus ATM we would do nothing but crash
        raise NotImplementedError("No URLs were provided.  Cannot download anything")
    url = urls[0]
    girder_server_url, asset_type, asset_id = parse_dandi_url(url)
    _download_from_girder(
        asset_id, asset_type, output_dir, recursive, existing, jobs, girder_server_url
    )


def _download_from_girder(
    asset_id,
    asset_type,
    output_dir,
    recursive,
    existing,
    jobs,
    girder_server_url,
    authenticate=False,
):
    # We could later try to "dandi_authenticate" if run into permission issues.
    # May be it could be not just boolean but the "id" to be used?
    client = girder.get_client(
        girder_server_url,
        authenticate=authenticate,
        progressbars=True,  # TODO: redo all this
    )
    lgr.info(f"Downloading {asset_type} with id {asset_id} from {girder_server_url}")
    # there might be multiple asset_ids, e.g. if multiple files were selected etc,
    # so we will traverse all of them
    files = flatten(
        client._get_asset_files(
            asset_id_, asset_type, output_dir, authenticate, existing, recursive
        )
        for asset_id_ in set(flattened([asset_id]))
    )
    Parallel(n_jobs=jobs, backend="threading")(
        delayed(client.download_file)(
            file["id"],
            op.join(output_dir, file["path"]),
            existing=existing,
            attrs=file["attrs"],
            # TODO: make it less "fluid" to not breed a bug where we stop verifying
            # for e.g. digests move
            digests={
                d: file.get("metadata")[d]
                for d in metadata_digests
                if d in file.get("metadata", {})
            },
        )
        for file in files
    )
