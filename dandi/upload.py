from datetime import datetime

# PurePosixPath to be cast to for paths on girder
from pathlib import Path, PurePosixPath
import re
import sys
import time

from .consts import (
    collection_drafts,
    dandiset_identifier_regex,
    dandiset_metadata_file,
    metadata_digests,
)
from . import __version__, lgr
from .utils import ensure_datetime, ensure_strtime, get_instance


def upload(
    paths,
    existing="refresh",
    validation="require",
    dandiset_path=None,
    girder_collection=collection_drafts,
    girder_top_folder=None,
    dandi_instance="dandi",
    fake_data=False,  # TODO: not implemented, prune?
    allow_any_path=False,
    upload_dandiset_metadata=False,
    devel_debug=False,
    jobs=None,
    jobs_per_file=None,
):
    from .dandiset import Dandiset
    from . import girder
    from .support.digests import Digester

    dandiset = Dandiset.find(dandiset_path)
    if not dandiset:
        raise RuntimeError(
            f"Found no {dandiset_metadata_file} anywhere.  "
            "Use 'dandi register', 'download', or 'organize' first"
        )

    # Should no longer be needed
    # dandiset_path = Path(dandiset_path).resolve()

    instance = get_instance(dandi_instance)
    if instance.girder is None:
        assert instance.api is not None
        return _new_upload(
            instance.api,
            dandiset,
            paths,
            existing,
            validation,
            dandiset_path,
            allow_any_path,
            upload_dandiset_metadata,
            devel_debug,
            jobs=jobs,
            jobs_per_file=jobs_per_file,
        )

    if upload_dandiset_metadata:
        raise NotImplementedError(
            "Upload of dandiset metadata to Girder based server is not supported."
        )

    client = girder.get_client(instance.girder)

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

    import multiprocessing

    from .metadata import get_metadata
    from .pynwb_utils import get_object_id, ignore_benign_pynwb_warnings
    from .support.generatorify import generator_from_callback
    from .support.pyout import naturalsize
    from .utils import find_dandi_files, find_files, path_is_subpath
    from .validate import validate_file

    ignore_benign_pynwb_warnings()  # so validate doesn't whine

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

    try:
        girder.lookup(client, girder_collection, path=girder_top_folder)
    except girder.GirderNotFound:
        raise ValueError(
            f"There is no {girder_top_folder} in {girder_collection}. "
            f"Did you use 'dandi register'?"
        )

    #
    # Treat paths
    #
    if not paths:
        paths = [dandiset.path]

    # Expand and validate all paths -- they should reside within dandiset
    paths = find_files(".*", paths) if allow_any_path else find_dandi_files(paths)
    paths = list(map(Path, paths))
    npaths = len(paths)
    lgr.info(f"Found {npaths} files to consider")
    for path in paths:
        if not (
            allow_any_path
            or path.name == dandiset_metadata_file
            or path.name.endswith(".nwb")
        ):
            raise NotImplementedError(
                f"ATM only .nwb and dandiset.yaml should be in the paths to upload. Got {path}"
            )
        if not path_is_subpath(str(path.absolute()), dandiset.path):
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
        """

        Parameters
        ----------
        path: Path
          Non Pure (OS specific) Path
        relpath:
          For location on Girder.  Will be cast to PurePosixPath

        Yields
        ------
        dict
          Records for pyout
        """
        # Ensure consistent types
        path = Path(path)
        relpath = PurePosixPath(relpath)
        try:
            try:
                path_stat = path.stat()
                yield {"size": path_stat.st_size}
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
            # TODO: enable back validation of dandiset.yaml
            if path.name != dandiset_metadata_file and validation != "skip":
                yield {"status": "pre-validating"}
                validation_errors = validate_file(path)
                yield {"errors": len(validation_errors)}
                # TODO: split for dandi, pynwb errors
                if validation_errors:
                    if validation == "require":
                        yield skip_file("failed validation")
                        return
                else:
                    yield {"status": "validated"}
            else:
                # yielding empty causes pyout to get stuck or crash
                # https://github.com/pyout/pyout/issues/91
                # yield {"errors": '',}
                pass

            #
            # Special handling for dandiset.yaml
            # Yarik hates it but that is life for now. TODO
            #
            if path.name == dandiset_metadata_file:
                # TODO This is a temporary measure to avoid breaking web UI
                # dandiset metadata schema assumptions.  All edits should happen
                # online.
                yield skip_file("should be edited online")
                return
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

            if file_recs:  # there is a file already
                if len(file_recs) > 1:
                    lgr.debug(f"Item {item_rec} contains multiple files: {file_recs}")
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
            if path.name != dandiset_metadata_file:
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
                    item_rec["_id"], str(path), progressCallback=c
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
                item_rec["_id"], path.name, path.absolute()
            )
            if not current:
                yield skip_file("File on server was unexpectedly changed")
                return

            # Compare file size against what download headers report
            # S3 doesn't seem to allow HEAD requests, so we need to instead do
            # a GET with a streaming response and not read the body.
            with client.sendRestRequest(
                "GET", f"file/{file_id}/download", jsonResp=False, stream=True
            ) as r:
                if int(r.headers["Content-Length"]) != path.stat().st_size:
                    yield skip_file("File size on server does not match local file")
                    return

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
    from .support import pyout as pyouts

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

    rec_fields = ["path", "size", "errors", "upload", "status", "message"]
    out = pyouts.LogSafeTabular(style=pyout_style, columns=rec_fields)

    with out, client.lock_dandiset(dandiset.identifier):
        for path in paths:
            while len(process_paths) >= 10:
                lgr.log(2, "Sleep waiting for some paths to finish processing")
                time.sleep(0.5)

            rec = {"path": str(path)}
            process_paths.add(str(path))

            try:
                relpath = path.absolute().relative_to(dandiset.path)

                rec["path"] = str(relpath)
                if devel_debug:
                    # DEBUG: do serially
                    for v in process_path(path, relpath):
                        print(str(v), flush=True)
                else:
                    rec[tuple(rec_fields[1:])] = process_path(path, relpath)
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


def _new_upload(
    api_url,
    dandiset,
    paths,
    existing,
    validation,
    dandiset_path,
    allow_any_path,
    upload_dandiset_metadata,
    devel_debug,
    jobs=None,
    jobs_per_file=None,
):
    from .dandiapi import DandiAPIClient
    from .dandiset import APIDandiset
    from .support.digests import get_digest

    client = DandiAPIClient(api_url)
    client.dandi_authenticate()

    dandiset = APIDandiset(dandiset.path)  # "cast" to a new API based dandiset

    ds_identifier = dandiset.identifier
    # this is a path not a girder id

    if not re.match(dandiset_identifier_regex, str(ds_identifier)):
        raise ValueError(
            f"Dandiset identifier {ds_identifier} does not follow expected "
            f"convention {dandiset_identifier_regex!r}.  Use "
            f"'dandi register' to get a legit identifier"
        )

    from .metadata import get_default_metadata, nwb2asset
    from .pynwb_utils import ignore_benign_pynwb_warnings
    from .support.pyout import naturalsize
    from .utils import find_dandi_files, find_files, path_is_subpath
    from .validate import validate_file

    ignore_benign_pynwb_warnings()  # so validate doesn't whine

    #
    # Treat paths
    #
    if not paths:
        paths = [dandiset.path]

    # Expand and validate all paths -- they should reside within dandiset
    paths = find_files(".*", paths) if allow_any_path else find_dandi_files(paths)
    paths = list(map(Path, paths))
    npaths = len(paths)
    lgr.info(f"Found {npaths} files to consider")
    for path in paths:
        if not (
            allow_any_path
            or path.name == dandiset_metadata_file
            or path.name.endswith(".nwb")
        ):
            raise NotImplementedError(
                f"ATM only .nwb and dandiset.yaml should be in the paths to upload. Got {path}"
            )
        if not path_is_subpath(str(path.absolute()), dandiset.path):
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

    # TODO: we might want to always yield a full record so no field is not
    # provided to pyout to cause it to halt
    def process_path(path, relpath):
        """

        Parameters
        ----------
        path: Path
          Non Pure (OS specific) Path
        relpath:
          For location on server.  Will be cast to PurePosixPath

        Yields
        ------
        dict
          Records for pyout
        """
        # Ensure consistent types
        path = Path(path)
        relpath = PurePosixPath(relpath)
        try:
            try:
                path_stat = path.stat()
                yield {"size": path_stat.st_size}
            except FileNotFoundError:
                yield skip_file("ERROR: File not found")
                return
            except Exception as exc:
                # without limiting [:50] it might cause some pyout indigestion
                yield skip_file("ERROR: %s" % str(exc)[:50])
                return

            #
            # Validate first, so we do not bother server at all if not kosher
            #
            # TODO: enable back validation of dandiset.yaml
            if path.name != dandiset_metadata_file and validation != "skip":
                yield {"status": "pre-validating"}
                validation_errors = validate_file(path)
                yield {"errors": len(validation_errors)}
                # TODO: split for dandi, pynwb errors
                if validation_errors:
                    if validation == "require":
                        yield skip_file("failed validation")
                        return
                else:
                    yield {"status": "validated"}
            else:
                # yielding empty causes pyout to get stuck or crash
                # https://github.com/pyout/pyout/issues/91
                # yield {"errors": '',}
                pass

            #
            # Special handling for dandiset.yaml
            # Yarik hates it but that is life for now. TODO
            #
            if path.name == dandiset_metadata_file:
                # TODO This is a temporary measure to avoid breaking web UI
                # dandiset metadata schema assumptions.  All edits should happen
                # online.
                if upload_dandiset_metadata:
                    yield {"status": "updating metadata"}
                    client.set_dandiset_metadata(
                        dandiset.identifier, metadata=dandiset.metadata
                    )
                    yield {"status": "updated metadata"}
                else:
                    yield skip_file("should be edited online")
                return

            #
            # Compute checksums
            #
            yield {"status": "digesting"}
            try:
                file_etag = get_digest(path, digest="dandi-etag")
            except Exception as exc:
                yield skip_file("failed to compute digest: %s" % str(exc))
                return

            extant = client.get_asset_bypath(ds_identifier, "draft", str(relpath))
            if extant is not None:
                # The endpoint used to search by paths doesn't include asset
                # metadata, so we need to make another API call:
                metadata = client.get_asset(ds_identifier, "draft", extant["asset_id"])
                local_mtime = ensure_datetime(path_stat.st_mtime)
                remote_mtime_str = metadata.get("blobDateModified")
                d = metadata.get("digest", {})
                if "dandi:dandi-etag" in d:
                    extant_etag = d["dandi:dandi-etag"]
                else:
                    # TODO: Should this error instead?
                    extant_etag = None
                if remote_mtime_str is not None:
                    remote_mtime = ensure_datetime(remote_mtime_str)
                    remote_file_status = (
                        "same"
                        if extant_etag == file_etag and remote_mtime == local_mtime
                        else (
                            "newer"
                            if remote_mtime > local_mtime
                            else ("older" if remote_mtime < local_mtime else "diff")
                        )
                    )
                else:
                    remote_mtime = None
                    remote_file_status = "no mtime"

                exists_msg = f"exists ({remote_file_status})"

                if existing == "error":
                    # as promised -- not gentle at all!
                    raise FileExistsError(exists_msg)
                if existing == "skip":
                    yield skip_file(exists_msg)
                    return
                # Logic below only for overwrite and reupload
                if existing == "overwrite":
                    if extant_etag == file_etag:
                        yield skip_file(exists_msg)
                        return
                elif existing == "refresh":
                    if extant_etag == file_etag:
                        yield skip_file("file exists")
                        return
                    elif remote_mtime is not None and remote_mtime >= local_mtime:
                        yield skip_file(exists_msg)
                        return
                elif existing == "force":
                    pass
                else:
                    raise ValueError(f"invalid value for 'existing': {existing!r}")

                yield {"message": f"{exists_msg} - reuploading"}

            #
            # Extract metadata - delayed since takes time, but is done before
            # actual upload, so we could skip if this fails
            #
            # Extract metadata before actual upload and skip if fails
            # TODO: allow for for non-nwb files to skip this step
            # ad-hoc for dandiset.yaml for now
            yield {"status": "extracting metadata"}
            try:
                asset_metadata = nwb2asset(
                    path, digest=file_etag, digest_type="dandi_etag"
                )
            except Exception as exc:
                lgr.exception("Failed to extract metadata from %s", path)
                if allow_any_path:
                    yield {"status": "failed to extract metadata"}
                    asset_metadata = get_default_metadata(
                        path, digest=file_etag, digest_type="dandi_etag"
                    )
                else:
                    yield skip_file("failed to extract metadata: %s" % str(exc))
                    return
            metadata = asset_metadata.json_dict()
            metadata["path"] = str(relpath)

            #
            # Upload file
            #
            yield {"status": "uploading"}
            validating = False
            for r in client.iter_upload(
                ds_identifier, "draft", metadata, str(path), jobs=jobs_per_file
            ):
                if r["status"] == "uploading":
                    uploaded_paths[str(path)]["size"] = r.pop("current")
                    yield r
                elif r["status"] == "post-validating":
                    # Only yield the first "post-validating" status
                    if not validating:
                        yield r
                        validating = True
                else:
                    yield r
            yield {"status": "done"}

        except Exception as exc:
            if devel_debug:
                raise
            # Custom formatting for some exceptions we know to extract
            # user-meaningful message
            message = str(exc)
            uploaded_paths[str(path)]["errors"].append(message)
            yield {"status": "ERROR", "message": message}
        finally:
            process_paths.remove(str(path))

    # We will again use pyout to provide a neat table summarizing our progress
    # with upload etc
    from .support import pyout as pyouts

    # for the upload speeds we need to provide a custom  aggregate
    t0 = time.time()

    def upload_agg(*ignored):
        dt = time.time() - t0
        # to help avoiding dict length changes during upload
        # might be not a proper solution
        # see https://github.com/dandi/dandi-cli/issues/502 for more info
        uploaded_recs = list(uploaded_paths.values())
        total = sum(v["size"] for v in uploaded_recs)
        if not total:
            return ""
        speed = total / dt if dt else 0
        return "%s/s" % naturalsize(speed)

    pyout_style = pyouts.get_style(hide_if_missing=False)
    pyout_style["upload"]["aggregate"] = upload_agg

    rec_fields = ["path", "size", "errors", "upload", "status", "message"]
    out = pyouts.LogSafeTabular(style=pyout_style, columns=rec_fields, max_workers=jobs)

    with out, client.session():
        for path in paths:
            while len(process_paths) >= 10:
                lgr.log(2, "Sleep waiting for some paths to finish processing")
                time.sleep(0.5)

            rec = {"path": str(path)}
            process_paths.add(str(path))

            try:
                relpath = path.absolute().relative_to(dandiset.path)

                rec["path"] = str(relpath)
                if devel_debug:
                    # DEBUG: do serially
                    for v in process_path(path, relpath):
                        print(str(v), flush=True)
                else:
                    rec[tuple(rec_fields[1:])] = process_path(path, relpath)
            except ValueError as exc:
                if "does not start with" in str(exc):
                    # if top_path is not the top path for the path
                    # Provide more concise specific message without path details
                    rec.update(skip_file("must be a child of top path"))
                else:
                    rec.update(skip_file(exc))
            out(rec)
