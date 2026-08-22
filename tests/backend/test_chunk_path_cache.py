"""
Direct unit tests for core.chunk_path_cache.ChunkPathCache (#4245 extraction)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ChunkPathCache`` was extracted from ``ChunkedAudioProcessor``'s
``_get_chunk_path`` / ``_get_wav_chunk_path`` / ``_lookup_cached_chunk`` trio
plus the cache-key-then-store pattern duplicated at each of its callers'
cache-write sites. These tests exercise it directly, with fake/mocked
collaborators, no ``ChunkedAudioProcessor`` involved.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_cache_manager import ChunkCacheManager
from core.chunk_path_cache import ChunkPathCache


def _write_valid_wav(path: Path) -> None:
    """ChunkCacheManager.cache_chunk_path() requires a complete WAV, not just
    an existing file — write a tiny real one."""
    from auralis.io.saver import save as save_audio
    path.parent.mkdir(parents=True, exist_ok=True)
    save_audio(str(path), np.zeros((100, 2), dtype=np.float32), 44100, subtype="PCM_16")


def _make_path_cache(tmp_path, chunk_cache=None):
    wav_encoder = MagicMock()
    wav_encoder.get_chunk_path.side_effect = (
        lambda track_id, file_signature, preset, intensity, chunk_index: str(
            tmp_path / f"track_{track_id}_{file_signature}_{preset}_{intensity}_chunk_{chunk_index}.wav"
        )
    )
    cache_manager = ChunkCacheManager(chunk_cache if chunk_cache is not None else {})
    path_cache = ChunkPathCache(
        track_id=1,
        file_signature="sig123",
        preset="adaptive",
        intensity=1.0,
        wav_encoder=wav_encoder,
        cache_manager=cache_manager,
    )
    return path_cache, wav_encoder, cache_manager


class TestGetChunkPath:
    def test_returns_path_from_wav_encoder(self, tmp_path):
        path_cache, wav_encoder, _ = _make_path_cache(tmp_path)

        result = path_cache.get_chunk_path(0)

        assert isinstance(result, Path)
        wav_encoder.get_chunk_path.assert_called_once_with(
            track_id=1, file_signature="sig123", preset="adaptive", intensity=1.0, chunk_index=0
        )

    def test_different_chunk_indices_get_different_paths(self, tmp_path):
        path_cache, _, _ = _make_path_cache(tmp_path)

        assert path_cache.get_chunk_path(0) != path_cache.get_chunk_path(1)


class TestCacheKey:
    def test_matches_chunk_cache_manager_directly(self, tmp_path):
        path_cache, _, _ = _make_path_cache(tmp_path)

        assert path_cache.cache_key(3) == ChunkCacheManager.get_chunk_cache_key(
            1, "sig123", "adaptive", 1.0, 3
        )


class TestLookupCached:
    def test_miss_when_nothing_cached(self, tmp_path):
        path_cache, _, _ = _make_path_cache(tmp_path)

        assert path_cache.lookup_cached(0) is None

    def test_in_memory_hit(self, tmp_path):
        path_cache, _, cache_manager = _make_path_cache(tmp_path)
        cached_path = tmp_path / "in_memory.wav"
        _write_valid_wav(cached_path)
        cache_manager.cache_chunk_path(path_cache.cache_key(0), cached_path)

        assert path_cache.lookup_cached(0) == cached_path

    def test_on_disk_hit_is_promoted_to_in_memory_cache(self, tmp_path):
        path_cache, _, cache_manager = _make_path_cache(tmp_path)
        chunk_path = path_cache.get_chunk_path(0)
        _write_valid_wav(chunk_path)

        # In-memory tier is empty — must fall through to the on-disk check.
        result = path_cache.lookup_cached(0)

        assert result == chunk_path
        # Promoted into the in-memory tier for the next lookup.
        assert cache_manager.get_cached_chunk_path(path_cache.cache_key(0)) == chunk_path

    def test_truncated_on_disk_wav_is_treated_as_a_miss(self, tmp_path):
        path_cache, _, _ = _make_path_cache(tmp_path)
        chunk_path = path_cache.get_chunk_path(0)
        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        chunk_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVEnot-a-complete-file")

        assert path_cache.lookup_cached(0) is None


class TestStore:
    def test_store_then_lookup_round_trips(self, tmp_path):
        path_cache, _, cache_manager = _make_path_cache(tmp_path)
        chunk_path = tmp_path / "chunk_0.wav"
        _write_valid_wav(chunk_path)

        path_cache.store(0, chunk_path)

        assert cache_manager.get_cached_chunk_path(path_cache.cache_key(0)) == chunk_path
        assert path_cache.lookup_cached(0) == chunk_path
