"""Smoke / regression tests for bundled data generation scripts.

These tests download external data and are not run in normal CI.
They are intended for a scheduled (e.g. weekly) run to ensure the
generation code is not broken and produces deterministic output.

Run with::

    pytest -m data_regeneration
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..data.generate_uberon_structures import generate
from ..tests.skip import mark


@pytest.mark.ai_generated
@pytest.mark.data_regeneration
@mark.skipif_no_network
def test_generate_uberon_structures(tmp_path: Path) -> None:
    """Regenerate UBERON structures and verify output matches committed file."""
    committed = (
        Path(__file__).resolve().parent.parent / "data" / "uberon_brain_structures.json"
    )
    output = tmp_path / "uberon_brain_structures.json"

    generate(output=output)

    assert output.exists()
    assert output.read_text() == committed.read_text(), (
        "Generated UBERON structures differ from committed file. "
        "Run 'dandi service-scripts generate-uberon-structures' to update."
    )
