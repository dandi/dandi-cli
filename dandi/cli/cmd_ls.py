import os
import time

import click
from dandi.cli.command import get_files

from .command import lgr, main


# TODO: all the recursion options etc


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


def get_metadata_pyout(path, keys=None, process_paths=None):
    from ..pynwb_utils import get_metadata, get_nwb_version, get_neurodata_types

    def safe_call(func, path, default=None):
        try:
            return func(path)
        except Exception as exc:
            lgr.debug("Call to %s on %s failed: %s", func.__name__, path, exc)
            return default

    def fn():
        rec = {}
        try:
            # No need for calling get_metadata if no keys are needed from it
            if keys is None or list(keys) != ["nwb_version"]:
                meta = safe_call(get_metadata, path)
                # normalize some fields and remove completely empty
                for f, v in (meta or dict()).items():
                    if keys is not None and f not in keys:
                        continue
                    if isinstance(v, (tuple, list)):
                        v = ", ".join(v)
                    if v:
                        rec[f] = v

            if "nwb_version" not in rec:
                # Let's at least get that one
                rec["nwb_version"] = safe_call(get_nwb_version, path, "ERROR") or ""

            rec["nd_types"] = ", ".join(safe_call(get_neurodata_types, path, []))

            return rec
        finally:
            # TODO: this is a workaround, remove after
            # https://github.com/pyout/pyout/issues/87 is resolved
            if process_paths is not None and path in process_paths:
                process_paths.remove(path)

    return fn
