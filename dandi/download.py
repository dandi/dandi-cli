import os.path as op
import requests
import urllib.parse as up

from . import girder, get_logger
from .consts import dandiset_metadata_file
from .dandiset import Dandiset
from .utils import flattened

lgr = get_logger()


def parse_dandi_url(url):
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
      https://gui.dandiarchive.org/#/dandiset-meta/5e6d5c6976569eb93f451e4f

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

    - supports DANDI naming, such as https://dandiarchive.org/dandiset/000001
      Since currently redirects, it just resorts to redirect if url lacks #.
      TODO: make more efficient, .head instead of .get or some other way to avoid
      full download_file.
    - uses some of `known_instance`s to map some urls, e.g. from
      gui.dandiarchive.org ones into girder.

    Returns
    -------
    server, asset_type, asset_id
      asset_type is either asset_id or folder ATM. asset_id might be a list
      in case of multiple files

    """
    if "#" not in url:
        # assume that it was a dandi notation, let's try to follow redirects
        # TODO: make .head work instead of .get on the redirector
        r = requests.get(url, allow_redirects=True)
        if r.status_code != 200:
            lgr.warning(
                f"Response for getting {url} to redirect returned "
                f"{r.status_code}.  We will ignore returned result."
            )
        elif r.url != url:
            url = r.url
        else:
            lgr.warning(f"Redirection did not happen for {url}")

    # We will just allow exception to escape if something goes wrong.
    # Warnings above could provide a clue in some cases
    u = up.urlsplit(url)
    assert not u.query

    if u.netloc in ("gui.dandiarchive.org", "dandiarchive.org"):
        hostname = "girder.dandiarchive.org"
    elif u.netloc in ("localhost:8092",):  # ad-hoc eh
        hostname = "localhost:8091"
    else:
        hostname = u.netloc

    # server address is without query and fragment identifier
    server = up.urlunsplit((u[0], hostname, u[2], None, None))
    # The rest will come from fragment
    # TODO: redo with regexp
    frags = u.fragment.rstrip("/").split("/")
    item_prefix = "item+"  # just a constant for reuse
    if (
        len(frags) >= 2
        and frags[-2] in ("folder", "collection", "dandiset-meta")
        and len(frags[-1]) == 24
    ):
        # Just use the term before the last entry which should be the ID
        if frags[-2] == "dandiset-meta":
            frags[-2] = "folder"
        asset_type = frags[-2]
        asset_ids = frags[-1]  # a single one
    elif "selected" in frags and frags[-1].startswith(item_prefix):
        # single or multiple files selected in web ui
        # get all item+ after selected
        asset_ids = []
        for v in frags[frags.index("selected") + 1 :]:
            if not v.startswith(item_prefix):
                raise ValueError(
                    f"Fragment seems to point to individual selected items but "
                    f"{v} is not of {item_prefix!r} format in the url: {url}"
                )
            asset_ids.append(v[len(item_prefix) :])
        asset_type = "item"
    else:
        raise ValueError(
            f"Fragment of the following URL is not following desired convention"
            f" .*/(folder|collection|dandiset-meta)/ID24 or pointing to "
            f"individual selected items: {url}"
        )
    return server, asset_type, asset_ids


def download(
    urls,
    output_dir,
    existing="error",
    develop_debug=False,
    authenticate=False,  # Seems to work just fine for public stuff
    recursive=True,
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
    files = flattened(
        _get_asset_files(
            asset_id_, asset_type, output_dir, client, authenticate, existing, recursive
        )
        for asset_id_ in set(flattened([asset_id]))
    )

    for file in files:
        client.download_file(
            file["id"],
            op.join(output_dir, file["path"]),
            existing=existing,
            attrs=file["attrs"],
        )


def _get_asset_files(
    asset_id, asset_type, output_dir, client, authenticate, existing, recursive
):
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
    # First we access top level records just to sense what we are working with
    top_entities = None
    while True:
        try:
            # this one should enhance them with "fullpath"
            top_entities = list(
                client.traverse_asset(asset_id, asset_type, recursive=False)
            )
            break
        except girder.gcl.HttpError as exc:
            response = girder.get_HttpError_response(exc)
            if not authenticate and (
                exc.status == 401 or "access denied" in response.get("message", "")
            ):
                lgr.warning("unauthenticated access denied, let's authenticate")
                client.dandi_authenticate()
                continue
            raise
    entity_type = list(set(e["type"] for e in top_entities))
    if len(entity_type) > 1:
        raise ValueError(
            f"Please point to a single type of entity - either dandiset(s),"
            f" folder(s) or file(s).  Got: {entity_type}"
        )
    entity_type = entity_type[0]
    if entity_type in ("dandiset", "folder"):
        # redo recursively
        lgr.info(
            "Traversing remote %ss (%s) recursively and downloading them " "locally",
            entity_type,
            ", ".join(e["name"] for e in top_entities),
        )
        entities = client.traverse_asset(asset_id, asset_type, recursive=recursive)
        # TODO: special handling for a dandiset -- we might need to
        #  generate dandiset.yaml out of the metadata record
        # we care only about files ATM
        files = (e for e in entities if e["type"] == "file")
    elif entity_type == "file":
        files = top_entities
    else:
        raise ValueError(f"Unexpected entity type {entity_type}")
    if entity_type == "dandiset":
        for e in top_entities:
            dandiset_path = op.join(output_dir, e["path"])
            dandiset_yaml = op.join(dandiset_path, dandiset_metadata_file)
            lgr.info(
                f"Updating {dandiset_metadata_file} from obtained dandiset " f"metadata"
            )
            if op.lexists(dandiset_yaml):
                if existing != "overwrite":
                    lgr.info(
                        f"{dandiset_yaml} already exists.  Set 'existing' "
                        f"to overwrite if you want it to be redownloaded. "
                        f"Skipping"
                    )
                    continue
            dandiset = Dandiset(dandiset_path, allow_empty=True)
            if not dandiset.path_obj.exists():
                dandiset.path_obj.mkdir()
            dandiset.update_metadata(e.get("metadata", {}).get("dandiset", {}))
    return files
