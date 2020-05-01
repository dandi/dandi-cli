from datetime import datetime
import os
import os.path as op
import json
import keyring
import random
import sys
import time

from functools import lru_cache
from pathlib import Path, PurePosixPath

import girder_client as gcl

from . import get_logger
from .utils import ensure_datetime, ensure_strtime, is_same_time
from .consts import known_instances, known_instances_rev


lgr = get_logger()


# TODO: more flexible
class GirderServer:
    __slots__ = ["url"]

    def __init__(self, url):
        self.url = url


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


def is_access_denied(exc):
    """Tell if an exception about denied access"""
    response = get_HttpError_response(exc)
    return exc.status == 401 or (
        response and "access denied" in response.get("message", "")
    )


from requests.adapters import HTTPAdapter


class GirderCli(gcl.GirderClient):
    """An "Adapter" to GirderClient

    ATM it just inherits from GirderClient. But in the long run we might want
    to make it fulfill our API and actually become and adapter (and delegate)
    to GirderClient.  TODO
    """

    def __init__(self, server_url, progressbars=False):
        self._server_url = server_url.rstrip("/")
        kw = {}
        if progressbars:
            kw["progressReporterCls"] = TQDMProgressReporter
        super().__init__(
            apiUrl="{}/api/v1".format(self._server_url),
            # seems to mess up our "dandi upload" reporting, although
            # I thought that it is used only for download. heh heh
            **kw,
        )

    def register_dandiset(self, name, description):
        """Register a dandiset and return created metadata record

        Returns
        -------
        dict
          Metadata record created for the dandiset
        """
        ret = self.createResource("dandi", {"name": name, "description": description})
        assert "meta" in ret
        assert "dandiset" in ret["meta"]
        # Return only our dandiset record
        return ret["meta"]["dandiset"]

    def dandi_authenticate(self):
        # Shortcut for advanced folks
        api_key = os.environ.get("DANDI_API_KEY", None)
        if api_key:
            self.authenticate(apiKey=api_key)
            return

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
        # TODO: figure out mtime/ctime between item and a file
        # On a sample (uploaded not using dandi-cli) upload -- item has both mtime/ctime
        # and a file -- only ctime
        #  (Pdb) p rec
        # {'_id': '5e60c19381bc3e47d94aa014', '_modelType': 'item',
        # 'baseParentId': '5da4b8fe51c340795cb18fd0', 'baseParentType':
        # 'user', 'created': '2020-03-05T09:08:35.193000+00:00', 'creatorId':
        # '5da4b8fe51c340795cb18fd0', 'description': '', 'folderId':
        # '5e60c14f81bc3e47d94aa012', 'meta': {}, 'name': '18516000.nwb',
        # 'size': 792849, 'updated': '2020-03-05T09:08:35.193000+00:00'}
        # (Pdb) c
        # > /home/yoh/proj/dandi/dandi-cli/dandi/girder.py(136)_adapt_record()
        # -> for girder, dandi in mapping.items():
        # (Pdb) p rec
        # {'_id': '5e60c19381bc3e47d94aa015', '_modelType': 'file',
        # 'created': '2020-03-05T09:08:35.196000+00:00', 'creatorId':
        # '5da4b8fe51c340795cb18fd0', 'downloadStatistics': {'completed': 1,
        # 'requested': 1, 'started': 1}, 'exts': ['nwb'], 'itemId':
        # '5e60c19381bc3e47d94aa014', 'mimeType': 'application/octet-stream',
        # 'name': '18516000.nwb', 'size': 792849}
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
                if not self.token and is_access_denied(exc):
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
            a_file["metadata"] = metadata = a["metadata"]
            # and since girder does not allow non-admin set 'ctime' for the file
            # we will use our metadata records
            if "uploaded_mtime" in metadata:
                a_file["attrs"]["mtime"] = metadata["uploaded_mtime"]
            a = a_file  # yield enhanced with metadata file entry
        elif a["type"] in ("folder", "collection", "user"):
            if recursive:
                # TODO: reconsider bothering with types, since could be done
                # upstairs and returning folder itself last complicates reporting
                # of intensions.  We could yield it twice, but then it might bring
                # confusion
                a["attrs"]["size"] = 0
                for child in self._list_folder(g["_id"], g["_modelType"]):
                    for child_a in self._traverse_asset_girder(child, a["path"]):
                        a["attrs"]["size"] += child_a["attrs"]["size"]
                        yield child_a
            # It could be a dandiset
            if a["type"] == "folder" and a["metadata"].get("dandiset", {}).get(
                "identifier", None
            ):
                a["type"] = "dandiset"
            else:
                # And now yield record about myself, but we do not care about collections
                a["type"] = "folder"
        else:
            raise NotImplementedError(f"Do not know how to handle {a['type']!r}")
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

    def download_file(self, file_id, path, existing="error", attrs=None):
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
                remote_file_mtime = self._get_file_mtime(attrs)
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
        # suboptimal since
        # 1. downloads into TMPDIR which might lack space etc.  If anything, we
        # might tune up setting/TMPDIR at the
        # level of download so it goes alongside with the target path
        # (e.g. under .FILENAME.dandi-download). That would speed things up
        # when finalizing the download, possibly avoiding `mv` across partitions
        # 2. unlike upload it doesn't use a callback but relies on a context
        #  manager to be called with an .update.  also it uses only filename
        #  in the progressbar label
        # For starters we would do this implementation but later RF
        # when RF - do not forget to remove progressReporterCls in __init__

        # Will do 3 attempts to avoid some problems due to flaky/overloaded
        # connections, see https://github.com/dandi/dandi-cli/issues/87
        for attempt in range(3):
            try:
                self.downloadFile(file_id, path)
                break
            except gcl.HttpError as exc:
                if is_access_denied(exc) or attempt >= 2:
                    raise
                # sleep a little and retry
                lgr.debug(
                    "Failed to download on attempt#%d, will sleep a bit and retry",
                    attempt,
                )
                time.sleep(random.random() * 5)
        # It seems that above call does not care about setting either mtime
        if attrs:
            mtime = self._get_file_mtime(attrs)
            if mtime:
                os.utime(path, (time.time(), mtime.timestamp()))

    @staticmethod
    def _get_file_mtime(attrs):
        if not attrs:
            return None
        # We would rely on uploaded_mtime from metadata being stored as mtime.
        # If that one was not provided, the best we know is the "ctime"
        # for the file, use that one
        return ensure_datetime(attrs.get("mtime", attrs.get("ctime", None)))


# TODO: our adapter on top of the Girder's client to simplify further
def get_client(server_url, authenticate=True, progressbars=False):
    """Simple authenticator which would store credential (api key) via keyring

    Parameters
    ----------
    server_url: str
      URL to girder instance
    """
    lgr.debug(f"Establishing a client for {server_url}")

    client = GirderCli(server_url, progressbars=progressbars)
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


class TQDMProgressReporter(object):
    reportProgress = True

    def __init__(self, label="", length=0):
        import tqdm

        self._pbar = tqdm.tqdm(desc=label, total=length, unit="B", unit_scale=True)
        self.label = label
        self.length = length

    def update(self, chunkSize):
        self._pbar.update(chunkSize)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self._pbar.clear()  # remove from screen -- not in effect ATM TODO
        self._pbar.close()
        del self._pbar
