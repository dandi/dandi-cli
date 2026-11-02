from click.testing import CliRunner
import pytest
from pytest_mock import MockerFixture

from ..base import map_to_click_exceptions
from ..cmd_upload import upload
from ...exceptions import UploadValidationError
from ...upload import ZarrMode


@pytest.mark.ai_generated
def test_upload_validation_error_has_no_traceback(mocker: MockerFixture) -> None:
    mocker.patch.object(map_to_click_exceptions, "_do_map", False)
    mocker.patch(
        "dandi.upload.upload",
        side_effect=UploadValidationError("failed validation"),
    )

    result = CliRunner().invoke(upload)

    assert result.exit_code == 1
    assert result.output == "Error: failed validation\n"
    assert "Traceback" not in result.output


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "args,expected",
    [
        ([], ZarrMode.FULL),
        (["--zarr-mode", "full"], ZarrMode.FULL),
        (["--zarr-mode", "patch"], ZarrMode.PATCH),
    ],
)
def test_upload_zarr_mode_option(
    mocker: MockerFixture, args: list[str], expected: ZarrMode
) -> None:
    """`--zarr-mode` takes the enum *values* and reaches `upload()`.

    Regression test: with ``click >= 8.2`` a plain ``click.Choice`` over an
    ``Enum`` matches members on ``.name``, so the command line would have
    required ``FULL``/``PATCH`` and even the ``full`` default would fail to
    validate -- making *every* ``dandi upload`` invocation exit with a usage
    error (exit code 2).  ``EnumChoice`` matches on ``.value`` instead.
    """
    upload_mock = mocker.patch("dandi.upload.upload")

    result = CliRunner().invoke(upload, args)

    assert result.exit_code == 0, result.output
    assert upload_mock.call_args.kwargs["zarr_mode"] == expected
