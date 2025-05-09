import json

import pytest

from dandi.validate import (
    Origin,
    OriginType,
    Scope,
    Severity,
    ValidationResult,
    Validator,
)


class TestValidationResult:
    @pytest.mark.parametrize(
        ("severity", "expected_json"),
        [
            (Severity.INFO, "INFO"),
            (Severity.WARNING, "WARNING"),
            (Severity.ERROR, "ERROR"),
        ],
    )
    def test_severity_serialization(self, severity, expected_json):
        """
        Test serialization of `Severity`
        """
        r = ValidationResult(
            id="foo",
            origin=Origin(
                type=OriginType.INTERNAL,
                validator=Validator.dandi,
                validator_version="123",
            ),
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
