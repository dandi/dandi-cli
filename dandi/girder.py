import os.path as op
import json
import keyring
import sys

from functools import lru_cache
from pathlib import Path, PurePosixPath

import girder_client as gcl

from . import get_logger

lgr = get_logger()


# TODO: more flexible
class GirderServer:
    __slots__ = ["url"]

    def __init__(self, url):
        self.url = url


# name: url
known_instances = {
    "local": "http://localhost:8080",
    "dandi": "https://girder.dandiarchive.org",
}
# to map back url: name
known_instances_rev = {v: k for k, v in known_instances.items()}
assert len(known_instances) == len(known_instances_rev)


class GirderNotFound(Exception):
    pass


@lru_cache(1024)
def lookup(client, name, asset_type="collection", path=None):
    """A helper for common logic while looking up things on girder by name"""
    req = f"/{asset_type}/{name}"
    target_msg = asset_type.capitalize()
    if path is not None:
        req += f"/{path}"
        target_msg = "Path"

    try:
        return client.resourceLookup(req)
    except gcl.HttpError as exc:
        response = get_HttpError_response(exc) or {}
        if not (response and f"{target_msg} not found" in response["message"]):
            raise exc  # we dunno much about this - so just reraise
        # but if it was indeed just a miss -- raise our dedicated Exception
        lgr.debug(f"{target_msg} was not found: {response}")
        raise GirderNotFound(response)


def get_HttpError_response(exc):
    """Given an gcl.HttpError exception instance, parse and return response

    Returns
    -------
    None or dict
      If exception does not contain valid json response record, returns None
    """
    try:
        responseText = getattr(exc, "responseText", "")
        return json.loads(responseText)
    except Exception as exc2:
        lgr.debug("Cannot parse response %s as json: %s", responseText, exc2)
    return None


from requests.adapters import HTTPAdapter


class GirderCli(gcl.GirderClient):
    """An "Adapter" to GirderClient

    ATM it just inherits from GirderClient. But in the long run we might want
    to make it fulfill our API and actually become and adapter (and delegate)
    to GirderClient.  TODO
    """

    def __init__(self, server_url):
        self._server_url = server_url.rstrip("/")
        super().__init__(apiUrl="{}/api/v1".format(self._server_url))

    def dandi_authenticate(self):
        if self._server_url in known_instances_rev:
            client_name = known_instances_rev[self._server_url]
        else:
            raise NotImplementedError("TODO client name derivation for keyring")

        app_id = "dandi-girder-{}".format(client_name)
        api_key = keyring.get_password(app_id, "key")
        # the dance about rejected authentication etc
        while True:
            if not api_key:
                api_key = input(
                    "Please provide API Key (created/found in My "
                    "Account/API keys "
                    "in Girder) for {}: ".format(client_name)
                )
                keyring.set_password(app_id, "key", api_key)
            try:
                self.authenticate(apiKey=api_key)
                break
            except Exception as exc:
                sys.stderr.write("Failed to authenticate: {}".format(exc))
                api_key = None

    # XXX causes strange 'NoneType' object has no attribute 'close'
    #  so TODO to investigate
    # def sendRestRequest(self, *args, **kwargs):
    #     with self.session() as session:
    #         # TODO: avoid hardcoded max_retries -- setup taken from girder_cli.client
    #         session.mount(self.urlBase, HTTPAdapter(max_retries=5))
    #         return super(GirderCli, self).sendRestRequest(*args, **kwargs)

    @classmethod
    def _adapt_record(cls, rec):
        # we will care about subset of fields girder provides and will reshape
        # them a little
        mapping = {
            "_id": "id",
            "name": "name",
            "_modelType": "type",
            "meta": "metadata",
            "size": ("attrs", "size"),  # only 1 level supported ATM
            "updated": ("attrs", "mtime"),
            "created": ("attrs", "ctime"),
        }
        rec_out = {}
        for girder, dandi in mapping.items():
            if girder not in rec:
                continue  # skip
            v = rec[girder]
            if isinstance(dandi, (tuple, list)):
                if dandi[0] not in rec_out:
                    rec_out[dandi[0]] = {}
                rec_out[dandi[0]][dandi[1]] = v
            else:
                rec_out[dandi] = v
        return rec_out

    def traverse_asset(self, asset_id, asset_type, parent_path=None, recursive=True):
        """Generator to produce asset records

        ATM the fields I see possibly non-exhaustive and would not be needed
        for some cases.  Later we could make some structure with on-demand
        late requests (e.g. if ["metadata"] is requested, request it at that
        point.

        We will "meld" notion of a Girder Item with File ATM.  File detail
        matters, Item not -- we just would "steal" its

        TODO:
        - make asset_type optional? i.e. discover it since IDs are unique
        - add "include" "exclude" filters to avoid even going into
          anything of no interest?  note that for folder/collection we now
          performing size computation.  So those would get affected, but
          could be taken as a feature.
        - makeup "children_unique_metadata" for folders?

        Parameters
        ----------

        Yields
        ------
         dicts with keys:
           type: str, {file, folder, dandiset}
           id: str, internal to backend id
           path: str, path within the asset
           attrs: dict, expected keys 'size', 'mtime', 'ctime' when known
           metadata: dict
        """
        # TODO: dandiset.  We can request folder id, verify that it has dataset.yaml
        # and populate metadata for the record with that content
        attempts_left = 4
        while attempts_left:
            attempts_left -= 1
            try:
                g = self.getResource(asset_type, asset_id)
                break
            except gcl.HttpError as exc:
                response = get_HttpError_response(exc)
                if not self.token and (
                    exc.status == 401 or "access denied" in response.get("message", "")
                ):
                    lgr.warning("unauthenticated access denied, let's authenticate")
                    self.dandi_authenticate()
                else:
                    raise
        if not attempts_left:
            raise RuntimeError("Failed to authenticate after a number of attempts")
        yield from self._traverse_asset_girder(g, parent_path, recursive=recursive)

    def _traverse_asset_girder(self, g, parent_path=None, recursive=True):
        """Helper which operates on girder record"""
        a = self._adapt_record(g)
        if parent_path:
            a["path"] = op.join(parent_path, a["name"])
        else:
            a["path"] = a["name"]

        if a["type"] == "file":
            # we are done, but hopefully it never sees outside since
            # item should be the one we care about
            pass
        elif a["type"] == "item":
            file_recs = list(self.listFile(g["_id"]))
            if len(file_recs) > 1:
                raise ValueError(
                    f"multiple files per item not yet supported (if ever will be)."
                    f" Got: {file_recs}"
                )
            if not file_recs:
                lgr.warning(f"Ran into an empty item: {g}")
                return
            # !!!! double trip
            a_file = next(
                self._traverse_asset_girder(file_recs[0], parent_path=parent_path)
            )
            assert not a_file.get("metadata", None), "metadata should be per item"
            a_file["metadata"] = a["metadata"]
            a = a_file  # yield enhanced with metadata file entry
        elif a["type"] in ("folder", "collection", "user") and recursive:
            a["attrs"]["size"] = 0
            for child in self._list_folder(g["_id"], g["_modelType"]):
                for child_a in self._traverse_asset_girder(child, a["path"]):
                    a["attrs"]["size"] += child_a["attrs"]["size"]
                    yield child_a
            # And now yield record about myself, but we do not care about collections
            a["type"] = "folder"
        else:
            raise NotImplementedError(f"Do not know how to handle a['type']")
        yield a

    def _list_folder(self, folder_id, folder_type="folder", types=None):
        """A helper to list a "folder" content

        types: {folder, item}, optional
          Collection cannot contain items, so we automagically decide
        """
        # ... probably could have made use of listResource
        g_id = self._checkResourcePath(folder_id)
        # Different for folder and item
        params = {
            "folder": {"parentType": folder_type, "parentId": g_id},
            "item": {"folderId": folder_id},
        }

        if types is None:
            types = ["folder"]
            if folder_type != "collection":
                types.append("item")

        for child_type in types:
            offset = 0
            while True:
                children = self.get(
                    child_type,
                    parameters=dict(
                        limit=gcl.DEFAULT_PAGE_LIMIT,
                        offset=offset,
                        **params[child_type],
                    ),
                )
                for child in children:
                    yield child

                offset += len(children)
                if len(children) < gcl.DEFAULT_PAGE_LIMIT:
                    break


# TODO: our adapter on top of the Girder's client to simplify further
def get_client(server_url, authenticate=True):
    """Simple authenticator which would store credential (api key) via keyring

    Parameters
    ----------
    server_url: str
      URL to girder instance
    """
    client = GirderCli(server_url)
    if authenticate:
        client.dandi_authenticate()
    return client


def get_collection(client, collection):
    return lookup(client, name=collection)


def ensure_collection(client, collection):
    try:
        return lookup(client, name=collection)
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
    assert folder and str(folder) not in (
        "/",
        ".",
    ), "Folder must not be empty, and should not be . or /"
    try:
        folder_rec = lookup(client, name=collection, path=folder)
    except GirderNotFound:
        # We need to create all the leading paths if not there yet, and arrive
        # to the target folder.
        # We will rely on memoization over lookup for all the folder_rec querying
        parent_id = collection_rec["_id"]
        parent_type = "collection"
        parent_path = Path()
        for parent_dirname in folder.parts or ("",):
            parent_path /= parent_dirname
            try:
                folder_rec = lookup(client, name=collection, path=parent_path)
            except GirderNotFound:
                lgr.debug(f"Forder {parent_dirname} was not found, creating")
                folder_rec = client.createFolder(
                    parent_id,
                    parent_dirname,
                    parentType=parent_type,
                    # for now just depend on collection setup public=True,
                )
            parent_id = folder_rec["_id"]
            parent_type = "folder"
    lgr.debug(f"Folder: {folder_rec}")
    return folder_rec
