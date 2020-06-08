import os.path as op
import re
import requests

from . import girder, get_logger
from .consts import dandiset_metadata_file, known_instances, metadata_digests
from .dandiset import Dandiset
from .exceptions import FailedToConnectError, NotFoundError, UnknownURLError
from .utils import flatten, flattened, Parallel, delayed
from .download import parse_dandi_url, _get_asset_files

lgr = get_logger()


def publish(
    dandiset_url,
    base_dir,
    *,
    existing="error",
    jobs=6,
    get_files=True,
    authenticate=False,
    develop_debug=False,
):
    """Publish a DANDI dataset"""
    urls = flattened([dandiset_url])
    if len(urls) > 1:
        raise NotImplementedError("multiple URLs not supported")
    if not urls:
        # if no paths provided etc, we will download dandiset path
        # we are at, BUT since we are not git -- we do not even know
        # on which instance it exists!  Thus ATM we would do nothing but crash
        raise NotImplementedError("No URLs were provided.  Cannot publish anything")
    url = urls[0]
    girder_server_url, asset_type, asset_id = parse_dandi_url(url)

    # We could later try to "dandi_authenticate" if run into permission issues.
    # May be it could be not just boolean but the "id" to be used?
    client = girder.get_client(
        girder_server_url,
        authenticate=authenticate,
        progressbars=True,  # TODO: redo all this
    )

    lgr.info(
        f"Getting folder metadata for {asset_type} with id {asset_id} from {girder_server_url}"
    )
    asset_id = set(flattened([asset_id]))
    if len(asset_id) > 1:
        raise ValueError(
            f"Please point to a single type of dandiset entity. Got: {asset_type}"
        )
    asset_id = asset_id.pop()
    # there might be multiple asset_ids, e.g. if multiple files were selected etc,
    # so we will traverse all of them
    dandiset_meta = _get_dandiset_meta(
        asset_id, asset_type, client, authenticate, get_files=get_files
    )
    identifier = dandiset_meta["dandiset"]["identifier"]
    with open(f"dandiset_{identifier}.json", "wt") as fp:
        import json

        json.dump(dandiset_meta, fp, indent=2)


def _get_dandiset_meta(asset_id, asset_type, client, authenticate, get_files=True):
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
            if not authenticate and girder.is_access_denied(exc):
                lgr.warning("unauthenticated access denied, let's authenticate")
                client.dandi_authenticate()
                continue
            raise
    entity_type = list(set(e["type"] for e in top_entities))
    if len(entity_type) > 1:
        raise ValueError(
            f"Please point to a single type of dandiset entity. Got: {entity_type}"
        )
    entity_type = entity_type[0]
    if entity_type not in ("dandiset",):
        raise ValueError(
            f"Please point to a single type of dandiset entity. Got: {entity_type}"
        )
    # redo recursively
    lgr.info(
        "Traversing remote %ss (%s) recursively",
        entity_type,
        ", ".join(e["name"] for e in top_entities),
    )
    dandiset_meta = top_entities[0].get("metadata", {})
    manifest = None
    if get_files:
        entities = client.traverse_asset(asset_id, asset_type, recursive=True)
        files = (e for e in entities if e["type"] == "file")
        files = flatten(files)
        manifest = []
        for file in files:
            girder_url = (
                f"https://girder.dandiarchive.org/api/v1/file/" f"{file['id']}/download"
            )
            r = requests.head(girder_url)
            if r.status_code == "404":
                raise NotFoundError(f"{girder_url} not found")
            aws_url = r.headers["Location"]
            aws_url = aws_url.split("?")[0]
            file["dandiURL"] = f"https://api.dandiarchive.org/v1/asset/{file['id']}"
            file["awsURL"] = aws_url
            manifest.append(file)
    dandiset_meta["assets"] = manifest
    return dandiset_meta
