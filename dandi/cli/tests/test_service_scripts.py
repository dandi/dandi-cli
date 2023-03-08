from click.testing import CliRunner
import pytest

from dandi.tests.fixtures import SampleDandiset

from ..command import service_scripts


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
