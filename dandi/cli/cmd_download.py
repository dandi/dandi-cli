import os

import click

from .base import instance_option, map_to_click_exceptions
from ..consts import known_instances, known_instances_rev
from ..dandiarchive import parse_dandi_url


class ChoiceList(click.ParamType):
    name = "choice-list"

    def __init__(self, values):
        self.values = set(values)

    def convert(self, value, param, ctx):
        if value is None or isinstance(value, set):
            return value
        selected = set()
        for v in value.split(","):
            if v == "all":
                selected = self.values.copy()
            elif v in self.values:
                selected.add(v)
            else:
                self.fail(f"{v!r}: invalid value", param, ctx)
        return selected

    def get_metavar(self, param):
        return "[" + ",".join(self.values) + ",all]"


@click.command()
@click.option(
    "-o",
    "--output-dir",
    help="Directory where to download to (directory must exist). "
    "Files will be downloaded with paths relative to that directory. ",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
    default=os.curdir,
)
@click.option(
    "-e",
    "--existing",
    type=click.Choice(
        ["error", "skip", "overwrite", "refresh"]
    ),  # TODO: verify-reupload (to become default)
    help="What to do if a file found existing locally. 'refresh': verify "
    "that according to the size and mtime, it is the same file, if not - "
    "download and overwrite.",
    default="refresh",
    show_default=True,
)
@click.option(
    "-f",
    "--format",
    help="Choose the format/frontend for output. TODO: support all of the ls",
    type=click.Choice(["pyout", "debug"]),
    default="pyout",
)
@click.option(
    "-J",
    "--jobs",
    help="Number of parallel download jobs.",
    default=6,  # TODO: come up with smart auto-scaling etc
    show_default=True,
)
@click.option(
    "--download",
    "download_types",
    type=ChoiceList(["dandiset.yaml", "assets"]),
    help="Comma-separated list of elements to download",
    default="all",
    show_default=True,
)
@instance_option()
# Might be a cool feature, not unlike verifying a checksum, we verify that
# downloaded file passes the validator, and if not -- alert
# @click.option(
#     "--validation",
#     "validation",
#     type=click.Choice(["require", "skip", "ignore"]),
#     default="require",
# )
# @devel_option(
#     "--develop-debug",
#     help="For development: do not use pyout callbacks, do not swallow exception",
#     default=False,
#     is_flag=True,
# )
@click.argument("url", nargs=-1)
@map_to_click_exceptions
def download(
    url, output_dir, existing, jobs, format, download_types, dandi_instance=None
):
    """Download a file or entire folder from DANDI"""
    # We need to import the download module rather than the download function
    # so that the tests can properly patch the function with a mock.
    from .. import download

    if dandi_instance is not None:
        if url:
            for u in url:
                _, server_url, _, _ = parse_dandi_url(u)
                if known_instances_rev.get(server_url.rstrip("/")) != dandi_instance:
                    raise click.UsageError(
                        f"{u} does not point to {dandi_instance!r} instance"
                    )
        else:
            from ..dandiset import Dandiset

            try:
                dandiset_id = Dandiset(os.curdir).identifier
            except ValueError:
                # No Dandiset here; leave `url` alone
                pass
            else:
                instance = known_instances[dandi_instance]
                if instance.gui is not None:
                    url = [f"{instance.gui}/#/dandiset/{dandiset_id}/draft"]
                elif instance.api is not None:
                    url = [f"{instance.api}/dandisets/{dandiset_id}/"]
                else:
                    raise NotImplementedError(
                        f"Do not know how to construct URLs for {dandi_instance!r}"
                    )

    return download.download(
        url,
        output_dir,
        existing=existing,
        format=format,
        jobs=jobs,
        get_metadata="dandiset.yaml" in download_types,
        get_assets="assets" in download_types,
        # develop_debug=develop_debug
    )
