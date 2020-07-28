from datetime import datetime
import os
import os.path as op
import json
import keyring
import random
import sys
import time


from functools import lru_cache
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

import requests

from . import get_logger
from .utils import ensure_datetime, ensure_strtime, is_same_time
from .consts import (
    REQ_BUFFER_SIZE,
    dandiset_metadata_file,
    known_instances,
    known_instances_rev,
    metadata_digests,
)
from .support.digests import Digester
from .dandiset import Dandiset

lgr = get_logger()


class HTTPError(requests.HTTPError):
    """An HTTP error occurred.

    Following Girder's recommendation of having its HttpError deprecated,
    this is just a helper to bring that HTTPError into our space
    """

    pass


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

        yield self._session

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
        if result.status_code in (200, 201):
            if json_resp:
                return result.json()
            else:
                return result
        else:
            raise HTTPError(
                f"Error {result.status_code} while sending {method} request to {url}",
                response=result,
            )

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
        return self.get(f"/dandisets/{dandiset_id}/versions/{version}/")

    def get_dandiset_assets(
        self, dandiset_id, version, location=None, page_size=None, include_metadata=True
    ):
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
        results_ = [
            {k: r[k] for k in ("path", "uuid", "size", "sha256", "metadata") if k in r}
            for r in results
        ]
        for r in results_:
            if include_metadata and "metadata" not in r:
                # metadata is not included ATM
                # https://github.com/dandi/dandi-publish/issues/78
                # so we need to query explicitly. Returned value is pretty much an asset record
                # we already have but also has "metadata"
                asset_res = self.get_asset(dandiset_id, version, r["uuid"])
                assert asset_res["path"] == r["path"]
                assert asset_res["uuid"] == r["uuid"]
                if "metadata" in asset_res:
                    r["metadata"] = asset_res["metadata"]
                    # check for paranoid Yarik with current multitude of checksums
                    # r['sha256'] is what "dandi-publish" computed, but then
                    # metadata could contain multiple digests computed upon upload
                    if (
                        "sha256" in r
                        and "sha256" in asset_res["metadata"]
                        and asset_res["metadata"]["sha256"] != r["sha256"]
                    ):
                        lgr.warning("sha256 mismatch for %s" % str(r))
            yield r

    def get_dandiset_and_assets(
        self, dandiset_id, version, location=None, include_metadata=True
    ):
        """This is pretty much an adapter to provide "harmonized" output in both
        girder and dandiapi clients.

        Harmonization should happen toward "dandiapi" BUT AFAIK it is still influx
        """
        # Fun begins!
        location_ = "/" + location if location else ""
        lgr.info(f"Traversing {dandiset_id}{location_} (version: {version})")

        # TODO: get all assets
        # 1. includes sha256, created, updated but those are of "girder" level so lack "uploaded_mtime"
        # and uploaded_nwb_object_id forbidding logic for deducing necessity to update/move.
        # But we still might want to rely on its sha256 instead of metadata since older uploads
        # would not have that metadata in them
        # 2. there is no API to list assets given a location
        # Get dandiset information
        dandiset = self.get_dandiset(dandiset_id, version)
        # TODO: location
        assets = self.get_dandiset_assets(
            dandiset_id, version, location=location, include_metadata=include_metadata
        )
        return dandiset, assets

    def get_download_file_iter(
        self, dandiset_id, version, uuid, chunk_size=REQ_BUFFER_SIZE
    ):
        url = self.get_url(
            f"/dandisets/{dandiset_id}/versions/{version}/assets/{uuid}/download/"
        )

        # TODO: just redo to have this function a generator
        def downloader():
            """Generator which will be yielding records updating on the progress etc"""
            with self.session.get(url, stream=True) as resp:
                for chunk in resp.raw.stream(chunk_size, decode_content=False):
                    if chunk:  # could be some "keep alive"?
                        yield chunk

        return downloader
