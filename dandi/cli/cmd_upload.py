import click
from datetime import datetime
import os
import os.path as op
import re
import sys
import time


from .command import (
    dandiset_path_option,
    devel_debug_option,
    devel_option,
    instance_option,
    main,
    map_to_click_exceptions,
    lgr,
)
from .. import __version__
from ..utils import ensure_datetime, ensure_strtime, find_parent_directory_containing
from ..consts import (
    collection_drafts,
    dandiset_identifier_regex,
    dandiset_metadata_file,
    known_instances,
    metadata_digests,
)


@main.command()
# @dandiset_path_option(
#     help="Top directory (local) of the dandiset.  Files will be uploaded with "
#     "paths relative to that directory. If not specified, current or a parent "
#     "directory containing dandiset.yaml file will be assumed "
# )
@click.option(
    "-e",
    "--existing",
    type=click.Choice(["error", "skip", "force", "overwrite", "refresh"]),
    help="What to do if a file found existing on the server. 'skip' would skip"
    "the file, 'force' - force reupload, 'overwrite' - force upload if "
    "either size or modification time differs; 'refresh' - upload only if "
    "local modification time is ahead of the remote.",
    default="refresh",
    show_default=True,
)
@click.option(
    "--validation",
    help="Data must pass validation before the upload.  Use of this option is highly discouraged.",
    type=click.Choice(["require", "skip", "ignore"]),
    default="require",
    show_default=True,
)
@click.argument("paths", nargs=-1)  # , type=click.Path(exists=True, dir_okay=False))
# &
# Development options:  Set DANDI_DEVEL for them to become available
#
# TODO: should always go to dandi for now
@instance_option()
# TODO: should always go into 'drafts' (consts.collection_drafts)
@devel_option(
    "-c", "--girder-collection", help="For development: Girder collection to upload to"
)
# TODO: figure out folder for the dandiset
@devel_option("--girder-top-folder", help="For development: Girder top folder")
#
@devel_option(
    "--fake-data",
    help="For development: fake file content (filename will be stored instead of actual load)",
    default=False,
    is_flag=True,
)
@devel_option(
    "--allow-any-path",
    help="For development: allow DANDI 'unsupported' file types/paths",
    default=False,
    is_flag=True,
)
@devel_debug_option()
@map_to_click_exceptions
def upload(
    paths,
    existing="refresh",
    validation="require",
    dandiset_path=None,
    # Development options should come as kwargs
    girder_collection=collection_drafts,
    girder_top_folder=None,
    dandi_instance="dandi",
    fake_data=False,  # TODO: not implemented, prune?
    allow_any_path=False,
    devel_debug=False,
):
    """Upload dandiset (files) to DANDI archive.

    Target dandiset to upload to must already be registered in the archive and
    locally "dandiset.yaml" should exist in `--dandiset-path`.  If you have not
    yet created a dandiset in the archive, use 'dandi register' command first.

    Local dandiset should pass validation.  For that it should be first organized
    using 'dandiset organize' command.

    By default all files in the dandiset (not following directories starting with a period)
    will be considered for the upload.  You can point to specific files you would like to
    validate and have uploaded.
    """
    from pathlib import Path, PurePosixPath
    from ..dandiset import Dandiset
    from ..support.digests import Digester

    dandiset_paths = []
    for p in paths:
        dandiset = Dandiset.find(Path(p).resolve())
        if not dandiset:
            raise RuntimeError(
                f"Found no {dandiset_metadata_file} anywhere in {p}.  Use 'dandi register', 'download', or 'organize' first"
            )
        dandiset_paths.append(dandiset.path)
    paths = dandiset_paths

    # Girder side details:

    if not girder_collection:
        girder_collection = collection_drafts

    if not girder_top_folder:
        # We upload to staging/dandiset_id
        ds_identifier = dandiset.identifier
        if not ds_identifier:
            raise ValueError(
                "No 'identifier' set for the dandiset yet.  Use 'dandi register'"
            )
        if not re.match(dandiset_identifier_regex, ds_identifier):
            raise ValueError(
                f"Dandiset identifier {ds_identifier} does not follow expected "
                f"convention {dandiset_identifier_regex!r}.  Use "
                f"'dandi register' to get a legit identifier"
            )
        # this is a path not a girder id
        girder_top_folder = ds_identifier
    girder_top_folder = PurePosixPath(girder_top_folder)

    if str(girder_top_folder) in (".", "..", "", "/"):
        raise ValueError(
            f"Got folder {girder_top_folder}, but files cannot be uploaded "
            f"into a collection directly."
        )

    # TODO: that the folder already exists
    if False:
        raise ValueError(
            f"There is no {girder_top_folder} in {girder_collection}. "
            f"Did you use 'dandi register'?"
        )

    import multiprocessing
    from .. import girder
    from ..pynwb_utils import ignore_benign_pynwb_warnings, get_object_id
    from ..metadata import get_metadata
    from ..validate import validate_file
    from ..utils import (
        find_dandi_files,
        find_files,
        path_is_subpath,
        get_utcnow_datetime,
    )
    from ..support.generatorify import generator_from_callback
    from ..support.pyout import naturalsize

    ignore_benign_pynwb_warnings()  # so validate doesn't whine

    client = girder.get_client(girder.known_instances[dandi_instance].girder)

    try:
        collection_rec = girder.ensure_collection(client, girder_collection)
    except girder.gcl.HttpError as exc:
        if devel_debug:
            raise
        # provide a bit less intimidating error reporting
        lgr.error(
            "Failed to assure presence of the %s collection: %s",
            girder_collection,
            (girder.get_HttpError_response(exc) or {}).get("message", str(exc)),
        )
        sys.exit(1)

    lgr.debug("Working with collection %s", collection_rec)

    # Expand and validate all paths -- they should reside within dandiset
    orig_paths = paths
    paths = list(find_files(".*", paths) if allow_any_path else find_dandi_files(paths))
    npaths = len(paths)
    lgr.info(f"Found {npaths} files to consider")
    for path in paths:
        path_basename = op.basename(path)
        if not (
            allow_any_path
            or path_basename == dandiset_metadata_file
            or path_basename.endswith(".nwb")
        ):
            raise NotImplementedError(
                f"ATM only .nwb and dandiset.yaml should be in the paths to upload. Got {path}"
            )
        fullpath = path if op.isabs(path) else op.abspath(path)
        if not path_is_subpath(fullpath, dandiset.path):
            raise ValueError(f"{path} is not under {dandiset.path}")

    # We will keep a shared set of "being processed" paths so
    # we could limit the number of them until
    #   https://github.com/pyout/pyout/issues/87
    # properly addressed
    process_paths = set()
    from collections import defaultdict

    uploaded_paths = defaultdict(lambda: {"size": 0, "errors": []})

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
            path_stat = os.stat(str(path))
            file_metadata_ = {
                "uploaded_size": path_stat.st_size,
                "uploaded_mtime": ensure_strtime(path_stat.st_mtime),
                # "uploaded_date": None,  # to be filled out upon upload completion
            }

            # A girder delete API target to .delete before uploading a file
            # (e.g. if decided to reupload)
            delete_before_upload = None

            def ensure_item():
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

            def ensure_folder():
                try:
                    lock.acquire(timeout=60)
                    folder_rec = girder.ensure_folder(
                        client, collection_rec, girder_collection, girder_folder
                    )
                finally:
                    lock.release()
                return folder_rec

            #
            # 1. Validate first, so we do not bother girder at all if not kosher
            #
            if validation != "skip":
                yield {"status": "validating"}
                validation_errors = validate_file(path)
                yield {"errors": len(validation_errors)}
                # TODO: split for dandi, pynwb errors
                if validation_errors:
                    if validation == "require":
                        yield skip_file("failed validation")
                        return
            else:
                # yielding empty causes pyout to get stuck or crash
                # https://github.com/pyout/pyout/issues/91
                # yield {"errors": '',}
                pass

            #
            # Special handling for dandiset.yaml
            # Yarik hates it but that is life for now. TODO
            #
            if op.basename(path) == dandiset_metadata_file:
                # We need to upload its content as metadata for the entire
                # folder.
                folder_rec = ensure_folder()
                remote_metadata = folder_rec["meta"]
                if remote_metadata.get("dandiset", {}) == dandiset.metadata:
                    yield skip_file("exists (same)")
                else:
                    remote_metadata["dandiset"] = dandiset.metadata
                    yield {"status": "uploading dandiset metadata"}
                    client.addMetadataToFolder(folder_rec["_id"], remote_metadata)
                    yield {"status": "done"}
                # Interrupt -- no file to upload
                return

            #
            # 2. Ensure having an item
            #
            item_rec = ensure_item()

            #
            # 3. Analyze possibly present on the remote files in the item
            #
            file_recs = list(client.listFile(item_rec["_id"]))

            # get metadata and if we have all indications that it is
            # probably the same -- we just skip
            stat_fields = [
                # Care only about mtime, ignore ctime which could change
                "uploaded_mtime",
                "uploaded_size",
            ]
            assert sorted(file_metadata_) == stat_fields
            item_metadata = item_rec.get("meta", {})
            item_file_metadata_ = {
                k: item_rec.get("meta", {}).get(k, None) for k in stat_fields
            }
            lgr.debug(
                "Files meta: local file: %s  remote file: %s",
                file_metadata_,
                item_file_metadata_,
            )

            if item_file_metadata_["uploaded_mtime"]:
                local_mtime = ensure_datetime(file_metadata_["uploaded_mtime"])
                remote_mtime = ensure_datetime(
                    item_file_metadata_.get("uploaded_mtime")
                )
                remote_file_status = (
                    "same"
                    if (file_metadata_ == item_file_metadata_)
                    else (
                        "newer"
                        if remote_mtime > local_mtime
                        else ("older" if remote_mtime < local_mtime else "diff")
                    )
                )
            else:
                remote_file_status = "no mtime"
            exists_msg = f"exists ({remote_file_status})"

            if len(file_recs) > 1:
                raise NotImplementedError(
                    f"Item {item_rec} contains multiple files: {file_recs}"
                )
            elif file_recs:  # there is a file already
                if existing == "error":
                    # as promised -- not gentle at all!
                    raise FileExistsError(exists_msg)
                if existing == "skip":
                    yield skip_file(exists_msg)
                    return
                # Logic below only for overwrite and reupload
                if existing == "overwrite":
                    if remote_file_status == "same":
                        yield skip_file(exists_msg)
                        return
                elif existing == "refresh":
                    if not remote_file_status == "older":
                        yield skip_file(exists_msg)
                        return
                elif existing == "force":
                    pass
                else:
                    raise ValueError("existing")

                delete_before_upload = f'/item/{item_rec["_id"]}'

                yield {"message": exists_msg + " - reuploading"}

            #
            # 4. Extract metadata - delayed since takes time, but is done
            #    before actual upload, so we could skip if this fails
            #
            # Extract metadata before actual upload and skip if fails
            # TODO: allow for for non-nwb files to skip this step
            # ad-hoc for dandiset.yaml for now
            if op.basename(path) != dandiset_metadata_file:
                yield {"status": "extracting metadata"}
                try:
                    metadata = get_metadata(path)
                except Exception as exc:
                    if allow_any_path:
                        yield {"status": "failed to extract metadata"}
                        metadata = {}
                    else:
                        yield skip_file("failed to extract metadata: %s" % str(exc))
                        if not file_recs:
                            # remove empty item
                            yield {"status": "deleting empty item"}
                            client.delete(f'/item/{item_rec["_id"]}')
                            yield {"status": "deleted empty item"}
                        return

            #
            # ?. Compute checksums and possible other digests (e.g. for s3, ipfs - TODO)
            #
            yield {"status": "digesting"}
            try:
                # TODO: in theory we could also cache the result, but since it is
                # critical to get correct checksums, safer to just do it all the time.
                # Should typically be faster than upload itself ;-)
                digester = Digester(metadata_digests)
                file_metadata_.update(digester(path))
            except Exception as exc:
                yield skip_file("failed to compute digests: %s" % str(exc))
                return

            #
            # 5. Upload file
            #
            # TODO: we could potentially keep new item "hidden" until we are
            #  done with upload, and only then remove old one and replace with
            #  a new one (rename from "hidden" name).
            if delete_before_upload:
                yield {"status": "deleting old"}
                client.delete(delete_before_upload)
                yield {"status": "old deleted"}
                # create a a new item
                item_rec = ensure_item()

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
                upload_perc = 100 * ((r["current"] / r["total"]) if r["total"] else 1.0)
                if girder._DANDI_LOG_GIRDER:
                    girder.lgr.debug(
                        "PROGRESS[%s]: done=%d %%done=%s",
                        str(path),
                        r["current"],
                        upload_perc,
                    )
                uploaded_paths[str(path)]["size"] = r["current"]
                yield {"upload": upload_perc}

            # Get uploaded file id
            file_id, current = client.isFileCurrent(
                item_rec["_id"], op.basename(path), op.abspath(path)
            )
            if not current:
                raise RuntimeError(
                    "Must not happen since file %s was just uploaded" % path
                )

            #
            # 6. Upload metadata
            #
            metadata_ = {}
            for k, v in metadata.items():
                if v in ("", None):
                    continue  # degenerate, why bother
                # XXX TODO: remove this -- it is only temporary, search should handle
                if isinstance(v, str):
                    metadata_[k] = v.lower()
                elif isinstance(v, datetime):
                    metadata_[k] = ensure_strtime(v)
            # we will add some fields which would help us with deciding to
            # reupload or not
            # .isoformat() would give is8601 representation but I see in girder
            # already
            # session_start_time   1971-01-01 12:00:00+00:00
            # decided to go for .isoformat for internal consistency -- let's see
            file_metadata_["uploaded_datetime"] = ensure_strtime(time.time())
            metadata_.update(file_metadata_)
            metadata_["uploaded_size"] = path_stat.st_size
            metadata_["uploaded_mtime"] = ensure_strtime(path_stat.st_mtime)
            metadata_["uploaded_by"] = "dandi %s" % __version__
            # Also store object_id for the file to help identify changes/moves
            try:
                metadata_["uploaded_nwb_object_id"] = get_object_id(str(path))
            except Exception as exc:
                (lgr.debug if allow_any_path else lgr.warning)(
                    "Failed to read object_id: %s", exc
                )

            # #
            # # 7. Also set remote file ctime to match local mtime
            # #   since for type "file", Resource has no "updated" field.
            # #   and this could us help to identify changes being done
            # #   to the remote file -- if metadata["uploaded_mtime"]
            # #   differs
            # yield {"status": "setting remote file timestamp"}
            # try:
            #     client.setResourceTimestamp(
            #         file_id, type="file", created=metadata_["uploaded_mtime"]
            #     )
            # except girder.gcl.HttpError as exc:
            #     if devel_debug:
            #         raise
            #     response = girder.get_HttpError_response(exc)
            #     message = response.get("message", str(exc))
            #     yield {"status": "WARNING", "message": message}

            # 7. Upload metadata
            yield {"status": "uploading metadata"}
            client.addMetadataToItem(item_rec["_id"], metadata_)
            yield {"status": "done"}

        except Exception as exc:
            if devel_debug:
                raise
            # Custom formatting for some exceptions we know to extract
            # user-meaningful message
            message = str(exc)
            if isinstance(exc, girder.gcl.HttpError):
                response = girder.get_HttpError_response(exc)
                if "message" in response:
                    message = response["message"]
            uploaded_paths[str(path)]["errors"].append(message)
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
        total = sum(v["size"] for v in uploaded_paths.values())
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

            rec = {"path": path}
            path = Path(path)
            process_paths.add(str(path))

            try:
                fullpath = path if path.is_absolute() else path.absolute()
                relpath = fullpath.relative_to(dandiset.path)

                rec["path"] = str(relpath)
                if devel_debug:
                    # DEBUG: do serially
                    for v in process_path(path, relpath):
                        sys.stdout.write(str(v) + os.linesep)
                        sys.stdout.flush()
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

    # # Provide summary of errors if any recorded
    # # well -- they are also in summary by pyout.  So, for now - do not bother
    # # It would be worthwhile if we decide to log also other errors
    # errors = defaultdict(set)
    # for p, v in uploaded_paths.items():
    #     for e in v['errors']:
    #         errors[e].add(p)
    # if errors:
    #     lgr.error("Following errors were detected while uploading")
    #     for e, paths in errors.items():
    #         lgr.error(" %s: %d paths", e, len(paths))
