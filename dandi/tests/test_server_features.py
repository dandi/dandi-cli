from __future__ import annotations

from collections.abc import Iterator
import logging
import os
import re
from typing import Any
from unittest.mock import Mock

import dandischema.consts
from packaging.version import Version
import pytest
from pytest_mock import MockerFixture
import requests
import responses

from .fixtures import DandiAPI
from .. import server_features
from ..consts import known_instances
from ..dandiapi import DandiAPIClient
from ..exceptions import SchemaVersionError
from ..server_features import (
    DISABLE_ENV_VAR,
    SERVER_FEATURES,
    FeatureSupport,
    ServerFeature,
    ServerFeatures,
    routes_endpoint,
)

API_URL = "https://test.nil/api"


def _mock_server_info(**fields: Any) -> None:
    """
    Mock the ``/server-info`` and ``/api/info/`` responses of a test server;
    ``fields`` override those of the latter, a value of `None` removing the
    field
    """
    info = {
        "schema_version": "0.7.0",
        "version": "1.1.0",
        "services": {"api": {"url": API_URL}},
        "cli-minimal-version": "0.0.0",
        "cli-bad-versions": [],
    }
    responses.add(responses.GET, "https://test.nil/server-info", json=info)
    info.update(fields)
    info = {k: v for k, v in info.items() if v is not None}
    responses.add(responses.GET, f"{API_URL}/info/", json=info)


@pytest.fixture
def sensers(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> dict[str, Mock]:
    """
    Replace the registry with features ``TEST_FEATURE`` and ``OTHER_FEATURE``,
    both sensed as supported, and return their (mock) ``sense`` functions
    """
    sensers = {
        codename: mocker.Mock(return_value=True)
        for codename in ("TEST_FEATURE", "OTHER_FEATURE")
    }
    monkeypatch.setattr(
        server_features,
        "SERVER_FEATURES",
        {
            codename: _test_feature(codename, sense)
            for codename, sense in sensers.items()
        },
    )
    monkeypatch.delenv(DISABLE_ENV_VAR, raising=False)
    return sensers


def _test_feature(
    codename: str,
    sense: Mock,
    base_version: str | None = "1.0.19",
    released_version: str | None = None,
) -> ServerFeature:
    return ServerFeature(
        codename=codename,
        description="A feature for tests",
        refs=("https://github.com/dandi/dandi-archive/pull/0",),
        sense=sense,
        base_version=base_version,
        released_version=released_version,
    )


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "server_version,base_version,released_version,expected",
    [
        # A release decides if the feature's release is known
        ("1.1.0", None, "1.1.0", FeatureSupport(True, "version")),
        ("1.2.3", "1.0.19", "1.1.0", FeatureSupport(True, "version")),
        ("1.0.19", "1.0.19", "1.1.0", FeatureSupport(False, "version")),
        ("1.0.20", "1.0.19", "1.1.0", FeatureSupport(False, "version")),
        # ... or if it is not newer than the release the feature was based on
        ("1.0.19", "1.0.19", None, FeatureSupport(False, "version")),
        ("0.23.0", "1.0.19", None, FeatureSupport(False, "version")),
        ("1.1.0", "1.0.19", None, FeatureSupport(True, "sensed")),
        ("1.1.0", None, None, FeatureSupport(True, "sensed")),
        # Anything but a release is sensed
        ("1.1.1.dev3+g1234567", "1.0.19", "1.1.0", FeatureSupport(True, "sensed")),
        ("1.0.19.dev3+g1234567", "1.0.19", "1.1.0", FeatureSupport(True, "sensed")),
        ("1.1.0rc1", "1.0.19", "1.1.0", FeatureSupport(True, "sensed")),
        # LINC as of 2026-10
        ("0.0.post6586+g39387b8", "1.0.19", "1.1.0", FeatureSupport(True, "sensed")),
        ("0+unknown", "1.0.19", "1.1.0", FeatureSupport(True, "sensed")),
        ("not a version", "1.0.19", "1.1.0", FeatureSupport(True, "sensed")),
        (None, "1.0.19", "1.1.0", FeatureSupport(True, "sensed")),
    ],
)
@responses.activate
def test_resolve_by_version_or_sensing(
    monkeypatch: pytest.MonkeyPatch,
    sensers: dict[str, Mock],
    server_version: str | None,
    base_version: str | None,
    released_version: str | None,
    expected: FeatureSupport,
) -> None:
    sense = sensers["TEST_FEATURE"]
    monkeypatch.setitem(
        server_features.SERVER_FEATURES,
        "TEST_FEATURE",
        _test_feature("TEST_FEATURE", sense, base_version, released_version),
    )
    _mock_server_info(version=server_version)
    client = DandiAPIClient(API_URL)
    assert client.server_features.resolve("TEST_FEATURE") == expected
    assert client.server_features.supports("TEST_FEATURE") is expected.supported
    if expected.how == "sensed":
        sense.assert_called_once_with(client)
    else:
        sense.assert_not_called()


@pytest.mark.ai_generated
@responses.activate
def test_sensed_once_per_client(sensers: dict[str, Mock]) -> None:
    _mock_server_info(version="1.1.1.dev3+g1234567")
    client = DandiAPIClient(API_URL)
    for _ in range(3):
        assert client.server_features.supports("TEST_FEATURE")
    sensers["TEST_FEATURE"].assert_called_once_with(client)
    # A new client senses again
    assert DandiAPIClient(API_URL).server_features.supports("TEST_FEATURE")
    assert sensers["TEST_FEATURE"].call_count == 2


@pytest.mark.ai_generated
@responses.activate
def test_disabled_by_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    sensers: dict[str, Mock],
) -> None:
    monkeypatch.setenv(DISABLE_ENV_VAR, "test_feature, NO_SUCH_FEATURE")
    _mock_server_info(version="1.2.0")
    with caplog.at_level(logging.WARNING, logger="dandi"):
        client = DandiAPIClient(API_URL)
        assert client.server_features.resolve("TEST_FEATURE") == FeatureSupport(
            False, "disabled"
        )
    assert any(
        DISABLE_ENV_VAR in r.getMessage() and "NO_SUCH_FEATURE" in r.getMessage()
        for r in caplog.records
    )
    sensers["TEST_FEATURE"].assert_not_called()
    # Other features are not affected
    assert client.server_features.resolve("OTHER_FEATURE") == FeatureSupport(
        True, "sensed"
    )
    # Recording support does not enable a disabled feature
    client.server_features.record("TEST_FEATURE", True)
    assert not client.server_features.supports("TEST_FEATURE")
    # An explicit list of disabled features overrides the environment variable
    assert ServerFeatures(client, disabled=()).supports("TEST_FEATURE")


@pytest.mark.ai_generated
@responses.activate
def test_record(sensers: dict[str, Mock]) -> None:
    _mock_server_info(version="1.1.1.dev3+g1234567")
    client = DandiAPIClient(API_URL)
    assert client.server_features.supports("TEST_FEATURE")
    client.server_features.record("TEST_FEATURE", False)
    assert client.server_features.resolve("TEST_FEATURE") == FeatureSupport(
        False, "recorded"
    )
    # Recording before first use spares sensing
    client.server_features.record("OTHER_FEATURE", False)
    assert not client.server_features.supports("OTHER_FEATURE")
    sensers["OTHER_FEATURE"].assert_not_called()


@pytest.mark.ai_generated
@responses.activate
def test_unknown_feature(sensers: dict[str, Mock]) -> None:
    _mock_server_info()
    client = DandiAPIClient(API_URL)
    with pytest.raises(ValueError, match="NO_SUCH_FEATURE"):
        client.server_features.supports("NO_SUCH_FEATURE")
    with pytest.raises(ValueError, match="NO_SUCH_FEATURE"):
        client.server_features.record("NO_SUCH_FEATURE", True)


_DJANGO_404: dict[str, Any] = {
    "status": 404,
    "content_type": "text/html; charset=utf-8",
    "body": "<h1>Not Found</h1>",
}


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "target,expected",
    [
        # An endpoint of a public server describes itself
        ({"status": 200, "json": {"name": "Bulk Delete"}}, True),
        # ... or asks for authentication (e.g., LINC)
        ({"status": 401, "json": {"detail": "Not authenticated"}}, True),
        # ... or the view itself fails to find something
        ({"status": 404, "json": {"detail": "Not found."}}, True),
        # Without the endpoint, Django answers as for any unrouted path
        (_DJANGO_404, False),
        # Responses which tell nothing
        ({"status": 503, "body": "Service Unavailable"}, False),
        ({"status": 429, "json": {"detail": "Request was throttled."}}, False),
        ({"body": requests.ConnectionError("no route to host")}, False),
    ],
)
@responses.activate
def test_routes_endpoint(target: dict[str, Any], expected: bool) -> None:
    _mock_server_info()
    responses.add(
        responses.OPTIONS,
        f"{API_URL}/dandisets/000000/versions/draft/assets/bulk-delete/",
        **target,
    )
    responses.add(
        responses.OPTIONS,
        f"{API_URL}/dandisets/000000/versions/draft/assets/dandi-cli-nonexistent-endpoint/",
        **_DJANGO_404,
    )
    client = DandiAPIClient(API_URL)
    assert (
        routes_endpoint(client, "/dandisets/000000/versions/draft/assets/bulk-delete/")
        is expected
    )


@pytest.mark.ai_generated
@responses.activate
def test_routes_endpoint_same_answer_for_any_path() -> None:
    # A server (or a proxy before it) answering any path the same way, here
    # demanding authentication, does not tell whether it has the endpoint
    _mock_server_info()
    for p in ("bulk-delete", "dandi-cli-nonexistent-endpoint"):
        responses.add(
            responses.OPTIONS,
            f"{API_URL}/dandisets/000000/versions/draft/assets/{p}/",
            status=401,
            json={"detail": "Not authenticated"},
        )
    client = DandiAPIClient(API_URL)
    assert not routes_endpoint(
        client, "/dandisets/000000/versions/draft/assets/bulk-delete/"
    )


@pytest.mark.ai_generated
@pytest.mark.parametrize("disable", [False, True])
@responses.activate
def test_check_schema_version_uses_allowed_schema_versions(
    monkeypatch: pytest.MonkeyPatch, disable: bool
) -> None:
    # A client schema version which the server accepts, but which the
    # installed dandischema does not list as an allowed input
    client_schema = "0.5.0"
    assert client_schema not in dandischema.consts.ALLOWED_INPUT_SCHEMAS
    if disable:
        monkeypatch.setenv(DISABLE_ENV_VAR, "ALLOWED_SCHEMA_VERSIONS")
    else:
        monkeypatch.delenv(DISABLE_ENV_VAR, raising=False)
    _mock_server_info(
        version="1.1.1.dev3+g1234567",
        schema_version="0.7.0",
        allowed_schema_versions=[client_schema, "0.7.0"],
    )
    client = DandiAPIClient(API_URL)
    if disable:
        with pytest.raises(SchemaVersionError, match="not among any of the allowed"):
            client.check_schema_version(client_schema)
    else:
        client.check_schema_version(client_schema)
        assert client.server_features.resolve(
            "ALLOWED_SCHEMA_VERSIONS"
        ) == FeatureSupport(True, "sensed")


@pytest.mark.ai_generated
@pytest.mark.parametrize("codename", sorted(SERVER_FEATURES))
def test_registry_entry(codename: str) -> None:
    feature = SERVER_FEATURES[codename]
    assert feature.codename == codename
    assert re.fullmatch(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*", codename)
    assert feature.description
    assert feature.refs
    assert all(re.match(r"https://github\.com/dandi/", ref) for ref in feature.refs)
    versions = [
        Version(v)
        for v in (feature.base_version, feature.released_version)
        if v is not None
    ]
    for v in versions:
        assert not (v.is_prerelease or v.is_postrelease or v.local)
    assert versions == sorted(versions)


@pytest.mark.ai_generated
def test_local_archive(local_dandi_api: DandiAPI) -> None:
    client = local_dandi_api.client
    assert client.server_features.supports("ALLOWED_SCHEMA_VERSIONS")
    # The probe tells an existing endpoint from a missing one on dandi-archive
    assert routes_endpoint(client, "/dandisets/000000/versions/draft/assets/paths/")
    assert not routes_endpoint(
        client, "/dandisets/000000/versions/draft/assets/dandi-cli-test-missing/"
    )
    # Deciding support for any registered feature works
    for codename in SERVER_FEATURES:
        client.server_features.resolve(codename)


#: The known instances whose support for the registered features the
#: survey checks
SURVEYED_INSTANCES = [
    name for name in known_instances if name != "dandi-api-local-docker-tests"
]


@pytest.fixture(scope="module")
def surveyed_clients() -> Iterator[dict[str, DandiAPIClient | Exception]]:
    """
    Clients for the surveyed instances, or the errors from retrieving their
    ``/info/``
    """
    clients: dict[str, DandiAPIClient | Exception] = {}
    for name in SURVEYED_INSTANCES:
        client = DandiAPIClient.for_dandi_instance(name)
        try:
            client.server_info
        except Exception as e:
            client.session.close()
            clients[name] = e
        else:
            clients[name] = client
    yield clients
    for c in clients.values():
        if isinstance(c, DandiAPIClient):
            c.session.close()


@pytest.mark.server_features_survey
@pytest.mark.ai_generated
@pytest.mark.parametrize("codename", sorted(SERVER_FEATURES))
def test_survey(
    codename: str, surveyed_clients: dict[str, DandiAPIClient | Exception]
) -> None:
    """
    Fail if all known instances support the feature ``codename``, i.e., if
    the code for servers without it is no longer needed.  Run weekly by the
    "Survey server features" workflow.
    """
    results: dict[str, str] = {}
    for name, client in surveyed_clients.items():
        try:
            if isinstance(client, Exception):
                raise client
            # Ignore DANDI_DEVEL_DISABLE_SERVER_FEATURES
            support = ServerFeatures(client, disabled=()).resolve(codename)
        except Exception as e:
            results[name] = f"unknown ({type(e).__name__}: {str(e)[:80]})"
        else:
            results[name] = f"{'yes' if support.supported else 'no'} ({support.how})"
    report = "\n".join(f"| {name} | {result} |" for name, result in results.items())
    report = f"### {codename}\n\n| Instance | Supported |\n|---|---|\n{report}\n"
    print(report)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as fp:
            print(report, file=fp)
    assert not all(r.startswith("yes") for r in results.values()), (
        f"All known instances support {codename}: remove the code for servers"
        f" without it and its entry in SERVER_FEATURES.\n\n{report}"
    )
