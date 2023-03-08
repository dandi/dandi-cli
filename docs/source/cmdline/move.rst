:program:`dandi move`
=====================

::

    dandi [<global options>] move [<options>] <src-path> ... <dest-path>
    dandi [<global options>] move --regex [<options>] <pattern> <replacement>

Move or rename assets in a local Dandiset and/or on the server.  The
:program:`dandi move` command takes one of more source paths of the assets to
move, followed by a destination path indicating where to move them to.  Paths
given on the command line must use forward slashes (``/``) as path separators,
even on Windows.  In addition, when running the command inside a subdirectory
of a Dandiset, all paths must be relative to the subdirectory, even if only
operating on the remote Dandiset.  (The exception is when the ``--dandiset``
option is given in order to operate on an arbitrary remote Dandiset, in which
case any local Dandiset is ignored and paths are interpreted relative to the
root of the remote Dandiset.)

If there is more than one source path, or if the destination path either names
an existing directory or ends in a trailing forward slash (``/``), then the
source assets are placed within the destination directory.  Otherwise, the
single source path is renamed to the given destination path.

Alternatively, if the ``--regex`` option is given, then there must be exactly
two arguments on the command line: a `Python regular expression`_ and a
replacement string, possibly containing regex backreferences.  :program:`dandi
move` will then apply the regular expression to the path of every asset in the
current directory recursively (using paths relative to the current directory,
if in a subdirectory of a Dandiset); if a path matches, the matching portion is
replaced with the replacement string, after expanding any backreferences.

.. _Python regular expression: https://docs.python.org/3/library/re.html
                               #regular-expression-syntax


Options
-------

.. option:: -i, --dandi-instance <instance-name>

    DANDI instance containing the remote Dandiset corresponding to the local
    Dandiset in the current directory [default: ``dandi``]

.. option:: -d, --dandiset <URL>

    A :ref:`resource identifier <resource_ids>` pointing to a Dandiset on a
    remote instance whose assets you wish to move/rename

.. option:: --dry-run

    Show what would be moved but do not move anything

.. option:: -e, --existing [error|skip|overwrite]

    How to handle assets that would be moved to a destination where an asset
    already exists:

    - ``error`` [default] — raise an error
    - ``skip`` — skip the move
    - ``overwrite`` — delete the asset already at the destination

.. option:: -J, --jobs <int>

    Number of assets to move in parallel; the default value is determined by
    the number of CPU cores on your machine

.. option:: --regex

    Treat the command-line arguments as a regular expression and a replacement
    string, and perform the given substitution on all asset paths in the
    current directory recursively.

.. option:: -w, --work-on [auto|both|local|remote]

    Whether to operate on the local Dandiset in the current directory, a remote
    Dandiset (either one specified by the ``--dandiset`` option or else the one
    corresponding to the local Dandiset), or both at once.  If ``auto`` (the
    default) is given, it is treated the same as ``remote`` if a ``--dandiset``
    option is given and as ``both`` otherwise.


Development Options
-------------------

The following options are intended only for development & testing purposes.
They are only available if the :envvar:`DANDI_DEVEL` environment variable is
set to a nonempty value.

.. option:: --devel-debug

    Do not use pyout callbacks, do not swallow exceptions, do not parallelize.


Examples
--------

- When working in a local clone of a Dandiset, a file
  :file:`sub-01/sub-01_blah.nii.gz` can be renamed to
  :file:`sub-02/sub-02_useful.nii.gz` in both the local clone and on the server
  with::

    dandi move sub-01/sub-01_blah.nii.gz sub-02/sub-02_useful.nii.gz

  To rename the file only in the local or remote instance, insert ``--work-on
  local`` or ``--work-on remote`` after ``move``.

- When not working in a local clone of a Dandiset, a file can be renamed in a
  remote Dandiset on a server by providing a resource identifier for the
  Dandiset to the ``--dandiset`` option.  For example, in order to operate on
  Dandiset 123456 on the main ``dandi`` instance, use::

    dandi move --dandiset DANDI:123456 sub-01/sub-01_blah.nii.gz sub-02/sub-02_useful.nii.gz

  To operate on Dandiset 123456 on ``dandi-staging``, you can use::

    dandi move --dandiset https://gui-staging.dandiarchive.org/dandiset/123456 sub-01/sub-01_blah.nii.gz sub-02/sub-02_useful.nii.gz

- To move the contents of a folder :file:`rawdata/` to the top level of a
  Dandiset, you can use the ``--regex`` option to strip the ``rawdata/`` prefix
  from the beginning of all matching asset paths::

    dandi move --regex "^rawdata/" ""
