import hashlib

from pprint import pprint  # TEMP TODO remove
import os
import os.path as op
import random
import re
import requests
import time

from urllib.parse import unquote as urlunquote

from . import girder, get_logger
from .consts import (
    dandiset_metadata_file,
    known_instances,
    known_instances_rev,
    metadata_digests,
)
from .dandiset import Dandiset
from .exceptions import FailedToConnectError, NotFoundError, UnknownURLError
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
        "$": {"server_type": "dandiapi"},
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

    # We could later try to "dandi_authenticate" if run into permission issues.
    # May be it could be not just boolean but the "id" to be used?
    # TODO: remove whenever API starts to support drafts in an unknown version
    if server_type == "dandiapi" and asset_id.get("version") == "draft":
        server_url = known_instances[known_instances_rev[server_url.rstrip("/")]].girder
        server_type = "girder"

        # "draft" datasets are not yet supported throught dandiapi. So we need to
        # perform special handling for now: discover girder_id for it and then proceed
        # with girder
        client = girder.get_client(server_url, authenticate=False, progressbars=True)
        # TODO: RF if https://github.com/dandi/dandiarchive/issues/316 gets addressed
        # A hybrid UI case not yet adjusted for drafts API. TODO: remove whenever it is gone in an unknown version
        if asset_id.get("folder_id"):
            asset_type = "folder"
            asset_id = [asset_id.get("folder_id")]
        else:
            girder_path = op.join("drafts", asset_id["dandiset_id"])
            asset_type = "folder"
            if asset_id.get("location"):
                # Not implemented by UI ATM but might come
                girder_path = op.join(girder_path, asset_id["location"])
            try:
                girder_rec = girder.lookup(client, girder_path)
            except:
                lgr.warning(f"Failed to lookup girder information for {girder_path}")
                girder_rec = None
            if not girder_rec:
                raise RuntimeError(f"Cannot download from {url}")
            asset_id = girder_rec.get("_id")
        args = asset_id, asset_type
    elif server_type == "girder":
        client = girder.get_client(
            server_url, authenticate=False, progressbars=True  # TODO: redo all this
        )
        args = asset_id, asset_type
    elif server_type == "dandiapi":
        from .dandiapi import DandiAPIClient

        client = DandiAPIClient(server_url)
        args = (asset_id["dandiset_id"], asset_id["version"], asset_id.get("location"))
    else:
        raise NotImplementedError(
            f"Download from server of type {server_type} is not yet implemented"
        )

    with client.session():
        # TODO: analysis for 'existing' for every item

        dandiset, assets = client.get_dandiset_and_assets(*args)  # recursive=recursive

        # TODO: wrap within pyout or tqdm capable "frontend"
        if dandiset:
            # TODO: if we are ALREADY in a dandiset - we can validate that it is the
            # same dandiset and use that dandiset path as the one to download under
            dandiset_path = op.join(output_dir, dandiset["dandiset"]["identifier"])
            for resp in _populate_dandiset_yaml(
                dandiset_path,
                dandiset.get("metadata", {}).get("dandiset", {}),
                existing == "overwrite",
            ):
                resp = dict(path=dandiset_metadata_file, **resp)
                print(resp)  # TEMP TODO
        else:
            dandiset_path = None

        # TODO: do analysis of assets for early detection of needed renames etc
        # to avoid any need for late treatment of existing and also for
        # more efficient download if files are just renamed etc

        for asset in assets:
            # unavoidable ugliness since girder and API have different "scopes" for identifying an asset
            digests_from_metadata = {
                d: asset.get("metadata")[d]
                for d in metadata_digests
                if d in asset.get("metadata", {})
            }

            if server_type == "girder":
                # TODO: harmonize
                down_args = (asset["id"],)
                digests = digests_from_metadata
            elif server_type == "dandiapi":
                # Even worse to get them from the asset record which also might have its return
                # record still changed, https://github.com/dandi/dandi-publish/issues/79
                down_args = args[:2] + (asset["uuid"],)
                if "sha256" not in asset:
                    lgr.warning("For some reason - there no sha256 in %s", str(asset))
                    digests = digests_from_metadata
                else:
                    digests = {"sha256": asset["sha256"]}
                    if (
                        "sha256" in digests_from_metadata
                        and asset["sha256"] != digests_from_metadata["sha256"]
                    ):
                        lgr.warning(
                            "Metadata seems to be outdated since API returned different sha256 for {path}"
                        )

            path = asset["path"].lstrip("/")  # make into relative path
            path = download_path = op.normpath(path)
            if dandiset_path:  # place under dandiset directory
                download_path = op.join(dandiset_path, path)
            download_path = op.join(output_dir, download_path)

            downloader = client.get_download_file_iter(*down_args)

            # Get size from the metadata, although I guess it could be returned directly
            # by server while establishing downloader... but it seems that girder itself
            # does get it from the "file" resource, not really from direct URL.  So I guess
            # we will just follow. For now we must find it in "attrs"
            for resp in _download_file(
                downloader,
                download_path,
                # size and modified generally should be there but better to redownload
                # than to crash
                size=asset.get("size"),
                mtime=asset.get("modified"),
                existing=existing,
                digests=digests,
            ):
                resp = dict(path=path, **resp)
                print(resp)


if False:
    # TODO: move where it belongs!

    import pdb

    pdb.set_trace()

    Parallel(n_jobs=jobs, backend="threading")(
        delayed(client.download_file)(
            rec["id"],
            op.join(output_dir, rec["path"]),
            existing=existing,
            attrs=rec["attrs"],
            # TODO: make it less "fluid" to not breed a bug where we stop verifying
            # for e.g. digests move
            digests={
                d: rec.get("metadata")[d]
                for d in metadata_digests
                if d in rec.get("metadata", {})
            },
        )
        for rec in asset_recs
    )


def skip_file(msg):
    return {"status": "skipped", "message": str(msg)}


def _populate_dandiset_yaml(dandiset_path, metadata, overwrite):
    if not metadata:
        lgr.warning(
            "Got completely empty metadata record for dandiset, not producing dandiset.yaml"
        )
        return
    dandiset_yaml = op.join(dandiset_path, dandiset_metadata_file)
    yield {"message": "updating"}
    lgr.debug(f"Updating {dandiset_metadata_file} from obtained dandiset " f"metadata")
    if op.lexists(dandiset_yaml) and not overwrite:
        yield skip_file("already exists")
        return
    else:
        dandiset = Dandiset(dandiset_path, allow_empty=True)
        dandiset.path_obj.mkdir(exist_ok=True)  # exist_ok in case of parallel race
        dandiset.update_metadata(metadata)
        yield {"status": "done"}


def _download_file(
    downloader, path, size=None, mtime=None, existing="error", digests=None
):
    """Common logic for downloading a single file

    Generator downloader:

    TODO: describe expected records it should yield
    - progress
    - error
    - completion

    Parameters
    ----------
    downloader: generator
      A backend (girder or dandiapi) specific fixture for downloading some file into
      path. It should be a generator yielding downloaded blocks.
    size: int, optional
      Target size if known
    digests: dict, optional
      possible checksums or other digests provided for the file. Only one
      will be used to verify download
    """

    if op.lexists(path):
        block = f"File {path!r} already exists"
        if existing == "error":
            raise FileExistsError(block)
        elif existing == "skip":
            yield skip_file("already exists")
            return
        elif existing == "overwrite":
            pass
        elif existing == "refresh":
            if mtime is None:
                lgr.warning(
                    f"{path!r} - no mtime or ctime in the record, redownloading"
                )
            else:
                stat = os.stat(op.realpath(path))
                same = []
                if is_same_time(stat.st_mtime, mtime):
                    same.append("mtime")
                if size is not None and stat.st_size == size:
                    same.append("size")
                # TODO: use digests if available? or if e.g. size is identical but mtime is different
                if same == ["mtime", "size"]:
                    # TODO: add recording and handling of .nwb object_id
                    yield skip_file("same time and size")
                    return
                lgr.debug(f"{path!r} - same attributes: {same}.  Redownloading")

    destdir = op.dirname(path)
    os.makedirs(destdir, exist_ok=True)

    yield {"status": "downloading"}

    algo, digester, digest, downloaded_digest = None, None, None, None
    if digests:
        # choose first available for now.
        # TODO: reuse that sorting based on speed
        for algo, digest in digests.items():
            digester = getattr(hashlib, algo, None)
            if digester:
                break
        if not digester:
            lgr.warning("Found no digests in hashlib for any of %s", str(digests))

    # TODO: how do we discover the total size????
    # TODO: do not do it in-place, but rather into some "hidden" file
    for attempt in range(3):
        try:
            downloaded = 0
            if digester:
                downloaded_digest = digester()  # start empty
            warned = False
            # I wonder if we could make writing async with downloader
            with open(path, "wb") as writer:
                for block in downloader:
                    if digester:
                        downloaded_digest.update(block)
                    downloaded += len(block)
                    # TODO: yield progress etc
                    msg = {"downloaded": downloaded}
                    if size:
                        if downloaded > size and not warned:
                            # Yield ERROR?
                            lgr.warning(
                                "Downloaded %d bytes although size was told to be just %d",
                                downloaded,
                                size,
                            )
                        msg["downloaded%"] = 100 * downloaded / size if size else "100"
                        # TODO: ETA etc
                    yield msg
                    writer.write(block)
            break
            # both girder and we use HttpError
        except requests.exceptions.HTTPError as exc:
            # TODO: actually we should probably retry only on selected codes, and also
            # respect Retry-After
            import pdb

            pdb.set_trace()
            if attempt >= 2 or exc.status not in (
                400,  # Bad Request, but happened with gider: https://github.com/dandi/dandi-cli/issues/87
                503,  # Service Unavailable
            ):
                raise
            # if is_access_denied(exc) or attempt >= 2:
            #     raise
            # sleep a little and retry
            lgr.debug(
                "Failed to download on attempt#%d, will sleep a bit and retry", attempt
            )
            time.sleep(random.random() * 5)

    if downloaded_digest:
        downloaded_digest = downloaded_digest.hexdigest()  # we care only about hex
        if digest != downloaded_digest:
            msg = f"{algo}: downloaded {downloaded_digest} != {digest}"
            yield {
                "errors": 1,
                "checksum": "differs",
                "status": "error",
                "message": msg,
            }
            lgr.warning("%s is different: %s.", path, msg)
            return
        else:
            yield {"checksum": "ok"}
            lgr.debug("Verified that %s has correct %s %s", path, algo, digest)
    else:
        # shouldn't happen with more recent metadata etc
        yield {"checksum": "N/A", "message": "no digests were provided"}

    # It seems that girder might not care about setting either mtime, so we will do if we know
    # TODO: dissolve attrs and pass specific mtime?
    if mtime:
        yield {"status": "setting mtime"}
        os.utime(path, (time.time(), mtime.timestamp()))

    yield {"status": "done"}


from .consts import REQ_BUFFER_SIZE
