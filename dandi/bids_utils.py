from .utils import pluralize


def is_valid(
    validation_result: dict,
    allow_invalid_filenames: bool = False,
    allow_missing_files: bool = False,
) -> bool:
    """Determine whether a dataset validation result marks it as valid.

    Parameters
    ----------
    validation_result: dict
        Dictionary as returned by `dandi.support.bids.validator.validate_bids()`.
    allow_missing_files: bool, optional
        Whether to consider the dataset invalid if any mandatory files are not present.
    allow_invalid_filenames: bool, optional
        Whether to consider the dataset invalid if any filenames inside are invalid.

    Returns
    -------
    bool: whether the dataset validation result marks it as valid.

    """

    if allow_invalid_filenames and allow_missing_files:
        return True
    missing_files = [
        i["regex"] for i in validation_result["schema_tracking"] if i["mandatory"]
    ]
    invalid_filenames = validation_result["path_tracking"]

    if missing_files and not allow_missing_files:
        return False
    if invalid_filenames and not allow_invalid_filenames:
        return False
    else:
        return True


def report_errors(
    validation_result: dict,
) -> None:
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
