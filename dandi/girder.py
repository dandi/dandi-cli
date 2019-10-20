import json
import keyring
import sys

from pathlib import Path

import girder_client as gcl

from .utils import memoize
from . import get_logger

lgr = get_logger()


# TODO: more flexible
class GirderServer:
    __slots__ = ["url"]

    def __init__(self, url):
        self.url = url


known_instances = {
    "local": GirderServer("http://localhost:8080/"),
    "dandi": GirderServer("https://girder.dandiarchive.org/"),
}


class GirderNotFound(Exception):
    pass


@memoize
def lookup(client, collection, path=None):
    """A helper for common logic while looking up things on girder"""
    req = f"/collection/{collection}"
    target = "Collection"
    if path:
        req += f"/{path}"
        target = "Path"

    try:
        return client.resourceLookup(req)
    except gcl.HttpError as exc:
        response = {}
        responseText = getattr(exc, "responseText", "")
        try:
            response = json.loads(responseText)
        except Exception as exc2:
            lgr.debug("Cannot parse response %s as json: %s", responseText, exc2)
        if not (response and f"{target} not found" in response["message"]):
            raise exc  # we dunno much about this - so just reraise
        # but if it was indeed just a miss -- raise our dedicated Exception
        lgr.debug(f"{target} was not found: {response}")
        raise GirderNotFound(response)


from requests.adapters import HTTPAdapter


class GirderCli(gcl.GirderClient):
    pass
    # XXX causes strange 'NoneType' object has no attribute 'close'
    #  so TODO to investigate
    # def sendRestRequest(self, *args, **kwargs):
    #     with self.session() as session:
    #         # TODO: avoid hardcoded max_retries -- setup taken from girder_cli.client
    #         session.mount(self.urlBase, HTTPAdapter(max_retries=5))
    #         return super(GirderCli, self).sendRestRequest(*args, **kwargs)


# TODO: our adapter on top of the Girder's client to simplify further
def authenticate(instance):
    """Simple authenticator which would store credential (api key) via keyring

    Parameters
    ----------
    instance: str
      Name of the instance to use
    """
    client = GirderCli(
        apiUrl="{}/api/v1".format(known_instances[instance].url.rstrip("/"))
    )
    from pathlib import Path, PosixPath

    app_id = "dandi-girder-{}".format(instance)
    api_key = keyring.get_password(app_id, "key")
    # the dance about rejected authentication etc
    while True:
        if not api_key:
            api_key = input(
                "Please provide API Key (created/found in My Account/API keys "
                "in Girder) for {}: ".format(instance)
            )
            keyring.set_password(app_id, "key", api_key)
        try:
            client.authenticate(apiKey=api_key)
            break
        except Exception as exc:
            sys.stderr.write("Failed to authenticate: {}".format(exc))
            api_key = None
    return client


def ensure_collection(client, collection):
    try:
        return lookup(client, collection=collection)
    except GirderNotFound:
        lgr.info(f"Collection {collection} was not found, creating")
        # TODO: split away or provide UI to tune (private, description)
        return client.createCollection(collection, public=True)


def ensure_folder(client, collection_rec, collection, folder):
    """Ensure presence of the folder.  If not present -- create all leading

    TODO:
     - ATM doesn't care about providing `description` and `public` options
     - doesn't check the type in folder_rec -- may be a file???
    """
    try:
        folder_rec = lookup(client, collection=collection, path=folder)
    except GirderNotFound:
        # We need to create all the leading paths if not there yet, and arrive
        # to the target folder.
        # We will rely on @memoize over lookup for all the folder_rec querying
        parent_id = collection_rec["_id"]
        parent_type = "collection"
        parent_path = Path()
        for parent_dirname in folder.parts:
            parent_path /= parent_dirname
            try:
                folder_rec = lookup(client, collection=collection, path=parent_path)
            except GirderNotFound:
                lgr.debug(f"Forder {parent_dirname} was not found, creating")
                folder_rec = client.createFolder(
                    parent_id, parent_dirname, parentType=parent_type
                )
            parent_id = folder_rec["_id"]
            parent_type = "folder"
    lgr.debug(f"Folder: {folder_rec}")
    return folder_rec
