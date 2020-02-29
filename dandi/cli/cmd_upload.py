import datetime
import os
import sys
import time

import click
from .command import main, lgr


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
        ["skip", "reupload", "refresh"]
    ),  # TODO: verify-reupload (to become default)
    help="What to do if a file found existing on the server. 'refresh': verify "
    "that according to the size and mtime, it is the same file, if not - "
    "reupload.",
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
    """Upload files to DANDI archive"""
    # Ensure that we have all Folders created as well
    assert local_top_path, "--local-top-path (-t) must be specified for now"
    assert girder_collection, "--girder-collection (-c) must be specified"

    from pathlib import Path, PurePosixPath

    local_top_path = Path(local_top_path).resolve()

    if not girder_top_folder:
        # TODO: UI
        #  Most often it would be the same directory name as of the local top dir
        girder_top_folder = local_top_path.name
        lgr.info(
            f"No folder on the server was specified, will use {girder_top_folder!r}"
        )

    if str(girder_top_folder) in (".", "..", "", "/"):
        lgr.error(
            f"Got folder {girder_top_folder}, but files cannot be uploaded "
            f"into a collection directly."
        )
        sys.exit(1)

    girder_top_folder = PurePosixPath(girder_top_folder)

    import multiprocessing
    from .. import girder
    from ..pynwb_utils import get_metadata
    from ..pynwb_utils import validate as pynwb_validate
    from ..pynwb_utils import ignore_benign_pynwb_warnings
    from ..utils import get_utcnow_datetime
    from ..support.generatorify import generator_from_callback
    from ..support.pyout import naturalsize

    ignore_benign_pynwb_warnings()  # so validate doesn't whine

    client = girder.authenticate(girder_instance)

    try:
        collection_rec = girder.ensure_collection(client, girder_collection)
    except girder.gcl.HttpError as exc:
        if develop_debug:
            raise
        # provide a bit less intimidating error reporting
        lgr.error(
            "Failed to assure presence of the %s collection: %s",
            girder_collection,
            (girder.get_HttpError_response(exc) or {}).get("message", str(exc)),
        )
        sys.exit(1)

    lgr.debug("Working with collection %s", collection_rec)

    # We will keep a shared set of "being processed" paths so
    # we could limit the number of them until
    #   https://github.com/pyout/pyout/issues/87
    # properly addressed
    process_paths = set()
    uploaded_paths = {}  # path: uploaded size

    def skip_file(msg):
        return {"status": "skipped", "message": str(msg)}

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

            # we will add some fields which would help us with deciding to
            # reupload or not
            file_metadata_ = {
                "uploaded_size": os.stat(str(path)).st_size,
                "uploaded_mtime": os.stat(str(path)).st_mtime,
                # "uploaded_date": None,  # to be filled out upon upload completion
            }

            # A girder delete API target to .delete before uploading a file
            # (e.g. if decided to reupload)
            delete_before_upload = None

            def get_item_rec():
                """This function might need to be called twice, e.g. if we
                are to reupload the entire item.

                ATM new versions of the files would create new items since
                the policy is one File per Item
                """
                try:
                    lock.acquire(timeout=60)
                    # TODO: we need to make this all thread safe all the way
                    #       until uploading the file since multiple threads would
                    #       create multiple
                    # ATM it even fails with  No such folder: 5e33658d6eb14e0bf49e97d5",
                    # so will first upload one file and then the rest... not sure why
                    # locking doesn't work
                    folder_rec = girder.ensure_folder(
                        client, collection_rec, girder_collection, girder_folder
                    )

                    # Get (if already exists) or create an item
                    item_rec = client.createItem(
                        folder_rec["_id"], name=relpath.name, reuseExisting=True
                    )
                finally:
                    lock.release()
                return item_rec

            item_rec = get_item_rec()
            file_recs = list(client.listFile(item_rec["_id"]))

            # get metadata and if we have all indications that it is
            # probably the same -- we just skip
            assert sorted(file_metadata_) == ["uploaded_mtime", "uploaded_size"]
            item_file_metadata_ = {
                k: item_rec.get("meta", {}).get(k, None)
                for k in ["uploaded_mtime", "uploaded_size"]
            }
            lgr.debug(
                "Files meta: local file: %s  remote file: %s",
                file_metadata_,
                item_file_metadata_,
            )

            file_thesame = file_metadata_ == item_file_metadata_
            file_thesame_str = "same" if file_thesame else "diff"
            exists_msg = f"exists ({file_thesame_str})"

            if len(file_recs) > 1:
                raise NotImplementedError(
                    f"Item {item_rec} contains multiple files: {file_recs}"
                )
            elif file_recs:  # there is a file already
                if existing == "skip":
                    yield skip_file(exists_msg)
                    return
                # Logic below only for refresh and reupload
                if existing == "refresh":
                    if file_thesame:
                        yield skip_file(exists_msg)
                        return
                elif existing == "reupload":
                    pass
                else:
                    raise ValueError("existing")

                delete_before_upload = f'/item/{item_rec["_id"]}'

                yield {"message": exists_msg + " - reuploading"}

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

            # TODO: we could potentially keep new item "hidden" until we are
            #  done with upload, and only then remove old one and replace with
            #  a new one (rename from "hidden" name).
            if delete_before_upload:
                yield {"status": "deleting old"}
                client.delete(delete_before_upload)
                yield {"status": "old deleted"}
                # create a a new item
                item_rec = get_item_rec()

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
            # .isoformat() would give is8601 representation but I see in girder
            # already
            # session_start_time   1971-01-01 12:00:00+00:00
            file_metadata_["uploaded_datetime"] = str(
                get_utcnow_datetime()
            )  # .isoformat()
            metadata_.update(file_metadata_)
            metadata_["uploaded_size"] = os.stat(str(path)).st_size
            metadata_["uploaded_mtime"] = os.stat(str(path)).st_mtime

            yield {"status": "uploading metadata"}
            client.addMetadataToItem(item_rec["_id"], metadata_)

            yield {"status": "done"}

        except Exception as exc:
            if develop_debug:
                raise
            # Custom formatting for some exceptions we know to extract
            # user-meaningful message
            message = str(exc)
            if isinstance(exc, girder.gcl.HttpError):
                response = girder.get_HttpError_response(exc)
                if "message" in response:
                    message = response["message"]
            yield {"status": "ERROR", "message": message}
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
                fullpath = path if path.is_absolute() else path.resolve()
                relpath = fullpath.relative_to(local_top_path)

                rec["path"] = str(relpath)
                if develop_debug:
                    # DEBUG: do serially
                    for v in process_path(path, relpath):
                        print(v)
                else:
                    rec[rec_fields[1:]] = process_path(path, relpath)
            except ValueError as exc:
                if "does not start with" in str(exc):
                    # if top_path is not the top path for the path
                    # Provide more concise specific message without path details
                    rec.update(skip_file("must be a child of top path"))
                else:
                    rec.update(skip_file(exc))
            out(rec)
