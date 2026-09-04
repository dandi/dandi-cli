.. module:: dandi.dandiset

``dandi.dandiset``
==================

This module provides the local Dandiset API.  A local Dandiset can report the
subject labels represented by its top-level ``sub-*`` directories without
opening or scanning the files within them:

.. code-block:: python

    from dandi.dandiset import Dandiset

    dandiset = Dandiset("/data/my-dandiset")
    print(dandiset.get_subject_ids())

.. autoclass:: Dandiset()
    :members:

.. autoclass:: AssetView()
    :members:
