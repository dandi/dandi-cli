from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os.path
from pathlib import Path
import re
from threading import Lock
from typing import Any, Callable, Dict, Iterator, Optional, Union, cast
from xml.etree.ElementTree import fromstring

import click
from pydantic import BaseModel, Field
import requests
import tenacity

from . import get_logger
from .consts import MAX_CHUNK_SIZE, known_instances_rev
from .exceptions import NotFoundError
from .keyring import keyring_lookup
from .utils import USER_AGENT, is_interactive, try_multiple

lgr = get_logger()


class APIBase(BaseModel):
    class Config:
        allow_population_by_field_name = True
        # To allow `client: Session`:
        arbitrary_types_allowed = True


class Version(APIBase):
    identifier: str = Field(alias="version")
    name: str
    asset_count: int
    size: int
    created: datetime
    modified: datetime


class RemoteDandiset(APIBase):
    client: "DandiAPIClient"
    identifier: str
    created: datetime
    modified: datetime
    version: Version
    most_recent_published_version: Optional[Version]
    draft_version: Optional[Version]

    @property
    def version_id(self) -> str:
        return self.version.identifier

    @property
    def api_path(self) -> str:
        return f"/dandisets/{self.identifier}/"

    @property
    def version_api_path(self) -> str:
        return f"/dandisets/{self.identifier}/versions/{self.version_id}/"

    def _mkasset(self, data: Dict[str, Any]) -> "RemoteAsset":
        return RemoteAsset(
            dandiset_id=self.identifier, version_id=self.version_id, **data
        )

    def get_versions(self) -> Iterator[Version]:
        for v in self.client.paginate(f"{self.api_path}versions/"):
            yield Version.parse_obj(v)

    def get_version(self, version_id: str) -> Version:
        # Raises a 404 if the version does not exist
        return Version.parse_obj(self.client.get(f"{self.version_api_path}info/"))

    def for_version(self, version_id: str) -> "RemoteDandiset":
        # Raises a 404 if the version does not exist
        return self.copy(update={"version": self.get_version(version_id)})

    def delete(self) -> None:
        self.client.delete(self.api_path)

    def get_raw_metadata(self) -> Dict[str, Any]:
        return cast(Dict[str, Any], self.client.get(self.version_api_path))

    def set_raw_metadata(self, metadata: Dict[str, Any]) -> None:
        self.client.put(
            self.version_api_path,
            json={"metadata": metadata, "name": metadata.get("name", "")},
        )

    def publish(self) -> Version:
        return Version.parse_obj(self.client.post(f"{self.version_api_path}publish/"))

    def get_assets(self, path=None) -> Iterator["RemoteAsset"]:
        for a in self.client.paginate(f"{self.version_api_path}assets/"):
            yield self._mkasset(a)

    def get_asset(self, asset_id: str) -> "RemoteAsset":
        # Raises a 404 if the asset does not exist
        return self._mkasset(
            self.client.get(f"{self.version_api_path}assets/{asset_id}/")
        )

    def get_assets_under_path(self, path: str) -> Iterator["RemoteAsset"]:
        for a in self.client.paginate(
            f"{self.version_api_path}assets/", params={"path": path}
        ):
            yield self._mkasset(a)

    def get_asset_by_path(self, path: str) -> "RemoteAsset":
        # Raises NotFoundError if the asset does not exist
        try:
            # Weed out any assets that happen to have the given path as a
            # proper prefix:
            (asset,) = (
                a for a in self.get_assets_under_path(path) if a["path"] == path
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
        if assets_dirpath and not assets_dirpath.endswith("/"):
            assets_dirpath += "/"
        assets = list(self.get_assets_under_path(assets_dirpath))
        for a in assets:
            filepath = Path(dirpath, a["path"][len(assets_dirpath) :])
            filepath.parent.mkdir(parents=True, exist_ok=True)
            a.download(filepath, chunk_size=chunk_size)

    def upload_raw_asset(
        self,
        filepath: Union[str, Path],
        asset_metadata: Dict[str, Any],
        jobs: Optional[int] = None,
    ) -> None:
        """
        Parameters
        ----------
        filepath: str or PathLike
          the path to the local file to upload
        asset_metadata: dict
          Metadata for the uploaded asset file.  Must include a "path" field
          giving the POSIX path at which the uploaded file will be placed on
          the server.
        """
        for _ in self.iter_upload_raw_asset(filepath, asset_metadata, jobs=jobs):
            pass

    def iter_upload_raw_asset(
        self,
        filepath: Union[str, Path],
        asset_metadata: Dict[str, Any],
        jobs: Optional[int] = None,
    ) -> Iterator[dict]:
        """
        Parameters
        ----------
        filepath: str or PathLike
          the path to the local file to upload
        asset_metadata: dict
          Metadata for the uploaded asset file.  Must include a "path" field
          giving the POSIX path at which the uploaded file will be placed on
          the server.

        Returns
        -------
        a generator of `dict`s containing at least a ``"status"`` key
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
        try:
            extant = self.get_asset_by_path(asset_path)
        except NotFoundError:
            self.client.post(
                f"{self.version_api_path}assets/",
                json={"metadata": asset_metadata, "blob_id": blob_id},
            )
        else:
            lgr.debug("%s: Asset already exists at path; updating", asset_path)
            self.client.put(
                extant.api_path, json={"metadata": asset_metadata, "blob_id": blob_id}
            )
        lgr.info("%s: Asset successfully uploaded", asset_path)
        yield {"status": "done"}


class RemoteAsset(APIBase):
    client: "DandiAPIClient"
    dandiset_id: str
    version_id: str
    identifier: str = Field(alias="asset_id")
    path: str
    size: int
    created: datetime
    modified: datetime

    @property
    def api_path(self) -> str:
        return f"/dandisets/{self.dandiset_id}/versions/{self.version_id}/assets/{self.identifier}/"

    def get_raw_metadata(self) -> Dict[str, Any]:
        return cast(Dict[str, Any], self.client.get(self.api_path))

    def delete(self) -> None:
        self.client.delete(self.api_path)

    def get_download_file_iter(
        self, chunk_size: int = MAX_CHUNK_SIZE
    ) -> Callable[..., Iterator[bytes]]:
        url = self.client.get_url(f"{self.api_path}download/")

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
        downloader = self.get_download_file_iter(chunk_size=chunk_size)
        with open(filepath, "wb") as fp:
            for chunk in downloader():
                fp.write(chunk)


# Following class is loosely based on GirderClient, with authentication etc
# being stripped.
# TODO: add copyright/license info
class RESTFullAPIClient:
    """A base class for REST clients"""

    def __init__(self, api_url, session=None, headers=None):
        self.api_url = api_url
        if session is None:
            session = requests.Session()
        if headers is not None:
            session.headers.update(headers)
        session.headers.setdefault("User-Agent", USER_AGENT)
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
            result = try_multiple(5, doretry, 1.1)(
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
    def __init__(self, api_url, token=None):
        super().__init__(api_url)
        if token is not None:
            self.authenticate(token)

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

    def get_asset(self, dandiset_id, version, asset_id):
        """

        /dandisets/{version__dandiset__pk}/versions/{version__version}/assets/{asset_id}/

        Parameters
        ----------
        dandiset_id
        version
        asset_id

        Returns
        -------

        """
        return self.get(
            f"/dandisets/{dandiset_id}/versions/{version}/assets/{asset_id}/"
        )

    def get_dandiset(self, dandiset_id, version):
        return self._migrate_dandiset_metadata(
            self.get(f"/dandisets/{dandiset_id}/versions/{version}/info/")
        )

    def set_dandiset_metadata(self, dandiset_id, *, metadata):
        # CLI should not update metadata for released dandisets so always "draft"
        return self.put(
            f"/dandisets/{dandiset_id}/versions/draft/",
            json={"metadata": metadata, "name": metadata.get("name", "")},
        )

    def delete_dandiset(self, dandiset_id):
        self.delete(f"/dandisets/{dandiset_id}/")

    def get_dandiset_assets(
        self, dandiset_id, version, page_size=None, path=None, include_metadata=False
    ):
        """A generator to provide asset records"""
        resp = self.get(
            f"/dandisets/{dandiset_id}/versions/{version}/assets/",
            params={"page_size": page_size, "path": path},
        )
        while True:
            for asset in resp["results"]:
                if include_metadata:
                    asset["metadata"] = self.get_asset(
                        dandiset_id, version, asset["asset_id"]
                    )
                yield asset
            if resp.get("next"):
                resp = self.get(resp["next"])
            else:
                break

    def get_dandiset_and_assets(self, dandiset_id, version, include_metadata=False):
        """This is pretty much an adapter to provide "harmonized" output in both
        girder and DANDI api clients.

        Harmonization should happen toward DANDI API BUT AFAIK it is still influx
        """
        lgr.info(f"Traversing {dandiset_id} (version: {version})")
        dandiset = self.get_dandiset(dandiset_id, version)
        assets = self.get_dandiset_assets(
            dandiset_id, version, include_metadata=include_metadata
        )
        return dandiset, assets

    def get_download_file_iter(
        self, dandiset_id, version, asset_id, chunk_size=MAX_CHUNK_SIZE
    ):
        url = self.get_url(
            f"/dandisets/{dandiset_id}/versions/{version}/assets/{asset_id}/download/"
        )

        def downloader(start_at=0):
            lgr.debug("Starting download from %s", url)
            headers = None
            if start_at > 0:
                headers = {"Range": f"bytes={start_at}-"}
            result = self.session.get(url, stream=True, headers=headers)
            # TODO: apparently we might need retries here as well etc
            # if result.status_code not in (200, 201):
            result.raise_for_status()

            for chunk in result.iter_content(chunk_size=chunk_size):
                if chunk:  # could be some "keep alive"?
                    yield chunk
            lgr.info("Asset %s successfully downloaded", asset_id)

        return downloader

    # TODO: remove when API stabilizes

    # Should perform changes in-place but also return the original record

    @classmethod
    def _migrate_dandiset_metadata(cls, dandiset):
        dandiset_metadata = dandiset.get("metadata", {})
        if not dandiset_metadata:
            return dandiset
        # DANDI API has no versioning yet, and things are in flux.
        # It used to have metadata within a key... just in case let's also
        # be able to handle "old" style
        if "identifier" not in dandiset_metadata and "dandiset" in dandiset_metadata:
            dandiset["metadata"] = dandiset_metadata.pop("dandiset")
        return dandiset

    def upload(self, dandiset_id, version_id, asset_metadata, filepath, jobs=None):
        """
        Parameters
        ----------
        dandiset_id: str
          the ID of the Dandiset to which to upload the file
        version_id: str
          the ID of the version of the Dandiset to which to upload the file
        asset_metadata: dict
          Metadata for the uploaded asset file.  Must include a "path" field
          giving the POSIX path at which the uploaded file will be placed on
          the server.
        filepath: str or PathLike
          the path to the local file to upload
        """
        for _ in self.iter_upload(
            dandiset_id, version_id, asset_metadata, filepath, jobs=jobs
        ):
            pass

    def iter_upload(self, dandiset_id, version_id, asset_metadata, filepath, jobs=None):
        """
        Parameters
        ----------
        dandiset_id: str
          the ID of the Dandiset to which to upload the file
        version_id: str
          the ID of the version of the Dandiset to which to upload the file
        asset_metadata: dict
          Metadata for the uploaded asset file.  Must include a "path" field
          giving the POSIX path at which the uploaded file will be placed on
          the server.
        filepath: str or PathLike
          the path to the local file to upload

        Returns
        -------
        a generator of `dict`s containing at least a ``"status"`` key
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
            resp = self.post(
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
                resp = self.post(
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
                resp = self.post(f"/uploads/{upload_id}/validate/")
                blob_id = resp["blob_id"]
        lgr.debug("%s: Assigning asset blob to dandiset & version", asset_path)
        yield {"status": "producing asset"}
        extant = self.get_asset_bypath(dandiset_id, version_id, asset_path)
        if extant is None:
            self.post(
                f"/dandisets/{dandiset_id}/versions/{version_id}/assets/",
                json={"metadata": asset_metadata, "blob_id": blob_id},
            )
        else:
            lgr.debug("%s: Asset already exists at path; updating", asset_path)
            self.put(
                f"/dandisets/{dandiset_id}/versions/{version_id}/assets/{extant['asset_id']}/",
                json={"metadata": asset_metadata, "blob_id": blob_id},
            )
        lgr.info("%s: Asset successfully uploaded", asset_path)
        yield {"status": "done"}

    def create_dandiset(self, name, metadata):
        return self.post("/dandisets/", json={"name": name, "metadata": metadata})

    def download_asset(
        self, dandiset_id, version, asset_id, filepath, chunk_size=MAX_CHUNK_SIZE
    ):
        downloader = self.get_download_file_iter(
            dandiset_id, version, asset_id, chunk_size=chunk_size
        )
        with open(filepath, "wb") as fp:
            for chunk in downloader():
                fp.write(chunk)

    def download_asset_bypath(
        self, dandiset_id, version, asset_path, filepath, chunk_size=MAX_CHUNK_SIZE
    ):
        asset = self.get_asset_bypath(dandiset_id, version, asset_path)
        if asset is None:
            raise RuntimeError(f"No asset found with path {asset_path!r}")
        self.download_asset(
            dandiset_id, version, asset["asset_id"], filepath, chunk_size=chunk_size
        )

    def download_assets_directory(
        self, dandiset_id, version, assets_dirpath, dirpath, chunk_size=MAX_CHUNK_SIZE
    ):
        if assets_dirpath and not assets_dirpath.endswith("/"):
            assets_dirpath += "/"
        assets = list(
            self.get_dandiset_assets(dandiset_id, version, path=assets_dirpath)
        )
        for a in assets:
            filepath = Path(dirpath, a["path"][len(assets_dirpath) :])
            filepath.parent.mkdir(parents=True, exist_ok=True)
            self.download_asset(
                dandiset_id, version, a["asset_id"], filepath, chunk_size=chunk_size
            )

    def get_asset_bypath(
        self, dandiset_id, version, asset_path, include_metadata=False
    ):
        try:
            # Weed out any assets that happen to have the given path as a
            # proper prefix:
            (asset,) = (
                a
                for a in self.get_dandiset_assets(
                    dandiset_id,
                    version,
                    path=asset_path,
                    include_metadata=include_metadata,
                )
                if a["path"] == asset_path
            )
        except ValueError:
            return None
        else:
            return asset

    def publish_version(self, dandiset_id, base_version_id):
        return self.post(
            f"/dandisets/{dandiset_id}/versions/{base_version_id}/publish/"
        )

    def delete_asset(self, dandiset_id, version_id, asset_id):
        self.delete(
            f"/dandisets/{dandiset_id}/versions/{version_id}/assets/{asset_id}/"
        )

    def delete_asset_bypath(self, dandiset_id, version_id, asset_path):
        asset = self.get_asset_bypath(dandiset_id, version_id, asset_path)
        if asset is None:
            raise RuntimeError(f"No asset found with path {asset_path!r}")
        self.delete_asset(dandiset_id, version_id, asset["asset_id"])


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
