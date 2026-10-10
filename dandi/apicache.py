"""Persistent sqlite3-backed cache for DANDI API metadata responses.

The cache stores metadata keyed by ``(api_url, entity_type, entity_id)`` and
validates entries against a *modified* timestamp so that stale data is
automatically discarded without extra API calls.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3

from platformdirs import user_cache_dir

from . import get_logger

lgr = get_logger()

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS metadata_cache (
    api_url     TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    modified    TEXT NOT NULL,
    metadata    TEXT NOT NULL,
    PRIMARY KEY (api_url, entity_type, entity_id)
);
"""


class APIMetadataCache:
    """A lightweight, persistent metadata cache backed by sqlite3.

    Parameters
    ----------
    db_path : Path or None
        Explicit path for the sqlite database.  When *None* (the default) the
        database is placed under ``platformdirs.user_cache_dir("dandi")``.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path(user_cache_dir("dandi")) / "api_metadata_cache.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path

        dandi_cache = os.environ.get("DANDI_CACHE", "").lower()
        if dandi_cache == "ignore":
            lgr.debug("DANDI_CACHE=ignore: API metadata cache disabled")
            self._enabled = False
            return

        self._enabled = True
        self._con = sqlite3.connect(str(db_path), check_same_thread=False)
        self._con.execute("PRAGMA journal_mode=WAL;")
        self._con.execute(_SCHEMA)
        self._con.commit()

        if dandi_cache == "clear":
            lgr.debug("DANDI_CACHE=clear: clearing API metadata cache")
            self.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(
        self,
        api_url: str,
        entity_type: str,
        entity_id: str,
        modified: str,
    ) -> dict | None:
        """Return cached metadata if *modified* matches, else ``None``.

        Parameters
        ----------
        api_url : str
            Base URL of the DANDI API server.
        entity_type : str
            ``"dandiset"`` or ``"asset"``.
        entity_id : str
            Unique identifier for the entity (asset UUID, or
            ``"<dandiset_id>/<version_id>"`` for Dandisets).
        modified : str
            ISO-8601 timestamp of the entity's last modification.  A cache
            hit is only returned when this value matches the stored entry.

        Returns
        -------
        dict or None
            The cached metadata dict, or ``None`` on a cache miss.
        """
        if not self._enabled:
            return None
        row = self._con.execute(
            "SELECT metadata FROM metadata_cache "
            "WHERE api_url = ? AND entity_type = ? AND entity_id = ? AND modified = ?",
            (api_url, entity_type, entity_id, modified),
        ).fetchone()
        if row is not None:
            lgr.debug("API cache hit: %s %s %s", entity_type, entity_id, modified)
            return json.loads(row[0])  # type: ignore[no-any-return]
        return None

    def set(
        self,
        api_url: str,
        entity_type: str,
        entity_id: str,
        modified: str,
        metadata: dict,
    ) -> None:
        """Insert or replace a cache entry.

        Parameters
        ----------
        api_url : str
            Base URL of the DANDI API server.
        entity_type : str
            ``"dandiset"`` or ``"asset"``.
        entity_id : str
            Unique identifier for the entity.
        modified : str
            ISO-8601 timestamp of the entity's last modification.
        metadata : dict
            The raw metadata dict to cache.
        """
        if not self._enabled:
            return
        self._con.execute(
            "INSERT OR REPLACE INTO metadata_cache "
            "(api_url, entity_type, entity_id, modified, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (api_url, entity_type, entity_id, modified, json.dumps(metadata)),
        )
        self._con.commit()
        lgr.debug("API cache set: %s %s %s", entity_type, entity_id, modified)

    def clear(self) -> None:
        """Delete all cached entries from the database."""
        if not self._enabled:
            return
        self._con.execute("DELETE FROM metadata_cache")
        self._con.commit()
        lgr.debug("API metadata cache cleared")
