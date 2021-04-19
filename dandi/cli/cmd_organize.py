import os
import os.path as op

import click

from .base import dandiset_path_option, devel_debug_option, lgr, map_to_click_exceptions
from ..consts import dandiset_metadata_file, file_operation_modes


@click.command()
@dandiset_path_option(
    help="A top directory (local) of the dandiset to organize files under. "
    "If not specified, dandiset current directory is under is assumed. "
    "For 'simulate' mode target dandiset/directory must not exist.",
    type=click.Path(dir_okay=True, file_okay=False),
)
# @dandiset_id_option()
@click.option(
    "--invalid",
    help="What to do if files without sufficient metadata are encountered.",
    type=click.Choice(["fail", "warn"]),
    default="fail",
    show_default=True,
)
@click.option(
    "-f",
    "--files-mode",
    help="If 'dry' - no action is performed, suggested renames are printed. "
    "If 'simulate' - hierarchy of empty files at --local-top-path is created. "
    "Note that previous layout should be removed prior this operation.  "
    "If 'auto' - whichever of symlink, hardlink, copy is allowed by system. "
    "The other modes (copy, move, symlink, hardlink) define how data files "
    "should be made available.",
    type=click.Choice(file_operation_modes),
    default="auto",
    show_default=True,
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@devel_debug_option()
@map_to_click_exceptions
def organize(
    paths,
    dandiset_path=None,
    dandiset_id=None,
    invalid="fail",
    files_mode="auto",
    devel_debug=False,
):
    """(Re)organize files according to the metadata.

    The purpose of this command is to take advantage of metadata contained in
    the .nwb files to provide datasets with consistently named files, so their
    naming reflects data they contain. In addition it will also populate
    the dataset level descriptor file dandiset.yaml with some of the
    collected metadata and statistics (e.g. number_of_cells).

    .nwb files are organized into a hierarchy of subfolders one per each
    "subject", e.g. sub-0001 if .nwb file had contained a Subject group with
    subject_id=0001.  Each file in a subject-specific subfolder follows the
    convention:

        sub-<subject_id>[_key-<value>][_mod1+mod2+...].nwb

    where following keys are considered if present in the data:

        ses -- session_id\n
        tis -- tissue_sample_id\n
        slice -- slice_id\n
        cell -- cell_id\n

    and `modX` are "modalities" as identified based on detected neural data types
    (such as "ecephys", "icephys") per extensions found in nwb-schema definitions:
    https://github.com/NeurodataWithoutBorders/nwb-schema/tree/dev/core

    In addition an "obj" key with a value corresponding to crc32 checksum of
    "object_id" is added if aforementioned keys and the list of modalities are
    not sufficient to disambiguate different files.

    You can visit https://dandiarchive.org/dandisets/drafts for a growing
    collection of (re)organized datasets (files content is original filenames).
    """
    from ..dandiset import Dandiset
    from ..metadata import get_metadata
    from ..organize import (
        create_dataset_yml_template,
        create_unique_filenames_from_metadata,
        detect_link_type,
        filter_invalid_metadata_rows,
        populate_dataset_yml,
    )
    from ..pynwb_utils import ignore_benign_pynwb_warnings
    from ..utils import Parallel, copy_file, delayed, find_files, load_jsonl, move_file

    in_place = False  # If we deduce that we are organizing in-place

    # will come handy when dry becomes proper separate option
    def dry_print(msg):
        print(f"DRY: {msg}")

    if files_mode == "dry":

        def act(func, *args, **kwargs):
            dry_print(f"{func.__name__} {args}, {kwargs}")

    else:

        def act(func, *args, **kwargs):
            lgr.debug("%s %s %s", func.__name__, args, kwargs)
            return func(*args, **kwargs)

    if dandiset_path is None:
        dandiset = Dandiset.find(os.curdir)
        if not dandiset:
            raise ValueError(
                "No --dandiset-path was provided, and no dandiset was found "
                "in/above current directory"
            )
        dandiset_path = dandiset.path
        del dandiset

    # Early checks to not wait to fail
    if files_mode == "simulate":
        # in this mode we will demand the entire output folder to be absent
        if op.exists(dandiset_path):
            # TODO: RF away
            raise RuntimeError(
                "In simulate mode %r (--top-path) must not exist, we will create it."
                % dandiset_path
            )

    ignore_benign_pynwb_warnings()

    if not paths:
        try:
            Dandiset(dandiset_path)
        except Exception as exc:
            lgr.debug("Failed to find dandiset at %s: %s", dandiset_path, exc)
            raise ValueError(
                f"No dandiset was found at {dandiset_path}, and no "
                f"paths were provided"
            )
        if files_mode not in ("dry", "move"):
            raise ValueError(
                "Only 'dry' or 'move' mode could be used to operate in-place "
                "within a dandiset (no paths were provided)"
            )
        lgr.info(f"We will organize {dandiset_path} in-place")
        in_place = True
        paths = dandiset_path

    if len(paths) == 1 and paths[0].endswith(".json"):
        # Our dumps of metadata
        metadata = load_jsonl(paths[0])
    else:
        paths = list(find_files(r"\.nwb\Z", paths=paths))
        lgr.info("Loading metadata from %d files", len(paths))
        # Done here so we could still reuse cached 'get_metadata'
        # without having two types of invocation and to guard against
        # problematic ones -- we have an explicit option on how to
        # react to those
        # Doesn't play nice with Parallel
        # with tqdm.tqdm(desc="Files", total=len(paths), unit="file", unit_scale=False) as pbar:
        failed = []

        def _get_metadata(path):
            try:
                meta = get_metadata(path)
            except Exception as exc:
                meta = {}
                failed.append(path)
                # pbar.desc = "Files (%d failed)" % len(failed)
                lgr.debug("Failed to get metadata for %s: %s", path, exc)
            # pbar.update(1)
            meta["path"] = path
            return meta

        if not devel_debug:
            # Note: It is Python (pynwb) intensive, not IO, so ATM there is little
            # to no benefit from Parallel without using multiproc!  But that would
            # complicate progress bar indication... TODO
            metadata = list(
                Parallel(n_jobs=-1, verbose=10)(
                    delayed(_get_metadata)(path) for path in paths
                )
            )
        else:
            metadata = list(map(_get_metadata, paths))
        if failed:
            lgr.warning(
                "Failed to load metadata for %d out of %d files",
                len(failed),
                len(paths),
            )

    metadata, skip_invalid = filter_invalid_metadata_rows(metadata)
    if skip_invalid:
        msg = (
            "%d out of %d files were found not containing all necessary "
            "metadata: %s"
            % (
                len(skip_invalid),
                len(metadata) + len(skip_invalid),
                ", ".join(m["path"] for m in skip_invalid),
            )
        )
        if invalid == "fail":
            raise ValueError(msg)
        elif invalid == "warn":
            lgr.warning(msg + " They will be skipped")
        else:
            raise ValueError(f"invalid has an invalid value {invalid}")

    if not op.exists(dandiset_path):
        act(os.makedirs, dandiset_path)

    if files_mode == "auto":
        files_mode = detect_link_type(dandiset_path)

    dandiset_metadata_filepath = op.join(dandiset_path, dandiset_metadata_file)
    if op.lexists(dandiset_metadata_filepath):
        if dandiset_id is not None:
            lgr.info(f"We found {dandiset_metadata_filepath} present")
    elif dandiset_id:
        # TODO: request it from the server and store into dandiset.yaml
        lgr.debug(
            f"Requesting metadata for the dandiset {dandiset_id} and"
            f" storing into {dandiset_metadata_filepath}"
        )
        # TODO
        pass
    elif files_mode == "simulate":
        lgr.info(
            f"In 'simulate' mode, since no {dandiset_metadata_filepath} found, "
            f"we will use a template"
        )
        create_dataset_yml_template(dandiset_metadata_filepath)
    elif files_mode == "dry":
        lgr.info(f"We do nothing about {dandiset_metadata_filepath} in 'dry' mode.")
        dandiset_metadata_filepath = None
    else:
        lgr.warning(
            f"Found no {dandiset_metadata_filepath}. This file will lack mandatory metadata."
            f" For upload later on, you must first use 'register'"
            f" to obtain a dandiset id.  Meanwhile you could use 'simulate' mode"
            f" to generate a sample dandiset.yaml if you are interested."
        )
    # If it was not decided not to do that above:
    if dandiset_metadata_filepath:
        populate_dataset_yml(dandiset_metadata_filepath, metadata)

    metadata = create_unique_filenames_from_metadata(metadata)

    # Verify first that the target paths do not exist yet, and fail if they do
    # Note: in "simulate" mode we do early check as well, so this would be
    # duplicate but shouldn't hurt
    existing = []
    for e in metadata:
        dandi_fullpath = op.join(dandiset_path, e["dandi_path"])
        if op.exists(dandi_fullpath):
            # It might be the same file, then we would not complain
            if not (
                op.realpath(e["path"])
                == op.realpath(op.join(dandiset_path, e["dandi_path"]))
            ):
                existing.append(dandi_fullpath)
            # TODO: it might happen that with "move" we are renaming files
            # so there is an existing, which also gets moved away "first"
            # May be we should RF so the actual loop below would be first done
            # "dry", collect info on what is actually to be done, and then we would complain here
    if existing:
        raise AssertionError(
            "%d paths already exist: %s%s.  Remove them first."
            % (
                len(existing),
                ", ".join(existing[:5]),
                " and more" if len(existing) > 5 else "",
            )
        )

    # we should take additional care about paths if both top_path and
    # provided paths are relative
    use_abs_paths = op.isabs(dandiset_path) or any(
        op.isabs(e["path"]) for e in metadata
    )
    skip_same = []
    acted_upon = []
    for e in metadata:
        dandi_path = e["dandi_path"]
        dandi_fullpath = op.join(dandiset_path, dandi_path)
        dandi_abs_fullpath = (
            op.abspath(dandi_fullpath)
            if not op.isabs(dandi_fullpath)
            else dandi_fullpath
        )
        dandi_dirpath = op.dirname(dandi_fullpath)  # could be sub-... subdir

        e_path = e["path"]
        e_abs_path = e_path

        if not op.isabs(e_path):
            e_abs_path = op.abspath(e_path)
            if use_abs_paths:
                e_path = e_abs_path
            elif files_mode == "symlink":  # path should be relative to the target
                e_path = op.relpath(e_abs_path, dandi_dirpath)

        if dandi_abs_fullpath == e_abs_path:
            lgr.debug("Skipping %s since the same in source/destination", e_path)
            skip_same.append(e)
            continue
        elif files_mode == "symlink" and op.realpath(dandi_abs_fullpath) == op.realpath(
            e_abs_path
        ):
            lgr.debug(
                "Skipping %s since mode is symlink and both resolve to the same path",
                e_path,
            )
            skip_same.append(e)
            continue

        if (
            files_mode == "dry"
        ):  # TODO: this is actually a files_mode on top of modes!!!?
            dry_print(f"{e_path} -> {dandi_path}")
        else:
            if not op.exists(dandi_dirpath):
                os.makedirs(dandi_dirpath)
            if files_mode == "simulate":
                os.symlink(e_path, dandi_fullpath)
                continue
            #
            if files_mode == "symlink":
                os.symlink(e_path, dandi_fullpath)
            elif files_mode == "hardlink":
                os.link(e_path, dandi_fullpath)
            elif files_mode == "copy":
                copy_file(e_path, dandi_fullpath)
            elif files_mode == "move":
                move_file(e_path, dandi_fullpath)
            else:
                raise NotImplementedError(files_mode)
            acted_upon.append(e)

    if acted_upon and in_place:
        # We might need to cleanup a bit - e.g. prune empty directories left
        # by the move in in-place mode
        dirs = set(op.dirname(e["path"]) for e in acted_upon)
        for d in sorted(dirs)[::-1]:  # from longest to shortest
            if op.exists(d):
                try:
                    os.rmdir(d)
                    lgr.info(f"Removed mepty directory {d}")
                except Exception as exc:
                    lgr.debug("Failed to remove directory %s: %s", d, exc)

    def msg_(msg, n, cond=None):
        if hasattr(n, "__len__"):
            n = len(n)
        if cond is None:
            cond = bool(n)
        if not cond:
            return ""
        return msg % n

    lgr.info(
        "Organized %d%s paths%s.%s Visit %s/",
        len(acted_upon),
        msg_(" out of %d", metadata, len(metadata) != len(acted_upon)),
        msg_(" (%d same existing skipped)", skip_same),
        msg_(" %d invalid not considered.", skip_invalid),
        dandiset_path.rstrip("/"),
    )
