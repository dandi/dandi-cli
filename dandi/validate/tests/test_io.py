from __future__ import annotations

from pathlib import Path

import pytest

from dandi.validate._io import (
    load_validation_jsonl,
    validation_companion_path,
    write_validation_jsonl,
)
from dandi.validate._types import (
    Origin,
    OriginType,
    Scope,
    Severity,
    ValidationResult,
    Validator,
)

FOO_ORIGIN = Origin(
    type=OriginType.INTERNAL,
    validator=Validator.dandi,
    validator_version="1.0.0",
)


def _make_result(id_: str, severity: Severity = Severity.WARNING) -> ValidationResult:
    return ValidationResult(
        id=id_,
        origin=FOO_ORIGIN,
        scope=Scope.FILE,
        severity=severity,
        message=f"Message for {id_}",
        path=Path(f"/tmp/{id_}.nwb"),
    )


@pytest.mark.ai_generated
class TestWriteAndLoad:
    def test_round_trip(self, tmp_path: Path) -> None:
        """Write results to JSONL and load them back."""
        results = [_make_result("A"), _make_result("B", Severity.ERROR)]
        out = tmp_path / "results.jsonl"
        ret = write_validation_jsonl(results, out)
        assert ret == out
        assert out.exists()

        loaded = load_validation_jsonl([out])
        assert len(loaded) == 2
        assert loaded[0].id == "A"
        assert loaded[1].id == "B"
        assert loaded[1].severity == Severity.ERROR

    def test_append(self, tmp_path: Path) -> None:
        """Append results to an existing JSONL file."""
        out = tmp_path / "results.jsonl"
        write_validation_jsonl([_make_result("A")], out)
        write_validation_jsonl([_make_result("B")], out, append=True)

        loaded = load_validation_jsonl([out])
        assert len(loaded) == 2
        assert loaded[0].id == "A"
        assert loaded[1].id == "B"

    def test_append_creates_file(self, tmp_path: Path) -> None:
        """Append creates the file if it doesn't exist."""
        out = tmp_path / "new.jsonl"
        write_validation_jsonl([_make_result("A")], out, append=True)
        assert out.exists()
        loaded = load_validation_jsonl([out])
        assert len(loaded) == 1

    def test_empty_file(self, tmp_path: Path) -> None:
        """Loading an empty file returns an empty list."""
        out = tmp_path / "empty.jsonl"
        write_validation_jsonl([], out)
        loaded = load_validation_jsonl([out])
        assert loaded == []

    def test_multi_file_load(self, tmp_path: Path) -> None:
        """Load from multiple JSONL files and concatenate."""
        f1 = tmp_path / "a.jsonl"
        f2 = tmp_path / "b.jsonl"
        write_validation_jsonl([_make_result("A")], f1)
        write_validation_jsonl([_make_result("B"), _make_result("C")], f2)

        loaded = load_validation_jsonl([f1, f2])
        assert len(loaded) == 3
        assert [r.id for r in loaded] == ["A", "B", "C"]

    def test_blank_lines_skipped(self, tmp_path: Path) -> None:
        """Blank lines in JSONL should be silently skipped."""
        out = tmp_path / "results.jsonl"
        write_validation_jsonl([_make_result("A")], out)
        # Add blank lines
        with out.open("a") as f:
            f.write("\n\n")
        loaded = load_validation_jsonl([out])
        assert len(loaded) == 1


@pytest.mark.ai_generated
class TestCompanionPath:
    def test_derives_from_logfile(self) -> None:
        """Companion path is derived from logfile by appending _validation.jsonl."""
        logfile = Path("/var/log/dandi/2026.03.19-12.00.00Z-12345.log")
        companion = validation_companion_path(logfile)
        assert companion == Path(
            "/var/log/dandi/2026.03.19-12.00.00Z-12345_validation.jsonl"
        )

    def test_string_input(self) -> None:
        """String input is accepted."""
        companion = validation_companion_path("/tmp/test.log")
        assert companion == Path("/tmp/test_validation.jsonl")
