import click
import os
import os.path as op

from collections import Counter

from .command import main, lgr


@main.command()
@click.option(
    "-t",
    "--top-path",
    help="Top directory (local) of the dataset.  If not specified, current "
    "directory is assumed.  Files will be (re)organized into that directory. "
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
    "--invalid",
    help="What to do if files without sufficient metadata are encountered.",
    type=click.Choice(["fail", "warn"]),
    default="fail",
)
@click.option(
    "--mode",
    help="If 'dry' - no action is performed, suggested renames are printed. "
    "I 'simulate' - hierarchy of empty files at --local-top-path is created. "
    "Note that previous files should be removed prior this operation.",
    type=click.Choice(["act", "dry", "simulate"]),
    default="act",
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
def organize(paths, top_path=os.curdir, format=None, invalid="fail", mode="act"):
    """(Re)organize (and rename) files according to the metadata.

    The purpose of this command is to provide datasets with consistently named files,
    so their naming reflects data they contain.

    Based on the metadata contained in the considered files, it will also generate
    the dataset level descriptor file, which possibly later would need to
    be adjusted "manually".
    """
    if format:
        raise NotImplementedError("format support is not yet implemented")
    from ..utils import load_jsonl, find_files
    from ..organize import (
        create_unique_filenames_from_metadata,
        filter_invalid_metadata_rows,
    )

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

    if len(paths) == 1 and paths[0].endswith(".json"):
        # Our dumps of metadata
        metadata = load_jsonl(paths[0])
    else:
        paths = list(find_files("\.nwb$", paths=paths))
        lgr.info("Loading metadata from %d files", len(paths))
        metadata = []
        raise NotImplementedError(
            "For now we are working only with already extracted metadata"
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
        "Finished processing %d paths with %d having duplicates. Visit %s"
        % (len(metadata), len(non_unique), top_path)
    )
