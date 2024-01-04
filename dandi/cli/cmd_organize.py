from __future__ import annotations

import click

from .base import dandiset_path_option, devel_debug_option, map_to_click_exceptions
from ..consts import dandi_layout_fields
from ..organize import CopyMode, FileOperationMode, OrganizeInvalid


@click.command()
@dandiset_path_option(
    help="The root directory of the Dandiset to organize files under. "
    "If not specified, the Dandiset under the current directory is assumed. "
    "For 'simulate' mode, the target Dandiset/directory must not exist.",
    type=click.Path(dir_okay=True, file_okay=False),
)
@click.option(
    "--invalid",
    help="What to do if files without sufficient metadata are encountered.",
    type=click.Choice(list(OrganizeInvalid)),
    default="fail",
    show_default=True,
)
@click.option(
    "-f",
    "--files-mode",
    help="If 'dry' - no action is performed, suggested renames are printed. "
    "If 'simulate' - hierarchy of empty files at --dandiset-path is created. "
    "Note that previous layout should be removed prior to this operation.  "
    "If 'auto' - whichever of symlink, hardlink, copy is allowed by system. "
    "The other modes (copy, move, symlink, hardlink) define how data files "
    "should be made available.",
    type=click.Choice(list(FileOperationMode)),
    default="auto",
    show_default=True,
)
@click.option(
    "--update-external-file-paths",
    is_flag=True,
    default=False,
    help="Rewrite the 'external_file' arguments of ImageSeries in NWB files. "
    "The new values will correspond to the new locations of the video files "
    "after being organized. "
    "This option requires --files-mode to be 'copy' or 'move'",
)
@click.option(
    "--media-files-mode",
    type=click.Choice(list(CopyMode)),
    default=None,
    help="How to relocate video files referenced by NWB files",
)
@click.option(
    "--required-field",
    "required_fields",
    type=click.Choice(list(dandi_layout_fields)),
    multiple=True,
    help=(
        "Force a given field to be included in the organized filename of any"
        " file for which it is nonempty.  Can be specified multiple times."
    ),
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("-J", "--jobs", type=int, help="Number of jobs during organization")
@devel_debug_option()
@map_to_click_exceptions
def organize(
    paths: tuple[str, ...],
    required_fields: tuple[str, ...],
    dandiset_path: str | None,
    invalid: OrganizeInvalid,
    files_mode: FileOperationMode,
    media_files_mode: CopyMode | None,
    update_external_file_paths: bool,
    jobs: int | None,
    devel_debug: bool = False,
) -> None:
    """(Re)organize NWB files according to their metadata.

    The purpose of this command is to take advantage of metadata contained in
    .nwb files to provide datasets with consistently-named files whose names
    reflect the data they contain.

    .nwb files are organized into a hierarchy of subfolders, one per "subject",
    e.g., `sub-0001` if an .nwb file contained a Subject group with
    `subject_id=0001`.  Each file in a subject-specific subfolder follows the
    pattern:

        sub-<subject_id>[_key-<value>][_mod1+mod2+...].nwb

    where the following keys are considered if present in the data:

    \b
        ses -- session_id
        tis -- tissue_sample_id
        slice -- slice_id
        cell -- cell_id

    and `modX` are "modalities" as identified based on detected neural data
    types (such as "ecephys", "icephys") per extensions found in nwb-schema
    definitions:
    https://github.com/NeurodataWithoutBorders/nwb-schema/tree/dev/core

    In addition, an "obj" key with a value corresponding to the crc32 checksum
    of "object_id" is added if the aforementioned keys and the list of
    modalities are not sufficient to disambiguate different files.

    You can visit https://dandiarchive.org for a growing collection of
    (re)organized dandisets.
    """
    from ..organize import organize

    organize(
        paths,
        dandiset_path=dandiset_path,
        invalid=invalid,
        files_mode=files_mode,
        devel_debug=devel_debug,
        update_external_file_paths=update_external_file_paths,
        media_files_mode=media_files_mode,
        required_fields=required_fields,
        jobs=jobs,
    )
