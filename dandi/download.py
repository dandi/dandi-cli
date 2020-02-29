import os.path as op
from pathlib import Path, PurePosixPath
import urllib.parse as up

import multiprocessing
from . import girder, get_logger
from .pynwb_utils import get_metadata
from .pynwb_utils import validate as pynwb_validate
from .pynwb_utils import ignore_benign_pynwb_warnings
from .utils import get_utcnow_datetime
from .support.generatorify import generator_from_callback
from .support.pyout import naturalsize

lgr = get_logger()


def parse_dandi_url(url):
    """Parse url like and return server (address), asset_id and/or directory

    Example URLs (as of 20200227):
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

    Individual file:
      dandi???
      https://girder.dandiarchive.org/api/v1/item/5dab0972f377535c7d96c392/download

    It will use some of `known_instance`s to map some urls, e.g. from
    gui.dandiarchive.org ones into girder.

    Returns
    -------
    server, asset_type, asset_id
      asset_type is either asset_id or folder ATM

    """
    u = up.urlsplit(url)
    assert not u.query
    if u.netloc in ("gui.dandiarchive.org", "dandiarchive.org"):
        hostname = "girder.dandiarchive.org"
    else:
        hostname = u.netloc
    # server address is without query and fragment identifier
    server = up.urlunsplit((u[0], hostname, u[2], None, None))
    # The rest will come from fragment
    # TODO: redo with regexp
    frags = u.fragment.rstrip("/").split("/")
    # Just use the term before the last entry which should be the ID
    if (
        len(frags) < 2
        or frags[-2] not in ("folder", "collection")
        or len(frags[-1]) != 24
    ):
        raise ValueError(
            f"Fragment of the following URL is not following desired convention"
            f" .*/(folder|collection)/ID24: {url}"
        )

    return server, frags[-2], frags[-1]


def download(
    urls,
    local_top_path,
    existing,
    develop_debug,
    authenticate=False,  # Seems to work just fine for public stuff
):
    """Download a file or entire folder from DANDI"""
    if len(urls) != 1:
        raise NotImplementedError("multiple URLs not supported")
    url = urls[0]
    girder_server_url, asset_type, asset_id = parse_dandi_url(url)

    # We could later try to "dandi_authenticate" if run into permission issues.
    # May be it could be not just boolean but the "id" to be used?
    client = girder.get_client(girder_server_url, authenticate=authenticate)
    # asset_rec = client.getResource(asset_type, asset_id)
    # lgr.info("Working with asset %s", str(asset_rec))

    # In principle Girder's client already has ability to download any
    # resource (collection/folder/item/file).  But it seems that "mending" it
    # with custom handling (e.g. later adding filtering to skip some files,
    # or add our own behavior on what to do when files exist locally, etc) would
    # not be easy.  So we will reimplement as a two step (kinda) procedure.

    # Return a generator which would be traversing girder and yield records
    # of encountered resources.
    # TODO later:  may be look into making it async

    try:
        # this one should enhance them with "fullpath"
        entities = client.traverse_asset(asset_id, asset_type)
    except girder.gcl.HttpError as exc:
        response = girder.get_HttpError_response(exc)
        if not authenticate and (
            exc.status == 401 or "access denied" in response.get("message", "")
        ):
            lgr.warning("unauthenticated access denied, let's authenticate")
            client.dandi_authenticate()
            entities = client.traverse_asset(asset_id, asset_type)
        else:
            raise
    for e in entities:
        print(e)
    # we care only about files ATM
    files = (e for e in entities if e["type"] == "file")
    for file in files:
        client.download(
            file["id"], op.join(local_top_path, file["path"]), file["attrs"]
        )
