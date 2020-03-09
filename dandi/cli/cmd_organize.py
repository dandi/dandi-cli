import click
import os
import os.path as op

from collections import Counter

from .command import main, lgr
from ..consts import dandiset_metadata_file


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
    "Note that previous files should be removed prior this operation.  The "
    "other modess (cp, mv, symlink, hardlink) define how data files should "
    "be made available.",
    type=click.Choice(
        ["dry", "simulate", "cp", "hardlink", "softlink"]
    ),  # TODO: hardlink, symlink
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
    from ..utils import delayed, find_files, load_jsonl, Parallel
    from ..pynwb_utils import ignore_benign_pynwb_warnings
    from ..organize import (
        create_unique_filenames_from_metadata,
        filter_invalid_metadata_rows,
        populate_dataset_yml,
        create_dataset_yml_template,
    )
    from ..metadata import get_metadata

    if mode not in ("dry", "simulate"):
        raise NotImplementedError(mode)
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
        # without having two types of invocation
        def _get_metadata_with_path(path):
            meta = get_metadata(path)
            meta["path"] = path
            return meta

        metadata = list(
            Parallel()(delayed(_get_metadata_with_path)(path) for path in paths)
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

    os.makedirs(top_path)
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
    else:
        lgr.warning(
            f"Found no {dandiset_metadata_filepath} and no --dandiset-id was"
            f" specified.  For upload later on, you must first use 'register'"
            f" to obtain a dandiset id.  Meanwhile you could use 'simulate' mode"
            f" to generate a sample dandiset.yaml if you are interested."
        )
        dandiset_metadata_filepath = None

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
            for m in metadata:
                if m["dandi_path"] == p:
                    orig_paths.append(m["path"])
            non_unique[p] = orig_paths  # overload with the list instead of count
        # TODO: in future should be an error, for now we will lay them out
        #  as well to ease investigation
        lgr.warning(
            "%d out of %d paths are not unique:\n%s"
            % (
                len(non_unique),
                len(all_paths),
                "\n".join("   %s: %s" % i for i in non_unique.items()),
            )
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

    for e in metadata:
        dandi_path = e["dandi_path"]
        dandi_fullpath = op.join(top_path, dandi_path)
        dandi_dirpath = op.dirname(dandi_fullpath)
        # print(f"{e['path']} -> {e['dandi_path']}")
        if mode == "dry":
            print(f"{e['path']} -> {e['dandi_path']}")
        elif mode == "simulate":
            if not op.exists(dandi_dirpath):
                os.makedirs(dandi_dirpath)
            if dandi_path in non_unique:
                # we will just populate all copies upon first hit
                if op.exists(dandi_fullpath):
                    assert op.isdir(dandi_fullpath)
                else:
                    os.makedirs(dandi_fullpath)
                    for i, filename in enumerate(non_unique[dandi_path]):
                        os.symlink(filename, op.join(dandi_fullpath, str(i)))
            else:
                # TODO: here and above -- ideally we should somehow reference to the original
                # files really.  We might need a dedicated option to make organized
                # version go into another folder.
                os.symlink(e["path"], dandi_fullpath)
        else:
            raise NotImplementedError(mode)

    lgr.info(
        "Finished processing %d paths (%d invalid skipped) with %d having duplicates. Visit %s"
        % (len(metadata), len(metadata_invalid), len(non_unique), top_path)
    )
