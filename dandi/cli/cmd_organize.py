import click
from .command import main, lgr


@main.command()
@click.option(
    "-t",
    "--local-top-path",
    help="Top directory (local) of the dataset.  Files will be uploaded with "
    "paths relative to that directory",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
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
    "--dry-run",
    help="Just print proposed layout without moving any files",
    default=False,
    is_flag=True,
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
def organize(paths, local_top_path=None, format=None, invalid="fail", dry_run=False):
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

    if len(paths) == 1 and paths[0].endswith(".json"):
        # Our dumps of metadata
        dry_run = True
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

    for e in metadata:
        print(f"{e['path']} -> {e['dandi_path']}")
