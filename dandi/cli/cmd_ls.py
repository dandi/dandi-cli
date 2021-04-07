from collections import defaultdict
import os
import os.path as op

import click

from .base import lgr, map_to_click_exceptions
from ..utils import is_url

# TODO: all the recursion options etc


@click.command()
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
@click.option(
    "-J",
    "--jobs",
    help="Number of parallel download jobs.",
    default=6,  # TODO: come up with smart auto-scaling etc
    show_default=True,
)
@click.option(
    "--metadata",
    type=click.Choice(["api", "all", "assets"]),
    default="api",
)
@click.option(
    "--schema",
    help="Convert metadata to new schema version",
    metavar="VERSION",
)
@click.argument("paths", nargs=-1, type=click.Path(exists=False, dir_okay=True))
@map_to_click_exceptions
def ls(paths, schema, metadata, fields=None, format="auto", recursive=False, jobs=6):
    """List .nwb files and dandisets metadata."""
    # TODO: more logical ordering in case of fields = None
    from .formatter import JSONFormatter, PYOUTFormatter, YAMLFormatter
    from ..consts import metadata_all_fields
    from ..dandiapi import DandiAPIClient

    # TODO: avoid
    from ..support.pyout import PYOUT_SHORT_NAMES_rev
    from ..utils import find_files

    common_fields = ("path", "size")
    if schema is not None:
        from ..models import AssetMeta, DandisetMeta

        all_fields = tuple(
            sorted(
                set(common_fields)
                | DandisetMeta.__fields__.keys()
                | AssetMeta.__fields__.keys()
            )
        )
    else:
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

    urls = map(is_url, paths)
    # Actually I do not see why and it could be useful to compare local-vs-remote
    # if any(urls) and not all(urls):
    #     raise ValueError(f"ATM cannot mix URLs with local paths. Got {paths}")

    def assets_gen():
        for path in paths:
            if is_url(path):
                from ..dandiarchive import navigate_url

                with navigate_url(path) as (client, dandiset, assets):
                    if dandiset:
                        dandiset_id = dandiset.get("dandiset", {}).get("identifier")
                        rec = {
                            "path": dandiset.pop("dandiset", {}).get(
                                "identifier", "ERR#%s" % id(dandiset)
                            )
                        }
                        # flatten the metadata into record to display
                        # rec.update(dandiset.get('metadata', {}))
                        rec.update(dandiset)
                        yield rec
                    else:
                        dandiset_id = None
                    if recursive and assets:
                        if isinstance(client, DandiAPIClient) and metadata in (
                            "all",
                            "assets",
                        ):
                            for a in assets:
                                if "metadata" not in a:
                                    a["metadata"] = client.get_asset(
                                        dandiset_id,
                                        dandiset["version"],
                                        a["asset_id"],
                                    )
                                yield a
                        else:
                            yield from assets
            else:
                # For now we support only individual files
                yield path
                if recursive:
                    yield from find_files(r"\.nwb\Z", path)

    if format == "auto":
        format = "yaml" if any(urls) or (len(paths) == 1 and not recursive) else "pyout"

    if format == "pyout":
        if fields and fields[0] != "path":
            # we must always have path - our "id"
            fields = ["path"] + fields
        out = PYOUTFormatter(fields=fields, wait_for_top=3, max_workers=jobs)
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

    errors = defaultdict(list)  # problem: [] paths
    with out:
        for asset in assets_gen():
            if isinstance(asset, str):  # path
                rec = {}
                rec["path"] = asset

                try:
                    if (not fields or "size" in fields) and not op.isdir(asset):
                        rec["size"] = os.stat(asset).st_size

                    if async_keys:
                        cb = get_metadata_ls(
                            asset,
                            async_keys,
                            errors=errors,
                            flatten=format == "pyout",
                            schema=schema,
                        )
                        if format == "pyout":
                            rec[async_keys] = cb
                        else:
                            # TODO: parallel execution
                            # For now just call callback and get all the fields
                            cb_res = cb()
                            # TODO: we should stop masking exceptions in get_metadata_ls,
                            # and centralize logic regardless either it is for pyout or not
                            # and do parallelizaion on our end, so at large it is
                            if cb_res is None:
                                raise
                            for k, v in cb_res.items():
                                rec[k] = v
                except Exception as exc:
                    _add_exc_error(asset, rec, errors, exc)
            elif isinstance(asset, dict):
                # ready record
                if schema is not None and asset.get("schemaVersion") != schema:
                    raise NotImplementedError(
                        "Record conversion between schema versions is not"
                        " implemented.  Found schemaVersion="
                        f"{asset.get('schemaVersion')} where {schema} was"
                        " requested"
                    )
                # TODO: harmonization for pyout
                rec = asset
            else:
                raise TypeError(asset)

            if not rec:
                errors["Empty record"].append(asset)
                lgr.debug("Skipping a record for %s since empty", asset)
                continue
            out(rec)
    if errors:
        lgr.warning(
            "Failed to operate on some paths (empty records were listed):\n %s",
            "\n ".join("%s: %d paths" % (k, len(v)) for k, v in errors.items()),
        )


def _add_exc_error(asset, rec, errors, exc):
    """A helper to centralize collection of errors for pyout and non-pyout reporting"""
    lgr.debug("Problem obtaining metadata for %s: %s", asset, exc)
    errors[str(type(exc).__name__)].append(asset)
    rec["errors"] = rec.get("errors", 0) + 1


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
    """Return while flattening nested lists/dicts

    lists and tuples would get items converted to strings and joined
    with ", " separator.

    dicts would get items represented as "key: value" before flattening
    a list of them.
    """
    if isinstance(v, (tuple, list)):
        return ", ".join(map(str, map(flatten_v, v)))
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


def get_metadata_ls(path, keys, errors, flatten=False, schema=None):
    from ..dandiset import APIDandiset
    from ..metadata import get_metadata, nwb2asset
    from ..pynwb_utils import get_nwb_version, ignore_benign_pynwb_warnings

    ignore_benign_pynwb_warnings()

    def fn():
        try:
            rec = {}
            # No need for calling get_metadata if no keys are needed from it
            if keys is None or list(keys) != ["nwb_version"]:
                try:
                    if schema is not None:
                        if op.isdir(path):
                            dandiset = APIDandiset(path, schema_version=schema)
                            rec = dandiset.metadata
                        else:
                            rec = nwb2asset(path, schema_version=schema).json_dict()
                    else:
                        rec = get_metadata(path)
                except Exception as exc:
                    _add_exc_error(path, rec, errors, exc)
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
                try:
                    rec["nwb_version"] = get_nwb_version(path)
                except Exception as exc:
                    _add_exc_error(path, rec, errors, exc)
            return rec
        finally:
            pass

    return fn
