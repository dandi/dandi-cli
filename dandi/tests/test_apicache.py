"""Tests for the persistent API metadata cache."""

from __future__ import annotations

import pytest

from dandi.apicache import APIMetadataCache


@pytest.mark.ai_generated
class TestAPIMetadataCache:
    API_URL = "https://api.dandiarchive.org/api"

    def test_cache_miss(self, tmp_path: pytest.TempPathFactory) -> None:
        cache = APIMetadataCache(db_path=tmp_path / "cache.sqlite")
        result = cache.get(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z")
        assert result is None

    def test_set_then_get(self, tmp_path: pytest.TempPathFactory) -> None:
        cache = APIMetadataCache(db_path=tmp_path / "cache.sqlite")
        metadata = {"name": "test-asset", "size": 42}
        cache.set(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z", metadata)
        result = cache.get(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z")
        assert result == metadata

    def test_stale_modified_returns_none(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        cache = APIMetadataCache(db_path=tmp_path / "cache.sqlite")
        metadata = {"name": "test-asset", "size": 42}
        cache.set(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z", metadata)
        # Different modified timestamp -> cache miss
        result = cache.get(self.API_URL, "asset", "abc-123", "2024-06-15T12:00:00Z")
        assert result is None

    def test_update_replaces_entry(self, tmp_path: pytest.TempPathFactory) -> None:
        cache = APIMetadataCache(db_path=tmp_path / "cache.sqlite")
        cache.set(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z", {"v": 1})
        cache.set(self.API_URL, "asset", "abc-123", "2024-06-15T12:00:00Z", {"v": 2})
        # Old modified no longer matches
        assert (
            cache.get(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z") is None
        )
        # New modified matches
        assert cache.get(self.API_URL, "asset", "abc-123", "2024-06-15T12:00:00Z") == {
            "v": 2
        }

    def test_clear(self, tmp_path: pytest.TempPathFactory) -> None:
        cache = APIMetadataCache(db_path=tmp_path / "cache.sqlite")
        cache.set(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z", {"a": 1})
        cache.clear()
        assert (
            cache.get(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z") is None
        )

    def test_different_entity_types(self, tmp_path: pytest.TempPathFactory) -> None:
        cache = APIMetadataCache(db_path=tmp_path / "cache.sqlite")
        cache.set(
            self.API_URL, "asset", "id1", "2024-01-01T00:00:00Z", {"type": "asset"}
        )
        cache.set(
            self.API_URL,
            "dandiset",
            "id1",
            "2024-01-01T00:00:00Z",
            {"type": "dandiset"},
        )
        assert cache.get(self.API_URL, "asset", "id1", "2024-01-01T00:00:00Z") == {
            "type": "asset"
        }
        assert cache.get(self.API_URL, "dandiset", "id1", "2024-01-01T00:00:00Z") == {
            "type": "dandiset"
        }

    def test_dandi_cache_ignore(
        self, tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DANDI_CACHE", "ignore")
        cache = APIMetadataCache(db_path=tmp_path / "cache.sqlite")
        cache.set(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z", {"a": 1})
        # Even after set, get returns None because cache is disabled
        assert (
            cache.get(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z") is None
        )

    def test_dandi_cache_clear(
        self, tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # First, populate the cache normally
        cache1 = APIMetadataCache(db_path=tmp_path / "cache.sqlite")
        cache1.set(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z", {"a": 1})
        assert cache1.get(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z") == {
            "a": 1
        }

        # Now open with DANDI_CACHE=clear — old data should be gone
        monkeypatch.setenv("DANDI_CACHE", "clear")
        cache2 = APIMetadataCache(db_path=tmp_path / "cache.sqlite")
        assert (
            cache2.get(self.API_URL, "asset", "abc-123", "2024-01-01T00:00:00Z") is None
        )
