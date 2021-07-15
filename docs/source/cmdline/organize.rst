:program:`dandi organize`
=========================

::

    dandi [<global options>] organize [<options>] [<path> ...]

(Re)organize files according to the metadata.

The purpose of this command is to take advantage of metadata contained in the
.nwb files to provide datasets with consistently named files, so their naming
reflects data they contain.

.nwb files are organized into a hierarchy of subfolders one per each "subject",
e.g. sub-0001 if .nwb file had contained a Subject group with subject_id=0001.
Each file in a subject-specific subfolder follows the convention::

    sub-<subject_id>[_key-<value>][_mod1+mod2+...].nwb

where following keys are considered if present in the data::

    ses -- session_id
    tis -- tissue_sample_id
    slice -- slice_id
    cell -- cell_id

and ``modX`` are "modalities" as identified based on detected neural data types
(such as "ecephys", "icephys") per extensions found in nwb-schema definitions:
https://github.com/NeurodataWithoutBorders/nwb-schema/tree/dev/core

In addition an "obj" key with a value corresponding to crc32 checksum of
"object_id" is added if aforementioned keys and the list of modalities are
not sufficient to disambiguate different files.

You can visit https://dandiarchive.org for a growing collection of
(re)organized dandisets.

Options
-------

.. options:: -d, --dandiset-path <dir>

    A top directory (local) of the dandiset to organize files under.  If not
    specified, dandiset current directory is under is assumed.  For 'simulate'
    mode target dandiset/directory must not exist.

.. option:: --invalid [fail|warn]

    What to do if files without sufficient metadata are encountered.

.. option:: -f, --files-mode [dry|simulate|copy|move|hardlink|symlink|auto]

    If 'dry' - no action is performed, suggested renames are printed.  If
    'simulate' - hierarchy of empty files at --local-top-path is created.  Note
    that previous layout should be removed prior this operation.  If 'auto'
    (default) - whichever of symlink, hardlink, copy is allowed by system.  The
    other modes (copy, move, symlink, hardlink) define how data files should be
    made available.
