"""
Commands definition for DANDI command line interface
"""

import datetime
import os
import os.path as op
import sys
import time

import click
from click_didyoumean import DYMGroup

import logging
from .. import get_logger, set_logger_level

from collections import OrderedDict

from .. import __version__

# Delay imports leading to import of heavy modules such as pynwb and h5py
# Import at the point of use
# from ..pynwb_utils import ...

lgr = get_logger()

#
# Main group
#


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(__version__)
    ctx.exit()


# group to provide commands
@click.group(cls=DYMGroup)
@click.option(
    "--version", is_flag=True, callback=print_version, expose_value=False, is_eager=True
)
@click.option(
    "-l",
    "--log-level",
    help="Log level (TODO non-numeric values)",
    type=click.IntRange(1, 40),
    default=logging.INFO,
)
@click.option("--pdb", help="Fall into pdb if errors out", is_flag=True)
def main(log_level, pdb=False):
    set_logger_level(get_logger(), log_level)  # common one
    if pdb:
        from ..utils import setup_exceptionhook

        setup_exceptionhook()


#
# ls
#

# TODO: all the recursion options etc
def get_files(paths, recursive=True, recurion_limit=None):
    """Given a list of paths, return a list of paths
    """
    # For now we support only individual files
    dirs = list(filter(op.isdir, paths))
    if dirs:
        raise NotImplementedError(
            "ATM supporting only listing of individual files, no recursive "
            "operation. Was provided following directories: {}".format(", ".join(dirs))
        )
    return paths


def get_metadata_pyout(path, keys=None, process_paths=None):
    from ..pynwb_utils import get_metadata, get_nwb_version

    def fn():
        rec = {}
        try:
            # No need for calling get_metadata if no keys are needed from it
            if keys is None or list(keys) != ["nwb_version"]:
                try:
                    meta = get_metadata(path)
                    # normalize some fields and remove completely empty
                    for f, v in meta.items():
                        if keys is not None and f not in keys:
                            continue
                        if isinstance(v, (tuple, list)):
                            v = ", ".join(v)
                        if v:
                            rec[f] = v
                except Exception as exc:
                    lgr.debug("Failed to get metadata from %s: %s", path, exc)

            if "nwb_version" not in rec:
                # Let's at least get that one
                try:
                    rec["nwb_version"] = get_nwb_version(path) or ""
                except Exception as exc:
                    rec["nwb_version"] = "ERROR"
                    lgr.debug("Failed to get even nwb_version from %s: %s", path, exc)
            return rec
        finally:
            # TODO: this is a workaround, remove after
            # https://github.com/pyout/pyout/issues/87 is resolved
            if process_paths is not None and path in process_paths:
                process_paths.remove(path)

    return fn


@main.command()
@click.option(
    "-F",
    "--fields",
    help="Comma-separated list of fields to display. "
    "An empty value to trigger a list of "
    "available fields to be printed out",
)
@click.option(
    "-f",
    "--format",
    help="Choose the format/frontend for output. If 'auto', 'pyout' will be "
    "used in case of multiple files, and 'yaml' for a single file.",
    type=click.Choice(["auto", "pyout", "json", "json_pp", "yaml"]),
    default="auto",
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=False))
def ls(paths, fields=None, format="auto"):
    """List file size and selected set of metadata fields
    """
    from ..consts import metadata_all_fields

    all_fields = sorted(["path", "size"] + list(metadata_all_fields))

    # TODO: more logical ordering in case of fields = None
    from .formatter import JSONFormatter, YAMLFormatter, PYOUTFormatter

    # TODO: avoid
    from ..support.pyout import PYOUT_SHORT_NAMES, PYOUT_SHORT_NAMES_rev

    if fields is not None:
        if fields.strip() == "":
            for field in all_fields:
                s = field
                if field in PYOUT_SHORT_NAMES:
                    s += " or %s" % PYOUT_SHORT_NAMES[field]
                click.secho(s)
            raise SystemExit(0)
        fields = fields.split(",")
        # Map possibly present short names back to full names
        fields = [PYOUT_SHORT_NAMES_rev.get(f.lower(), f) for f in fields]
        unknown_fields = set(fields).difference(all_fields)
        if unknown_fields:
            raise ValueError(
                "Following fields are not known: %s" % ", ".join(unknown_fields)
            )

    # For now we support only individual files
    files = get_files(paths)

    if not files:
        return

    if format == "auto":
        format = "yaml" if len(files) == 1 else "pyout"

    if format == "pyout":
        out = PYOUTFormatter(files=files, fields=fields)
    elif format == "json":
        out = JSONFormatter()
    elif format == "json_pp":
        out = JSONFormatter(indent=2)
    elif format == "yaml":
        out = YAMLFormatter()
    else:
        raise NotImplementedError("Unknown format %s" % format)

    if fields is not None:
        async_keys = tuple(set(metadata_all_fields).intersection(fields))
    else:
        async_keys = metadata_all_fields

    process_paths = set()
    with out:
        for path in files:
            while len(process_paths) >= 10:
                lgr.log(2, "Sleep waiting for some paths to finish processing")
                time.sleep(0.5)
            process_paths.add(path)

            rec = {}
            rec["path"] = path

            try:
                if not fields or "size" in fields:
                    rec["size"] = os.stat(path).st_size

                if async_keys:
                    cb = get_metadata_pyout(path, async_keys, process_paths)
                    if format == "pyout":
                        rec[async_keys] = cb
                    else:
                        # TODO: parallel execution
                        # For now just call callback and get all the fields
                        for k, v in cb().items():
                            rec[k] = v
            except FileNotFoundError as exc:
                lgr.debug("File is not available: %s", exc)
            except Exception as exc:
                lgr.debug("Problem obtaining metadata for %s: %s", path, exc)
            if not rec:
                lgr.debug("Skipping a record for %s since emtpy", path)
                continue
            out(rec)


#
# Validate
#


@main.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=False))
def validate(paths):
    """Validate files for NWB (and DANDI) compliance

    Exits with non-0 exit code if any file is not compliant.
    """
    files = get_files(paths)
    from ..pynwb_utils import validate as pynwb_validate, ignore_benign_pynwb_warnings

    # below we are using load_namespaces but it causes HDMF to whine if there
    # is no cached name spaces in the file.  It is benign but not really useful
    # at this point, so we ignore it although ideally there should be a formal
    # way to get relevant warnings (not errors) from PyNWB
    ignore_benign_pynwb_warnings()

    view = "one-at-a-time"  # TODO: rename, add groupped
    all_files_errors = {}
    for path in files:
        errors = pynwb_validate(path)
        if view == "one-at-a-time":
            display_errors(path, errors)
        all_files_errors[path] = errors

    if view == "groupped":
        # TODO: Most likely we want to summarize errors across files since they
        # are likely to be similar
        # TODO: add our own criteria for validation (i.e. having needed metadata)

        # # can't be done since fails to compare different types of errors
        # all_errors = sum(errors.values(), [])
        # all_error_types = []
        # errors_unique = sorted(set(all_errors))
        # from collections import Counter
        # # Let's make it
        # print(
        #     "{} unique errors in {} files".format(
        #     len(errors_unique), len(errors))
        # )
        raise NotImplementedError("TODO")

    files_with_errors = [f for f, errors in all_files_errors.items() if errors]

    if files_with_errors:
        click.secho(
            "Summary: Validation errors in {} out of {} files".format(
                len(files_with_errors), len(files)
            ),
            bold=True,
            fg="red",
        )
        raise SystemExit(1)
    else:
        click.secho(
            "Summary: No validation errors among {} file(s)".format(len(files)),
            bold=True,
            fg="green",
        )


def display_errors(path, errors):
    click.echo(
        "{}: {}".format(
            click.style(path, bold=True),
            click.style("ok", fg="green")
            if not errors
            else click.style("{} error(s)".format(len(errors)), fg="red"),
        )
    )
    for error in errors:
        click.secho("  {}".format(error), fg="red")


@main.command()
@click.option("-c", "--girder-collection", help="Girder: collection to upload to")
@click.option("-d", "--girder-top-folder")
@click.option(
    "-i",
    "--girder-instance",
    help="Girder instance to use",
    type=click.Choice(["dandi", "local"]),
    default="dandi",
)
@click.option(
    "-t",
    "--local-top-path",
    help="Top directory (local) of the dataset.  Files will be uploaded with "
    "paths relative to that directory",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
)
@click.option(
    "-e",
    "--existing",
    type=click.Choice(
        ["skip", "reupload"]
    ),  # TODO: verify-reupload (to become default)
    default="skip",
)
@click.option(
    "--validation",
    "validation_",
    type=click.Choice(["require", "skip", "ignore"]),
    default="require",
)
@click.option(
    "--fake-data",
    help="For development: fake file content (filename will be stored instead of actual load)",
    default=False,
    is_flag=True,
)
@click.option(
    "--develop-debug",
    help="For development: do not use pyout callbacks, do not swallow exception",
    default=False,
    is_flag=True,
)
@click.argument("paths", nargs=-1)  # , type=click.Path(exists=True, dir_okay=False))
def upload(
    paths,
    girder_collection,
    girder_top_folder,
    local_top_path,
    girder_instance,
    existing,
    validation_,
    fake_data,
    develop_debug,
):
    # Ensure that we have all Folders created as well
    assert local_top_path, "--local-top-path must be specified for now"
    assert girder_collection, "--collection must be specified"

    if not girder_top_folder:
        # TODO: UI
        #  Most often it would be the same directory name as of the local top dir
        girder_top_folder = op.basename(local_top_path)
        if girder_top_folder in (op.pardir, op.curdir):
            girder_top_folder = op.basename(op.realpath(local_top_path))

    import multiprocessing
    from .. import girder
    from ..pynwb_utils import get_metadata
    from ..pynwb_utils import validate as pynwb_validate
    from ..pynwb_utils import ignore_benign_pynwb_warnings
    from ..support.generatorify import generator_from_callback
    from ..support.pyout import naturalsize
    from pathlib import Path, PurePosixPath

    ignore_benign_pynwb_warnings()  # so validate doesn't whine

    client = girder.authenticate(girder_instance)

    collection_rec = girder.ensure_collection(client, girder_collection)
    lgr.debug("Working with collection %s", collection_rec)

    local_top_path = Path(local_top_path)
    girder_top_folder = PurePosixPath(girder_top_folder)

    # We will keep a shared set of "being processed" paths so
    # we could limit the number of them until
    #   https://github.com/pyout/pyout/issues/87
    # properly addressed
    process_paths = set()
    uploaded_paths = {}  # path: uploaded size

    def skip_file(msg):
        return {"status": "skipped", "message": msg}

    lock = multiprocessing.Lock()

    # TODO: we might want to always yield a full record so no field is not
    # provided to pyout to cause it to halt
    def process_path(path, relpath):
        try:
            try:
                stat = os.stat(path)
                yield {"size": stat.st_size}
            except FileNotFoundError:
                yield skip_file("ERROR: File not found")
                return
            except Exception as exc:
                # without limiting [:50] it might cause some pyout indigestion
                yield skip_file("ERROR: %s" % str(exc)[:50])
                return

            yield {"status": "checking girder"}

            girder_folder = girder_top_folder / relpath.parent

            while True:
                try:
                    lock.acquire(timeout=60)
                    # TODO: we need to make this all thread safe all the way
                    #       until uploading the file since multiple threads would
                    #       create multiple
                    folder_rec = girder.ensure_folder(
                        client, collection_rec, girder_collection, girder_folder
                    )

                    # Get (if already exists) or create an item
                    item_rec = client.createItem(
                        folder_rec["_id"], name=relpath.name, reuseExisting=True
                    )
                finally:
                    lock.release()

                file_recs = list(client.listFile(item_rec["_id"]))
                if len(file_recs) > 1:
                    raise NotImplementedError(
                        f"Item {item_rec} contains multiple files: {file_recs}"
                    )
                elif file_recs:  # there is a file already
                    if existing == "skip":
                        yield skip_file("exists already")
                        return
                    elif existing == "reupload":
                        yield {
                            "message": "exists - reuploading",
                            "status": "deleting old item",
                        }
                        # TODO: delete an item here
                        raise NotImplementedError("yarik did not find deleteItem API")
                        continue
                    else:
                        raise ValueError(existing)
                break  # no need to loop

            # we need to delete it first??? I do not see a method TODO
            if validation_ != "skip":
                yield {"status": "validating"}
                validation_errors = pynwb_validate(path)
                yield {"errors": len(validation_errors)}
                # TODO: split for dandi, pynwb errors
                if validation_errors:
                    if validation_ == "require":
                        yield skip_file("failed validation")
                        return
            else:
                # yielding empty causes pyout to get stuck or crash
                # https://github.com/pyout/pyout/issues/91
                # yield {"errors": '',}
                pass

            # Extract metadata before actual upload and skip if fails
            # TODO: allow for for non-nwb files to skip this step
            yield {"status": "extracting metadata"}
            try:
                metadata = get_metadata(path)
            except Exception as exc:
                yield skip_file("failed to extract metadata: %s" % str(exc))
                return

            yield {"status": "uploading"}
            # Upload file to an item
            # XXX TODO progress reporting back to pyout is actually tricky
            #     if possible to implement via callback since
            #     callback would need to yield somehow from the context here.
            #     yoh doesn't see how that could be done yet. In the worst
            #     case we would copy uploadFileToItem and _uploadContents
            #     and make them into generators to relay progress instead of
            #     via callback
            # https://stackoverflow.com/questions/9968592/turn-functions-with-a-callback-into-python-generators
            # has some solutions but all IMHO are abit too complex

            for r in generator_from_callback(
                lambda c: client.uploadFileToItem(
                    item_rec["_id"], path, progressCallback=c
                )
            ):
                uploaded_paths[str(path)] = r["current"]
                yield {
                    "upload": 100.0
                    * ((r["current"] / r["total"]) if r["total"] else 1.0)
                }

            # Provide metadata for the item from the file, could be done via
            #  a callback to be triggered upon successfull upload, or we could
            #  just do it "manually"
            metadata_ = {}
            for k, v in metadata.items():
                if v in ("", None):
                    continue  # degenerate, why bother
                # XXX TODO: remove this -- it is only temporary, search should handle
                if isinstance(v, str):
                    metadata_[k] = v.lower()
                elif isinstance(v, datetime.datetime):
                    metadata_[k] = str(v)
            # we will add some fields which would help us with deciding to
            # reupload or not
            metadata_["uploaded_size"] = os.stat(str(path)).st_size
            metadata_["uploaded_mtime"] = os.stat(str(path)).st_mtime

            yield {"status": "uploading metadata"}
            client.addMetadataToItem(item_rec["_id"], metadata_)

            yield {"status": "done"}

        except Exception as exc:
            if develop_debug:
                raise
            yield {"status": "ERROR", "message": str(exc)}
        finally:
            process_paths.remove(str(path))

    # We will again use pyout to provide a neat table summarizing our progress
    # with upload etc
    import pyout
    from ..support import pyout as pyouts

    # for the upload speeds we need to provide a custom  aggregate
    t0 = time.time()

    def upload_agg(*ignored):
        dt = time.time() - t0
        total = sum(uploaded_paths.values())
        if not total:
            return ""
        speed = total / dt if dt else 0
        return "%s/s" % naturalsize(speed)

    pyout_style = pyouts.get_style(hide_if_missing=False)
    pyout_style["upload"]["aggregate"] = upload_agg

    rec_fields = ("path", "size", "errors", "upload", "status", "message")
    out = pyout.Tabular(style=pyout_style, columns=rec_fields)

    with out:
        for path in paths:
            while len(process_paths) >= 10:
                lgr.log(2, "Sleep waiting for some paths to finish processing")
                time.sleep(0.5)
            process_paths.add(path)

            rec = {"path": path}
            path = Path(path)
            try:
                relpath = path.relative_to(local_top_path)
                rec["path"] = str(relpath)
                if develop_debug:
                    # DEBUG: do serially
                    for v in process_path(path, relpath):
                        print(v)
                else:
                    rec[rec_fields[1:]] = process_path(path, relpath)
            except ValueError as exc:
                # typically if local_top_path is not the top path for the path
                rec["status"] = skip_file(exc)
            out(rec)
