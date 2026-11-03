from __future__ import annotations

import gc
from io import BytesIO

import pytest

from ..misctypes import _GCPausedFile


@pytest.mark.ai_generated
def test_gc_paused_file() -> None:
    # Automatic garbage collection is disabled while any wrapped file is open
    assert gc.isenabled()
    with _GCPausedFile(BytesIO(b"0123456789")) as fp:
        assert not gc.isenabled()
        fp2 = _GCPausedFile(BytesIO(b"abc"))
        assert fp2.read(2) == b"ab"
        fp2.close()
        assert not gc.isenabled()
        fp.seek(2)
        assert fp.read(3) == b"234"
    assert fp.closed
    assert gc.isenabled()
    # Closing again changes nothing
    fp.close()
    assert gc.isenabled()
    # Dropping an unclosed file re-enables it too
    fp3 = _GCPausedFile(BytesIO(b""))
    assert not gc.isenabled()
    del fp3
    assert gc.isenabled()


@pytest.mark.ai_generated
def test_gc_paused_file_gc_disabled() -> None:
    # If automatic garbage collection was disabled already, it stays disabled
    gc.disable()
    try:
        with _GCPausedFile(BytesIO(b"")):
            assert not gc.isenabled()
        assert not gc.isenabled()
    finally:
        gc.enable()
