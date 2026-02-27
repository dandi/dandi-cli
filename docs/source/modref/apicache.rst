.. module:: dandi.apicache

``dandi.apicache``
==================

This module provides a persistent, sqlite3-backed cache for metadata returned
by the DANDI REST API.  It is used internally by `~dandi.dandiapi.DandiAPIClient`
when ``cache=True`` is passed at construction time.

Cached entries are keyed by ``(api_url, entity_type, entity_id)`` and validated
against the ``modified`` timestamp already present on every Dandiset version and
asset — no extra API calls are needed to check freshness.

The cache database is stored at
``platformdirs.user_cache_dir("dandi") / "api_metadata_cache.sqlite"``
by default and is controlled by the :envvar:`DANDI_CACHE` environment variable:

* ``DANDI_CACHE=ignore`` — disables the cache entirely (reads always miss).
* ``DANDI_CACHE=clear`` — wipes existing entries when the cache is opened.

.. autoclass:: APIMetadataCache
    :members:
