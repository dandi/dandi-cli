from dandi.bids_validator_xs import validate_bids
from dandi.dandiapi import DandiAPIClient

from .utils import get_logger, pluralize

lgr = get_logger()


def is_valid(
    validation_result: dict,
    allow_invalid_filenames: bool = False,
    allow_missing_files: bool = False,
) -> bool:
    """Determine whether a dataset validation result marks it as valid.

    Parameters
    ----------
    validation_result: dict
        Dictionary as returned by `dandi.bids_validator_xs.validate_bids()`.
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


def print_summary(
    summary,
    sections=[
        ["subject", "session"],
        ["session", "subject"],
        ["subject", "sample"],
        ["subject", "stain"],
    ],
    max_detail=3,
):
    out = ""
    for section in sections:
        base = section[0]
        detail = section[1]
        out += f"Here is the {base} to {detail} summary:\n"
        for entry in summary[base + "_summary"]:
            details = entry[detail + "s"]
            detail_literal = f"{len(details)} ("
            if len(details) > max_detail:
                detail_literal += ", ".join(details[:max_detail]) + ", ...)"
            else:
                detail_literal += ", ".join(details) + ")"
            out += f"\t-`{entry[base]}`\t{detail_literal}\n"
    print(out)


def summary(
    dandi_id,
    entities=["subject", "session", "sample", "stain"],
):

    with DandiAPIClient.for_dandi_instance("dandi") as client:
        dandiset = client.get_dandiset(dandi_id)
        path_list = []
        for asset in dandiset.get_assets():
            i = f"dummy/{asset.path}"
            if "sub-MITU01h3" in i and "sub-MITU01" in i:
                lgr.warning("Fixing subject field inconsistencies:")
                lgr.warning(" - Pre-repair:  %s", i)
                i = i.replace("sub-MITU01h3", "sub-MITU01")
                lgr.warning(" + Post-repair: %s", i)
            # ome.zarr support pending:
            # https://github.com/dandi/dandi-cli/pull/1050
            if "ome.zarr" not in i:
                path_list.append(i)

    result = validate_bids(path_list, dummy_paths=True)
    for i in result["path_tracking"]:
        lgr.warning("`%s` was not matched by any BIDS regex pattern.", i)
    match_listing = result["match_listing"]
    entity_sets = {}
    for entity in entities:
        entity_sets[entity] = set(
            [i[entity] for i in match_listing if entity in i.keys()]
        )

    summary_full = {}
    for entity in entities:
        sub_summary = []
        for value in entity_sets[entity]:
            entry = {}
            entry[entity] = value
            for _entity in entities:
                if _entity == entity:
                    continue
                entry[_entity + "s"] = list(
                    set(
                        [
                            i[_entity]
                            for i in match_listing
                            if entity in i.keys()
                            and _entity in i.keys()
                            and i[entity] == value
                        ]
                    )
                )
            sub_summary.append(entry)
        summary_full[entity + "_summary"] = sub_summary
    print_summary(summary_full)
