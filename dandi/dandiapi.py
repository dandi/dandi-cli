from contextlib import contextmanager

import requests

from . import get_logger
from .utils import ensure_datetime
from .consts import MAX_CHUNK_SIZE

lgr = get_logger()


# Following class is loosely based on GirderClient, with authentication etc
# being stripped.
# TODO: add copyright/license info
class RESTFullAPIClient(object):
    """A base class for REST clients"""

    def __init__(self, api_url):
        self.api_url = api_url
        self._session = None

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

        result = f(
            url,
            params=parameters,
            data=data,
            files=files,
            json=json,
            headers=_headers,
            **kwargs,
        )

        # If success, return the json object. Otherwise throw an exception.
        if not result.ok:
            raise requests.HTTPError(
                f"Error {result.status_code} while sending {method} request to {url}",
                response=result,
            )

        if json_resp:
            return result.json()
        else:
            return result

    def get_url(self, path):
        # Construct the url
        if self.api_url.endswith("/") and path.startswith("/"):
            path = path[1:]
        url = self.api_url + path
        return url

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

    def get_dandiset_assets(self, dandiset_id, version, location=None, page_size=None):
        """A generator to provide asset records
        """
        if location is not None:
            raise NotImplementedError(
                "location specific query. See https://github.com/dandi/dandi-publish/issues/77"
            )
            # although we could just provide ad-hoc implementation here for now. TODO
        if page_size is not None:
            raise NotImplementedError("paginated query is not supported yet")
        page_size = 1000000
        resp = self.get(
            f"/dandisets/{dandiset_id}/versions/{version}/assets/",
            parameters={"page_size": page_size},
        )
        try:
            assert not resp.get(
                "next"
            ), "ATM we do not support pagination and result should have not been paginated"
            assert not resp.get("prev")
            results = resp.get("results", [])
            assert len(results) == resp.get("count")
            # Just some sanity checks for now, but might change, see
            # https://github.com/dandi/dandi-publish/issues/79
            assert all(
                r.get("version", {}).get("dandiset", {}).get("identifier")
                == dandiset_id
                for r in results
            )
            assert all(r.get("version", {}).get("version") == version for r in results)
        except AssertionError:
            lgr.error(
                f"Some expectations on returned /assets/ for {dandiset_id}@{version} are violated"
            )
            raise
        # Things might change, so let's just return only "relevant" ATM information
        # under assumption that assets belong to the current version of the dataset requested
        # results_ = [
        #     {k: r[k] for k in ("path", "uuid", "size", "sha256", "metadata") if k in r}
        #     for r in results
        # ]
        for r in results:
            # check for paranoid Yarik with current multitude of checksums
            # r['sha256'] is what "dandi-publish" computed, but then
            # metadata could contain multiple digests computed upon upload
            metadata = r.get("metadata")
            if (
                "sha256" in r
                and "sha256" in metadata
                and metadata["sha256"] != r["sha256"]
            ):
                lgr.warning("sha256 mismatch for %s" % str(r))
            # There is no "modified" time stamp and "updated" also shows something
            # completely different, so if "modified" is not there -- we will try to
            # get it from metadata
            if "modified" not in r and metadata:
                uploaded_mtime = metadata.get("uploaded_mtime")
                if uploaded_mtime:
                    r["modified"] = ensure_datetime(uploaded_mtime)
            yield r

    def get_dandiset_and_assets(self, dandiset_id, version, location=None):
        """This is pretty much an adapter to provide "harmonized" output in both
        girder and DANDI api clients.

        Harmonization should happen toward DADNDI API BUT AFAIK it is still influx
        """
        # Fun begins!
        location_ = "/" + location if location else ""
        lgr.info(f"Traversing {dandiset_id}{location_} (version: {version})")

        # TODO: get all assets
        # 1. includes sha256, created, updated but those are of "girder" level
        # so lack "uploaded_mtime" and uploaded_nwb_object_id forbidding logic for
        # deducing necessity to update/move. But we still might want to rely on its
        # sha256 instead of metadata since older uploads would not have that metadata
        # in them
        # 2. there is no API to list assets given a location
        #
        # Get dandiset information
        dandiset = self.get_dandiset(dandiset_id, version)
        # TODO: location
        assets = self.get_dandiset_assets(dandiset_id, version, location=location)
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
