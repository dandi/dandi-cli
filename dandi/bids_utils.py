from typing import Optional

import click

from .utils import pluralize


def evaluate_validation(
    validation_result: dict,
    allow_errors: Optional[bool] = False,
    cli_output: Optional[bool] = False,
) -> bool:
    missing_files = [
        pattern["regex"]
        for pattern in validation_result["schema_tracking"]
        if pattern["mandatory"]
    ]
    error_list = []
    if missing_files:
        error_substring = (
            f"{pluralize(len(missing_files), 'filename pattern')} required "
            "by BIDS could not be found"
        )
        error_list.append(error_substring)
    if validation_result["path_tracking"]:
        error_substring = (
            f"{pluralize(len(validation_result['path_tracking']), 'filename')} "
            "did not match any pattern known to BIDS"
        )
        error_list.append(error_substring)
    if error_list:
        if cli_output:
            error_string = " and ".join(error_list)
            error_string = f"Summary: {error_string}."
            click.secho(
                error_string,
                bold=True,
                fg="red",
            )
        if not allow_errors:
            return False
    return True
