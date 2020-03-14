import os
import os.path as op
import time

import click
from dandi.cli.command import get_files

from .command import lgr, main, map_to_click_exceptions

from ..utils import safe_call

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
@click.option(
    "-r",
    "--recursive",
    help="Recurse into content of dandisets/directories. Only .nwb files will "
    "be considered.",
    is_flag=True,
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=True))
@map_to_click_exceptions
def ls(paths, fields=None, format="auto", recursive=False):
    """List .nwb files and dandisets metadata.
    """
    from ..consts import metadata_all_fields

    # TODO: more logical ordering in case of fields = None
    from .formatter import JSONFormatter, YAMLFormatter, PYOUTFormatter

    # TODO: avoid
    from ..support.pyout import PYOUT_SHORT_NAMES, PYOUT_SHORT_NAMES_rev
    from ..utils import find_files

    common_fields = ("path", "size")
    all_fields = tuple(sorted(set(common_fields + metadata_all_fields)))

    if fields is not None:
        if fields.strip() == "":
            display_known_fields(all_fields)
            return

        fields = fields.split(",")
        # Map possibly present short names back to full names
        fields = [PYOUT_SHORT_NAMES_rev.get(f.lower(), f) for f in fields]
        unknown_fields = set(fields).difference(all_fields)
        if unknown_fields:
            display_known_fields(all_fields)
            raise click.UsageError(
                "Following fields are not known: %s" % ", ".join(unknown_fields)
            )

    # For now we support only individual files
    if recursive:
        files = list(find_files(".nwb$", paths))
    else:
        files = paths

    if not files:
        return

    if format == "auto":
        format = "yaml" if len(files) == 1 else "pyout"

    if format == "pyout":
        if fields and fields[0] != "path":
            # we must always have path - our "id"
            fields = ["path"] + fields
        out = PYOUTFormatter(files=files, fields=fields)
    elif format == "json":
        out = JSONFormatter()
    elif format == "json_pp":
        out = JSONFormatter(indent=2)
    elif format == "yaml":
        out = YAMLFormatter()
    else:
        raise NotImplementedError("Unknown format %s" % format)

    async_keys = set(all_fields)
    if fields is not None:
        async_keys = async_keys.intersection(fields)
    async_keys = tuple(async_keys.difference(common_fields))

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
                if (not fields or "size" in fields) and not op.isdir(path):
                    rec["size"] = os.stat(path).st_size

                if async_keys:
                    cb = get_metadata_pyout(
                        path, async_keys, process_paths, flatten=format == "pyout"
                    )
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


def display_known_fields(all_fields):
    from ..support.pyout import PYOUT_SHORT_NAMES

    # Display all known fields
    click.secho("Known fields:")
    for field in all_fields:
        s = "- " + field
        if field in PYOUT_SHORT_NAMES:
            s += " or %s" % PYOUT_SHORT_NAMES[field]
        click.secho(s)
    return


def flatten_v(v):
    if isinstance(v, (tuple, list)):
        return ", ".join(map(flatten_v, v))
    elif isinstance(v, dict):
        return flatten_v(["%s: %s" % i for i in v.items()])
    return v


def flatten_meta_to_pyout_v1(meta):
    """Given a meta record, possibly flatten record since no nested records
    supported yet

    lists become joined using ', ', dicts get individual key: values.
    lists of dict - doing nothing magical.

    Empty values are not considered.

    Parameters
    ----------
    meta: dict
    """
    out = {}

    # normalize some fields and remove completely empty
    for f, v in (meta or dict()).items():
        if not v:
            continue
        if isinstance(v, dict):
            for vf, vv in flatten_meta_to_pyout_v1(v).items():
                out["%s_%s" % (f, vf)] = flatten_v(vv)
        else:
            out[f] = flatten_v(v)
    return out


def flatten_meta_to_pyout(meta):
    """Given a meta record, possibly flatten record since no nested records
    supported yet

    lists become joined using ', ', dicts become lists of "key: value" strings first.
    lists of dict - doing nothing magical.

    Empty values are not considered.

    Parameters
    ----------
    meta: dict
    """
    out = {}

    # normalize some fields and remove completely empty
    for f, v in (meta or dict()).items():
        if not v:
            continue
        out[f] = flatten_v(v)
    return out


def get_metadata_pyout(path, keys=None, process_paths=None, flatten=False):
    from ..pynwb_utils import get_nwb_version, ignore_benign_pynwb_warnings
    from ..metadata import get_metadata

    ignore_benign_pynwb_warnings()

    def fn():
        try:
            rec = {}
            # No need for calling get_metadata if no keys are needed from it
            if keys is None or list(keys) != ["nwb_version"]:
                rec = safe_call(get_metadata, path)
                if flatten:
                    rec = flatten_meta_to_pyout(rec)
            if keys is not None:
                rec = {k: v for k, v in rec.items() if k in keys}
            if (
                not op.isdir(path)
                and "nwb_version" not in rec
                and (keys and "nwb_version" in keys)
            ):
                # Let's at least get that one
                rec["nwb_version"] = safe_call(get_nwb_version, path, "ERROR") or ""
            return rec
        finally:
            # TODO: this is a workaround, remove after
            # https://github.com/pyout/pyout/issues/87 is resolved
            if process_paths is not None and path in process_paths:
                process_paths.remove(path)

    return fn
