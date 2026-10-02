from __future__ import annotations

import click

from .base import map_to_click_exceptions


@click.command()
@click.option(
    "-d",
    "--digest",
    "digest_alg",
    type=click.Choice(
        [
            "dandi-etag",
            "md5",
            "sha1",
            "sha256",
            "sha512",
            "zarr-checksum",
            "zarr-checksum-multipart",
        ],
        case_sensitive=False,
    ),
    default="dandi-etag",
    help="Digest algorithm to use",
    show_default=True,
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@map_to_click_exceptions
def digest(paths: tuple[str, ...], digest_alg: str) -> None:
    """Calculate file digests

    A Zarr's checksum depends on the scheme its entries were uploaded with, so
    the two schemes are named apart: use "zarr-checksum" for a Zarr uploaded
    via single-part PUTs and "zarr-checksum-multipart" for one uploaded via S3
    multipart upload, which is the scheme `dandi upload` uses for new Zarrs.

    Example: dandi digest --digest zarr-checksum-multipart sample.zarr
    """
    # Avoid heavy import by importing within function:
    from ..support.digests import get_digest

    for p in paths:
        print(f"{p}:", get_digest(p, digest=digest_alg))
