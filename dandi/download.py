import inspect
import os
import os.path as op
import re
import requests
import time

from urllib.parse import unquote as urlunquote

from . import girder, get_logger
from .consts import dandiset_metadata_file, known_instances, metadata_digests
from .exceptions import FailedToConnectError, NotFoundError, UnknownURLError
from .support.digests import Digester
from .utils import Parallel, delayed, ensure_datetime, flatten, flattened, is_same_time

lgr = get_logger()


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
        #   - 'dandiapi' - the "new" (as of 20200715 state of various PRs)
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
        f"{server_grp}#.*/(?P<asset_type>dandiset)/{dandiset_id_grp}"
        "/(?P<version>([.0-9]{5,}|draft))"
        "(/files(\\?location=(?P<location>.*)?)?)?$": {"server_type": "dandiapi"},
        # https://deploy-preview-341--gui-dandiarchive-org.netlify.app/#/dandiset/000006/draft (no API yet)
        "https?://.*": {"handle_redirect": "only"},
    }
    # We might need to remap some assert_types
    map_asset_types = {"dandiset": "folder"}
    # And lets create our mapping into girder instances from known_instances:
    map_to = {"girder": {}, "dandiapi": {}}
    for girder, gui, redirector, dandiapi in known_instances.values():  # noqa: F402
        for h in (gui, redirector):
            if h:
                map_to["girder"][h] = girder
                map_to["dandiapi"][h] = dandiapi

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
                    server_type, server, *_ = cls.parse(url, map_instance=False)
                    if settings["map_instance"] not in known_instances:
                        raise ValueError(
                            "Unknown instance {}. Known are: {}".format(
                                settings["map_instance"], ", ".join(known_instances)
                            )
                        )
                    known_instance = known_instances[settings["map_instance"]]
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
        elif server_type == "dandiapi":
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
    server_type, server_url, asset_type, asset_id = parse_dandi_url(url)

    # TODO: analysis for 'existing' for every item
    if server_type == "girder":
        return _download_from_girder(
            server_url, asset_type, asset_id, output_dir, recursive, existing, jobs
        )
    elif server_type == "dandiapi":
        return _download_from_dandiapi(
            server_url,
            asset_id["dandiset_id"],
            asset_id["version"],
            asset_id.get("location"),
            output_dir,
            recursive,
            existing,
            jobs,
        )
    else:
        raise NotImplementedError(
            f"Download from server of type {server_type} is not yet implemented"
        )


def _download_from_dandiapi(
    server_url, dandiset_id, version, location, output_dir, recursive, existing, jobs
):
    # Fun begins!
    location_ = "/" + location if location else ""
    lgr.info(
        f"Downloading {dandiset_id}{location_} (version: {version}) from {server_url}"
    )

    # TODO: get all assets
    # 1. includes sha256, created, updated but those are of "girder" level so lack "uploaded_mtime"
    # and uploaded_nwb_object_id forbidding logic for deducing necessity to update/move.
    # But we still might want to rely on its sha256 instead of metadata since older uploads
    # would not have that metadata in them
    # 2. there is no API to list assets given a location
    from .dandiapi import DandiAPIClient

    client = DandiAPIClient(server_url)
    with client.session():
        # TODO: location
        assets = client.get_dandiset_assets(dandiset_id, version)
        lgr.info("TODO: download %d assets", len(assets))
        # import pdb; pdb.set_trace()
        # TODO: download all assets

        # TODO: get metadata record for digests etc
        #  might be needed in cases when there is an existing local file and strategy is not to
        #  just override
        # "/dandisets/{dandiset_id}/versions/{version}/assets/{uuid}/"
        # TODO: actual download
        "/dandisets/{dandiset_id}/versions/{version}/assets/{uuid}/download/"
    pass


def _download_from_girder(
    server_url,
    asset_type,
    asset_id,
    output_dir,
    recursive,
    existing,
    jobs,
    authenticate=False,
):
    # We could later try to "dandi_authenticate" if run into permission issues.
    # May be it could be not just boolean but the "id" to be used?
    client = girder.get_client(
        server_url, authenticate=authenticate, progressbars=True  # TODO: redo all this
    )
    lgr.info(f"Downloading {asset_type} with id {asset_id} from {server_url}")
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


def _get_file_mtime(attrs):
    if not attrs:
        return None
    # We would rely on uploaded_mtime from metadata being stored as mtime.
    # If that one was not provided, the best we know is the "ctime"
    # for the file, use that one
    return ensure_datetime(attrs.get("mtime", attrs.get("ctime", None)))


def _download_file(downloader, path, existing="error", attrs=None, digests=None):
    """Common logic for downloading a single file

    Generator downloader:

    TODO: describe expected records it should yield
    - progress
    - error
    - completion

    Parameters
    ----------
    downloader: callable
      A backend (girder or dandiapi) specific fixture for downloading some file into
      path. It could be a function or a generator.
    digests: dict, optional
      possible checksums or other digests provided for the file. Only one
      will be used to verify download
    """
    if op.lexists(path):
        msg = f"File {path!r} already exists"
        if existing == "error":
            raise FileExistsError(msg)
        elif existing == "skip":
            lgr.info(msg + " skipping")
            return
        elif existing == "overwrite":
            pass
        elif existing == "refresh":
            remote_file_mtime = _get_file_mtime(attrs)
            if remote_file_mtime is None:
                lgr.warning(
                    f"{path!r} - no mtime or ctime in the record, redownloading"
                )
            else:
                stat = os.stat(op.realpath(path))
                same = []
                if is_same_time(stat.st_mtime, remote_file_mtime):
                    same.append("mtime")
                if "size" in attrs and stat.st_size == attrs["size"]:
                    same.append("size")
                if same == ["mtime", "size"]:
                    # TODO: add recording and handling of .nwb object_id
                    lgr.info(f"{path!r} - same time and size, skipping")
                    return
                lgr.debug(f"{path!r} - same attributes: {same}.  Redownloading")

    destdir = op.dirname(path)
    os.makedirs(destdir, exist_ok=True)
    if inspect.isgenerator(downloader):
        yield from downloader
    else:
        downloader()
    # It seems that above call does not care about setting either mtime
    if attrs:
        mtime = _get_file_mtime(attrs)
        if mtime:
            os.utime(path, (time.time(), mtime.timestamp()))
    if digests:
        # Pick the first one (ordered according to speed of computation)
        for algo in metadata_digests:
            if algo in digests:
                break
        else:
            algo = list(digests)[:1]  # first available
        digest = Digester([algo])(path)[algo]
        if digests[algo] != digest:
            lgr.warning(
                "%s %s is different: downloaded %s, should have been %s.",
                path,
                algo,
                digest,
                digests[algo],
            )
        else:
            lgr.debug("Verified that %s has correct %s %s", path, algo, digest)
