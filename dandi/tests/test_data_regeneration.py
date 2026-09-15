"""Smoke / regression tests for bundled data generation scripts.

These tests download external data and are not run in normal CI.
They are intended for a scheduled (e.g. weekly) run to ensure the
generation code is not broken and produces deterministic output.

Run with::

    pytest -m data_regeneration
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..data.generate_uberon_structures import generate
from ..tests.skip import mark


@pytest.mark.ai_generated
@pytest.mark.data_regeneration
@mark.skipif_no_network
def test_generate_uberon_structures(tmp_path: Path) -> None:
    """Smoke-test the UBERON generator: only the output *shape* is checked.

    UBERON is updated upstream, so byte-level comparison against the committed
    file would break on every ontology release. This test verifies the
    generator runs end-to-end and produces well-formed records (a list of
    dicts with required keys and the expected synonym sub-shape) — not that
    the contents match the bundled snapshot.
    """
    output = tmp_path / "uberon_brain_structures.json"
    generate(output=output)

    assert output.exists()
    data = json.loads(output.read_text())

    assert isinstance(data, list) and data, "expected a non-empty list of structures"
    for entry in data:
        assert isinstance(entry, dict)
        assert isinstance(entry.get("id"), str) and entry["id"]
        assert isinstance(entry.get("name"), str) and entry["name"]
        if "synonyms" in entry:
            assert isinstance(entry["synonyms"], list)
            for syn in entry["synonyms"]:
                assert isinstance(syn, list) and len(syn) == 2
                assert all(isinstance(x, str) for x in syn)
