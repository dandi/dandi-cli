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

        # Construct the url
        if self.api_url.endswith("/") and path.startswith("/"):
            path = path[1:]
        url = self.api_url + path

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
    def get_dandiset_assets(self, dandiset_id, version, page_size=None):
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
            {k: r[k] for k in ("path", "uuid", "size", "sha256") if k in r}
            for r in results
        ]
        return results_
