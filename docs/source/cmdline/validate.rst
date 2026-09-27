:program:`dandi validate`
=========================

::

    dandi [<global options>] validate [<path> ...]

Validate files for data standards compliance.

Exits with non-zero exit code if any file is not compliant.

Options
-------

.. option:: -g, --grouping [none|path]

    Set how to group reported errors & warnings: by path or not at all
    (default)

.. option:: --ignore REGEX

    Ignore any validation errors & warnings whose ID matches the given regular
    expression

.. option:: --min-severity [INFO|HINT|WARNING|ERROR|CRITICAL]

    Only display issues with severities above this level (HINT by default)

.. option:: --missing-file-content [error|only-non-data|skip|stream]

    How to handle files whose content is unavailable, such as the broken
    symbolic links of a DataLad_ dataset (a git-annex_ repository) whose
    content has not been fetched:

    ``error``
        Emit a concise ``DANDI.FILE_CONTENT_MISSING`` error for each such file
        (default)

    ``skip``
        Skip each such file, emitting a warning

    ``only-non-data``
        Skip content-dependent validators (pynwb, nwbinspector, ...) for each
        such file but still validate its path layout

    ``stream``
        Stream the content of each such file from the URLs registered for it in
        git-annex so that content-dependent validators run without the file
        having to be downloaded; see `Validating DataLad Dandisets`_ below.

.. option:: -f, --format [text|json|json_pp|json_lines|yaml]

    Output format (``text`` by default)

.. option:: -o, --output <file>

    Write the output to the given file instead of standard output.  The format
    is inferred from the file's extension unless :option:`--format` is given.

.. _DataLad: https://www.datalad.org
.. _git-annex: https://git-annex.branchable.com


Validating DataLad Dandisets
----------------------------

Every Dandiset on the DANDI Archive is mirrored as a DataLad dataset at
https://github.com/dandisets (with https://github.com/dandisets/dandisets as
the superdataset containing all of them).  In such a dataset, the assets are
annexed files: symbolic links that remain broken until the content is fetched,
which for some Dandisets would mean downloading terabytes of data.  The
``stream`` policy of :option:`--missing-file-content` lets ``dandi validate``
run the content-dependent validators (pynwb and nwbinspector for NWB files) on
such files by streaming their content on demand from the URLs registered in
git-annex (preferring the direct S3 URLs), reading only the parts of each file
that the validators need.  Only ``git`` is needed to read that information
(git-annex and DataLad do not need to be installed), plus fsspec_ for the
streaming itself (``pip install "dandi[extras]"``).

For example, to produce a JSON Lines record of *all* validation results for
a Dandiset::

    git clone https://github.com/dandisets/000003
    dandi validate --missing-file-content=stream --min-severity=INFO \
        --format=json_lines --output=000003.jsonl 000003

Each streamed file yields an ``INFO``-level ``DANDI.FILE_CONTENT_STREAMED``
result naming the URL its content was read from; a file that cannot be streamed
(not an annexed file, or no URL registered for it) yields a
``DANDI.FILE_CONTENT_MISSING`` error instead.  To do this for every Dandiset,
install the subdatasets of the superdataset without fetching any content and
validate each one (the superdataset itself is not a Dandiset)::

    datalad clone https://github.com/dandisets/dandisets
    cd dandisets
    datalad get -n -r .   # or: git submodule update --init
    for ds in 0*/; do
        dandi validate --missing-file-content=stream --min-severity=INFO \
            --format=json_lines --output="records/${ds%/}.jsonl" "$ds"
    done

Notes:

- The URLs are read from the ``git-annex`` branch of the repository (or its
  remote-tracking counterpart, e.g., ``origin/git-annex``), so the clone must
  include that branch: do not clone with ``--single-branch`` or a
  ``--depth`` that excludes it.
- Some nwbinspector checks read data arrays (e.g., timestamps), so the amount
  of data streamed for a file depends on its content; it is nevertheless
  usually a small fraction of the file.
- Zarr assets are stored as separate subdatasets (https://github.com/dandizarrs)
  and are not streamed: an uninstalled Zarr subdataset is an empty directory
  that is not validated at all.
- The BIDS validator cannot stream content, so BIDS errors that require reading
  a file (e.g., unreadable NIfTI headers) are suppressed for annexed files under
  the ``stream`` and ``only-non-data`` policies.

Alternatively, `datalad-fuse`_ can mount a DataLad dataset as a file system
that fetches content transparently on read, in which case plain ``dandi
validate`` (without :option:`--missing-file-content`) can be run on the mount
point; that approach requires FUSE and thus does not work in every
environment (e.g., many containers).

.. _fsspec: https://github.com/fsspec/filesystem_spec
.. _datalad-fuse: https://github.com/datalad/datalad-fuse


Development Options
-------------------

The following options are intended only for development & testing purposes.
They are only available if the :envvar:`DANDI_DEVEL` environment variable is
set to a nonempty value.

.. option:: --allow-any-path

    Validate all file types, not just NWBs and Zarrs

.. option:: --devel-debug

    Do not use pyout callbacks, do not swallow exceptions, do not parallelize.

.. option:: --schema <version>

    Validate against new schema version
