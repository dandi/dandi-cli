from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import os.path
from pathlib import Path
import re
from threading import Lock
from time import sleep, time
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    FrozenSet,
    Iterator,
    Optional,
    Union,
    cast,
)
from urllib.parse import urlparse, urlunparse
from xml.etree.ElementTree import fromstring

import click
from dandischema import models
from pydantic import BaseModel, Field, PrivateAttr
import requests
import tenacity

from . import get_logger
from .consts import (
    DRAFT,
    MAX_CHUNK_SIZE,
    DandiInstance,
    known_instances,
    known_instances_rev,
)
from .exceptions import NotFoundError, SchemaVersionError
from .keyring import keyring_lookup
from .utils import (
    USER_AGENT,
    check_dandi_version,
    ensure_datetime,
    is_interactive,
    try_multiple,
)

lgr = get_logger()


# Following class is loosely based on GirderClient, with authentication etc
# being stripped.
# TODO: add copyright/license info
class RESTFullAPIClient:
    """A base class for REST clients"""

    def __init__(self, api_url, session=None, headers=None):
        self.api_url = api_url
        if session is None:
            session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        if headers is not None:
            session.headers.update(headers)
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def request(
        self,
        method,
        path,
        params=None,
        data=None,
        files=None,
        json=None,
        headers=None,
        json_resp=True,
        retry=None,
        **kwargs,
    ):
        """
        This method looks up the appropriate method, constructs a request URL
        from the base URL, path, and parameters, and then sends the request. If
        the method is unknown or if the path is not found, an exception is
        raised, otherwise a JSON object is returned with the response.

        This is a convenience method to use when making basic requests that do
        not involve multipart file data that might need to be specially encoded
        or handled differently.

        :param method: The HTTP method to use in the request (GET, POST, etc.)
        :type method: str
        :param path: A string containing the path elements for this request.
            Note that the path string should not begin or end with the path  separator, '/'.
        :type path: str
        :param params: A dictionary mapping strings to strings, to be used
            as the key/value pairs in the request parameters.
        :type params: dict
        :param data: A dictionary, bytes or file-like object to send in the body.
        :param files: A dictionary of 'name' => file-like-objects for multipart encoding upload.
        :type files: dict
        :param json: A JSON object to send in the request body.
        :type json: dict
        :param headers: If present, a dictionary of headers to encode in the request.
        :type headers: dict
        :param json_resp: Whether the response should be parsed as JSON. If False, the raw
            response object is returned. To get the raw binary content of the response,
            use the ``content`` attribute of the return value, e.g.

            .. code-block:: python

                resp = client.get('my/endpoint', json_resp=False)
                print(resp.content)  # Raw binary content
                print(resp.headers)  # Dict of headers

        :type json_resp: bool
        :param retry: an optional tenacity `retry` argument for retrying the
            request method
        """

        # Look up the HTTP method we need
        f = getattr(self.session, method.lower())

        url = self.get_url(path)

        if headers is None:
            headers = {}
        if json_resp and "accept" not in headers:
            headers["accept"] = "application/json"

        lgr.debug("%s %s", method.upper(), url)

        # urllib3's ConnectionPool isn't thread-safe, so we sometimes hit
        # ConnectionErrors on the start of an upload.  Retry when this happens.
        # Cf. <https://github.com/urllib3/urllib3/issues/951>.
        doretry = tenacity.retry_if_exception_type(
            requests.ConnectionError
        ) | tenacity.retry_if_result(lambda r: r.status_code == 503)
        if retry is not None:
            doretry |= retry

        try:
            result = try_multiple(12, doretry, 1.25)(
                f,
                url,
                params=params,
                data=data,
                files=files,
                json=json,
                headers=headers,
                **kwargs,
            )
        except Exception:
            lgr.exception("HTTP connection failed")
            raise

        lgr.debug("Response: %d", result.status_code)

        # If success, return the json object. Otherwise throw an exception.
        if not result.ok:
            msg = f"Error {result.status_code} while sending {method} request to {url}"
            if result.status_code == 409:
                # Blob exists on server; log at DEBUG level
                lgr.debug("%s: %s", msg, result.text)
            else:
                lgr.error("%s: %s", msg, result.text)
            raise requests.HTTPError(msg, response=result)

        if json_resp:
            if result.text.strip():
                return result.json()
            else:
                return None
        else:
            return result

    def get_url(self, path):
        # Construct the url
        if path.lower().startswith(("http://", "https://")):
            return path
        else:
            return self.api_url.rstrip("/") + "/" + path.lstrip("/")

    def get(self, path, **kwargs):
        """
        Convenience method to call :py:func:`request` with the 'GET' HTTP method.
        """
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        """
        Convenience method to call :py:func:`request` with the 'POST' HTTP method.
        """
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        """
        Convenience method to call :py:func:`request` with the 'PUT' HTTP
        method.
        """
        return self.request("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        """
        Convenience method to call :py:func:`request` with the 'DELETE' HTTP
        method.
        """
        return self.request("DELETE", path, **kwargs)

    def patch(self, path, **kwargs):
        """
        Convenience method to call :py:func:`request` with the 'PATCH' HTTP
        method.
        """
        return self.request("PATCH", path, **kwargs)

    def paginate(self, path, page_size=None, params=None, **kwargs):
        if page_size is not None:
            if params is None:
                params = {}
            params["page_size"] = page_size
        r = self.get(path, params=params, **kwargs)
        while True:
            for item in r["results"]:
                yield item
            if r.get("next"):
                r = self.get(r["next"])
            else:
                break


class DandiAPIClient(RESTFullAPIClient):
    def __init__(self, api_url=None, token=None):
        check_dandi_version()
        if api_url is None:
            instance_name = os.environ.get("DANDI_INSTANCE", "dandi")
            api_url = known_instances[instance_name].api
            if api_url is None:
                raise ValueError(f"No API URL for instance {instance_name!r}")
        super().__init__(api_url)
        if token is not None:
            self.authenticate(token)

    @classmethod
    def for_dandi_instance(
        cls, instance: Union[str, DandiInstance], token=None, authenticate=False
    ) -> "DandiAPIClient":
        if isinstance(instance, str):
            instance = known_instances[instance]
        client = cls(instance.api, token=token)
        if token is None and authenticate:
            client.dandi_authenticate()
        return client

    def authenticate(self, token):
        # Fails if token is invalid:
        self.get("/auth/token", headers={"Authorization": f"token {token}"})
        self.session.headers["Authorization"] = f"token {token}"

    def dandi_authenticate(self):
        # Shortcut for advanced folks
        api_key = os.environ.get("DANDI_API_KEY", None)
        if api_key:
            self.authenticate(api_key)
            return
        if self.api_url in known_instances_rev:
            client_name = known_instances_rev[self.api_url]
        else:
            raise NotImplementedError("TODO client name derivation for keyring")
        app_id = f"dandi-api-{client_name}"
        keyring_backend, api_key = keyring_lookup(app_id, "key")
        key_from_keyring = api_key is not None
        while True:
            if not api_key:
                api_key = input(f"Please provide API Key for {client_name}: ")
                key_from_keyring = False
            try:
                self.authenticate(api_key)
            except requests.HTTPError:
                if is_interactive() and click.confirm(
                    "API key is invalid; enter another?"
                ):
                    api_key = None
                    continue
                else:
                    raise
            else:
                if not key_from_keyring:
                    keyring_backend.set_password(app_id, "key", api_key)
                    lgr.debug("Stored key in keyring")
                break

    def get_dandiset(
        self, dandiset_id: str, version_id: Optional[str] = None, lazy: bool = True
    ) -> "RemoteDandiset":
        """
        Fetches the Dandiset with the given ``dandiset_id``.  If ``version_id``
        is not specified, the `RemoteDandiset`'s version is set to the most
        recent published version if there is one, otherwise to the draft
        version.

        If ``lazy`` is true, no requests are actually made until any data is
        requested from the `RemoteDandiset`.
        """
        if lazy:
            return RemoteDandiset(self, dandiset_id, version_id)
        else:
            d = RemoteDandiset._make(self, self.get(f"/dandisets/{dandiset_id}/"))
            if version_id is not None and version_id != d.version_id:
                if version_id == DRAFT:
                    return d.for_version(d.draft_version)
                else:
                    return d.for_version(version_id)
            return d

    def get_dandisets(self) -> Iterator["RemoteDandiset"]:
        for data in self.paginate("/dandisets/"):
            yield RemoteDandiset._make(self, data)

    def create_dandiset(self, name: str, metadata: Dict[str, Any]) -> "RemoteDandiset":
        """Creates a Dandiset with the given name & metadata"""
        return RemoteDandiset._make(
            self, self.post("/dandisets/", json={"name": name, "metadata": metadata})
        )

    def check_schema_version(self, schema_version: Optional[str] = None) -> None:
        if schema_version is None:
            schema_version = models.get_schema_version()
        server_info = self.get("/info/")
        server_schema_version = server_info.get("schema_version")
        if not server_schema_version:
            raise RuntimeError(
                "Server did not provide schema_version in /info/;"
                f" returned {server_info!r}"
            )
        if server_schema_version != schema_version:
            raise SchemaVersionError(
                f"Server requires schema version {server_schema_version};"
                f" client only supports {schema_version}.  You may need to"
                " upgrade dandi and/or dandischema."
            )

    def get_asset(self, asset_id: str) -> "BaseRemoteAsset":
        return BaseRemoteAsset._from_metadata(self, self.get(f"/assets/{asset_id}"))


class APIBase(BaseModel):
    """Base class for API objects"""

    JSON_EXCLUDE: ClassVar[FrozenSet[str]] = frozenset(["client"])

    def json_dict(self) -> Dict[str, Any]:
        """
        Convert to a JSONable `dict`, omitting the ``client`` attribute and
        using the same field names as in the API
        """
        return json.loads(self.json(exclude=self.JSON_EXCLUDE, by_alias=True))

    class Config:
        allow_population_by_field_name = True
        # To allow `client: Session`:
        arbitrary_types_allowed = True


class Version(APIBase):
    """The version information for a Dandiset retrieved from the API"""

    identifier: str = Field(alias="version")
    name: str
    asset_count: int
    size: int
    created: datetime
    modified: datetime


class RemoteDandiset:
    """
    Representation of a Dandiset (as of a certain version) retrieved from the
    API
    """

    def __init__(
        self,
        client: DandiAPIClient,
        identifier: str,
        version: Union[str, Version, None] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.client = client
        self.identifier = identifier
        self._version_id: Optional[str]
        self._version: Optional[Version]
        if version is None:
            self._version_id = None
            self._version = None
        elif isinstance(version, str):
            self._version_id = version
            self._version = None
        else:
            self._version_id = version.identifier
            self._version = version
        self._data = data

    def _get_data(self) -> Dict[str, Any]:
        if self._data is None:
            self._data = self.client.get(f"/dandisets/{self.identifier}/")
        return self._data

    @property
    def version_id(self) -> str:
        if self._version_id is None:
            self._version_id = self.version.identifier
        return self._version_id

    @property
    def version(self) -> Version:
        """The version in question of the Dandiset"""
        if self._version is None:
            if self._version_id is None:
                self._get_data()
            if self._data is not None:
                for vattr in ["most_recent_published_version", "draft_version"]:
                    vdict = self._data.get(vattr)
                    if vdict and (
                        self._version_id is None or vdict["version"] == self.version_id
                    ):
                        self._version = Version.parse_obj(vdict)
                        self._version_id = self._version.identifier
                        return self._version
            assert self._version_id is not None
            self._version = self.get_version(self._version_id)
        return self._version

    @property
    def created(self) -> datetime:
        return ensure_datetime(self._get_data()["created"])

    @property
    def modified(self) -> datetime:
        return ensure_datetime(self._get_data()["modified"])

    @property
    def contact_person(self) -> str:
        return self._get_data()["contact_person"]

    @property
    def most_recent_published_version(self) -> Optional[Version]:
        v = self._get_data().get("most_recent_published_version")
        if v is None:
            return None
        else:
            return Version.parse_obj(v)

    @property
    def draft_version(self) -> Version:
        return Version.parse_obj(self._get_data()["draft_version"])

    @property
    def api_path(self) -> str:
        return f"/dandisets/{self.identifier}/"

    @property
    def version_api_path(self) -> str:
        return f"/dandisets/{self.identifier}/versions/{self.version_id}/"

    @classmethod
    def _make(cls, client: "DandiAPIClient", data: Dict[str, Any]) -> "RemoteDandiset":
        """
        Construct a `RemoteDandiset` instance from a `dict` returned from the
        API.  If the ``"most_recent_published_version"`` field is set, use that
        as the Dandiset's version; otherwise, use ``"draft_version"``.
        """
        if data.get("most_recent_published_version") is not None:
            version = Version.parse_obj(data["most_recent_published_version"])
        else:
            version = Version.parse_obj(data["draft_version"])
        return cls(
            client=client, identifier=data["identifier"], version=version, data=data
        )

    def _mkasset(self, data: Dict[str, Any]) -> "RemoteAsset":
        return RemoteAsset(
            client=self.client,
            dandiset_id=self.identifier,
            version_id=self.version_id,
            **data,
        )

    def _mkasset_from_metadata(self, metadata: Dict[str, Any]) -> "RemoteAsset":
        return RemoteAsset(
            client=self.client,
            dandiset_id=self.identifier,
            version_id=self.version_id,
            identifier=metadata["identifier"],
            path=metadata["path"],
            size=metadata["contentSize"],
            modified=metadata["dateModified"],
            _metadata=metadata,
        )

    def json_dict(self) -> Dict[str, Any]:
        """
        Convert to a JSONable `dict`, omitting the ``client`` attribute and
        using the same field names as in the API
        """
        data = {
            **self._get_data(),
            "version": self.version.json_dict(),
            "draft_version": self.draft_version.json_dict(),
        }
        if self.most_recent_published_version is not None:
            data[
                "most_recent_published_version"
            ] = self.most_recent_published_version.json_dict()
        return data

    def refresh(self) -> None:
        """
        Update the `RemoteDandiset` in-place with the latest data from the
        server.  The `RemoteDandiset` continues to have the same version as
        before, but the cached version data is internally cleared and may be
        different upon subsequent access.
        """
        self._data = self.client.get(f"/dandisets/{self.identifier}/")
        # Clear _version so it will be refetched the next time it is accessed
        self._version = None

    def get_versions(self) -> Iterator[Version]:
        """Returns an iterator of all available `Version`\\s for the Dandiset"""
        for v in self.client.paginate(f"{self.api_path}versions/"):
            yield Version.parse_obj(v)

    def get_version(self, version_id: str) -> Version:
        """
        Get information about a given version of the Dandiset.  If the given
        version does not exist, a `requests.HTTPError` is raised with a 404
        status code.
        """
        return Version.parse_obj(
            self.client.get(f"/dandisets/{self.identifier}/versions/{version_id}/info")
        )

    def for_version(self, version_id: Union[str, Version]) -> "RemoteDandiset":
        """
        Returns a copy of the `RemoteDandiset` with the `version` attribute set
        to given `Version` object or the `Version` with the given version ID.
        If a version ID given and the version does not exist, a
        `requests.HTTPError` is raised with a 404 status code.
        """
        if isinstance(version_id, str):
            version_id = self.get_version(version_id)
        return type(self)(
            client=self.client,
            identifier=self.identifier,
            version=version_id,
            data=self._data,
        )

    def delete(self) -> None:
        """
        Delete the Dandiset from the server.  Any further access of the
        instance's data attributes afterwards will result in a 404.
        """
        self.client.delete(self.api_path)
        self._data = None
        self._version = None

    def get_metadata(self) -> models.Dandiset:
        """
        Fetch the metadata for this version of the Dandiset as a
        `dandischema.models.Dandiset` instance
        """
        return models.Dandiset.parse_obj(self.get_raw_metadata())

    def get_raw_metadata(self) -> Dict[str, Any]:
        """
        Fetch the metadata for this version of the Dandiset as an unprocessed
        `dict`
        """
        return cast(Dict[str, Any], self.client.get(self.version_api_path))

    def set_metadata(self, metadata: models.Dandiset) -> None:
        """
        Set the metadata for this version of the Dandiset to the given value
        """
        self.set_raw_metadata(metadata.json_dict())

    def set_raw_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Set the metadata for this version of the Dandiset to the given value
        """
        self.client.put(
            self.version_api_path,
            json={"metadata": metadata, "name": metadata.get("name", "")},
        )

    def wait_until_valid(self, min_time=20):
        """
        Wait for a Dandiset to be valid.  Validation is a background celery
        task which runs asynchronously, so we need to wait for it to complete.
        """
        lgr.debug("Waiting for Dandiset %s to complete validation ...", self.identifier)
        start = time()
        while time() - start < min_time:
            r = self.client.get(f"{self.version_api_path}info/")
            if "status" not in r:
                # Running against older version of dandi-api that doesn't
                # validate
                return
            if r["status"] == "Valid":
                return
            sleep(0.5)
        raise ValueError(
            f"Dandiset {self.identifier} is {r['status']}: {r['validation_error']}"
        )

    def publish(self) -> "RemoteDandiset":
        """
        Publish this version of the Dandiset.  Returns a copy of the
        `RemoteDandiset` with the `version` attribute set to the new published
        `Version`.
        """
        return self.for_version(
            Version.parse_obj(self.client.post(f"{self.version_api_path}publish/"))
        )

    def get_assets(self) -> Iterator["RemoteAsset"]:
        """Returns an iterator of all assets in this version of the Dandiset"""
        for a in self.client.paginate(f"{self.version_api_path}assets/"):
            yield self._mkasset(a)

    def get_asset(self, asset_id: str) -> "RemoteAsset":
        """
        Fetch the asset in this version of the Dandiset with the given asset
        ID.  If the given asset does not exist, a `requests.HTTPError` is
        raised with a 404 status code.
        """
        return self._mkasset_from_metadata(
            self.client.get(f"{self.version_api_path}assets/{asset_id}/")
        )

    def get_assets_with_path_prefix(self, path: str) -> Iterator["RemoteAsset"]:
        """
        Returns an iterator of all assets in this version of the Dandiset whose
        `~RemoteAsset.path` attributes start with ``path``
        """
        for a in self.client.paginate(
            f"{self.version_api_path}assets/", params={"path": path}
        ):
            yield self._mkasset(a)

    def get_asset_by_path(self, path: str) -> "RemoteAsset":
        """
        Fetch the asset in this version of the Dandiset whose
        `~RemoteAsset.path` equals ``path``.  If the given asset does not
        exist, a `NotFoundError` is raised.
        """
        try:
            # Weed out any assets that happen to have the given path as a
            # proper prefix:
            (asset,) = (
                a for a in self.get_assets_with_path_prefix(path) if a.path == path
            )
        except ValueError:
            raise NotFoundError(f"No asset at path {path!r}")
        else:
            return asset

    def download_directory(
        self,
        assets_dirpath: str,
        dirpath: Union[str, Path],
        chunk_size: int = MAX_CHUNK_SIZE,
    ) -> None:
        """
        Download all assets under the virtual directory ``assets_dirpath`` to
        the directory ``dirpath``.  Downloads are synchronous.
        """
        if assets_dirpath and not assets_dirpath.endswith("/"):
            assets_dirpath += "/"
        assets = list(self.get_assets_with_path_prefix(assets_dirpath))
        for a in assets:
            filepath = Path(dirpath, a.path[len(assets_dirpath) :])
            filepath.parent.mkdir(parents=True, exist_ok=True)
            a.download(filepath, chunk_size=chunk_size)

    def upload_raw_asset(
        self,
        filepath: Union[str, Path],
        asset_metadata: Dict[str, Any],
        jobs: Optional[int] = None,
        replace_asset: Optional["RemoteAsset"] = None,
    ) -> "RemoteAsset":
        """
        Upload the file at ``filepath`` with metadata ``asset_metadata`` to
        this version of the Dandiset and return the resulting asset.  Blocks
        until the upload is complete.

        :param filepath: the path to the local file to upload
        :type filepath: str or PathLike
        :param dict asset_metadata:
            Metadata for the uploaded asset file.  Must include a "path" field
            giving the POSIX path at which the uploaded file will be placed on
            the server.
        :param int jobs: Number of threads to use for uploading; defaults to 5
        :param RemoteAsset replace_asset: If set, replace the given asset,
            which must have the same path as the new asset
        """
        for status in self.iter_upload_raw_asset(
            filepath, asset_metadata, jobs=jobs, replace_asset=replace_asset
        ):
            if status["status"] == "done":
                return status["asset"]
        raise RuntimeError("iter_upload_raw_asset() finished without returning 'done'")

    def iter_upload_raw_asset(
        self,
        filepath: Union[str, Path],
        asset_metadata: Dict[str, Any],
        jobs: Optional[int] = None,
        replace_asset: Optional["RemoteAsset"] = None,
    ) -> Iterator[dict]:
        """
        Upload the file at ``filepath`` with metadata ``asset_metadata`` to
        this version of the Dandiset, returning a generator of status
        `dict`\\s.

        :param filepath: the path to the local file to upload
        :type filepath: str or PathLike
        :param dict asset_metadata:
            Metadata for the uploaded asset file.  Must include a "path" field
            giving the POSIX path at which the uploaded file will be placed on
            the server.
        :param int jobs:
            Number of threads to use for uploading; defaults to 5
        :param RemoteAsset replace_asset: If set, replace the given asset,
            which must have the same path as the new asset
        :returns:
            A generator of `dict`\\s containing at least a ``"status"`` key.
            Upon successful upload, the last `dict` will have a status of
            ``"done"`` and an ``"asset"`` key containing the resulting
            `RemoteAsset`.
        """
        from .support.digests import get_dandietag

        asset_path = asset_metadata["path"]
        yield {"status": "calculating etag"}
        etagger = get_dandietag(filepath)
        filetag = etagger.as_str()
        lgr.debug("Calculated dandi-etag of %s for %s", filetag, filepath)
        digest = asset_metadata.get("digest", {})
        if "dandi:dandi-etag" in digest:
            if digest["dandi:dandi-etag"] != filetag:
                raise RuntimeError(
                    f"{filepath}: File etag changed; was originally"
                    f" {digest['dandi:dandi-etag']} but is now {filetag}"
                )
        yield {"status": "initiating upload"}
        lgr.debug("%s: Beginning upload", asset_path)
        total_size = os.path.getsize(filepath)
        try:
            resp = self.client.post(
                "/uploads/initialize/",
                json={
                    "contentSize": total_size,
                    "digest": {
                        "algorithm": "dandi:dandi-etag",
                        "value": filetag,
                    },
                },
            )
        except requests.HTTPError as e:
            if e.response.status_code == 409:
                lgr.debug("%s: Blob already exists on server", asset_path)
                blob_id = e.response.headers["Location"]
            else:
                raise
        else:
            upload_id = resp["upload_id"]
            parts = resp["parts"]
            if len(parts) != etagger.part_qty:
                raise RuntimeError(
                    f"Server and client disagree on number of parts for upload;"
                    f" server says {len(parts)}, client says {etagger.part_qty}"
                )
            parts_out = []
            bytes_uploaded = 0
            lgr.debug("Uploading %s in %d parts", filepath, len(parts))
            with RESTFullAPIClient("http://nil.nil") as storage:
                with open(filepath, "rb") as fp:
                    with ThreadPoolExecutor(max_workers=jobs or 5) as executor:
                        lock = Lock()
                        futures = [
                            executor.submit(
                                upload_part,
                                storage_session=storage,
                                fp=fp,
                                lock=lock,
                                etagger=etagger,
                                asset_path=asset_path,
                                part=part,
                            )
                            for part in parts
                        ]
                        for fut in as_completed(futures):
                            out_part = fut.result()
                            bytes_uploaded += out_part["size"]
                            yield {
                                "status": "uploading",
                                "upload": 100 * bytes_uploaded / total_size,
                                "current": bytes_uploaded,
                            }
                            parts_out.append(out_part)
                lgr.debug("%s: Completing upload", asset_path)
                resp = self.client.post(
                    f"/uploads/{upload_id}/complete/",
                    json={"parts": parts_out},
                )
                lgr.debug(
                    "%s: Announcing completion to %s",
                    asset_path,
                    resp["complete_url"],
                )
                r = storage.post(
                    resp["complete_url"], data=resp["body"], json_resp=False
                )
                lgr.debug(
                    "%s: Upload completed. Response content: %s",
                    asset_path,
                    r.content,
                )
                rxml = fromstring(r.text)
                m = re.match(r"\{.+?\}", rxml.tag)
                ns = m.group(0) if m else ""
                final_etag = rxml.findtext(f"{ns}ETag")
                if final_etag is not None:
                    final_etag = final_etag.strip('"')
                    if final_etag != filetag:
                        raise RuntimeError(
                            "Server and client disagree on final ETag of uploaded file;"
                            f" server says {final_etag}, client says {filetag}"
                        )
                # else: Error? Warning?
                resp = self.client.post(f"/uploads/{upload_id}/validate/")
                blob_id = resp["blob_id"]
        lgr.debug("%s: Assigning asset blob to dandiset & version", asset_path)
        yield {"status": "producing asset"}
        if replace_asset is not None:
            lgr.debug("%s: Replacing pre-existing asset")
            a = self._mkasset(
                self.client.put(
                    replace_asset.api_path,
                    json={"metadata": asset_metadata, "blob_id": blob_id},
                )
            )
        else:
            a = self._mkasset(
                self.client.post(
                    f"{self.version_api_path}assets/",
                    json={"metadata": asset_metadata, "blob_id": blob_id},
                )
            )
        lgr.info("%s: Asset successfully uploaded", asset_path)
        yield {"status": "done", "asset": a}


class BaseRemoteAsset(APIBase):
    client: "DandiAPIClient"

    #: The asset identifier
    identifier: str = Field(alias="asset_id")
    path: str
    size: int
    modified: datetime
    #: Metadata supplied at initialization; returned when metadata is requested
    #: instead of performing an API call
    _metadata: Optional[Dict[str, Any]] = PrivateAttr(default_factory=None)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # Pydantic insists on not initializing any attributes that start with
        # underscores, so we have to do it ourselves.
        self._metadata = data.get("metadata", data.get("_metadata"))

    @classmethod
    def _from_metadata(
        self, client: "DandiAPIClient", metadata: Dict[str, Any]
    ) -> "BaseRemoteAsset":
        return BaseRemoteAsset(
            client=client,
            identifier=metadata["identifier"],
            path=metadata["path"],
            size=metadata["contentSize"],
            modified=metadata["dateModified"],
            _metadata=metadata,
        )

    @property
    def api_path(self) -> str:
        return f"/assets/{self.identifier}/"

    @property
    def download_url(self) -> str:
        return self.client.get_url(f"{self.api_path}download/")

    def get_metadata(self) -> models.Asset:
        """
        Fetch the metadata for the asset as a `dandischema.models.Asset`
        instance
        """
        return models.Asset.parse_obj(self.get_raw_metadata())

    def get_raw_metadata(self) -> Dict[str, Any]:
        """Fetch the metadata for the asset as an unprocessed `dict`"""
        if self._metadata is not None:
            return self._metadata
        else:
            return cast(Dict[str, Any], self.client.get(self.api_path))

    def get_digest(
        self, digest_type: Union[str, models.DigestType] = models.DigestType.dandi_etag
    ) -> str:
        """
        Retrieves the value of the given type of digest from the asset's
        metadata.  Raises `NotFoundError` if there is no entry for the given
        digest type.
        """
        if isinstance(digest_type, models.DigestType):
            digest_type = digest_type.value
        metadata = self.get_raw_metadata()
        try:
            return metadata["digest"][digest_type]
        except KeyError:
            raise NotFoundError(f"No {digest_type} digest found in metadata")

    def get_content_url(
        self,
        regex: str = r".*",
        follow_redirects: Union[bool, int] = False,
        strip_query: bool = False,
    ) -> str:
        """
        Returns a URL for downloading the asset, found by inspecting the
        metadata; specifically, returns the first ``contentUrl`` that matches
        ``regex``.  Raises `NotFoundError` if the metadata does not contain a
        matching URL.

        If ``follow_redirects`` is `True`, a ``HEAD`` request is made to
        resolve any & all redirects before returning the URL.  If
        ``follow_redirects`` is an integer, at most that many redirects are
        followed.

        If ``strip_query`` is true, any query parameters are removed from the
        final URL before returning it.
        """
        for url in self.get_raw_metadata().get("contentUrl", []):
            if re.search(regex, url):
                break
        else:
            raise NotFoundError(
                "No matching URL found in asset's contentUrl metadata field"
            )
        if follow_redirects is True:
            url = self.client.request(
                "HEAD", url, json_resp=False, allow_redirects=True
            ).url
        elif follow_redirects:
            for _ in range(follow_redirects):
                r = self.client.request(
                    "HEAD", url, json_resp=False, allow_redirects=False
                )
                if "Location" in r.headers:
                    url = r.headers["Location"]
                else:
                    break
        if strip_query:
            url = urlunparse(urlparse(url)._replace(query=""))
        return url

    def get_download_file_iter(
        self, chunk_size: int = MAX_CHUNK_SIZE
    ) -> Callable[..., Iterator[bytes]]:
        """
        Returns a function that when called (optionally with an offset into the
        asset to start downloading at) returns a generator of chunks of the
        asset
        """
        url = self.download_url

        def downloader(start_at: int = 0) -> Iterator[bytes]:
            lgr.debug("Starting download from %s", url)
            headers = None
            if start_at > 0:
                headers = {"Range": f"bytes={start_at}-"}
            result = self.client.session.get(url, stream=True, headers=headers)
            # TODO: apparently we might need retries here as well etc
            # if result.status_code not in (200, 201):
            result.raise_for_status()
            for chunk in result.iter_content(chunk_size=chunk_size):
                if chunk:  # could be some "keep alive"?
                    yield chunk
            lgr.info("Asset %s successfully downloaded", self.identifier)

        return downloader

    def download(
        self, filepath: Union[str, Path], chunk_size: int = MAX_CHUNK_SIZE
    ) -> None:
        """
        Download the asset to ``filepath``.  Blocks until the download is
        complete.
        """
        downloader = self.get_download_file_iter(chunk_size=chunk_size)
        with open(filepath, "wb") as fp:
            for chunk in downloader():
                fp.write(chunk)


class RemoteAsset(BaseRemoteAsset):
    """
    Representation of an asset retrieved from the API with associated Dandiset
    information
    """

    JSON_EXCLUDE = frozenset(["client", "dandiset_id", "version_id"])

    #: The identifier for the Dandiset to which the asset belongs
    dandiset_id: str
    #: The identifier for the version of the Dandiset to which the asset
    #: belongs
    version_id: str

    @property
    def api_path(self) -> str:
        return f"/dandisets/{self.dandiset_id}/versions/{self.version_id}/assets/{self.identifier}/"

    def set_metadata(self, metadata: models.Asset) -> None:
        """
        Set the metadata for the asset to the given value and update the
        `RemoteAsset` in place.
        """
        return self.set_raw_metadata(metadata.json_dict())

    def set_raw_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Set the metadata for the asset to the given value and update the
        `RemoteAsset` in place.
        """
        try:
            etag = metadata["digest"]["dandi:dandi-etag"]
        except KeyError:
            raise ValueError("dandi-etag digest not set in new asset metadata")
        r = self.client.post(
            "/blobs/digest/",
            json={"algorithm": "dandi:dandi-etag", "value": etag},
        )
        data = self.client.put(
            self.api_path, json={"metadata": metadata, "blob_id": r["blob_id"]}
        )
        self.identifier = data["asset_id"]
        self.path = data["path"]
        self.size = int(data["size"])
        self.modified = ensure_datetime(data["modified"])
        self._metadata = data["metadata"]

    def delete(self) -> None:
        """Delete the asset"""
        self.client.delete(self.api_path)


def upload_part(storage_session, fp, lock, etagger, asset_path, part):
    etag_part = etagger.get_part(part["part_number"])
    if part["size"] != etag_part.size:
        raise RuntimeError(
            f"Server and client disagree on size of upload part"
            f" {part['part_number']}; server says {part['size']},"
            f" client says {etag_part.size}"
        )
    with lock:
        fp.seek(etag_part.offset)
        chunk = fp.read(part["size"])
    if len(chunk) != part["size"]:
        raise RuntimeError(
            f"End of file {fp.name} reached unexpectedly early:"
            f" read {len(chunk)} bytes of out of an expected {part['size']}"
        )
    lgr.debug(
        "%s: Uploading part %d/%d (%d bytes)",
        asset_path,
        part["part_number"],
        etagger.part_qty,
        part["size"],
    )
    r = storage_session.put(
        part["upload_url"],
        data=chunk,
        json_resp=False,
        retry=tenacity.retry_if_result(lambda r: r.status_code == 500),
    )
    server_etag = r.headers["ETag"].strip('"')
    lgr.debug(
        "%s: Part upload finished ETag=%s Content-Length=%s",
        asset_path,
        server_etag,
        r.headers.get("Content-Length"),
    )
    client_etag = etagger.get_part_etag(etag_part)
    if server_etag != client_etag:
        raise RuntimeError(
            f"Server and client disagree on ETag of upload part"
            f" {part['part_number']}; server says"
            f" {server_etag}, client says {client_etag}"
        )
    return {
        "part_number": part["part_number"],
        "size": part["size"],
        "etag": server_etag,
    }
