import re

import pytest
import responses

from dandi.consts import DandiInstance, known_instances
from dandi.dandiarchive import (
    AssetFolderURL,
    AssetGlobURL,
    AssetIDURL,
    AssetItemURL,
    AssetPathPrefixURL,
    BaseAssetIDURL,
    DandisetURL,
    ParsedDandiURL,
    follow_redirect,
    multiasset_target,
    parse_dandi_url,
)
from dandi.exceptions import NotFoundError, UnknownURLError
from dandi.tests.skip import mark

from .fixtures import DandiAPI, SampleDandiset


@pytest.mark.parametrize(
    "url,parsed_url",
    [
        # New DANDI web UI driven by DANDI API.
        pytest.param(
            "https://gui.dandiarchive.org/#/dandiset/000001",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000001",
                version_id=None,
            ),
            marks=mark.skipif_no_network,
        ),
        pytest.param(
            "https://gui.dandiarchive.org/#/dandiset/000001/",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000001",
                version_id=None,
            ),
            marks=mark.skipif_no_network,
        ),
        pytest.param(
            "https://gui.dandiarchive.org/#/dandiset/000001/0.201104.2302",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000001",
                version_id="0.201104.2302",
            ),
            marks=mark.skipif_no_network,
        ),
        pytest.param(
            "https://gui.dandiarchive.org/#/dandiset/000001/0.201104.2302/",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000001",
                version_id="0.201104.2302",
            ),
            marks=mark.skipif_no_network,
        ),
        pytest.param(
            "https://gui.dandiarchive.org/#/dandiset/000001/0.201104.2302/files",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000001",
                version_id="0.201104.2302",
            ),
            marks=mark.skipif_no_network,
        ),
        pytest.param(
            "https://gui.dandiarchive.org/#/dandiset/000001/draft",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000001",
                version_id="draft",
            ),
            marks=mark.skipif_no_network,
        ),
        pytest.param(
            "https://gui.dandiarchive.org/dandiset/000001",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000001",
                version_id=None,
            ),
            marks=mark.skipif_no_network,
        ),
        pytest.param(
            "https://gui.dandiarchive.org/dandiset/000001/0.201104.2302",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000001",
                version_id="0.201104.2302",
            ),
            marks=mark.skipif_no_network,
        ),
        pytest.param(
            "https://gui.dandiarchive.org/dandiset/000001/0.201104.2302/files",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000001",
                version_id="0.201104.2302",
            ),
            marks=mark.skipif_no_network,
        ),
        pytest.param(
            "https://gui.dandiarchive.org/dandiset/000001/draft",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000001",
                version_id="draft",
            ),
            marks=mark.skipif_no_network,
        ),
        (
            "DANDI:000027",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000027",
                version_id=None,
            ),
        ),
        (
            "DANDI:000027/0.210831.2033",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000027",
                version_id="0.210831.2033",
            ),
        ),
        (
            "DANDI:000027/draft",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000027",
                version_id="draft",
            ),
        ),
        # lower cased
        (
            "dandi:000027/0.210831.2033",
            DandisetURL(
                instance=known_instances["dandi"],
                dandiset_id="000027",
                version_id="0.210831.2033",
            ),
        ),
        (
            "http://localhost:8000/api/dandisets/000002/",
            DandisetURL(
                instance=known_instances["dandi-api-local-docker-tests"],
                dandiset_id="000002",
                version_id=None,
            ),
        ),
        (
            "http://localhost:8000/api/dandisets/000002",
            DandisetURL(
                instance=known_instances["dandi-api-local-docker-tests"],
                dandiset_id="000002",
                version_id=None,
            ),
        ),
        (
            "http://localhost:8000/api/dandisets/000002/versions/draft",
            DandisetURL(
                instance=known_instances["dandi-api-local-docker-tests"],
                dandiset_id="000002",
                version_id="draft",
            ),
        ),
        (
            "http://localhost:8000/api/dandisets/000002/versions/draft/",
            DandisetURL(
                instance=known_instances["dandi-api-local-docker-tests"],
                dandiset_id="000002",
                version_id="draft",
            ),
        ),
        (
            "http://localhost:8085/dandiset/000002",
            DandisetURL(
                instance=known_instances["dandi-api-local-docker-tests"],
                dandiset_id="000002",
                version_id=None,
            ),
        ),
        pytest.param(
            "https://gui.dandiarchive.org/#/dandiset/000001/files"
            "?location=%2Fsub-anm369962",
            AssetFolderURL(
                instance=known_instances["dandi"],
                dandiset_id="000001",
                version_id=None,
                path="sub-anm369962/",
            ),
            marks=mark.skipif_no_network,
        ),
        pytest.param(
            "https://gui.dandiarchive.org/#/dandiset/000006/0.200714.1807/files"
            "?location=%2Fsub-anm369962",
            AssetFolderURL(
                instance=known_instances["dandi"],
                dandiset_id="000006",
                version_id="0.200714.1807",
                path="sub-anm369962/",
            ),
            marks=mark.skipif_no_network,
        ),
        pytest.param(
            "https://gui.dandiarchive.org/#/dandiset/001001/draft/files"
            "?location=sub-RAT123%2F",
            AssetFolderURL(
                instance=known_instances["dandi"],
                dandiset_id="001001",
                version_id="draft",
                path="sub-RAT123/",
            ),
            marks=mark.skipif_no_network,
        ),
        # by direct instance name ad-hoc URI instance:ID[@version][/path]
        (
            "dandi://dandi-api-local-docker-tests/000002@draft",
            DandisetURL(
                instance=known_instances["dandi-api-local-docker-tests"],
                dandiset_id="000002",
                version_id="draft",
            ),
        ),
        (
            "dandi://dandi-api-local-docker-tests/000002@draft/path",
            AssetItemURL(
                instance=known_instances["dandi-api-local-docker-tests"],
                dandiset_id="000002",
                version_id="draft",
                path="path",
            ),
        ),
        (
            "dandi://dandi-api-local-docker-tests/000002/path",
            AssetItemURL(
                instance=known_instances["dandi-api-local-docker-tests"],
                dandiset_id="000002",
                version_id=None,
                path="path",
            ),
        ),
        (  # test on "public" instance and have trailing / to signal the folder
            "dandi://dandi/000002/path/",
            AssetFolderURL(
                instance=known_instances["dandi"],
                dandiset_id="000002",
                version_id=None,
                path="path/",
            ),
        ),
        (
            "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
            "/assets/0a748f90-d497-4a9c-822e-9c63811db412/download/",
            AssetIDURL(
                instance=known_instances["dandi"],
                dandiset_id="000003",
                version_id="draft",
                asset_id="0a748f90-d497-4a9c-822e-9c63811db412",
            ),
        ),
        (
            "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
            "/assets/0a748f90-d497-4a9c-822e-9c63811db412/download",
            AssetIDURL(
                instance=known_instances["dandi"],
                dandiset_id="000003",
                version_id="draft",
                asset_id="0a748f90-d497-4a9c-822e-9c63811db412",
            ),
        ),
        (
            "https://api.dandiarchive.org/api"
            "/assets/0a748f90-d497-4a9c-822e-9c63811db412/download/",
            BaseAssetIDURL(
                instance=known_instances["dandi"],
                asset_id="0a748f90-d497-4a9c-822e-9c63811db412",
            ),
        ),
        (
            "https://api.dandiarchive.org/api"
            "/assets/0a748f90-d497-4a9c-822e-9c63811db412/download",
            BaseAssetIDURL(
                instance=known_instances["dandi"],
                asset_id="0a748f90-d497-4a9c-822e-9c63811db412",
            ),
        ),
        (
            "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
            "/assets/?path=sub-YutaMouse20",
            AssetPathPrefixURL(
                instance=known_instances["dandi"],
                dandiset_id="000003",
                version_id="draft",
                path="sub-YutaMouse20",
            ),
        ),
        (
            "https://gui-staging.dandiarchive.org/#/dandiset/000018",
            DandisetURL(
                instance=known_instances["dandi-staging"],
                dandiset_id="000018",
                version_id=None,
            ),
        ),
        (
            "https://deploy-preview-854--gui-dandiarchive-org.netlify.app"
            "/#/dandiset/000018",
            DandisetURL(
                instance=known_instances["dandi-staging"],
                dandiset_id="000018",
                version_id=None,
            ),
        ),
        pytest.param(
            "https://gui.dandiarchive.org/#/dandiset/001001/draft/files"
            "?location=sub-RAT123/*.nwb",
            AssetFolderURL(
                instance=known_instances["dandi"],
                dandiset_id="001001",
                version_id="draft",
                path="sub-RAT123/*.nwb/",
            ),
            marks=mark.skipif_no_network,
        ),
        (
            "dandi://dandi-api-local-docker-tests/000002/f*/bar.nwb",
            AssetItemURL(
                instance=known_instances["dandi-api-local-docker-tests"],
                dandiset_id="000002",
                version_id=None,
                path="f*/bar.nwb",
            ),
        ),
        (
            "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
            "/assets/?glob=sub-YutaMouse*",
            AssetGlobURL(
                instance=known_instances["dandi"],
                dandiset_id="000003",
                version_id="draft",
                path="sub-YutaMouse*",
            ),
        ),
    ],
)
def test_parse_api_url(url: str, parsed_url: ParsedDandiURL) -> None:
    assert parse_dandi_url(url) == parsed_url


@pytest.mark.parametrize(
    "url,parsed_url",
    [
        (
            "https://dandiarchive.org/dandiset/001001/draft/files"
            "?location=sub-RAT123/*.nwb",
            AssetGlobURL(
                instance=known_instances["dandi"],
                dandiset_id="001001",
                version_id="draft",
                path="sub-RAT123/*.nwb",
            ),
        ),
        pytest.param(
            "https://gui.dandiarchive.org/#/dandiset/001001/draft/files"
            "?location=sub-RAT123/*.nwb",
            AssetGlobURL(
                instance=known_instances["dandi"],
                dandiset_id="001001",
                version_id="draft",
                path="sub-RAT123/*.nwb",
            ),
            marks=mark.skipif_no_network,
        ),
        (
            "dandi://dandi-api-local-docker-tests/000002/f*/bar.nwb",
            AssetGlobURL(
                instance=known_instances["dandi-api-local-docker-tests"],
                dandiset_id="000002",
                version_id=None,
                path="f*/bar.nwb",
            ),
        ),
        (
            # `path=` does not produce a glob:
            "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
            "/assets/?path=sub-YutaMouse*",
            AssetPathPrefixURL(
                instance=known_instances["dandi"],
                dandiset_id="000003",
                version_id="draft",
                path="sub-YutaMouse*",
            ),
        ),
        (
            "https://api.dandiarchive.org/api/dandisets/000003/versions/draft"
            "/assets/?glob=sub-YutaMouse*",
            AssetGlobURL(
                instance=known_instances["dandi"],
                dandiset_id="000003",
                version_id="draft",
                path="sub-YutaMouse*",
            ),
        ),
    ],
)
def test_parse_api_url_glob(url: str, parsed_url: ParsedDandiURL) -> None:
    assert parse_dandi_url(url, glob=True) == parsed_url


@pytest.mark.parametrize(
    "url",
    [
        "DANDI:27",
        # Currently takes too long to run; cf. #830:
        # "https://identifiers.org/DANDI:000027/draft",
    ],
)
def test_parse_bad_api_url(url: str) -> None:
    with pytest.raises(UnknownURLError):
        parse_dandi_url(url)


def test_known_instances() -> None:
    # all should be lower cased
    assert all(i.islower() for i in known_instances)


def test_parse_dandi_url_unknown_instance() -> None:
    with pytest.raises(UnknownURLError) as excinfo:
        parse_dandi_url("dandi://not-an-instance/000001")

    valid_instances = ", ".join(sorted(known_instances.keys()))
    expected_message = f"Unknown instance 'not-an-instance'.  Valid instances: {valid_instances}"

    assert str(excinfo.value) == expected_message


@mark.skipif_no_network
@pytest.mark.xfail(reason="https://github.com/dandi/dandi-archive/issues/1020")
def test_parse_dandi_url_not_found() -> None:
    # Unlikely this one would ever come to existence
    with pytest.raises(NotFoundError):
        parse_dandi_url("https://dandiarchive.org/dandiset/999999")


@mark.skipif_no_network
def test_follow_redirect() -> None:
    url = follow_redirect("https://bit.ly/dandi12")
    assert re.match(r"https://(.*\.)?dandiarchive.org", url)


@responses.activate
def test_parse_gui_new_redirect() -> None:
    responses.add(
        responses.HEAD,
        "https://gui.dandiarchive.org/#/dandiset/000003",
        status=302,
        headers={"Location": "https://dandiarchive.org/"},
    )
    responses.add(responses.HEAD, "https://dandiarchive.org/")
    responses.add(
        responses.GET,
        "https://dandiarchive.org/server-info",
        json={
            "version": "1.2.0",
            "cli-minimal-version": "0.6.0",
            "cli-bad-versions": [],
            "services": {
                "webui": {"url": "https://dandiarchive.org"},
                "api": {"url": "https://api.dandiarchive.org/api"},
                "jupyterhub": {"url": "https://hub.dandiarchive.org"},
            },
        },
    )
    assert parse_dandi_url(
        "https://gui.dandiarchive.org/#/dandiset/000003"
    ) == DandisetURL(
        instance=known_instances["dandi"],
        dandiset_id="000003",
        version_id=None,
    )


@responses.activate
def test_parse_arbitrary_gui_url() -> None:
    responses.add(
        responses.GET,
        "https://example.test/server-info",
        json={
            "version": "1.2.0",
            "cli-minimal-version": "0.6.0",
            "cli-bad-versions": [],
            "services": {
                "webui": {"url": "https://example.test"},
                "api": {"url": "https://api.example.test/api"},
            },
        },
    )
    assert parse_dandi_url("https://example.test/dandiset/000123") == DandisetURL(
        instance=DandiInstance(
            name="api.example.test",
            gui="https://example.test",
            api="https://api.example.test/api",
        ),
        dandiset_id="000123",
        version_id=None,
    )


@responses.activate
def test_parse_arbitrary_api_url() -> None:
    responses.add(
        responses.GET,
        "https://api.example.test/server-info",
        status=404,
    )
    responses.add(
        responses.GET,
        "https://api.example.test/api/info/",
        json={
            "version": "1.2.0",
            "cli-minimal-version": "0.6.0",
            "cli-bad-versions": [],
            "services": {
                "api": {"url": "https://api.example.test/api"},
            },
        },
    )
    assert parse_dandi_url(
        "https://api.example.test/api/dandiset/000123"
    ) == DandisetURL(
        instance=DandiInstance(
            name="api.example.test",
            gui=None,
            api="https://api.example.test/api",
        ),
        dandiset_id="000123",
        version_id=None,
    )


@pytest.mark.parametrize("version_suffix", ["", "@draft", "@0.999999.9999"])
def test_get_nonexistent_dandiset(
    local_dandi_api: DandiAPI, version_suffix: str
) -> None:
    url = f"dandi://{local_dandi_api.instance_id}/999999{version_suffix}"
    parsed_url = parse_dandi_url(url)
    client = local_dandi_api.client
    parsed_url.get_dandiset(client)  # No error
    with pytest.raises(NotFoundError) as excinfo:
        parsed_url.get_dandiset(client, lazy=False)
    assert str(excinfo.value) == "No such Dandiset: '999999'"
    assert list(parsed_url.get_assets(client)) == []
    with pytest.raises(NotFoundError) as excinfo:
        next(parsed_url.get_assets(client, strict=True))
    assert str(excinfo.value) == "No such Dandiset: '999999'"


@pytest.mark.parametrize("version", ["draft", "0.999999.9999"])
def test_get_nonexistent_dandiset_asset_id(
    local_dandi_api: DandiAPI, version: str
) -> None:
    url = (
        f"{local_dandi_api.api_url}/dandisets/999999/versions/{version}"
        "/assets/00000000-0000-0000-0000-000000000000/"
    )
    parsed_url = parse_dandi_url(url)
    client = local_dandi_api.client
    assert list(parsed_url.get_assets(client)) == []
    with pytest.raises(NotFoundError) as excinfo:
        next(parsed_url.get_assets(client, strict=True))
    assert str(excinfo.value) == "No such Dandiset: '999999'"


def test_get_dandiset_nonexistent_asset_id(text_dandiset: SampleDandiset) -> None:
    url = (
        f"{text_dandiset.api.api_url}/dandisets/"
        f"{text_dandiset.dandiset_id}/versions/draft/assets/"
        "00000000-0000-0000-0000-000000000000/"
    )
    parsed_url = parse_dandi_url(url)
    client = text_dandiset.client
    assert list(parsed_url.get_assets(client)) == []
    with pytest.raises(NotFoundError) as excinfo:
        next(parsed_url.get_assets(client, strict=True))
    assert str(excinfo.value) == (
        "No such asset: '00000000-0000-0000-0000-000000000000' for"
        f" DANDI-API-LOCAL-DOCKER-TESTS:{text_dandiset.dandiset_id}/draft"
    )


def test_get_nonexistent_asset_id(local_dandi_api: DandiAPI) -> None:
    url = f"{local_dandi_api.api_url}/assets/00000000-0000-0000-0000-000000000000/"
    parsed_url = parse_dandi_url(url)
    client = local_dandi_api.client
    assert list(parsed_url.get_assets(client)) == []
    with pytest.raises(NotFoundError) as excinfo:
        next(parsed_url.get_assets(client, strict=True))
    assert str(excinfo.value) == "No such asset: '00000000-0000-0000-0000-000000000000'"


@pytest.mark.parametrize("version_suffix", ["", "@draft", "@0.999999.9999"])
def test_get_nonexistent_dandiset_asset_path(
    local_dandi_api: DandiAPI, version_suffix: str
) -> None:
    url = f"dandi://{local_dandi_api.instance_id}/999999{version_suffix}/does/not/exist"
    parsed_url = parse_dandi_url(url)
    client = local_dandi_api.client
    assert list(parsed_url.get_assets(client)) == []
    with pytest.raises(NotFoundError) as excinfo:
        next(parsed_url.get_assets(client, strict=True))
    assert str(excinfo.value) == "No such Dandiset: '999999'"


def test_get_nonexistent_asset_path(text_dandiset: SampleDandiset) -> None:
    url = (
        f"dandi://{text_dandiset.api.instance_id}/"
        f"{text_dandiset.dandiset_id}/does/not/exist"
    )
    parsed_url = parse_dandi_url(url)
    client = text_dandiset.client
    assert list(parsed_url.get_assets(client)) == []
    with pytest.raises(NotFoundError) as excinfo:
        next(parsed_url.get_assets(client, strict=True))
    assert str(excinfo.value) == "No asset at path 'does/not/exist'"


@pytest.mark.parametrize("version_suffix", ["", "@draft", "@0.999999.9999"])
def test_get_nonexistent_dandiset_asset_folder(
    local_dandi_api: DandiAPI, version_suffix: str
) -> None:
    url = (
        f"dandi://{local_dandi_api.instance_id}/999999{version_suffix}"
        "/does/not/exist/"
    )
    parsed_url = parse_dandi_url(url)
    client = local_dandi_api.client
    assert list(parsed_url.get_assets(client)) == []
    with pytest.raises(NotFoundError) as excinfo:
        next(parsed_url.get_assets(client, strict=True))
    assert str(excinfo.value) == "No such Dandiset: '999999'"


def test_get_nonexistent_asset_folder(text_dandiset: SampleDandiset) -> None:
    url = (
        f"dandi://{text_dandiset.api.instance_id}/"
        f"{text_dandiset.dandiset_id}/does/not/exist/"
    )
    parsed_url = parse_dandi_url(url)
    client = text_dandiset.client
    assert list(parsed_url.get_assets(client)) == []
    with pytest.raises(NotFoundError) as excinfo:
        list(parsed_url.get_assets(client, strict=True))
    assert str(excinfo.value) == "No assets found under folder 'does/not/exist/'"


@pytest.mark.parametrize("version", ["draft", "0.999999.9999"])
def test_get_nonexistent_dandiset_asset_prefix(
    local_dandi_api: DandiAPI, version: str
) -> None:
    url = (
        f"{local_dandi_api.api_url}/dandisets/999999/versions/{version}"
        "/assets/?path=does/not/exist"
    )
    parsed_url = parse_dandi_url(url)
    client = local_dandi_api.client
    assert list(parsed_url.get_assets(client)) == []
    with pytest.raises(NotFoundError) as excinfo:
        next(parsed_url.get_assets(client, strict=True))
    assert str(excinfo.value) == "No such Dandiset: '999999'"


def test_get_nonexistent_asset_prefix(text_dandiset: SampleDandiset) -> None:
    url = (
        f"{text_dandiset.api.api_url}/dandisets/"
        f"{text_dandiset.dandiset_id}/versions/draft/assets/?path=does/not/exist"
    )
    parsed_url = parse_dandi_url(url)
    client = text_dandiset.client
    assert list(parsed_url.get_assets(client)) == []
    with pytest.raises(NotFoundError) as excinfo:
        list(parsed_url.get_assets(client, strict=True))
    assert str(excinfo.value) == "No assets found with path prefix 'does/not/exist'"


def test_get_nonexistent_asset_glob(text_dandiset: SampleDandiset) -> None:
    url = (
        f"{text_dandiset.api.api_url}/dandisets/"
        f"{text_dandiset.dandiset_id}/versions/draft/assets/?glob=d*/*/*st"
    )
    parsed_url = parse_dandi_url(url)
    client = text_dandiset.client
    assert list(parsed_url.get_assets(client)) == []
    with pytest.raises(NotFoundError) as excinfo:
        list(parsed_url.get_assets(client, strict=True))
    assert str(excinfo.value) == "No assets found matching glob 'd*/*/*st'"


@pytest.mark.parametrize(
    "url_path,asset_path,target",
    [
        ("", "foo/bar", "foo/bar"),
        ("fo", "foo/bar", "foo/bar"),
        ("foo", "foo/bar", "foo/bar"),
        ("foo/", "foo/bar", "foo/bar"),
        ("foo/bar", "foo/bar/baz/quux", "bar/baz/quux"),
        ("foo/bar/", "foo/bar/baz/quux", "bar/baz/quux"),
        ("/foo/bar", "foo/bar/baz/quux", "bar/baz/quux"),
        ("foo/ba", "foo/bar/baz/quux", "bar/baz/quux"),
        ("foo/bar", "foo/bar", "bar"),
    ],
)
def test_multiasset_target(url_path: str, asset_path: str, target: str) -> None:
    assert multiasset_target(url_path, asset_path) == target
