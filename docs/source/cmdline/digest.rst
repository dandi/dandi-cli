:program:`dandi digest`
=======================

::

    dandi [<global options>] digest [<options>] [<path> ...]

Calculate file digests

Options
-------

.. option:: -d, --digest [dandi-etag|md5|sha1|sha256|sha512|zarr-checksum|zarr-checksum-multipart]

    Digest algorithm to use  [default: ``dandi-etag``]

    A Zarr's checksum is an aggregate over its entries' S3 ETags, which differ
    by the scheme the Zarr was uploaded with, so the two schemes are named
    apart: ``zarr-checksum`` is the checksum of a Zarr uploaded via single-part
    PUTs, and ``zarr-checksum-multipart`` that of one uploaded via S3 multipart
    upload, the scheme :program:`dandi upload` uses for new Zarrs.
