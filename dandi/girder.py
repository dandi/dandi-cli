import contextlib
from functools import lru_cache
import json
import os
import os.path as op
from pathlib import Path
import random
import sys
import time

import click
import girder_client as gcl
from keyring.backend import get_all_keyring
from keyring.core import get_keyring, load_config, load_env
from keyring.errors import KeyringError
from keyring.util.platform_ import config_root
from keyrings.alt.file import EncryptedKeyring

from .consts import MAX_CHUNK_SIZE, known_instances_rev
from .exceptions import LockingError
from . import get_logger
from .utils import ensure_datetime, flatten, flattened, remap_dict, try_multiple

lgr = get_logger()


# TODO: more flexible
class GirderServer:
    __slots__ = ["url"]

    def __init__(self, url):
        self.url = url


class GirderNotFound(Exception):
    pass


# TODO: remove if we start to expose this as a Python library which could
# be longer lived than just a CLI
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


def get_HttpError_message(exc):
    resp = get_HttpError_response(exc)
    if isinstance(resp, dict):
        return resp.get("message", None)
    return resp


def is_access_denied(exc):
    """Tell if an exception about denied access"""
    response = get_HttpError_response(exc)
    return exc.status == 401 or (
        response and "access denied" in response.get("message", "")
    )


# Provide additional "heavy" logging at DEBUG level about interactions
# with girder, including progress indication.  The need came up to troubleshoot
# https://github.com/dandi/dandi-cli/issues/136
_DANDI_LOG_GIRDER = os.environ.get("DANDI_LOG_GIRDER")


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

    if _DANDI_LOG_GIRDER:
        # Overload this core method to be able to log interactions with girder
        # server from the client side
        def sendRestRequest(self, *args, **kwargs):
            lgr.debug("REST>: args=%s kwargs=%s", args, kwargs)
            res = super().sendRestRequest(*args, **kwargs)
            lgr.debug("REST<: %s", str(res))
            return res

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
        api_key = os.environ.get("DANDI_GIRDER_API_KEY", None)
        if api_key:
            self.authenticate(apiKey=api_key)
            lgr.debug("Successfully authenticated using the key from the envvar")
            return

        if self._server_url in known_instances_rev:
            client_name = known_instances_rev[self._server_url]
        else:
            raise NotImplementedError("TODO client name derivation for keyring")

        app_id = "dandi-girder-{}".format(client_name)
        keyring_backend, api_key = keyring_lookup(app_id, "key")
        # the dance about rejected authentication etc
        while True:
            if not api_key:
                api_key = input(
                    "Please provide API Key (created/found in My "
                    "Account/API keys "
                    "in Girder) for {}: ".format(client_name)
                )
                keyring_backend.set_password(app_id, "key", api_key)
                lgr.debug("Stored key in keyring")

            try:
                self.authenticate(apiKey=api_key)
                lgr.debug("Successfully authenticated using the key")
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
        import requests

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
            file_recs = try_multiple(5, requests.ConnectionError, 1.1)(
                lambda: list(self.listFile(g["_id"]))
            )
            if len(file_recs) > 1:
                lgr.warning("Multiple files found for %s; using oldest one", a["path"])
                file_recs = [
                    min(file_recs, key=lambda fr: ensure_datetime(fr["created"]))
                ]
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

    def get_download_file_iter(self, file_id, chunk_size=MAX_CHUNK_SIZE):
        def downloader(start_at=0):
            # TODO: make it a common decorator here?
            # Will do 3 attempts to avoid some problems due to flaky/overloaded
            # connections, see https://github.com/dandi/dandi-cli/issues/87
            for attempt in range(3):
                try:
                    path = f"file/{file_id}/download"
                    if start_at > 0:
                        headers = {"Range": f"bytes={start_at}-"}
                        # Range requests result in a 206 response, which the
                        # Girder client treats as an error (at least until they
                        # merge girder/girder#3301).  Hence, we need to make
                        # the request directly through `requests`.
                        import requests

                        resp = requests.get(
                            f"{self._server_url}/api/v1/{path}",
                            stream=True,
                            headers=headers,
                        )
                        resp.raise_for_status()
                    else:
                        resp = self.sendRestRequest(
                            "get", path, stream=True, jsonResp=False
                        )
                    return resp.iter_content(chunk_size=chunk_size)
                except gcl.HttpError as exc:
                    if is_access_denied(exc) or attempt >= 2:
                        raise
                    # sleep a little and retry
                    lgr.debug(
                        "Failed to download on attempt#%d, will sleep a bit and retry",
                        attempt,
                    )
                    time.sleep((1 + random.random()) * 5)

        return downloader

    def _get_asset_recs(self, asset_id, asset_type, authenticate=False, recursive=True):
        """

        Parameters
        ----------
        asset_id
        asset_type
        authenticate
        recursive

        Returns
        -------
        dandiset_rec, files_rec
           dandiset_rec will be None if asset_id is not pointing to a dandiset
        """
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
        files = None
        dandiset = None

        while True:
            try:
                # this one should enhance them with "fullpath"
                top_entities = list(
                    self.traverse_asset(asset_id, asset_type, recursive=False)
                )
                break
            except gcl.HttpError as exc:
                if not authenticate and is_access_denied(exc):
                    lgr.warning("unauthenticated access denied, let's authenticate")
                    self.dandi_authenticate()
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
                "Traversing remote %ss (%s) recursively",
                entity_type,
                ", ".join(e["name"] for e in top_entities),
            )
            entities = self.traverse_asset(asset_id, asset_type, recursive=recursive)
            # TODO: special handling for a dandiset -- we might need to
            #  generate dandiset.yaml out of the metadata record
            # we care only about files ATM
            files = (e for e in entities if e["type"] == "file")
        elif entity_type == "file":
            files = top_entities
        else:
            raise ValueError(f"Unexpected entity type {entity_type}")
        # TODO: move -- common and has nothing to do with getting a list of assets
        if entity_type == "dandiset":
            if len(top_entities) > 1:
                raise NotImplementedError(
                    "A single dandiset at a time only supported ATM, got %d: %s"
                    % (len(top_entities), top_entities)
                )
            dandiset = top_entities[0]

        return dandiset, files

    def get_dandiset_and_assets(
        self, asset_id, asset_type, recursive=True, authenticate=False
    ):
        lgr.debug(f"Traversing {asset_type} with id {asset_id}")
        # there might be multiple asset_ids, e.g. if multiple files were selected etc,
        # so we will traverse all of them
        dandiset_asset_recs = [
            self._get_asset_recs(
                asset_id_, asset_type, authenticate=authenticate, recursive=recursive
            )
            for asset_id_ in set(flattened([asset_id]))
        ]

        dandiset = None

        if not dandiset_asset_recs:
            lgr.warning("Got empty listing for %s %s", asset_type, asset_id)
            return
        elif (
            len(dandiset_asset_recs) > 1
        ):  # had multiple asset_ids, should not be dandisets
            if any(r[0] for r in dandiset_asset_recs):
                raise NotImplementedError("Got multiple ids for dandisets")
        else:
            dandiset = dandiset_asset_recs[0][0]

        # Return while harmonizing
        if dandiset:
            dandiset = _harmonize_girder_dandiset_to_dandi_api(dandiset)

        return (
            dandiset,
            (
                _harmonize_girder_asset_to_dandi_api(a)
                for a in flatten(r[1] for r in dandiset_asset_recs)
            ),
        )

    @contextlib.contextmanager
    def lock_dandiset(self, dandiset_identifier: str):
        presumably_locked = False
        try:
            lgr.debug("Trying to acquire lock for %s", dandiset_identifier)
            try:
                resp = self.post(f"dandi/{dandiset_identifier}/lock")
                lgr.debug("Locking response: %s", str(resp))
            except gcl.HttpError as exc:
                msg = get_HttpError_message(exc) or str(exc)
                raise LockingError(
                    f"Failed to lock dandiset {dandiset_identifier} due to: {msg}"
                )
            else:
                presumably_locked = True

            yield
        finally:
            if presumably_locked:
                lgr.debug("Trying to release the lock for %s", dandiset_identifier)
                try:
                    resp = self.post(f"dandi/{dandiset_identifier}/unlock")
                    lgr.debug("Unlocking response: %s", str(resp))
                except gcl.HttpError as exc:
                    msg = get_HttpError_message(exc) or str(exc)
                    raise LockingError(
                        f"Failed to unlock dandiset {dandiset_identifier} due to: {msg}"
                    )

    NGINX_MAX_CHUNK_SIZE = 400 * (1 << 20)  # 400 MiB

    def _uploadContents(self, uploadObj, stream, size, progressCallback=None):
        """
        Uploads contents of a file.  Overridden so that the chunk size can be
        set on a per-file basis.

        :param uploadObj: The upload object contain the upload id.
        :type uploadObj: dict
        :param stream: Readable stream object.
        :type stream: file-like
        :param size: The length of the file. This must be exactly equal to the
            total number of bytes that will be read from ``stream``, otherwise
            the upload will fail.
        :type size: str
        :param progressCallback: If passed, will be called after each chunk
            with progress information. It passes a single positional argument
            to the callable which is a dict of information about progress.
        :type progressCallback: callable
        """
        offset = 0
        uploadId = uploadObj["_id"]

        chunk_size = max(self.MAX_CHUNK_SIZE, (size + 999) // 1000)
        if chunk_size > self.NGINX_MAX_CHUNK_SIZE:
            raise Exception("File requires too many chunks to upload")

        with self.progressReporterCls(
            label=uploadObj.get("name", ""), length=size
        ) as reporter:

            while True:
                chunk = stream.read(min(chunk_size, (size - offset)))

                if not chunk:
                    break

                if isinstance(chunk, str):
                    chunk = chunk.encode("utf8")

                uploadObj = self.post(
                    "file/chunk?offset=%d&uploadId=%s" % (offset, uploadId),
                    data=gcl._ProgressBytesIO(chunk, reporter=reporter),
                )

                if "_id" not in uploadObj:
                    raise Exception(
                        "After uploading a file chunk, did not receive object with _id. "
                        "Got instead: " + json.dumps(uploadObj)
                    )

                offset += len(chunk)

                if callable(progressCallback):
                    progressCallback({"current": offset, "total": size})

        if offset != size:
            self.delete("file/upload/" + uploadId)
            raise gcl.IncorrectUploadLengthError(
                "Expected upload to be %d bytes, but received %d." % (size, offset),
                upload=uploadObj,
            )

        return uploadObj


def _harmonize_girder_dandiset_to_dandi_api(rec):
    """
    Compare API (on a released version):

    {'count': 1,
     'created': '2020-07-21T22:22:15.396171Z',
     'dandiset': {'created': '2020-07-21T22:22:14.732729Z',
                  'identifier': '000027',
                  'updated': '2020-07-21T22:22:14.732762Z'},
     'metadata': {'dandiset': {...}},
     'updated': '2020-07-21T22:22:15.396295Z',
     'version': '0.200721.2222'}

    to Girder (on drafts):

    {'attrs': {'ctime': '2020-07-08T21:54:42.543000+00:00',
               'mtime': '2020-07-21T22:02:34.918000+00:00',
               'size': 0},
     'id': '5f0640a2ab90ac46c4561e4f',
     'metadata': {'dandiset': {...}},
     'name': '000027',
     'path': '000027',
     'type': 'dandiset'}

    So we will place some girder specific ones under 'girder' and populate 'dandiset', e.g.
    (there is absent clarify of what date times API returns:
    https://github.com/dandi/dandi-publish/issues/107
    so we will assume that my take was more or less correct and then we would have them
    correspond in case of a draft, as it is served by girder ATM:

    {# 'count': 1,  # no count
     'created': '2020-07-21T22:22:15.396171Z',  # attrs.ctime
     'dandiset': {'created': '2020-07-08T21:54:42.543000+00:00',  # attrs.ctime
                  'identifier': '000027',  # name
                  'updated': '2020-07-21T22:02:34.918000+00:00' },  # attrs.mtime
     'metadata': {'dandiset': {...}},
     'updated': '2020-07-21T22:02:34.918000+00:00'}  # attrs.mtime

    Parameters
    ----------
    rec

    Returns
    -------
    dict
    """
    # ATM it is just a simple remapping but might become more sophisticated later on
    return remap_dict(
        rec,
        {
            "metadata": "metadata.dandiset",  # 1-to-1 for now
            "dandiset.created": "attrs.ctime",
            "created": "attrs.ctime",
            "dandiset.uptimed": "attrs.mtime",
            "updated": "attrs.mtime",
            "dandiset.identifier": "name",
        },
    )


def _get_file_mtime(attrs):
    if not attrs:
        return None
    # We would rely on uploaded_mtime from metadata being stored as mtime.
    # If that one was not provided, the best we know is the "ctime"
    # for the file, use that one
    return ensure_datetime(attrs.get("mtime", attrs.get("ctime", None)))


def _harmonize_girder_asset_to_dandi_api(rec):
    """
    girder rec:

    *(Pdb) pprint(_a[0])
    {'attrs': {'ctime': '2020-07-21T22:00:36.362000+00:00',
               'mtime': '2020-07-21T17:31:55.283394-04:00',
               'size': 18792},
     'id': '5f176584f63d62e1dbd06946',
     'metadata': {... identical at this level
                  'uploaded_by': 'dandi 0.5.0+12.gd4ef762.dirty',
                  'uploaded_datetime': '2020-07-21T18:00:36.703727-04:00',
                  'uploaded_mtime': '2020-07-21T17:31:55.283394-04:00',
                  'uploaded_size': 18792},
     'name': 'sub-RAT123.nwb',
     'path': '000027/sub-RAT123/sub-RAT123.nwb',
     'type': 'file'}

    and API (lacking clear "modified" so needs tuning too):

        {
          "version": {
            "dandiset": {
              "identifier": "000027",
              "created": "2020-07-21T22:22:14.732729Z",
              "updated": "2020-07-21T22:22:14.732762Z"
            },
            "version": "0.200721.2222",
            "created": "2020-07-21T22:22:15.396171Z",
            "updated": "2020-07-21T22:22:15.396295Z",
            "count": 1
          },
          "uuid": "bca53c42-7fc2-41b6-b836-5ed102ba8447",
          "path": "/sub-RAT123/sub-RAT123.nwb",
          "size": 18792,
          "sha256": "1a765509384ea96b7b12136353d9c5b94f23d764ad0431e049197f7875eb352c",
          "created": "2020-07-21T22:22:16.882594Z",
          "updated": "2020-07-21T22:22:16.882641Z",
          "metadata": {
    ...
            "sha256": "1a765509384ea96b7b12136353d9c5b94f23d764ad0431e049197f7875eb352c",
    ...
            "uploaded_size": 18792,
            "uploaded_mtime": "2020-07-21T17:31:55.283394-04:00",
            "uploaded_datetime": "2020-07-21T18:00:36.703727-04:00",
    ...
          }
        }


    Parameters
    ----------
    rec

    Returns
    -------
    """
    rec = rec.copy()  # we will modify in place

    metadata = rec.get("metadata", {})
    size = rec["size"] = rec.get("attrs", {}).get("size")
    # we will add messages leading to decision that metadata is outdated and thus should not be used
    metadata_outdated = []
    uploaded_size = metadata.get("uploaded_size")
    if size is None:
        lgr.debug("Found no size in attrs from girder!")
        if uploaded_size is not None:
            lgr.debug("Taking 'uploaded_size' of %d", uploaded_size)
            rec["size"] = uploaded_size
    else:
        if uploaded_size is not None and size != uploaded_size:
            metadata_outdated.append(
                f"uploaded_size of {uploaded_size} != size of {size}"
            )

    # duplication but ok for now
    modified = rec["modified"] = _get_file_mtime(rec.get("attrs"))
    uploaded_mtime = metadata.get("uploaded_mtime")
    if uploaded_mtime:
        uploaded_mtime = ensure_datetime(uploaded_mtime)
    if modified is None:
        lgr.debug("Found no mtime (modified) among girder attrs")
        if uploaded_mtime is not None:
            rec["modified"] = uploaded_mtime
    else:
        if uploaded_mtime is not None and modified != uploaded_mtime:
            metadata_outdated.append(
                f"uploaded_mtime of {uploaded_mtime} != mtime of {modified}"
            )

    if metadata_outdated:
        lgr.warning(
            "Found discrepancies in girder record and metadata: %s",
            ", ".join(metadata_outdated),
        )

    # we need to strip off the leading dandiset identifier from the path
    path = rec["path"]
    if path.startswith("00"):
        # leading / is for consistency with API although yoh dislikes it
        # https://github.com/dandi/dandi-publish/issues/109
        # Girder client returned paths are OS specific.
        path = "/" + path.split(op.sep, 1)[1]
    else:
        lgr.debug(
            "Unexpected: an asset path did not have leading dandiset identifier: %s",
            path,
        )
    rec["path"] = path

    if "id" in rec:
        # Let's create a dedicated section for girder specific information
        rec["girder"] = {"id": rec.pop("id")}

    # Some additional fields which should appear at the top level in the records returned
    # by DANDI API
    if "sha256" in metadata:
        rec["sha256"] = metadata["sha256"]
    return rec


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

        self.label = label
        self.length = length

        self._pbar = None
        try:
            self._pbar = tqdm.tqdm(desc=label, total=length, unit="B", unit_scale=True)
        except AssertionError as exc:
            lgr.warning(
                "No progress indication for %s. Failed to initiate tqdm progress bar: %s",
                label,
                exc,
            )

    def update(self, chunkSize):
        if _DANDI_LOG_GIRDER:
            lgr.debug("PROGRESS[%s]: +%d", id(self), chunkSize)
        if self._pbar:
            self._pbar.update(chunkSize)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if self._pbar:
            self._pbar.clear()  # remove from screen -- not in effect ATM TODO
            self._pbar.close()
            del self._pbar


def keyring_lookup(service_name, username):
    """
    Determine a keyring backend to use for storing & retrieving credentials as
    follows:

    - If the user has specified a backend explicitly via the
      ``PYTHON_KEYRING_BACKEND`` environment variable or a ``keyringrc.cfg``
      file, use that backend without checking whether it's usable (If it's not,
      the user messed up).

    - Otherwise, query the default backend (which is guaranteed to already have
      the requisite dependencies installed) for the credentials for the given
      service name and username.  If this completes without error (regardless
      of whether the backend contains any such credentials), use that backend.

    - If the query fails (e.g., because a GUI is required but the session is in
      a plain terminal), try using the ``EncryptedKeyring`` backend.

      - If the default backend *was* the ``EncryptedKeyring`` backend, error.

      - If the ``EncryptedKeyring`` backend is not in the list of available
        backends (likely because its dependencies are not installed, though
        that shouldn't happen if dandi was installed properly), error.

      - If ``EncryptedKeyring``'s data file already exists, use it as the
        backend.

      - If ``EncryptedKeyring``'s data file does not already exist, ask the
        user whether they want to start using ``EncryptedKeyring``.  If yes,
        then set ``keyringrc.cfg`` (if it does not already exist) to specify it
        as the default backend, and return the backend.  If no, error.

    Returns a keyring backend and the password it holds (if any) for the given
    service and username.
    """

    kb = load_env() or load_config()
    if kb:
        return (kb, kb.get_password(service_name, username))
    kb = get_keyring()
    try:
        password = kb.get_password(service_name, username)
    except KeyringError as e:
        lgr.info("Default keyring errors on query: %s", e)
        if isinstance(kb, EncryptedKeyring):
            lgr.info(
                "Default keyring is EncryptedKeyring; abandoning keyring procedure"
            )
            raise
        # Use `type(..) is` instead of `isinstance()` to weed out subclasses
        kbs = [k for k in get_all_keyring() if type(k) is EncryptedKeyring]
        assert (
            len(kbs) == 1
        ), "EncryptedKeyring not available; is pycryptodomex installed?"
        kb = kbs[0]
        if op.exists(kb.file_path):
            lgr.info("EncryptedKeyring file exists; using as keyring backend")
            return (kb, kb.get_password(service_name, username))
        lgr.info("EncryptedKeyring file does not exist")
        if click.confirm(
            "Would you like to establish an encrypted keyring?", default=True
        ):
            keyring_cfg = Path(keyringrc_file())
            if keyring_cfg.exists():
                lgr.info("%s exists; refusing to overwrite", keyring_cfg)
            else:
                lgr.info(
                    "Configuring %s to use EncryptedKeyring as default backend",
                    keyring_cfg,
                )
                keyring_cfg.parent.mkdir(parents=True, exist_ok=True)
                keyring_cfg.write_text(
                    "[backend]\n"
                    "default-keyring = keyrings.alt.file.EncryptedKeyring\n"
                )
            return (kb, None)
        raise
    else:
        return (kb, password)


def keyringrc_file():
    return op.join(config_root(), "keyringrc.cfg")
