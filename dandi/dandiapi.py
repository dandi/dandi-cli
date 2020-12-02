from contextlib import contextmanager
import os.path
from time import sleep
import requests

from . import get_logger
from .consts import MAX_CHUNK_SIZE
from .support.digests import Digester

lgr = get_logger()


# Following class is loosely based on GirderClient, with authentication etc
# being stripped.
# TODO: add copyright/license info
class RESTFullAPIClient(object):
    """A base class for REST clients"""

    def __init__(self, api_url):
        self.api_url = api_url
        self._session = None
        self._headers = {}

    @contextmanager
    def session(self, session=None):
        """
        Use a :class:`requests.Session` object for all outgoing requests.
        If `session` isn't passed into the context manager
        then one will be created and yielded. Session objects are useful for enabling
        persistent HTTP connections as well as partially applying arguments to many
        requests, such as headers.

        Note: `session` is closed when the context manager exits, regardless of who
        created it.

        .. code-block:: python

            with client.session() as session:
                session.headers.update({'User-Agent': 'myapp 1.0'})

                for item in items:
                    client.downloadItem(item, fh)

        In the above example, each request will be executed with the User-Agent header
        while reusing the same TCP connection.

        :param session: An existing :class:`requests.Session` object, or None.
        """
        self._session = session if session else requests.Session()
        self._session.headers.update(self._headers)

        try:
            yield self._session
        finally:
            # close only if we started a new one
            if not session:
                self._session.close()
            self._session = None

    def _request_func(self, method):
        if self._session is not None:
            return getattr(self._session, method.lower())
        else:
            return getattr(requests, method.lower())

    def send_request(
        self,
        method,
        path,
        parameters=None,
        data=None,
        files=None,
        json=None,
        headers=None,
        json_resp=True,
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
        :param parameters: A dictionary mapping strings to strings, to be used
            as the key/value pairs in the request parameters.
        :type parameters: dict
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
        """
        if not parameters:
            parameters = {}

        # Look up the HTTP method we need
        f = self._request_func(method)

        url = self.get_url(path)

        # Make the request, passing parameters and authentication info
        _headers = headers or {}

        if json_resp and "accept" not in _headers:
            _headers["accept"] = "application/json"

        lgr.debug("%s %s", method.upper(), url)
        result = f(
            url,
            params=parameters,
            data=data,
            files=files,
            json=json,
            headers=_headers,
            **kwargs,
        )
        lgr.debug("Response: %d", result.status_code)

        # If success, return the json object. Otherwise throw an exception.
        if not result.ok:
            raise requests.HTTPError(
                f"Error {result.status_code} while sending {method} request to {url}",
                response=result,
            )

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

    def get(self, path, parameters=None, json_resp=True):
        """
        Convenience method to call :py:func:`send_request` with the 'GET' HTTP method.
        """
        return self.send_request("GET", path, parameters, json_resp=json_resp)

    def post(
        self,
        path,
        parameters=None,
        files=None,
        data=None,
        json=None,
        headers=None,
        json_resp=True,
    ):
        """
        Convenience method to call :py:func:`send_request` with the 'POST' HTTP method.
        """
        return self.send_request(
            "POST",
            path,
            parameters,
            files=files,
            data=data,
            json=json,
            headers=headers,
            json_resp=json_resp,
        )

    def put(self, path, parameters=None, data=None, json=None, json_resp=True):
        """
        Convenience method to call :py:func:`send_request` with the 'PUT'
        HTTP method.
        """
        return self.send_request(
            "PUT", path, parameters, data=data, json=json, json_resp=json_resp
        )

    def delete(self, path, parameters=None, json_resp=True):
        """
        Convenience method to call :py:func:`send_request` with the 'DELETE' HTTP method.
        """
        return self.send_request("DELETE", path, parameters, json_resp=json_resp)

    def patch(self, path, parameters=None, data=None, json=None, json_resp=True):
        """
        Convenience method to call :py:func:`send_request` with the 'PATCH' HTTP method.
        """
        return self.send_request(
            "PATCH", path, parameters, data=data, json=json, json_resp=json_resp
        )


class DandiAPIClient(RESTFullAPIClient):
    def __init__(self, api_url, token=None):
        super().__init__(api_url)
        if token is not None:
            self._headers["Authorization"] = f"token {token}"

    def get_asset(self, dandiset_id, version, uuid):
        """

        /dandisets/{version__dandiset__pk}/versions/{version__version}/assets/{uuid}/

        Parameters
        ----------
        dandiset_id
        version
        uuid

        Returns
        -------

        """
        return self.get(f"/dandisets/{dandiset_id}/versions/{version}/assets/{uuid}/")

    def get_dandiset(self, dandiset_id, version):
        return self._migrate_dandiset_metadata(
            self.get(f"/dandisets/{dandiset_id}/versions/{version}/")
        )

    def get_dandiset_assets(self, dandiset_id, version, page_size=None):
        """ A generator to provide asset records """
        resp = self.get(
            f"/dandisets/{dandiset_id}/versions/{version}/assets/",
            parameters={"page_size": page_size},
        )
        while True:
            yield from resp["results"]
            if "next" in resp:
                resp = self.get(resp["next"])
            else:
                break

    def get_dandiset_and_assets(self, dandiset_id, version):
        """This is pretty much an adapter to provide "harmonized" output in both
        girder and DANDI api clients.

        Harmonization should happen toward DANDI API BUT AFAIK it is still influx
        """
        lgr.info(f"Traversing {dandiset_id} (version: {version})")
        dandiset = self.get_dandiset(dandiset_id, version)
        assets = self.get_dandiset_assets(dandiset_id, version)
        return dandiset, assets

    def get_download_file_iter(
        self, dandiset_id, version, uuid, chunk_size=MAX_CHUNK_SIZE
    ):
        url = self.get_url(
            f"/dandisets/{dandiset_id}/versions/{version}/assets/{uuid}/download/"
        )

        def downloader(start_at=0):
            lgr.debug("Starting download from %s", url)
            headers = None
            if start_at > 0:
                headers = {"Range": f"bytes={start_at}-"}
            result = (self._session if self._session else requests).get(
                url, stream=True, headers=headers
            )
            # TODO: apparently we might need retries here as well etc
            # if result.status_code not in (200, 201):
            result.raise_for_status()

            for chunk in result.raw.stream(chunk_size, decode_content=False):
                if chunk:  # could be some "keep alive"?
                    yield chunk

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

    def upload(self, dandiset_id, version_id, asset_path, asset_metadata, filepath):
        filehash = Digester(["sha256"])(filepath)["sha256"]
        lgr.debug("Calculated sha256 digest of %s for %s", filehash, filepath)
        try:
            self.post("/uploads/validate/", json={"sha256": filehash})
        except requests.HTTPError as e:
            if e.response.status_code == 400:
                lgr.debug("Blob does not already exist on server")
                blob_exists = False
            else:
                raise
        else:
            lgr.debug("Blob is already uploaded to server")
            blob_exists = True
        if not blob_exists:
            lgr.debug("Beginning upload")
            resp = self.post(
                "/uploads/initialize/",
                json={
                    "file_name": f"{dandiset_id}/{version_id}/{asset_path}",
                    "file_size": os.path.getsize(filepath),
                },
            )
            object_key = resp["object_key"]
            upload_id = resp["upload_id"]
            parts_out = []
            with open(filepath, "rb") as fp:
                for part in resp["parts"]:
                    chunk = fp.read(part["size"])
                    if len(chunk) != part["size"]:
                        raise RuntimeError(
                            f"End of file {filepath} reached unexpectedly early"
                        )
                    lgr.debug(
                        "Uploading part %d (%d bytes)",
                        part["part_number"],
                        part["size"],
                    )
                    r = self.put(part["upload_url"], data=chunk, json_resp=False)
                    parts_out.append(
                        {
                            "part_number": part["part_number"],
                            "size": part["size"],
                            "etag": r.headers["ETag"],
                        }
                    )
            lgr.debug("Completing upload")
            resp = self.post(
                "/uploads/complete/",
                json={
                    "object_key": object_key,
                    "upload_id": upload_id,
                    "parts": parts_out,
                },
            )
            self.post(resp["complete_url"], data=resp["body"], json_resp=False)
            self.post(
                "/uploads/validate/",
                json={"sha256": filehash, "object_key": object_key},
            )
        while True:
            lgr.debug("Waiting for server-side validation to complete")
            resp = self.get(f"/uploads/validations/{filehash}/")
            if resp["state"] != "IN_PROGRESS":
                if resp["state"] == "FAILED":
                    raise RuntimeError(
                        "Server-side asset validation failed!"
                        f"  Error reported: {resp.get('error')}"
                    )
                break
            sleep(0.1)
        lgr.debug("Assigning asset blob to dandiset & version")
        self.post(
            f"/dandisets/{dandiset_id}/versions/{version_id}/assets/",
            json={"path": asset_path, "metadata": asset_metadata, "sha256": filehash},
        )

    def create_dandiset(self, name, metadata):
        return self.post("/dandisets/", json={"name": name, "metadata": metadata})
