import click
import os
import os.path as op
from glob import glob
from collections import Counter

from .command import main, lgr
from ..consts import dandiset_metadata_file, file_operation_modes


@main.command()
@click.option(
    "-t",
    "--top-path",
    help="Top directory (local) of the dataset to organize files under.  "
    "If not specified, current directory is assumed. "
    "For 'simulate' mode target directory must not exist.",
    type=click.Path(dir_okay=True, file_okay=False),  # exists=True,
    default=os.curdir,
)
@click.option(
    "-f",
    "--format",
    help="Python .format() template to be used to create a full path to a file. "
    "It will be provided a dict with metadata fields and some prepared "
    "fields such as '_filename' which is prepared according to internal rules.",
)
@click.option(
    "--dandiset-id",
    help=f"ID of the dandiset on DANDI archive.  Necessary to populate "
    f"{dandiset_metadata_file}. Please use 'register' command to first "
    f"register a new dandiset.",
    # TODO: could add a check for correct regexp
)
@click.option(
    "--invalid",
    help="What to do if files without sufficient metadata are encountered.",
    type=click.Choice(["fail", "warn"]),
    default="fail",
)
@click.option(
    "--mode",
    help="If 'dry' - no action is performed, suggested renames are printed. "
    "I 'simulate' - hierarchy of empty files at --local-top-path is created. "
    "Note that previous layout should be removed prior this operation.  The "
    "other modes (copy, move, symlink, hardlink) define how data files should "
    "be made available.",
    type=click.Choice(file_operation_modes),
    default="dry",
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
def organize(
    paths, top_path=os.curdir, format=None, dandiset_id=None, invalid="fail", mode="dry"
):
    """(Re)organize files according to the metadata.

    The purpose of this command is to provide datasets with consistently named files,
    so their naming reflects data they contain.

    Based on the metadata contained in the considered files, it will also generate
    the dataset level descriptor file, which possibly later would need to
    be adjusted "manually".

    See https://github.com/dandi/metadata-dumps/tree/organize/organized/ for
    examples of (re)organized datasets (files content is original filenames)
    """
    if format:
        raise NotImplementedError("format support is not yet implemented")
    # import tqdm
    from ..utils import copy_file, delayed, find_files, load_jsonl, move_file, Parallel
    from ..pynwb_utils import ignore_benign_pynwb_warnings
    from ..organize import (
        create_unique_filenames_from_metadata,
        filter_invalid_metadata_rows,
        populate_dataset_yml,
        create_dataset_yml_template,
    )
    from ..metadata import get_metadata

    # will come handy when dry becomes proper separate option
    def dry_print(msg):
        print(f"DRY: {msg}")

    if mode == "dry":

        def act(func, *args, **kwargs):
            dry_print(f"{func.__name__} {args}, {kwargs}")

    else:

        def act(func, *args, **kwargs):
            lgr.debug("%s %s %s", func.__name__, args, kwargs)
            return func(*args, **kwargs)

    # Early checks to not wait to fail
    if mode == "simulate":
        # in this mode we will demand the entire output folder to be absent
        if op.exists(top_path):
            # TODO: RF away
            raise RuntimeError(
                "In simulate mode %r (--top-path) must not exist, we will create it."
                % top_path
            )

    ignore_benign_pynwb_warnings()

    if len(paths) == 1 and paths[0].endswith(".json"):
        # Our dumps of metadata
        metadata = load_jsonl(paths[0])
    else:
        paths = list(find_files("\.nwb$", paths=paths))
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

        # Note: It is Python (pynwb) intensive, not IO, so ATM there is little
        # to no benefit from Parallel without using multiproc!  But that would
        # complicate progress bar indication... TODO
        metadata = list(
            Parallel(n_jobs=-1, verbose=10)(
                delayed(_get_metadata)(path) for path in paths
            )
        )
        if failed:
            lgr.warning(
                "Failed to load metadata for %d out of %d files",
                len(failed),
                len(paths),
            )

    metadata, metadata_invalid = filter_invalid_metadata_rows(metadata)
    if metadata_invalid:
        msg = (
            "%d out of %d files were found not containing all necessary "
            "metadata: %s"
            % (
                len(metadata_invalid),
                len(metadata) + len(metadata_invalid),
                ", ".join(m["path"] for m in metadata_invalid),
            )
        )
        if invalid == "fail":
            raise ValueError(msg)
        elif invalid == "warn":
            lgr.warning(msg + " They will be skipped")
        else:
            raise ValueError(f"invalid has an invalid value {invalid}")

    if not op.exists(top_path):
        act(os.makedirs, top_path)

    dandiset_metadata_filepath = op.join(top_path, dandiset_metadata_file)
    if op.lexists(dandiset_metadata_filepath):
        if dandiset_id is not None:
            lgr.info(
                f"We found {dandiset_metadata_filepath} present, provided"
                f" {dandiset_id} will be ignored."
            )
    elif dandiset_id:
        # TODO: request it from the server and store into dandiset.yaml
        lgr.debug(
            f"Requesting metadata for the dandiset {dandiset_id} and"
            f" storing into {dandiset_metadata_filepath}"
        )
        # TODO
        pass
    elif mode == "simulate":
        lgr.info(
            f"In 'simulate' mode, since no {dandiset_metadata_filepath} found, "
            f"we will use a template"
        )
        create_dataset_yml_template(dandiset_metadata_filepath)
    elif mode == "dry":
        lgr.info(f"We do nothing about {dandiset_metadata_filepath} in 'dry' mode.")
        dandiset_metadata_filepath = None
    else:
        lgr.warning(
            f"Found no {dandiset_metadata_filepath} and no --dandiset-id was"
            f" specified. This file will lack mandatory metadata."
            f" For upload later on, you must first use 'register'"
            f" to obtain a dandiset id.  Meanwhile you could use 'simulate' mode"
            f" to generate a sample dandiset.yaml if you are interested."
        )
    # If it was not decided not to do that above:
    if dandiset_metadata_filepath:
        populate_dataset_yml(dandiset_metadata_filepath, metadata)

    metadata = create_unique_filenames_from_metadata(metadata)

    # Verify that we got unique paths
    all_paths = [m["dandi_path"] for m in metadata]
    all_paths_unique = set(all_paths)
    non_unique = {}
    if not len(all_paths) == len(all_paths_unique):
        counts = Counter(all_paths)
        non_unique = {p: c for p, c in counts.items() if c > 1}
        # Let's prepare informative listing
        for p in non_unique:
            orig_paths = []
            for e in metadata:
                if e["dandi_path"] == p:
                    orig_paths.append(e["path"])
            non_unique[p] = orig_paths  # overload with the list instead of count
        msg = "%d out of %d paths are not unique:\n%s" % (
            len(non_unique),
            len(all_paths),
            "\n".join("   %s: %s" % i for i in non_unique.items()),
        )
        if mode == "simulate":
            # TODO: in future should be an error, for now we will lay them out
            #  as well to ease investigation
            lgr.warning(
                msg + "\nIn this mode we will still produce files layout, and "
                "each non-unique file will be a directory where each file "
                "would be just a numbered symlink to the original."
            )
        else:
            raise RuntimeError(
                msg + "\nPlease adjust/provide metadata in your .nwb files to "
                "disambiguate.  You can also use 'simulate' mode to "
                "produce a tentative layout."
            )

    # Verify first that the target paths do not exist yet, and fail if they do
    # Note: in "simulate" mode we do early check as well, so this would be
    # duplicate but shouldn't hurt
    existing = []
    for e in metadata:
        dandi_fullpath = op.join(top_path, e["dandi_path"])
        if op.exists(dandi_fullpath):
            existing.append(dandi_fullpath)

    if existing:
        raise AssertionError(
            "%d paths already exists: %s%s.  Remove them first"
            % (
                len(existing),
                ", ".join(existing[:5]),
                " and more" if len(existing) > 5 else "",
            )
        )

    # we should take additional care about paths if both top_path and
    # provided paths are relative
    use_abs_paths = op.isabs(top_path) or any(op.isabs(e["path"]) for e in metadata)
    for e in metadata:
        dandi_path = e["dandi_path"]
        dandi_fullpath = op.join(top_path, dandi_path)
        dandi_dirpath = op.dirname(dandi_fullpath)  # could be sub-... subdir

        e_path = e["path"]
        if not op.isabs(e_path):
            abs_path = op.abspath(e_path)
            if use_abs_paths:
                e_path = abs_path
            else:
                e_path = op.relpath(abs_path, dandi_dirpath)

        if mode == "dry":  # TODO: this is actually a mode on top of modes!!!?
            dry_print(f"{e['path']} -> {e['dandi_path']}")
        else:
            if not op.exists(dandi_dirpath):
                os.makedirs(dandi_dirpath)
            if mode == "simulate":
                if dandi_path in non_unique:
                    if op.exists(dandi_fullpath):
                        assert op.isdir(dandi_fullpath)
                    else:
                        os.makedirs(dandi_fullpath)
                    n = len(glob(op.join(dandi_fullpath, "*")))
                    os.symlink(
                        op.join(os.pardir, e_path), op.join(dandi_fullpath, str(n + 1))
                    )
                else:
                    os.symlink(e_path, dandi_fullpath)
                continue
            #
            assert dandi_path not in non_unique
            if mode == "symlink":
                os.symlink(e_path, dandi_fullpath)
            elif mode == "hardlink":
                os.link(e_path, dandi_fullpath)
            elif mode == "copy":
                copy_file(e_path, dandi_fullpath)
            elif mode == "move":
                move_file(e_path, dandi_fullpath)
            else:
                raise NotImplementedError(mode)

    lgr.info(
        "Finished processing %d paths (%d invalid skipped) with %d having duplicates. Visit %s"
        % (len(metadata), len(metadata_invalid), len(non_unique), top_path)
    )
