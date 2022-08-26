from .utils import pluralize
from .validate import ValidationResult


def print_validation_results(
    validation_result: list[ValidationResult],
    # TODO: options for control
    #  - either report warnings, hints, ...
    #  - either report groupped by severity, record.id
) -> None:
    raise NotImplementedError("TODO: RF to use ValidationResult records")
    import click

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
        error_string = " and ".join(error_list)
        error_string = f"Summary: {error_string}."
        click.secho(
            error_string,
            bold=True,
            fg="red",
        )
    else:
        click.secho(
            "All filenames are BIDS-valid and no mandatory files are missing.",
            bold=True,
            fg="green",
        )
