.. module:: dandi.dandiset

``dandi.dandiset``
==================

This module provides the local Dandiset API.  A local Dandiset can report the
subject labels represented by populated, valid top-level ``sub-*`` directories.
It walks directory entries to establish that a subject contains a file, but it
does not open file contents. Empty and symlinked subject directories are
ignored:

.. code-block:: python

    from dandi.dandiset import Dandiset

    dandiset = Dandiset("/data/my-dandiset")
    print(dandiset.get_subject_ids())

.. autoclass:: Dandiset()
    :members:

.. autoclass:: AssetView()
    :members:
