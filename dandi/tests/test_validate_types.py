from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError
import pytest

from dandi.validate_types import (
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
    validator_version="123",
)


class TestValidationResult:
    @pytest.mark.parametrize(
        ("severity", "expected_json"),
        [
            (Severity.INFO, "INFO"),
            (Severity.WARNING, "WARNING"),
            (Severity.ERROR, "ERROR"),
            (None, None),
        ],
    )
    def test_severity_serialization(
        self, severity: Severity | None, expected_json: str
    ) -> None:
        """
        Test serialization of `Severity`
        """
        r = ValidationResult(
            id="foo",
            origin=FOO_ORIGIN,
            scope=Scope.FILE,
            severity=severity,
        )

        # Dump into JSON serializable dict
        json_dump = r.model_dump(mode="json")
        assert json_dump["severity"] == expected_json

        # Dump into JSON string
        json_dumps = r.model_dump_json(indent=2)
        json_dict = json.loads(json_dumps)
        assert json_dict["severity"] == expected_json

        # Dump into a Python dict
        #   (severity should remain the same in this serialized form)
        python_dump = r.model_dump(mode="python")
        assert python_dump["severity"] is severity

    @pytest.mark.parametrize("severity", list(Severity.__members__.values()) + [None])
    def test_severity_round_trip(self, severity: Severity | None) -> None:
        """
        Test round trip serializing and deserializing `Severity` with in a
        `ValidationResult` object
        """
        r = ValidationResult(
            id="foo",
            origin=FOO_ORIGIN,
            scope=Scope.FILE,
            severity=severity,
        )

        # Dump into JSON serializable dict
        json_dump = r.model_dump(mode="json")

        # Dump into JSON string
        json_dumps = r.model_dump_json(indent=2)

        # Dump into a Python dict
        #   (severity should remain the same in this serialized form)
        python_dump = r.model_dump(mode="python")

        for dump in (json_dump, python_dump):
            # Reconstitute from dict
            r_reconstituted = ValidationResult.model_validate(dump)
            assert r == r_reconstituted

        # Reconstitute from JSON string
        r_reconstituted = ValidationResult.model_validate_json(json_dumps)
        assert r == r_reconstituted

    @pytest.mark.parametrize("severity", Severity.__members__.values())
    def test_severity_validation_from_int(self, severity: Severity) -> None:
        """
        Test validation of `Severity` from an integer in a `ValidationResult` object
        """
        r = ValidationResult(
            id="foo",
            origin=FOO_ORIGIN,
            scope=Scope.FILE,
            severity=severity,
        )

        # Dump into JSON serializable dict
        json_dump = r.model_dump(mode="json")
        json_dump["severity"] = severity.value  # Modify severity into its int value

        # Dump into JSON string
        json_dumps = json.dumps(json_dump, indent=2)

        # Reconstitute from JSON serializable dict
        r_reconstituted = ValidationResult.model_validate(json_dump)
        assert r == r_reconstituted

        # Reconstitute from JSON string
        r_reconstituted = ValidationResult.model_validate_json(json_dumps)
        assert r == r_reconstituted

    @pytest.mark.parametrize("invalid_severity", ["foo", 42, True])
    def test_invalid_severity_validation(self, invalid_severity: Any) -> None:
        """
        Test validation of `Severity` from an invalid value in a `ValidationResult`
        object
        """
        r = ValidationResult(
            id="foo",
            origin=FOO_ORIGIN,
            scope=Scope.FILE,
            severity=None,
        )

        # Dump into JSON serializable dict
        json_dump = r.model_dump(mode="json")
        json_dump["severity"] = invalid_severity

        # Dump into JSON string
        json_dumps = json.dumps(json_dump, indent=2)

        # Dump into a Python dict
        python_dump = r.model_dump(mode="python")
        python_dump["severity"] = invalid_severity

        for dump in (json_dump, python_dump):
            with pytest.raises(ValidationError) as excinfo:
                # Reconstitute from dict
                ValidationResult.model_validate(dump)

            assert excinfo.value.error_count() == 1
            assert excinfo.value.errors()[0]["loc"][-1] == "severity"

        with pytest.raises(ValidationError) as excinfo:
            # Reconstitute from JSON string
            ValidationResult.model_validate_json(json_dumps)

        assert excinfo.value.error_count() == 1
        assert excinfo.value.errors()[0]["loc"][-1] == "severity"
