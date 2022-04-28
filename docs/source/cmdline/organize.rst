.. _dandi_organize:

:program:`dandi organize`
=========================

::

    dandi [<global options>] organize [<options>] [<path> ...]

(Re)organize files according to their metadata.

The purpose of this command is to take advantage of metadata contained in
:file:`*.nwb` files to provide datasets with consistently-named files whose
names reflect the data they contain.

:file:`*.nwb` files are organized into a hierarchy of subfolders, one per
"subject", e.g. :file:`sub-0001` if an :file:`*.nwb` file contained a Subject
group with ``subject_id=0001``.  Each file in a subject-specific subfolder
follows the pattern::

    sub-<subject_id>[_key-<value>][_mod1+mod2+...].nwb

where the following keys are considered if present in the data:

- ``ses`` — ``session_id``
- ``tis`` — ``tissue_sample_id``
- ``slice`` — ``slice_id``
- ``cell`` — ``cell_id``

and ``modX`` are "modalities" as identified based on detected neural data types
(such as "ecephys", "icephys") per extensions found in `nwb-schema definitions
<https://github.com/NeurodataWithoutBorders/nwb-schema/tree/dev/core>`_.

In addition, an "obj" key with a value corresponding to the crc32 checksum of
"object_id" is added if the aforementioned keys and the list of modalities are
not sufficient to disambiguate different files.

You can visit https://dandiarchive.org for a growing collection of
(re)organized dandisets.

Options
-------

.. option:: -d, --dandiset-path <dir>

    The root directory of the Dandiset to organize files under.  If not
    specified, the Dandiset under the current directory is assumed.  For
    'simulate' mode, the target Dandiset/directory must not exist.

.. option:: -f, --files-mode [dry|simulate|copy|move|hardlink|symlink|auto]

    How to relocate the files.

    - ``auto`` [default] — The first of ``symlink``, ``hardlink``, and ``copy``
      that is supported by the local filesystem

    - ``dry`` — No action is performed, suggested renames are printed

    - ``simulate`` — A hierarchy of empty files at :option:`--dandiset-path` is
      created.  Note that the previous layout should be removed prior to this
      operation.

.. option:: --invalid [fail|warn]

    What to do if files without sufficient metadata are encountered  [default:
    ``fail``]

.. option:: --update-external-file-paths

    Rewrite the ``external_file`` arguments of ImageSeries in NWB files.  The
    new values will correspond to the new locations of the video files after
    being organized.  This option requires :option:`--files-mode` to be
    "``copy``" or "``move``".

.. option:: --media-files-mode [copy|move|symlink|hardlink]

    How to relocate video files referenced by NWB files [default: ``symlink``]

Development Options
-------------------

The following options are intended only for development & testing purposes.
They are only available if the :envvar:`DANDI_DEVEL` environment variable is
set to a nonempty value.

.. option:: --devel-debug

    Do not use pyout callbacks, do not swallow exceptions, do not parallelize.
