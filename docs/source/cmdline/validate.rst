.. _dandi_validate:

:program:`dandi validate`
=========================

::

    dandi [<global options>] validate [<options>] [<path> ...]

Validate files for data standards compliance.

Exits with non-zero exit code if any file is not compliant.

The validation results are automatically saved as a JSON Lines companion file
next to the dandi-cli log file (unless :option:`--output` is used or
:option:`--load` is active).  Use :option:`--load` to re-render saved results
later with different grouping, filtering, or format options.

Options
-------

.. option:: -g, --grouping [none|path|severity|id|validator|standard|dandiset]

    How to group the reported results.  Repeat the option for hierarchical
    nesting, e.g., ``-g severity -g id``.  [default: ``none``]

.. option:: --ignore REGEX

    Ignore any validation results whose ID matches the given regular
    expression

.. option:: --min-severity [INFO|HINT|WARNING|ERROR|CRITICAL]

    Only display results with severities at or above this level  [default:
    ``HINT``]

.. option:: -f, --format [text|json|json_pp|json_lines|yaml]

    Output format  [default: ``text``]

.. option:: -o, --output <file>

    Write the output to the given file instead of standard output.  This
    requires a structured :option:`--format`; if none is given, the format is
    inferred from the file's extension (``.json``, ``.jsonl``, ``.yaml``, or
    ``.yml``).  :option:`--grouping` cannot be combined with the ``json_lines``
    format.

.. option:: --summary, --no-summary

    Whether to show summary statistics (counts of results by severity,
    validator, and standard) after the results  [default: ``--no-summary``]

.. option:: --max-per-group N

    Limit the number of results shown per group (or in total when not
    grouping); the excess is replaced by a count of omitted results

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
        Stream the content of each such file with datalad-fuse_ so that
        content-dependent validators run without the file having to be
        downloaded; see `Validating DataLad Dandisets Remotely`_
        below.

.. option:: --load <file>

    Instead of running validation, load previously saved results from the
    given JSON Lines file (e.g., an automatically saved companion file) and
    render them.  Can be specified multiple times; cannot be combined with
    paths.

.. _DataLad: https://www.datalad.org
.. _git-annex: https://git-annex.branchable.com


Validating DataLad Dandisets Remotely
-------------------------------------

Every Dandiset on the DANDI Archive is mirrored as a DataLad dataset at
https://github.com/dandisets (with https://github.com/dandisets/dandisets as
the superdataset containing all of them).  In such a dataset, the assets are
annexed files: symbolic links that remain broken until the content is fetched,
which for some Dandisets would mean downloading terabytes of data.  The
``stream`` policy of :option:`--missing-file-content` lets ``dandi validate``
run the content-dependent validators (pynwb and nwbinspector for NWB files) on
such files by streaming their content on demand with datalad-fuse_ (without
mounting anything), which asks git-annex where the content is, reading only
the parts of each file that the validators need.  This requires git-annex and
``pip install "dandi[datalad]"``.

For example, to produce a JSON Lines record of *all* validation results for
a Dandiset::

    datalad clone https://github.com/dandisets/000003
    dandi validate --missing-file-content=stream --min-severity=INFO \
        --format=json_lines --output=000003.jsonl 000003

Each streamed file yields an ``INFO``-level ``DANDI.FILE_CONTENT_STREAMED``
result naming the first URL known for its content (for a Dandiset, the DANDI
Archive's API download URL, which redirects to S3); a file that cannot be streamed
(not an annexed file, or no URL known to git-annex) yields a
``DANDI.FILE_CONTENT_MISSING`` error instead.

Notes:

- git-annex must be initialized in the clone, which ``datalad clone`` does
  (after ``git clone``, run ``git annex init``).
- With the development version of datalad-fuse from
  https://github.com/datalad/datalad-fuse/pull/131 and remfile_ installed
  (``pip install remfile``), NWB and other HDF5-based files are read with
  remfile, which is optimized for HDF5's access pattern, and content exported
  to S3 without a URL registered in git-annex can be found too.
- datalad-fuse does not use the HTTP proxy environment variables
  (``HTTPS_PROXY`` etc.), so the URLs must be reachable directly.
- Some nwbinspector checks read data arrays (e.g., timestamps), so the amount
  of data streamed for a file depends on its content; it is nevertheless
  usually a small fraction of the file.
- The pynwb validation results and the metadata of a streamed file are cached
  under its git-annex key (a digest of its content), just as those of a local
  file are cached under its modification time and size, so re-running the
  command skips that work for files whose key has not changed since.  As for
  local files, set the :envvar:`DANDI_CACHE` environment variable to ``clear``
  to start afresh or to ``ignore`` to bypass the cache.
- Zarr assets are stored as separate subdatasets (https://github.com/dandizarrs)
  and are not streamed yet: an uninstalled Zarr subdataset is an empty directory
  that is not validated at all.  Streaming them is a follow-up for when NWB Zarr
  support has matured across the ecosystem.
- The BIDS validator cannot stream content, so BIDS errors that require reading
  a file (e.g., unreadable NIfTI headers) are suppressed for annexed files under
  the ``stream`` and ``only-non-data`` policies.  For NWB datasets, the primary
  use case, nothing is lost: everything the BIDS validator needs is either
  present (the non-annexed sidecar files, which are kept in git) or encoded in
  the file and folder names of the annexed files themselves.

.. _datalad-fuse: https://github.com/datalad/datalad-fuse
.. _remfile: https://github.com/flatironinstitute/remfile


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
