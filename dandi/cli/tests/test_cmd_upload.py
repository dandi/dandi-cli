from click.testing import CliRunner
import pytest
from pytest_mock import MockerFixture

from ..cmd_upload import upload
from ...exceptions import UploadValidationError


@pytest.mark.ai_generated
def test_upload_validation_error_has_no_traceback(mocker: MockerFixture) -> None:
    mocker.patch(
        "dandi.upload.upload",
        side_effect=UploadValidationError("failed validation"),
    )

    result = CliRunner().invoke(upload)

    assert result.exit_code == 1
    assert result.output == "Error: failed validation\n"
    assert "Traceback" not in result.output
