"""
Registry of dandi-archive features which dandi-cli uses only where the server
supports them.

dandi-cli talks to several independently deployed dandi-archive instances (see
`dandi.consts.known_instances`), which gain new features at different times.
Each such feature is registered in `SERVER_FEATURES` as a `ServerFeature` under
a short uppercase CODENAME, and code using it asks the client whether its
server supports it::

    if client.server_features.supports("BULK_DELETE"):
        ...  # use the new endpoint
    else:
        ...  # prior implementation

so that all such conditionals can be found, reviewed, and removed once all
known instances support the feature.  Setting
:envvar:`DANDI_DEVEL_DISABLE_SERVER_FEATURES` to a comma-separated list of
CODENAMEs makes dandi-cli use the prior implementation even where the server
supports the feature.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import os
import posixpath
import threading
from typing import TYPE_CHECKING, Literal

from packaging.version import InvalidVersion, Version
import requests

from . import get_logger

if TYPE_CHECKING:
    from .dandiapi import DandiAPIClient

lgr = get_logger()

#: Environment variable listing (comma- or space-separated) CODENAMEs of server
#: features not to use, even where the server supports them
DISABLE_ENV_VAR = "DANDI_DEVEL_DISABLE_SERVER_FEATURES"

#: Timeout (in seconds) for each request probing a server for a feature
PROBE_TIMEOUT = 30


@dataclass(frozen=True)
class ServerFeature:
    """A dandi-archive feature which dandi-cli uses only where supported"""

    #: Short uppercase identifier of the feature, e.g. ``"BULK_DELETE"``
    codename: str
    #: What the feature is, and what dandi-cli does without it
    description: str
    #: URLs of the dandi-archive (and dandi-cli) issues and pull requests
    #: about the feature
    refs: tuple[str, ...]
    #: Function telling whether the server of the given client supports the
    #: feature.  It must not modify anything on the server.  It is called at
    #: most once per client, and only if the server's version does not decide.
    sense: Callable[[DandiAPIClient], bool]
    #: The dandi-archive release on top of which the feature was developed:
    #: servers reporting this or an earlier release do not support it
    base_version: str | None = None
    #: The dandi-archive release which added the feature, once known: servers
    #: reporting an earlier release do not support it, and servers reporting
    #: this or a later release do
    released_version: str | None = None


@dataclass(frozen=True)
class FeatureSupport:
    """Whether a server supports a `ServerFeature`, and how that was decided"""

    #: Whether dandi-cli should use the feature with the server
    supported: bool
    #: How ``supported`` was decided: by :envvar:`DANDI_DEVEL_DISABLE_SERVER_FEATURES`,
    #: by the server's release version, by the feature's ``sense`` function, or
    #: by `ServerFeatures.record()`
    how: Literal["disabled", "version", "sensed", "recorded"]


def _has_allowed_schema_versions(client: DandiAPIClient) -> bool:
    return "allowed_schema_versions" in client.server_info


def _content_type(r: requests.Response) -> str:
    return r.headers.get("Content-Type", "").partition(";")[0].strip().lower()


def routes_endpoint(client: DandiAPIClient, path: str) -> bool:
    """
    Tell whether the server of ``client`` routes the API endpoint ``path``,
    without any side effects.

    Sends an ``OPTIONS`` request for ``path`` and for a sibling path which no
    server routes, and compares the responses: a server without the endpoint
    answers both the same way (with Django's HTML "Not Found" page), whereas an
    endpoint answers in JSON, e.g. with its description (200) or with 401 if
    the server requires authentication.  Rate limiting, server errors, and
    connection errors count as the server not routing ``path``.
    """
    control = posixpath.join(
        posixpath.dirname(path.rstrip("/")), "dandi-cli-nonexistent-endpoint/"
    )
    try:
        target_r, control_r = (
            client.session.options(client.get_url(p), timeout=PROBE_TIMEOUT)
            for p in (path, control)
        )
    except requests.RequestException as e:
        lgr.debug("%s: could not probe %s: %s", client.api_url, path, e)
        return False
    for r in (target_r, control_r):
        if r.status_code == 429 or r.status_code >= 500:
            lgr.debug(
                "%s: could not probe %s: %s returned %d",
                client.api_url,
                path,
                r.url,
                r.status_code,
            )
            return False
    return (target_r.status_code, _content_type(target_r)) != (
        control_r.status_code,
        _content_type(control_r),
    )


def _routes_bulk_delete(client: DandiAPIClient) -> bool:
    # Routing does not depend on the Dandiset or version existing
    return routes_endpoint(
        client, "/dandisets/000000/versions/draft/assets/bulk-delete/"
    )


#: The registered server features, by CODENAME
SERVER_FEATURES: dict[str, ServerFeature] = {
    f.codename: f
    for f in [
        ServerFeature(
            codename="ALLOWED_SCHEMA_VERSIONS",
            description=(
                "``/api/info/`` lists, as ``allowed_schema_versions``, the"
                " schema versions the server accepts in metadata.  Without it,"
                " `DandiAPIClient.check_schema_version()` uses"
                " ``dandischema.consts.ALLOWED_INPUT_SCHEMAS`` of the installed"
                " dandischema instead."
            ),
            refs=(
                "https://github.com/dandi/dandi-archive/issues/2624",
                "https://github.com/dandi/dandi-archive/pull/2625",
                "https://github.com/dandi/dandi-cli/pull/1732",
            ),
            sense=_has_allowed_schema_versions,
            released_version="0.19.0",
        ),
        ServerFeature(
            codename="BULK_DELETE",
            description=(
                "``POST /dandisets/{id}/versions/{version}/assets/bulk-delete/``"
                " removes many assets from a version in one request.  Not used"
                " yet; without it, assets are deleted one request per asset."
            ),
            refs=(
                "https://github.com/dandi/dandi-archive/pull/2920",
                "https://github.com/dandi/dandi-cli/pull/1960",
            ),
            sense=_routes_bulk_delete,
            base_version="1.0.19",
        ),
    ]
}


def disabled_features() -> frozenset[str]:
    """
    Return the CODENAMEs listed in :envvar:`DANDI_DEVEL_DISABLE_SERVER_FEATURES`,
    warning about any which are not registered
    """
    names = set(os.environ.get(DISABLE_ENV_VAR, "").replace(",", " ").upper().split())
    if unknown := names - SERVER_FEATURES.keys():
        lgr.warning(
            "%s lists unknown server features, which are ignored: %s (known: %s)",
            DISABLE_ENV_VAR,
            ", ".join(sorted(unknown)),
            ", ".join(sorted(SERVER_FEATURES)),
        )
    return frozenset(names & SERVER_FEATURES.keys())


class ServerFeatures:
    """
    Which `ServerFeature`\\s the server of a `~dandi.dandiapi.DandiAPIClient`
    supports, as available from its
    `~dandi.dandiapi.DandiAPIClient.server_features` attribute.  Support for
    each feature is decided when first asked about, and remembered.
    """

    def __init__(
        self, client: DandiAPIClient, disabled: Iterable[str] | None = None
    ) -> None:
        """
        :param client: the client whose server to ask
        :param disabled: CODENAMEs of features not to use; defaults to those
            listed in :envvar:`DANDI_DEVEL_DISABLE_SERVER_FEATURES`
        """
        self._client = client
        self._disabled = (
            disabled_features() if disabled is None else frozenset(disabled)
        )
        self._support: dict[str, FeatureSupport] = {}
        self._lock = threading.Lock()

    def supports(self, codename: str) -> bool:
        """
        Whether dandi-cli should use the feature ``codename`` with the server:
        the server supports it, and it is not disabled
        """
        return self.resolve(codename).supported

    def resolve(self, codename: str) -> FeatureSupport:
        """Like `supports()`, but also tell how support was decided"""
        feature = self._get_feature(codename)
        with self._lock:
            if (support := self._support.get(codename)) is None:
                support = self._support[codename] = self._decide(feature)
                lgr.debug(
                    "%s: server feature %s is %s (%s)",
                    self._client.api_url,
                    codename,
                    "supported" if support.supported else "not supported",
                    support.how,
                )
        return support

    def record(self, codename: str, supported: bool) -> None:
        """
        Record whether the server supports the feature ``codename``, as found
        out by using it, e.g., when an endpoint that the server was expected to
        have turns out to be missing.  Has no effect on a disabled feature.
        """
        self._get_feature(codename)
        if codename in self._disabled:
            return
        with self._lock:
            self._support[codename] = FeatureSupport(supported, "recorded")
        lgr.debug(
            "%s: recorded server feature %s as %s",
            self._client.api_url,
            codename,
            "supported" if supported else "not supported",
        )

    @staticmethod
    def _get_feature(codename: str) -> ServerFeature:
        try:
            return SERVER_FEATURES[codename]
        except KeyError:
            raise ValueError(f"Unknown server feature: {codename!r}") from None

    def _decide(self, feature: ServerFeature) -> FeatureSupport:
        if feature.codename in self._disabled:
            return FeatureSupport(False, "disabled")
        if (version := self._release_version()) is not None:
            if feature.released_version is not None:
                return FeatureSupport(
                    version >= Version(feature.released_version), "version"
                )
            if feature.base_version is not None and version <= Version(
                feature.base_version
            ):
                return FeatureSupport(False, "version")
        return FeatureSupport(feature.sense(self._client), "sensed")

    def _release_version(self) -> Version | None:
        """
        The dandi-archive release the server reports being, or `None` if it
        reports something else, such as a development version (e.g., of a
        sandbox instance) or the version of a fork, which cannot be compared
        with dandi-archive releases
        """
        try:
            version = Version(str(self._client.server_info.get("version")))
        except InvalidVersion:
            return None
        if version.is_prerelease or version.is_postrelease or version.local is not None:
            return None
        return version
