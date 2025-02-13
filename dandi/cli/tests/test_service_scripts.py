from __future__ import annotations

from contextlib import nullcontext
import json
import os
from pathlib import Path
import re
import sys

import anys
from click.testing import CliRunner
from dandischema.consts import DANDI_SCHEMA_VERSION
import pytest

from dandi import __version__
from dandi.tests.fixtures import SampleDandiset

from ..cmd_service_scripts import service_scripts

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
    monkeypatch.setenv("DANDI_API_KEY", nwb_dandiset.api.api_key)
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
    monkeypatch.setenv("DANDI_API_KEY", new_dandiset.api.api_key)
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
    with (DATA_DIR / "update_dandiset_from_doi" / f"{name}.json").open() as fp:
        expected = json.load(fp)
    expected["id"] = f"DANDI:{dandiset_id}/draft"
    expected["url"] = f"{repository}/dandiset/{dandiset_id}/draft"
    expected["@context"] = (
        "https://raw.githubusercontent.com/dandi/schema/master/releases"
        f"/{DANDI_SCHEMA_VERSION}/context.json"
    )
    expected["identifier"] = f"DANDI:{dandiset_id}"
    expected["repository"] = repository
    expected["dateCreated"] = anys.ANY_AWARE_DATETIME_STR
    expected["schemaVersion"] = DANDI_SCHEMA_VERSION
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
