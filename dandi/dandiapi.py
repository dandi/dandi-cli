from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
import json
import os.path
from pathlib import Path, PurePosixPath
import re
from time import sleep, time
from types import TracebackType
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    FrozenSet,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    cast,
)
from urllib.parse import unquote, urlparse, urlunparse

import click
from dandischema import models
import dateutil.parser
from pydantic import AnyHttpUrl, BaseModel, Field, PrivateAttr
import requests
import tenacity

from . import get_logger
from .consts import (
    DRAFT,
    MAX_CHUNK_SIZE,
    RETRY_STATUSES,
    ZARR_DELETE_BATCH_SIZE,
    DandiInstance,
    EmbargoStatus,
    known_instances,
    known_instances_rev,
)
from .exceptions import HTTP404Error, NotFoundError, SchemaVersionError
from .keyring import keyring_lookup
from .misctypes import BasePath, Digest
from .utils import (
    USER_AGENT,
    check_dandi_version,
    chunked,
    ensure_datetime,
    is_interactive,
    is_page2_url,
)

lgr = get_logger()

T = TypeVar("T")


class AssetType(Enum):
    """
    .. versionadded:: 0.36.0

    An enum for the different kinds of resources that an asset's actual data
    can be
    """

    BLOB = 1
    ZARR = 2


class VersionStatus(Enum):
    PENDING = "Pending"
    VALIDATING = "Validating"
    VALID = "Valid"
    INVALID = "Invalid"
    PUBLISHING = "Publishing"
    PUBLISHED = "Published"


# Following class is loosely based on GirderClient, with authentication etc
# being stripped.
# TODO: add copyright/license info
class RESTFullAPIClient:
    """
    Base class for a JSON-based HTTP(S) client for interacting with a given
    base API URL.

    All request methods can take either an absolute URL or a slash-separated
    path; in the latter case, the path is appended to the base API URL
    (separated by a slash) in order to determine the actual URL to make the
    request of.

    `RESTFullAPIClient` instances are usable as context managers, in which case
    they will close their associated session on exit.
    """

    def __init__(
        self,
        api_url: str,
        session: Optional[requests.Session] = None,
        headers: Optional[dict] = None,
    ) -> None:
        """
        :param str api_url: The base HTTP(S) URL to prepend to request paths
        :param session: an optional `requests.Session` instance to use; if not
            specified, a new session is created
        :param headers: an optional `dict` of headers to send in every request
        """
        self.api_url = api_url
        if session is None:
            session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        if headers is not None:
            session.headers.update(headers)
        self.session = session
        #: Default number of items to request per page when paginating (`None`
        #: means to use the server's default)
        self.page_size: Optional[int] = None
        #: How many pages to fetch at once when parallelizing pagination
        self.page_workers: int = 5

    def __enter__(self: T) -> T:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.session.close()

    def request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        data: Any = None,
        files: Optional[dict] = None,
        json: Any = None,
        headers: Optional[dict] = None,
        json_resp: bool = True,
        retry_statuses: Sequence[int] = (),
        retry_if: Optional[Callable[[requests.Response], Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """
        This method looks up the appropriate method, constructs a request URL
        from the base URL, path, and parameters, and then sends the request. If
        the method is unknown or if the path is not found, an exception is
        raised; otherwise, a JSON object is returned with the response.

        This is a convenience method to use when making basic requests that do
        not involve multipart file data that might need to be specially encoded
        or handled differently.

        :param method: The HTTP method to use in the request (GET, POST, etc.)
        :type method: str
        :param path: A string containing the path elements for this request
        :type path: str
        :param params: A dictionary mapping strings to strings, to be used
            as the key/value pairs in the request parameters.
        :type params: dict
        :param data: A dictionary, bytes or file-like object to send in the
            body.
        :param files: A dictionary of 'name' => file-like-objects for multipart
            encoding upload.
        :type files: dict
        :param json: A JSON object to send in the request body.
        :type json: dict
        :param headers: If present, a dictionary of headers to encode in the
            request.
        :type headers: dict
        :param json_resp: Whether the response should be parsed as JSON. If
            False, the raw response object is returned. To get the raw binary
            content of the response, use the ``content`` attribute of the
            return value, e.g.

            .. code-block:: python

                resp = client.get('my/endpoint', json_resp=False)
                print(resp.content)  # Raw binary content
                print(resp.headers)  # Dict of headers

        :type json_resp: bool
        :param retry_statuses: a sequence of HTTP response status codes to
            retry in addition to `dandi.consts.RETRY_STATUSES`
        :param retry_if: an optional predicate applied to a failed HTTP
            response to test whether to retry
        """

        url = self.get_url(path)

        if headers is None:
            headers = {}
        if json_resp and "accept" not in headers:
            headers["accept"] = "application/json"

        lgr.debug("%s %s", method.upper(), url)

        try:
            for i, attempt in enumerate(
                tenacity.Retrying(
                    wait=tenacity.wait_exponential(exp_base=1.25, multiplier=1.25),
                    # urllib3's ConnectionPool isn't thread-safe, so we
                    # sometimes hit ConnectionErrors on the start of an upload.
                    # Retry when this happens.
                    # Cf. <https://github.com/urllib3/urllib3/issues/951>.
                    retry=tenacity.retry_if_exception_type(
                        (requests.ConnectionError, requests.HTTPError)
                    ),
                    stop=tenacity.stop_after_attempt(12),
                    reraise=True,
                )
            ):
                with attempt:
                    if attempt.retry_state.attempt_number > 1:
                        lgr.warning("Retrying %s %s", method.upper(), url)
                    result = self.session.request(
                        method,
                        url,
                        params=params,
                        data=data,
                        files=files,
                        json=json,
                        headers=headers,
                        **kwargs,
                    )
                    if result.status_code in [*RETRY_STATUSES, *retry_statuses] or (
                        retry_if is not None and retry_if(result)
                    ):
                        result.raise_for_status()
        except Exception:
            lgr.exception("HTTP connection failed")
            raise

        if i > 0:
            lgr.info(
                "%s %s succeeded after %d retr%s",
                method.upper(),
                url,
                i,
                "y" if i == 1 else "ies",
            )

        lgr.debug("Response: %d", result.status_code)

        # If success, return the json object. Otherwise throw an exception.
        if not result.ok:
            msg = f"Error {result.status_code} while sending {method} request to {url}"
            if result.status_code == 409:
                # Blob exists on server; log at DEBUG level
                lgr.debug("%s: %s", msg, result.text)
            else:
                lgr.error("%s: %s", msg, result.text)
            if len(result.text) <= 1024:
                msg += f": {result.text}"
            else:
                msg += f": {result.text[:1024]}... [{len(result.text)}-char response truncated]"
            if result.status_code == 404:
                raise HTTP404Error(msg, response=result)
            else:
                raise requests.HTTPError(msg, response=result)

        if json_resp:
            if result.text.strip():
                return result.json()
            else:
                return None
        else:
            return result

    def get_url(self, path: str) -> str:
        """
        Append a slash-separated ``path`` to the instance's base URL.  The two
        components are separated by a single slash, and any trailing slashes
        are removed.

        If ``path`` is already an absolute URL, it is returned unchanged.
        """
        # Construct the url
        if path.lower().startswith(("http://", "https://")):
            return path
        else:
            return self.api_url.rstrip("/") + "/" + path.lstrip("/")

    def get(self, path: str, **kwargs: Any) -> Any:
        """
        Convenience method to call `request()` with the 'GET' HTTP method.
        """
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        """
        Convenience method to call `request()` with the 'POST' HTTP method.
        """
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        """
        Convenience method to call `request()` with the 'PUT' HTTP method.
        """
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        """
        Convenience method to call `request()` with the 'DELETE' HTTP method.
        """
        return self.request("DELETE", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Any:
        """
        Convenience method to call `request()` with the 'PATCH' HTTP method.
        """
        return self.request("PATCH", path, **kwargs)

    def paginate(
        self,
        path: str,
        page_size: Optional[int] = None,
        params: Optional[dict] = None,
    ) -> Iterator:
        """
        Paginate through the resources at the given path: GET the path, yield
        the values in the ``"results"`` key, and repeat with the URL in the
        ``"next"`` key until it is ``null``.

        If the first ``"next"`` key is the same as the initially-requested URL
        but with the ``page`` query parameter set to ``2``, then the remaining
        pages are fetched concurrently in separate threads, `page_workers`
        (default 5) at a time.  This behavior requires the initial response to
        contain a ``"count"`` key giving the number of items across all pages.

        :param Optional[int] page_size:
            If non-`None`, overrides the client's `page_size` attribute for
            this sequence of pages
        """
        if page_size is None:
            page_size = self.page_size
        if page_size is not None:
            if params is None:
                params = {}
            params["page_size"] = page_size

        resp = self.get(path, params=params, json_resp=False)
        r = resp.json()
        if r["next"] is not None:
            page1 = resp.history[0].url if resp.history else resp.url
            if not is_page2_url(page1, r["next"]):
                lgr.warning(
                    "Pagination request to %s returned unexpected 'next' URL: %s",
                    page1,
                    r["next"],
                )
                if os.environ.get("DANDI_PAGINATION_DISABLE_FALLBACK"):
                    raise RuntimeError(
                        f"API server changed pagination strategy: {page1} URL"
                        f" is now followed by {r['next']}"
                    )
                else:
                    while True:
                        yield from r["results"]
                        if r.get("next"):
                            r = self.get(r["next"])
                        else:
                            return
        yield from r["results"]
        if r["next"] is None:
            return

        if page_size is None:
            page_size = len(r["results"])
        pages = (r["count"] + page_size - 1) // page_size

        def get_page(pageno: int) -> list:
            params2 = params.copy() if params is not None else {}
            params2["page"] = pageno
            results = self.get(path, params=params2)["results"]
            assert isinstance(results, list)
            return results

        with ThreadPoolExecutor(max_workers=self.page_workers) as pool:
            futures = [pool.submit(get_page, i) for i in range(2, pages + 1)]
            try:
                for f in futures:
                    yield from f.result()
            finally:
                for f in futures:
                    f.cancel()


class DandiAPIClient(RESTFullAPIClient):
    """A client for interacting with a Dandi Archive server"""

    def __init__(
        self, api_url: Optional[str] = None, token: Optional[str] = None
    ) -> None:
        """
        Construct a client instance.

        :param str api_url: Base API URL of the server to interact with.
        - For DANDI production, use  ``"https://api.dandiarchive.org/api"``
        - For DANDI staging, use ``"https://api-staging.dandiarchive.org/api"``
        - If no URL is supplied, the URL is looked up in `known_instances` using the value of the
        :envvar:`DANDI_INSTANCE` environment variable (default value: ``"dandi"``).
        :param str token: User API Key. Note that different instance APIs have different
        keys.
        """

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
        cls,
        instance: Union[str, DandiInstance],
        token: Optional[str] = None,
        authenticate: bool = False,
    ) -> "DandiAPIClient":
        """
        Construct a client instance for the server identified by ``instance``
        (either the name of a registered Dandi Archive instance or a
        `DandiInstance` instance) and an optional authentication token/API key.
        If no token is supplied and ``authenticate`` is true,
        `dandi_authenticate()` is called on the instance before returning it.
        """
        if isinstance(instance, str):
            instance = known_instances[instance]
        client = cls(instance.api, token=token)
        if token is None and authenticate:
            client.dandi_authenticate()
        return client

    def authenticate(self, token: str) -> None:
        """
        Set the authentication token/API key used by the `DandiAPIClient`.
        Before setting the token, a test request to ``/auth/token`` is made to
        check the token's validity; if it fails, a `requests.HTTPError` is
        raised.
        """
        # Fails if token is invalid:
        self.get("/auth/token", headers={"Authorization": f"token {token}"})
        self.session.headers["Authorization"] = f"token {token}"

    def dandi_authenticate(self) -> None:
        """
        Acquire and set the authentication token/API key used by the
        `DandiAPIClient`.  If the :envvar:`DANDI_API_KEY` environment variable
        is set, its value is used as the token.  Otherwise, the token is looked
        up in the user's keyring under the service
        ":samp:`dandi-api-{INSTANCE_NAME}`" [#auth]_ and username "``key``".
        If no token is found there, the user is prompted for the token, and, if
        it proves to be valid, it is stored in the user's keyring.

        .. [#auth] E.g., "``dandi-api-dandi``" for the production server or
                   "``dandi-api-dandi-staging``" for the staging server
        """
        # Shortcut for advanced folks
        api_key = os.environ.get("DANDI_API_KEY", None)
        if api_key:
            lgr.debug("Using api key from DANDI_API_KEY environment variable")
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
                lgr.debug(
                    "Using API key from %s",
                    {True: "keyring", False: "user input"}[key_from_keyring],
                )
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

    @property
    def _instance_id(self) -> str:
        url = self.api_url.rstrip("/")
        try:
            return known_instances_rev[url].upper()
        except KeyError:
            return url

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
            try:
                d = RemoteDandiset.from_data(
                    self, self.get(f"/dandisets/{dandiset_id}/")
                )
            except HTTP404Error:
                raise NotFoundError(f"No such Dandiset: {dandiset_id!r}")
            if version_id is not None and version_id != d.version_id:
                if version_id == DRAFT:
                    return d.for_version(d.draft_version)
                else:
                    return d.for_version(version_id)
            return d

    def get_dandisets(self) -> Iterator["RemoteDandiset"]:
        """
        Returns a generator of all Dandisets on the server.  For each Dandiset,
        the `RemoteDandiset`'s version is set to the most recent published
        version if there is one, otherwise to the draft version.
        """
        for data in self.paginate("/dandisets/"):
            yield RemoteDandiset.from_data(self, data)

    def create_dandiset(self, name: str, metadata: Dict[str, Any]) -> "RemoteDandiset":
        """Creates a Dandiset with the given name & metadata"""
        return RemoteDandiset.from_data(
            self, self.post("/dandisets/", json={"name": name, "metadata": metadata})
        )

    def check_schema_version(self, schema_version: Optional[str] = None) -> None:
        """
        Confirms that the server is using the same version of the Dandi schema
        as the client.  If it is not, a `SchemaVersionError` is raised.

        :param schema_version: the schema version to confirm that the server
            uses; if not set, the schema version for the installed
            ``dandischema`` library is used
        """
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
        """
        Fetch the asset with the given asset ID.  If the given asset does not
        exist, a `NotFoundError` is raised.

        The returned object will not have any information about the Dandiset
        associated with the asset; for that, the `RemoteDandiset.get_asset()`
        method must be used instead.
        """
        try:
            info = self.get(f"/assets/{asset_id}/info/")
        except HTTP404Error:
            raise NotFoundError(f"No such asset: {asset_id!r}")
        metadata = info.pop("metadata", None)
        return BaseRemoteAsset.from_base_data(self, info, metadata)


class APIBase(BaseModel):
    """
    Base class for API objects implemented in pydantic.

    This class (aside from the `json_dict()` method) is an implementation
    detail; do not rely on it.
    """

    JSON_EXCLUDE: ClassVar[FrozenSet[str]] = frozenset(["client"])

    def json_dict(self) -> Dict[str, Any]:
        """
        Convert to a JSONable `dict`, omitting the ``client`` attribute and
        using the same field names as in the API
        """
        return cast(
            Dict[str, Any],
            json.loads(self.json(exclude=self.JSON_EXCLUDE, by_alias=True)),
        )

    class Config:
        allow_population_by_field_name = True
        # To allow `client: Session`:
        arbitrary_types_allowed = True


class Version(APIBase):
    """
    The version information for a Dandiset retrieved from the API.

    Stringifying a `Version` returns its identifier.

    This class should not be instantiated by end-users directly.  Instead,
    instances should be retrieved from the appropriate attributes & methods of
    `RemoteDandiset`.
    """

    #: The version identifier
    identifier: str = Field(alias="version")
    #: The name of the version
    name: str
    #: The number of assets in the version
    asset_count: int
    #: The total size in bytes of all assets in the version
    size: int
    #: The timestamp at which the version was created
    created: datetime
    #: The timestamp at which the version was last modified
    modified: datetime
    status: VersionStatus

    def __str__(self) -> str:
        return self.identifier


class RemoteDandisetData(APIBase):
    """
    Class for storing the data for a Dandiset retrieved from the API.

    This class is an implementation detail and should not be used by third
    parties.
    """

    identifier: str
    created: datetime
    modified: datetime
    contact_person: str
    embargo_status: EmbargoStatus
    most_recent_published_version: Optional[Version]
    draft_version: Version


class RemoteDandiset:
    """
    Representation of a Dandiset (as of a certain version) retrieved from the
    API.

    Stringifying a `RemoteDandiset` returns a string of the form
    :samp:`"{server_id}:{dandiset_id}/{version_id}"`.

    This class should not be instantiated by end-users directly.  Instead,
    instances should be retrieved from the appropriate attributes & methods of
    `DandiAPIClient` and `RemoteDandiset`.
    """

    def __init__(
        self,
        client: DandiAPIClient,
        identifier: str,
        version: Union[str, Version, None] = None,
        data: Union[Dict[str, Any], RemoteDandisetData, None] = None,
    ) -> None:
        #: The `DandiAPIClient` instance that returned this `RemoteDandiset`
        #: and which the latter will use for API requests
        self.client: DandiAPIClient = client
        #: The Dandiset identifier
        self.identifier: str = identifier
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
        self._data: Optional[RemoteDandisetData]
        if data is not None:
            self._data = RemoteDandisetData.parse_obj(data)
        else:
            self._data = None

    def __str__(self) -> str:
        return f"{self.client._instance_id}:{self.identifier}/{self.version_id}"

    def _get_data(self) -> RemoteDandisetData:
        if self._data is None:
            try:
                self._data = RemoteDandisetData.parse_obj(
                    self.client.get(f"/dandisets/{self.identifier}/")
                )
            except HTTP404Error:
                raise NotFoundError(f"No such Dandiset: {self.identifier}")
        return self._data

    @property
    def version_id(self) -> str:
        """The identifier for the Dandiset version"""
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
                for v in [
                    self._data.most_recent_published_version,
                    self._data.draft_version,
                ]:
                    if v is not None and (
                        self._version_id is None or v.identifier == self.version_id
                    ):
                        self._version = v
                        self._version_id = v.identifier
                        return v
            assert self._version_id is not None
            self._version = self.get_version(self._version_id)
        return self._version

    @property
    def created(self) -> datetime:
        """The timestamp at which the Dandiset was created"""
        return self._get_data().created

    @property
    def modified(self) -> datetime:
        """The timestamp at which the Dandiset was last modified"""
        return self._get_data().modified

    @property
    def contact_person(self) -> str:
        """The name of the registered contact person for the Dandiset"""
        return self._get_data().contact_person

    @property
    def embargo_status(self) -> EmbargoStatus:
        """The current embargo status for the Dandiset"""
        return self._get_data().embargo_status

    @property
    def most_recent_published_version(self) -> Optional[Version]:
        """
        The most recent published (non-draft) version of the Dandiset, or
        `None` if no versions have been published
        """
        return self._get_data().most_recent_published_version

    @property
    def draft_version(self) -> Version:
        """The draft version of the Dandiset"""
        return self._get_data().draft_version

    @property
    def api_path(self) -> str:
        """
        The path (relative to the base endpoint for a Dandi Archive API) at
        which API requests for interacting with the Dandiset itself are made
        """
        return f"/dandisets/{self.identifier}/"

    @property
    def api_url(self) -> str:
        """
        The URL at which API requests for interacting with the Dandiset itself
        are made
        """
        return self.client.get_url(self.api_path)

    @property
    def version_api_path(self) -> str:
        """
        The path (relative to the base endpoint for a Dandi Archive API) at
        which API requests for interacting with the version in question of the
        Dandiset are made
        """
        return f"/dandisets/{self.identifier}/versions/{self.version_id}/"

    @property
    def version_api_url(self) -> str:
        """
        The URL at which API requests for interacting with the version in
        question of the Dandiset are made
        """
        return self.client.get_url(self.version_api_path)

    @classmethod
    def from_data(
        cls, client: "DandiAPIClient", data: Dict[str, Any]
    ) -> "RemoteDandiset":
        """
        Construct a `RemoteDandiset` instance from a `DandiAPIClient` and a
        `dict` of raw string fields in the same format as returned by the API.
        If the ``"most_recent_published_version"`` field is set, that is used
        as the Dandiset's version; otherwise, ``"draft_version"`` is used.

        This is a low-level method that non-developers would normally only use
        when acquiring data using means outside of this library.
        """
        if data.get("most_recent_published_version") is not None:
            version = Version.parse_obj(data["most_recent_published_version"])
        else:
            version = Version.parse_obj(data["draft_version"])
        return cls(
            client=client, identifier=data["identifier"], version=version, data=data
        )

    def json_dict(self) -> Dict[str, Any]:
        """
        Convert to a JSONable `dict`, omitting the ``client`` attribute and
        using the same field names as in the API
        """
        return {
            **self._get_data().json_dict(),
            "version": self.version.json_dict(),
        }

    def refresh(self) -> None:
        """
        Update the `RemoteDandiset` in-place with the latest data from the
        server.  The `RemoteDandiset` continues to have the same version as
        before, but the cached version data is internally cleared and may be
        different upon subsequent access.
        """
        self._data = None
        self._get_data()
        # Clear _version so it will be refetched the next time it is accessed
        self._version = None

    def get_versions(self, order: Optional[str] = None) -> Iterator[Version]:
        """
        Returns an iterator of all available `Version`\\s for the Dandiset

        Versions can be sorted by a given field by passing the name of that
        field as the ``order`` parameter.  Currently, the only accepted field
        name is ``"created"``.  Prepend a hyphen to the field name to reverse
        the sort order.
        """
        try:
            for v in self.client.paginate(
                f"{self.api_path}versions/", params={"order": order}
            ):
                yield Version.parse_obj(v)
        except HTTP404Error:
            raise NotFoundError(f"No such Dandiset: {self.identifier!r}")

    def get_version(self, version_id: str) -> Version:
        """
        Get information about a given version of the Dandiset.  If the given
        version does not exist, a `NotFoundError` is raised.
        """
        try:
            return Version.parse_obj(
                self.client.get(
                    f"/dandisets/{self.identifier}/versions/{version_id}/info"
                )
            )
        except HTTP404Error:
            raise NotFoundError(
                f"No such version: {version_id!r} of Dandiset {self.identifier}"
            )

    def for_version(self, version_id: Union[str, Version]) -> "RemoteDandiset":
        """
        Returns a copy of the `RemoteDandiset` with the `version` attribute set
        to the given `Version` object or the `Version` with the given version
        ID.  If a version ID given and the version does not exist, a
        `NotFoundError` is raised.
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
        instance's data attributes afterwards will result in a `NotFoundError`.
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
        try:
            return cast(Dict[str, Any], self.client.get(self.version_api_path))
        except HTTP404Error:
            raise NotFoundError(f"No such asset: {self}")

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

    def wait_until_valid(self, max_time: float = 120) -> None:
        """
        Wait at most ``max_time`` seconds for the Dandiset to be valid for
        publication.  If the Dandiset does not become valid in time, a
        `ValueError` is raised.
        """
        lgr.debug("Waiting for Dandiset %s to complete validation ...", self.identifier)
        start = time()
        while time() - start < max_time:
            try:
                r = self.client.get(f"{self.version_api_path}info/")
            except HTTP404Error:
                raise NotFoundError(
                    f"No such version: {self.version_id!r} of Dandiset {self.identifier}"
                )
            if "status" not in r:
                # Running against older version of dandi-api that doesn't
                # validate
                return
            if r["status"] == "Valid":
                return
            sleep(0.5)
        # TODO: Improve the presentation of the error messages
        about = {
            "asset_validation_errors": r.get("asset_validation_errors"),
            "version_validation_errors": r.get("version_validation_errors"),
        }
        raise ValueError(
            f"Dandiset {self.identifier} is {r['status']}: {json.dumps(about, indent=4)}"
        )

    def publish(self, max_time: float = 120) -> "RemoteDandiset":
        """
        Publish the draft version of the Dandiset and wait at most ``max_time``
        seconds for the publication operation to complete.  If the operation
        does not complete in time, a `ValueError` is raised.

        Returns a copy of the `RemoteDandiset` with the `version` attribute set
        to the new published `Version`.
        """
        draft_api_path = f"/dandisets/{self.identifier}/versions/draft/"
        self.client.post(f"{draft_api_path}publish/")
        lgr.debug(
            "Waiting for Dandiset %s to complete publication ...", self.identifier
        )
        start = time()
        while time() - start < max_time:
            v = Version.parse_obj(self.client.get(f"{draft_api_path}info/"))
            if v.status is VersionStatus.PUBLISHED:
                break
            sleep(0.5)
        else:
            raise ValueError(f"Dandiset {self.identifier} did not publish in time")
        for v in self.get_versions(order="-created"):
            return self.for_version(v)
        raise AssertionError(
            f"No published versions found for Dandiset {self.identifier}"
        )

    def get_assets(self, order: Optional[str] = None) -> Iterator["RemoteAsset"]:
        """
        Returns an iterator of all assets in this version of the Dandiset.

        Assets can be sorted by a given field by passing the name of that field
        as the ``order`` parameter.  The accepted field names are
        ``"created"``, ``"modified"``, and ``"path"``.  Prepend a hyphen to the
        field name to reverse the sort order.
        """
        try:
            for a in self.client.paginate(
                f"{self.version_api_path}assets/", params={"order": order}
            ):
                yield RemoteAsset.from_data(self, a)
        except HTTP404Error:
            raise NotFoundError(
                f"No such version: {self.version_id!r} of Dandiset {self.identifier}"
            )

    def get_asset(self, asset_id: str) -> "RemoteAsset":
        """
        Fetch the asset in this version of the Dandiset with the given asset
        ID.  If the given asset does not exist, a `NotFoundError` is raised.
        """
        try:
            info = self.client.get(f"{self.version_api_path}assets/{asset_id}/info/")
        except HTTP404Error:
            raise NotFoundError(f"No such asset: {asset_id!r} for {self}")
        metadata = info.pop("metadata", None)
        return RemoteAsset.from_data(self, info, metadata)

    def get_assets_with_path_prefix(
        self, path: str, order: Optional[str] = None
    ) -> Iterator["RemoteAsset"]:
        """
        Returns an iterator of all assets in this version of the Dandiset whose
        `~RemoteAsset.path` attributes start with ``path``

        Assets can be sorted by a given field by passing the name of that field
        as the ``order`` parameter.  The accepted field names are
        ``"created"``, ``"modified"``, and ``"path"``.  Prepend a hyphen to the
        field name to reverse the sort order.
        """
        try:
            for a in self.client.paginate(
                f"{self.version_api_path}assets/",
                params={"path": path, "order": order},
            ):
                yield RemoteAsset.from_data(self, a)
        except HTTP404Error:
            raise NotFoundError(
                f"No such version: {self.version_id!r} of Dandiset {self.identifier}"
            )

    def get_assets_by_glob(
        self, pattern: str, order: Optional[str] = None
    ) -> Iterator["RemoteAsset"]:
        """
        .. versionadded:: 0.44.0

        Returns an iterator of all assets in this version of the Dandiset whose
        `~RemoteAsset.path` attributes match the glob pattern ``pattern``

        Assets can be sorted by a given field by passing the name of that field
        as the ``order`` parameter.  The accepted field names are
        ``"created"``, ``"modified"``, and ``"path"``.  Prepend a hyphen to the
        field name to reverse the sort order.
        """
        try:
            for a in self.client.paginate(
                f"{self.version_api_path}assets/",
                params={"glob": pattern, "order": order},
            ):
                yield RemoteAsset.from_data(self, a)
        except HTTP404Error:
            raise NotFoundError(
                f"No such version: {self.version_id!r} of Dandiset {self.identifier}"
            )

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

        .. deprecated:: 0.36.0
            Use the ``upload()`` method of `~dandi.files.LocalAsset` instances
            instead

        :param filepath: the path to the local file to upload
        :type filepath: str or PathLike
        :param dict asset_metadata:
            Metadata for the uploaded asset file.  Must include a "path" field
            giving the forward-slash-separated path at which the uploaded file
            will be placed on the server.
        :param int jobs: Number of threads to use for uploading; defaults to 5
        :param RemoteAsset replace_asset: If set, replace the given asset,
            which must have the same path as the new asset
        """
        from .files import LocalAsset, dandi_file

        df = dandi_file(filepath)
        if not isinstance(df, LocalAsset):
            raise ValueError(f"{filepath}: not an asset file")
        return df.upload(
            self, metadata=asset_metadata, jobs=jobs, replacing=replace_asset
        )

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

        .. deprecated:: 0.36.0
            Use the ``iter_upload()`` method of `~dandi.files.LocalAsset`
            instances instead

        :param filepath: the path to the local file to upload
        :type filepath: str or PathLike
        :param dict asset_metadata:
            Metadata for the uploaded asset file.  Must include a "path" field
            giving the forward-slash-separated path at which the uploaded file
            will be placed on the server.
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
        from .files import LocalAsset, dandi_file

        df = dandi_file(filepath)
        if not isinstance(df, LocalAsset):
            raise ValueError(f"{filepath}: not an asset file")
        return df.iter_upload(
            self, metadata=asset_metadata, jobs=jobs, replacing=replace_asset
        )


class BaseRemoteAsset(ABC, APIBase):
    """
    Representation of an asset retrieved from the API without associated
    Dandiset information.

    This is an abstract class; its concrete subclasses are
    `BaseRemoteBlobAsset` (for assets backed by blobs) and
    `BaseRemoteZarrAsset` (for assets backed by Zarrs).

    Stringifying a `BaseRemoteAsset` returns a string of the form
    :samp:`"{server_id}:asset/{asset_id}"`.

    This class should not be instantiated by end-users directly.  Instead,
    instances should be retrieved from the appropriate methods of
    `DandiAPIClient`.
    """

    #: The `DandiAPIClient` instance that returned this `BaseRemoteAsset`
    #: and which the latter will use for API requests
    client: "DandiAPIClient"
    #: The asset identifier
    identifier: str = Field(alias="asset_id")
    #: The asset's (forward-slash-separated) path
    path: str
    #: The size of the asset in bytes
    size: int
    #: The date at which the asset was created
    created: datetime
    #: The date at which the asset was last modified
    modified: datetime
    #: Metadata supplied at initialization; returned when metadata is requested
    #: instead of performing an API call
    _metadata: Optional[Dict[str, Any]] = PrivateAttr(default_factory=None)

    def __init__(self, **data: Any) -> None:  # type: ignore[no-redef]
        super().__init__(**data)
        # Pydantic insists on not initializing any attributes that start with
        # underscores, so we have to do it ourselves.
        self._metadata = data.get("metadata", data.get("_metadata"))

    def __str__(self) -> str:
        return f"{self.client._instance_id}:assets/{self.identifier}"

    @classmethod
    def from_base_data(
        self,
        client: "DandiAPIClient",
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "BaseRemoteAsset":
        """
        Construct a `BaseRemoteAsset` instance from a `DandiAPIClient`, a
        `dict` of raw data in the same format as returned by the API's
        pagination endpoints, and optional raw asset metadata.

        This is a low-level method that non-developers would normally only use
        when acquiring data using means outside of this library.
        """
        klass: Type[BaseRemoteAsset]
        if data.get("blob") is not None:
            klass = BaseRemoteBlobAsset
            if data.pop("zarr", None) is not None:
                raise ValueError("Asset data contains both `blob` and `zarr`'")
        elif data.get("zarr") is not None:
            klass = BaseRemoteZarrAsset
            if data.pop("blob", None) is not None:
                raise ValueError("Asset data contains both `blob` and `zarr`'")
        else:
            raise ValueError("Asset data contains neither `blob` nor `zarr`")
        return klass(client=client, **data, _metadata=metadata)  # type: ignore[call-arg]

    @property
    def api_path(self) -> str:
        """
        The path (relative to the base endpoint for a Dandi Archive API) at
        which API requests for interacting with the asset itself are made
        """
        return f"/assets/{self.identifier}/"

    @property
    def api_url(self) -> str:
        """
        The URL at which API requests for interacting with the asset itself are
        made
        """
        return self.client.get_url(self.api_path)

    @property
    def base_download_url(self) -> str:
        """
        The URL from which the asset can be downloaded, sans any Dandiset
        identifiers (cf. `RemoteAsset.download_url`)
        """
        return self.client.get_url(f"/assets/{self.identifier}/download/")

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
            try:
                return cast(Dict[str, Any], self.client.get(self.api_path))
            except HTTP404Error:
                raise NotFoundError(f"No such asset: {self}")

    def get_raw_digest(
        self, digest_type: Union[str, models.DigestType, None] = None
    ) -> str:
        """
        Retrieves the value of the given type of digest from the asset's
        metadata.  Raises `NotFoundError` if there is no entry for the given
        digest type.

        If no digest type is specified, the same type as used by `get_digest()`
        is returned.

        .. versionchanged:: 0.36.0
            Renamed from ``get_digest()`` to ``get_raw_digest()``
        """
        if digest_type is None:
            digest_type = self.digest_type.value
        elif isinstance(digest_type, models.DigestType):
            digest_type = digest_type.value
        metadata = self.get_raw_metadata()
        try:
            return cast(str, metadata["digest"][digest_type])
        except KeyError:
            raise NotFoundError(f"No {digest_type} digest found in metadata")

    def get_digest(self) -> Digest:
        """
        .. versionadded:: 0.36.0
            Replaces the previous version of ``get_digest()``, now renamed to
            `get_raw_digest()`

        Retrieves the DANDI etag digest of the appropriate type for the asset:
        a dandi-etag digest for blob resources or a dandi-zarr-checksum for
        Zarr resources
        """
        algorithm = self.digest_type
        return Digest(algorithm=algorithm, value=self.get_raw_digest(algorithm))

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
        url: str
        for url in self.get_raw_metadata().get("contentUrl", []):
            if re.search(regex, url):
                break
        else:
            raise NotFoundError(
                "No matching URL found in asset's contentUrl metadata field"
            )
        try:
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
        except requests.HTTPError as e:
            url = e.request.url
        if strip_query:
            url = urlunparse(urlparse(url)._replace(query=""))
        return url

    def get_download_file_iter(
        self, chunk_size: int = MAX_CHUNK_SIZE
    ) -> Callable[[int], Iterator[bytes]]:
        """
        Returns a function that when called (optionally with an offset into the
        asset to start downloading at) returns a generator of chunks of the
        asset.

        :raises ValueError: if the asset is not backed by a blob
        """
        if self.asset_type is not AssetType.BLOB:
            raise ValueError(
                f"Cannot download asset {self} directly: asset is of type"
                f" {self.asset_type.name}, not BLOB"
            )

        url = self.base_download_url

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

        :raises ValueError: if the asset is not backed by a blob
        """
        downloader = self.get_download_file_iter(chunk_size=chunk_size)
        with open(filepath, "wb") as fp:
            for chunk in downloader(0):
                fp.write(chunk)

    @property
    @abstractmethod
    def asset_type(self) -> AssetType:
        """
        .. versionadded:: 0.36.0

        The type of the asset's underlying data
        """
        ...

    @property
    def digest_type(self) -> models.DigestType:
        """
        .. versionadded:: 0.36.0

        The primary digest algorithm used by Dandi Archive for the asset,
        determined based on its underlying data: dandi-etag for blob resources,
        dandi-zarr-checksum for Zarr resources
        """
        if self.asset_type is AssetType.ZARR:
            return models.DigestType.dandi_zarr_checksum
        else:
            return models.DigestType.dandi_etag


class BaseRemoteBlobAsset(BaseRemoteAsset):
    """
    .. versionadded:: 0.36.0

    A `BaseRemoteAsset` whose actual data is a blob resource
    """

    #: The ID of the underlying blob resource
    blob: str

    @property
    def asset_type(self) -> AssetType:
        """
        .. versionadded:: 0.36.0

        The type of the asset's underlying data
        """
        return AssetType.BLOB


class BaseRemoteZarrAsset(BaseRemoteAsset):
    """
    .. versionadded:: 0.36.0

    A `BaseRemoteAsset` whose actual data is a Zarr resource
    """

    #: The ID of the underlying Zarr resource
    zarr: str

    @property
    def asset_type(self) -> AssetType:
        """
        .. versionadded:: 0.36.0

        The type of the asset's underlying data
        """
        return AssetType.ZARR

    @property
    def filetree(self) -> "RemoteZarrEntry":
        """
        The `RemoteZarrEntry` for the root of the hierarchy of files within the
        Zarr
        """
        return RemoteZarrEntry(
            client=self.client, zarr_id=self.zarr, parts=(), _known_dir=True
        )

    def iterfiles(self, include_dirs: bool = False) -> Iterator["RemoteZarrEntry"]:
        """
        Returns a generator of all `RemoteZarrEntry`\\s within the Zarr.  By
        default, only instances for files are produced, unless ``include_dirs``
        is true.
        """
        return self.filetree.iterfiles(include_dirs=include_dirs)

    def rmfiles(
        self, files: Iterable["RemoteZarrEntry"], reingest: bool = True
    ) -> None:
        """
        Delete one or more files from the Zarr.

        If ``reingest`` is true, after performing the deletion, the client
        triggers a recalculation of the Zarr's checksum and waits for it to
        complete.
        """
        # Don't bother checking that the entries are actually files or even
        # belong to this Zarr, as if they're not, the server will return an
        # error anyway.
        for entries in chunked(files, ZARR_DELETE_BATCH_SIZE):
            self.client.delete(
                f"/zarr/{self.zarr}/files/",
                json=[{"path": str(e)} for e in entries],
            )
        if reingest:
            self.client.post(f"/zarr/{self.zarr}/ingest/")
            while True:
                sleep(2)
                r = self.client.get(f"/zarr/{self.zarr}/")
                if r["status"] == "Complete":
                    break


class RemoteAsset(BaseRemoteAsset):
    """
    Subclass of `BaseRemoteAsset` that includes information about the Dandiset
    to which the asset belongs.

    This is an abstract class; its concrete subclasses are `RemoteBlobAsset`
    (for assets backed by blobs) and `RemoteZarrAsset` (for assets backed by
    Zarrs).

    This class should not be instantiated by end-users directly.  Instead,
    instances should be retrieved from the appropriate attributes & methods of
    `RemoteDandiset`.
    """

    JSON_EXCLUDE = frozenset(["client", "dandiset_id", "version_id"])

    #: The identifier for the Dandiset to which the asset belongs
    dandiset_id: str
    #: The identifier for the version of the Dandiset to which the asset
    #: belongs
    version_id: str

    @classmethod
    def from_data(
        cls,
        dandiset: RemoteDandiset,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "RemoteAsset":
        """
        Construct a `RemoteAsset` instance from a `RemoteDandiset`, a `dict` of
        raw data in the same format as returned by the API's pagination
        endpoints, and optional raw asset metadata.

        This is a low-level method that non-developers would normally only use
        when acquiring data using means outside of this library.
        """
        klass: Type[RemoteAsset]
        if data.get("blob") is not None:
            klass = RemoteBlobAsset
            if data.pop("zarr", None) is not None:
                raise ValueError("Asset data contains both `blob` and `zarr`'")
        elif data.get("zarr") is not None:
            klass = RemoteZarrAsset
            if data.pop("blob", None) is not None:
                raise ValueError("Asset data contains both `blob` and `zarr`'")
        else:
            raise ValueError("Asset data contains neither `blob` nor `zarr`")
        return klass(  # type: ignore[call-arg]
            client=dandiset.client,
            dandiset_id=dandiset.identifier,
            version_id=dandiset.version_id,
            **data,
            _metadata=metadata,
        )

    @property
    def api_path(self) -> str:
        """
        The path (relative to the base endpoint for a Dandi Archive API) at
        which API requests for interacting with the asset itself are made
        """
        return f"/dandisets/{self.dandiset_id}/versions/{self.version_id}/assets/{self.identifier}/"

    @property
    def api_url(self) -> str:
        """
        The URL at which API requests for interacting with the asset itself are
        made
        """
        return self.client.get_url(self.api_path)

    @property
    def download_url(self) -> str:
        """
        The URL from which the asset can be downloaded, including Dandiset
        identifiers (cf. `BaseRemoteAsset.base_download_url`)
        """
        return self.client.get_url(f"{self.api_path}download/")

    def set_metadata(self, metadata: models.Asset) -> None:
        """
        Set the metadata for the asset to the given value and update the
        `RemoteAsset` in place.
        """
        return self.set_raw_metadata(metadata.json_dict())

    @abstractmethod
    def set_raw_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Set the metadata for the asset on the server to the given value and
        update the `RemoteAsset` in place.
        """
        ...

    def rename(self, dest: str) -> None:
        """
        .. versionadded:: 0.41.0

        Change the path of the asset on the server to the given value and
        update the `RemoteAsset` in place.  If another asset already exists at
        the given path, a `requests.HTTPError` is raised.
        """
        md = self.get_raw_metadata().copy()
        md["path"] = dest
        self.set_raw_metadata(md)

    def delete(self) -> None:
        """Delete the asset"""
        self.client.delete(self.api_path)


class RemoteBlobAsset(RemoteAsset, BaseRemoteBlobAsset):
    """
    .. versionadded:: 0.36.0

    A `RemoteAsset` whose actual data is a blob resource
    """

    def set_raw_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Set the metadata for the asset on the server to the given value and
        update the `RemoteBlobAsset` in place.
        """
        data = self.client.put(
            self.api_path, json={"metadata": metadata, "blob_id": self.blob}
        )
        self.identifier = data["asset_id"]
        self.path = data["path"]
        self.size = int(data["size"])
        self.created = ensure_datetime(data["created"])
        self.modified = ensure_datetime(data["modified"])
        self._metadata = data["metadata"]


class RemoteZarrAsset(RemoteAsset, BaseRemoteZarrAsset):
    """
    .. versionadded:: 0.36.0

    A `RemoteAsset` whose actual data is a Zarr resource
    """

    def set_raw_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Set the metadata for the asset on the server to the given value and
        update the `RemoteZarrAsset` in place.
        """
        data = self.client.put(
            self.api_path, json={"metadata": metadata, "zarr_id": self.zarr}
        )
        self.identifier = data["asset_id"]
        self.path = data["path"]
        self.size = int(data["size"])
        self.created = ensure_datetime(data["created"])
        self.modified = ensure_datetime(data["modified"])
        self._metadata = data["metadata"]


class ZarrListing(BaseModel):
    """
    .. versionadded:: 0.36.0

    Information about a directory within a `RemoteZarrAsset`
    """

    #: API URLs for the listings of the directory's subdirectories
    directories: List[AnyHttpUrl]
    #: API URLs for downloading the files in the directory
    files: List[AnyHttpUrl]
    #: The checksums (MD5 or Dandi Zarr checksum, as appropriate) for the
    #: directory's entries, as a mapping from basenames to checksums
    checksums: Dict[str, str]
    #: The Dandi Zarr checksum for the directory
    checksum: str

    @property
    def dirnames(self) -> List[str]:
        """The basenames of the directory URLs in `directories`"""
        return [PurePosixPath(unquote(url.path or "")).name for url in self.directories]

    @property
    def filenames(self) -> List[str]:
        """The basenames of the file URLs in `files`"""
        return [PurePosixPath(unquote(url.path or "")).name for url in self.files]


@dataclass
class ZarrEntryStat:
    """
    .. versionadded:: 0.36.0

    Combined size & timestamp information for a file in a `RemoteZarrAsset`
    """

    #: The size of the file
    size: int
    #: The time at which the file was last modified
    modified: datetime


@dataclass
class RemoteZarrEntry(BasePath):
    """
    .. versionadded:: 0.36.0

    A file or directory within a `RemoteZarrAsset`.  Implements
    `~dandi.misctypes.BasePath`.
    """

    #: The `DandiAPIClient` instance used for API requests
    client: DandiAPIClient
    #: The ID of the Zarr backing the asset
    zarr_id: str
    _known_dir: Optional[bool] = field(default=None, compare=False, repr=False)
    _digest: Optional[Digest] = field(default=None, compare=False, repr=False)

    def _get_subpath(
        self, name: str, isdir: Optional[bool] = None, checksum: Optional[str] = None
    ) -> "RemoteZarrEntry":
        if not name or "/" in name:
            raise ValueError(f"Invalid path component: {name!r}")
        elif name == ".":
            return self
        elif name == "..":
            return self.parent
        else:
            if checksum is not None and isdir is not None:
                if isdir:
                    algorithm = models.DigestType.dandi_zarr_checksum
                else:
                    algorithm = models.DigestType.md5
                digest = Digest(algorithm=algorithm, value=checksum)
            else:
                digest = None
            return replace(
                self, parts=self.parts + (name,), _known_dir=isdir, _digest=digest
            )

    @property
    def parent(self) -> "RemoteZarrEntry":
        if self.is_root():
            return self
        else:
            return replace(
                self,
                parts=self.parts[:-1],
                _known_dir=True if self._known_dir is not None else None,
                _digest=None,
            )

    def _isdir(self) -> bool:
        if self._known_dir is not None:
            return self._known_dir
        elif self.is_root():
            try:
                self.client.get(f"/zarr/{self.zarr_id}/")
            except HTTP404Error:
                raise NotFoundError(f"No such Zarr: {self.zarr_id!r}")
            return True
        else:
            listing = self.parent.get_listing()
            if self.name in listing.dirnames:
                return True
            elif self.name in listing.filenames:
                return False
            else:
                raise NotFoundError(
                    f"No such entry {str(self)!r} in Zarr {self.zarr_id!r}"
                )

    def exists(self) -> bool:
        try:
            self._isdir()
        except NotFoundError:
            return False
        else:
            return True

    def is_file(self) -> bool:
        try:
            return not self._isdir()
        except NotFoundError:
            return False

    def is_dir(self) -> bool:
        try:
            return self._isdir()
        except NotFoundError:
            return False

    def iterdir(self) -> Iterator["RemoteZarrEntry"]:
        listing = self.get_listing()
        for name in listing.dirnames:
            if name == "." or name == "..":
                continue
            yield self._get_subpath(name, isdir=True, checksum=listing.checksums[name])
        for name in listing.filenames:
            yield self._get_subpath(name, isdir=False, checksum=listing.checksums[name])

    def get_digest(self) -> Digest:
        """
        Retrieve the DANDI etag digest for the entry.  If the entry is a
        directory, the algorithm will be the Dandi Zarr checksum algorithm; if
        it is a file, it will be MD5.

        :raises NotFoundError: if the path does not exist in the Zarr asset
        """
        if self._digest is not None:
            # `self` was returned by `parent.iterdir()`, which iterated over a
            # ZarrListing and thus had access to the checksum, which it stored
            # on `self`; use that value.
            return self._digest
        if self.is_root():
            algorithm = models.DigestType.dandi_zarr_checksum
            value = self.get_listing().checksum
        else:
            listing = self.parent.get_listing()
            if self.name in listing.dirnames:
                algorithm = models.DigestType.dandi_zarr_checksum
            elif self.name in listing.filenames:
                algorithm = models.DigestType.md5
            else:
                raise NotFoundError(
                    f"No such entry {str(self)!r} in Zarr {self.zarr_id!r}"
                )
            value = listing.checksums[self.name]
        return Digest(algorithm=algorithm, value=value)

    @property
    def size(self) -> int:
        """
        The size of the entry, which must be a file

        :raises NotFoundError: if the path does not exist in the Zarr asset
        :raises ValueError: if the path is a directory
        """
        return self.stat().size

    @property
    def modified(self) -> datetime:
        """
        The time at which the entry (which must be a file) was last modified

        :raises NotFoundError: if the path does not exist in the Zarr asset
        :raises ValueError: if the path is a directory
        """
        return self.stat().modified

    def stat(self) -> ZarrEntryStat:
        """
        Return combined size & timestamp information for the entry, which must
        be a file

        :raises NotFoundError: if the path does not exist in the Zarr asset
        :raises ValueError: if the path is a directory
        """
        if not self.is_file():
            raise ValueError("Cannot stat directories in Zarrs")
        try:
            r = self.client.request(
                "HEAD",
                f"/zarr/{self.zarr_id}.zarr/{'/'.join(self.parts)}",
                json_resp=False,
                allow_redirects=True,
            )
        except HTTP404Error:
            raise NotFoundError(
                f"{str(self)!r} in Zarr {self.zarr_id!r} does not exist"
            )
        return ZarrEntryStat(
            size=int(r.headers["Content-Length"]),
            modified=dateutil.parser.parse(r.headers["Last-Modified"]),
        )

    def get_listing(self) -> ZarrListing:
        """
        Return the `ZarrListing` for the entry, which must be a directory

        :raises NotFoundError:
            if the path does not exist in the Zarr asset or is not a directory
        """
        path = "".join(p + "/" for p in self.parts)
        try:
            r = self.client.get(f"/zarr/{self.zarr_id}.zarr/{path}")
        except HTTP404Error:
            raise NotFoundError(
                f"{str(self)!r} in Zarr {self.zarr_id!r} does not exist or is"
                " not a directory"
            )
        return ZarrListing.parse_obj(r)

    def get_download_file_iter(
        self, chunk_size: int = MAX_CHUNK_SIZE
    ) -> Callable[[int], Iterator[bytes]]:
        """
        Returns a function that when called (optionally with an offset into the
        file to start downloading at) returns a generator of chunks of the file
        """
        if not self.is_file():
            raise RuntimeError(
                f"{str(self)!r} in Zarr {self.zarr_id!r} does not exist or"
                " is not a file"
            )

        url = self.client.get_url(f"/zarr/{self.zarr_id}.zarr/{'/'.join(self.parts)}")

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
            lgr.info("File %s in Zarr %s successfully downloaded", self, self.zarr_id)

        return downloader

    def iterfiles(self, include_dirs: bool = False) -> Iterator["RemoteZarrEntry"]:
        """
        Returns a generator of all `RemoteZarrEntry`\\s under the directory.
        By default, only instances for files are produced, unless
        ``include_dirs`` is true.
        """
        dirs = deque([self])
        while dirs:
            d = dirs.popleft()
            try:
                subpaths = list(d.iterdir())
            except NotFoundError:
                if d.is_root():
                    # Empty zarr; can happen if an upload is interrupted during
                    # the initial batch
                    return
                else:
                    raise
            for p in subpaths:
                if p.is_dir():
                    dirs.append(p)
                    if include_dirs:
                        yield p
                else:
                    yield p

    def clear_cache(self) -> None:
        """Delete any locally-cached data about the entry"""
        self._known_dir = None
        self._digest = None
