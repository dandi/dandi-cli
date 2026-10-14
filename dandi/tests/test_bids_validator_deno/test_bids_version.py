from collections.abc import Iterator
import logging
from pathlib import Path

import pytest
import responses

from dandi.bids_validator_deno import bids_validate
from dandi.bids_validator_deno._bids_version import (
    SCHEMA_TO_BIDS_URL,
    _bundled_mapping,
    _published_mapping,
    get_bids_version,
)
from dandi.validate._types import Standard


@pytest.fixture
def clear_mapping_caches() -> Iterator[None]:
    _bundled_mapping.cache_clear()
    _published_mapping.cache_clear()
    yield
    _bundled_mapping.cache_clear()
    _published_mapping.cache_clear()


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "schema_version, bids_version",
    [
        (None, None),
        ("0.11.3", "1.10.0"),
        ("1.1.0", "1.10.1"),
        ("1.2.1", "1.11.1"),
        ("1.2.7", "1.11.1+22-ge37e21053"),
        ("2.0.0", "1.11.2"),
    ],
)
@responses.activate
def test_get_bids_version_bundled(
    schema_version: str | None, bids_version: str | None, clear_mapping_caches: None
) -> None:
    # Known schema versions must not require fetching the published mapping
    assert get_bids_version(schema_version) == bids_version
    assert len(responses.calls) == 0


@pytest.mark.ai_generated
@responses.activate
def test_get_bids_version_published(clear_mapping_caches: None) -> None:
    responses.get(
        SCHEMA_TO_BIDS_URL,
        json={
            "99.0.0": {
                "bids_version_released": "9.9.9",
                "bids_version_exact": "9.9.9+1-g123456789",
            },
        },
    )
    assert get_bids_version("99.0.0") == "9.9.9+1-g123456789"
    assert get_bids_version("99.0.1") is None
    # fetched only once
    assert len(responses.calls) == 1


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "response_kwargs",
    [{"status": 404}, {"body": "not JSON"}, {"json": {"99.0.0": "1.0.0"}}],
)
@responses.activate
def test_get_bids_version_published_unavailable(
    response_kwargs: dict, clear_mapping_caches: None, caplog: pytest.LogCaptureFixture
) -> None:
    responses.get(SCHEMA_TO_BIDS_URL, **response_kwargs)
    with caplog.at_level(logging.WARNING, logger="dandi"):
        assert get_bids_version("99.0.0") is None
    assert SCHEMA_TO_BIDS_URL in caplog.text


@pytest.mark.ai_generated
def test_bids_validate_standard_version(bids_examples: Path) -> None:
    """
    The BIDS version is provided along with the schema version the validator
    reports (https://github.com/dandi/dandi-cli/issues/1961)
    """
    results = bids_validate(bids_examples / "ieeg_epilepsyNWB")
    assert results
    origins = [r.origin for r in results if r.origin.standard is Standard.BIDS]
    assert origins
    origin = origins[0]
    assert all(o == origin for o in origins)
    assert origin.standard_schema_version is not None
    assert origin.standard_version is not None
    assert origin.standard_version == get_bids_version(origin.standard_schema_version)
