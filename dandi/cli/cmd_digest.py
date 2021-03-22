import click

from .base import map_to_click_exceptions


@click.command()
@click.option(
    "-d",
    "--digest",
    "digest_alg",
    type=click.Choice(
        ["dandi-etag", "md5", "sha1", "sha256", "sha512"], case_sensitive=False
    ),
    default="dandi-etag",
    help="Digest algorithm to use",
    show_default=True,
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True, dir_okay=False))
@map_to_click_exceptions
def digest(paths, digest_alg):
    """ Calculate file digests """
    from ..support.digests import get_digest

    for p in paths:
        print(f"{p}:", get_digest(p, digest=digest_alg))
