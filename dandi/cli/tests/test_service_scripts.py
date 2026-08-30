from __future__ import annotations

from contextlib import nullcontext
import json
import os
from pathlib import Path
import re
import sys

import anys
import click
from click.testing import CliRunner
from dandischema.models import ID_PATTERN
import pytest
import responses

from dandi import __version__
from dandi.tests.fixtures import SampleDandiset

from ..cmd_service_scripts import (
    DOI_CSL_ACCEPT,
    fetch_doi_citation_metadata,
    normalize_doi,
    service_scripts,
)

DATA_DIR = Path(__file__).with_name("data")


@pytest.mark.xfail(
    "nfsmount" in os.environ.get("TMPDIR", ""),
    reason="https://github.com/dandi/dandi-cli/issues/1507",
)
def test_reextract_metadata(
    monkeypatch: pytest.MonkeyPatch, nwb_dandiset: SampleDandiset
) -> None:
    pytest.importorskip("fsspec")
    asset_id = nwb_dandiset.dandiset.get_asset_by_path(
        "sub-mouse001/sub-mouse001.nwb"
    ).identifier
    nwb_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    r = CliRunner().invoke(
        service_scripts,
        ["reextract-metadata", "--when=always", nwb_dandiset.dandiset.version_api_url],
    )
    assert r.exit_code == 0
    asset_id2 = nwb_dandiset.dandiset.get_asset_by_path(
        "sub-mouse001/sub-mouse001.nwb"
    ).identifier
    assert asset_id2 != asset_id


def record_only_doi_requests(request):
    if request.host in ("doi.org", "api.crossref.org"):
        # We need to capture api.crossref.org requests as doi.org redirects
        # there.
        return request
    else:
        return None


@pytest.mark.xfail(
    sys.version_info < (3, 10),
    reason="Some difference in VCR tape: https://github.com/dandi/dandi-cli/pull/1337",
)
@pytest.mark.parametrize(
    "doi,name",
    [
        ("10.1101/2020.01.17.909838", "biorxiv"),
        ("10.1523/JNEUROSCI.6157-08.2009", "jneurosci"),
        ("10.1016/j.neuron.2019.10.012", "neuron"),
        ("10.7554/eLife.48198", "elife"),
        ("10.1038/s41467-023-37704-5", "nature"),
    ],
)
def test_update_dandiset_from_doi(
    doi: str,
    name: str,
    new_dandiset: SampleDandiset,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dandiset_id = new_dandiset.dandiset_id
    repository = new_dandiset.api.instance.gui
    new_dandiset.api.monkeypatch_set_api_key_env(monkeypatch)
    if os.environ.get("DANDI_TESTS_NO_VCR", "") or sys.version_info <= (3, 10):
        # Older vcrpy has an issue with Python 3.9 and newer urllib2 >= 2
        # But we require newer urllib2 for more correct operation, and
        # do still support 3.9.  Remove when 3.9 support is dropped
        ctx = nullcontext()
    else:
        import vcr

        ctx = vcr.use_cassette(
            str(DATA_DIR / "update_dandiset_from_doi" / f"{name}.vcr.yaml"),
            before_record_request=record_only_doi_requests,
        )
    with ctx:
        r = CliRunner().invoke(
            service_scripts,
            [
                "update-dandiset-from-doi",
                "--dandiset",
                dandiset_id,
                "--dandi-instance",
                new_dandiset.api.instance_id,
                "--existing=overwrite",
                "--yes",
                doi,
            ],
        )
    assert r.exit_code == 0
    metadata = new_dandiset.dandiset.get_raw_metadata()
    # The DANDI schema version in the metadata under test is the server's,
    # not this client's.
    server_schema_version = new_dandiset.client.get("/info/")["schema_version"]
    with (DATA_DIR / "update_dandiset_from_doi" / f"{name}.json").open() as fp:
        expected = json.load(fp)
    expected["id"] = anys.AnyFullmatch(rf"{ID_PATTERN}:{dandiset_id}/draft")
    expected["url"] = f"{repository}/dandiset/{dandiset_id}/draft"
    expected["@context"] = (
        "https://raw.githubusercontent.com/dandi/schema/master/releases"
        f"/{server_schema_version}/context.json"
    )
    expected["identifier"] = anys.AnyFullmatch(rf"{ID_PATTERN}:{dandiset_id}")
    expected["repository"] = repository
    expected["dateCreated"] = anys.ANY_AWARE_DATETIME_STR
    expected["schemaVersion"] = server_schema_version
    expected["wasGeneratedBy"][0]["id"] = anys.AnyFullmatch(
        r"urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    )
    expected["wasGeneratedBy"][0]["endDate"] = anys.ANY_AWARE_DATETIME_STR
    expected["wasGeneratedBy"][0]["startDate"] = anys.ANY_AWARE_DATETIME_STR
    expected["wasGeneratedBy"][0]["wasAssociatedWith"][0]["version"] = __version__
    expected["manifestLocation"][
        0
    ] = f"{new_dandiset.api.api_url}/dandisets/{dandiset_id}/versions/draft/assets/"
    citation = re.sub(
        r"\S+\Z",
        f"{repository}/dandiset/{dandiset_id}/draft",
        expected["citation"],
    )
    if m := re.search(r"\(\d{4}\)", citation):
        citation_rgx = (
            re.escape(citation[: m.start()])
            + r"\(\d{4}\)"
            + re.escape(citation[m.end() :])
        )
        expected["citation"] = anys.AnyFullmatch(citation_rgx)
    else:
        expected["citation"] = citation
    assert metadata == expected


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "given",
    [
        "10.48324/dandi.001827/0.260505.1322",
        "  10.48324/dandi.001827/0.260505.1322  ",
        "doi:10.48324/dandi.001827/0.260505.1322",
        "DOI:10.48324/dandi.001827/0.260505.1322",
        "https://doi.org/10.48324/dandi.001827/0.260505.1322",
        "http://doi.org/10.48324/dandi.001827/0.260505.1322",
        "https://dx.doi.org/10.48324/dandi.001827/0.260505.1322",
        "doi.org/10.48324/dandi.001827/0.260505.1322",
    ],
)
def test_normalize_doi(given: str) -> None:
    assert normalize_doi(given) == "10.48324/dandi.001827/0.260505.1322"


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "given",
    [
        "",
        "not a doi",
        "https://doi.org/",
        "https://example.com/10.1234/foo",
        "10.1/too-short-prefix",
    ],
)
def test_normalize_doi_rejects_non_doi(given: str) -> None:
    with pytest.raises(ValueError, match="does not look like a DOI"):
        normalize_doi(given)


@pytest.mark.ai_generated
@responses.activate
def test_fetch_doi_citation_metadata_non_json() -> None:
    # doi.org falls back to redirecting to the landing page when the
    # registration agency cannot serve CSL JSON, so we get HTML with a 200.
    # See https://github.com/dandi/dandi-cli/issues/1855
    doi = "10.48324/dandi.001827/0.260505.1322"
    responses.add(
        responses.GET,
        f"https://doi.org/{doi}",
        body="<!DOCTYPE html><html><body>Dandiset 001827</body></html>",
        status=200,
        content_type="text/html; charset=utf-8",
    )
    with pytest.raises(click.ClickException) as excinfo:
        fetch_doi_citation_metadata(doi)
    message = str(excinfo.value)
    assert doi in message
    assert "did not resolve to citation metadata" in message
    assert "text/html" in message


@pytest.mark.ai_generated
@responses.activate
def test_fetch_doi_citation_metadata_not_found() -> None:
    doi = "10.48324/dandi.999999/0.000000.0000"
    responses.add(
        responses.GET,
        f"https://doi.org/{doi}",
        body="DOI Not Found",
        status=404,
        content_type="text/plain",
    )
    with pytest.raises(click.ClickException) as excinfo:
        fetch_doi_citation_metadata(doi)
    assert "is not registered" in str(excinfo.value)


@pytest.mark.ai_generated
@responses.activate
def test_fetch_doi_citation_metadata_ok() -> None:
    doi = "10.1101/2020.01.17.909838"
    responses.add(
        responses.GET,
        f"https://doi.org/{doi}",
        json={"title": "A paper", "author": []},
        status=200,
    )
    assert fetch_doi_citation_metadata(doi) == {"title": "A paper", "author": []}


@pytest.mark.ai_generated
@responses.activate
def test_fetch_doi_citation_metadata_requests_csl_json() -> None:
    # The CSL Accept header used to be set on the session only, where
    # `RESTFullAPIClient.request()` overrode it with "application/json" while
    # building a JSON request.  See https://github.com/dandi/dandi-cli/issues/1855
    doi = "10.1101/2020.01.17.909838"
    responses.add(
        responses.GET, f"https://doi.org/{doi}", json={"title": "A paper"}, status=200
    )
    fetch_doi_citation_metadata(doi)
    assert responses.calls[0].request.headers["Accept"] == DOI_CSL_ACCEPT


@pytest.mark.ai_generated
def test_update_dandiset_from_doi_bad_doi() -> None:
    r = CliRunner().invoke(
        service_scripts,
        ["update-dandiset-from-doi", "-d", "000001", "not-a-doi"],
    )
    assert r.exit_code == 2
    assert "does not look like a DOI" in r.output
    assert "Traceback" not in r.output
