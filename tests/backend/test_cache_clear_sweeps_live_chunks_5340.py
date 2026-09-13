"""Cache clears reach the chunk files live playback wrote to disk (#5340).

StreamlinedCacheManager.clear_track()/clear_all() only unlinked paths recorded
in its tier dicts, which only the background worker populates. Live playback
(and pre-warm) write the same chunk directory directly, and ChunkPathCache
finds those files by name alone — so "Clear Cache" and library reset left
exactly the files the next play serves. Chunk names here come from the real
WAVEncoder.get_chunk_path, so the sweep's glob cannot drift from the writer.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# tests/backend/conftest.py puts auralis-web/backend on sys.path.
from cache.manager import StreamlinedCacheManager
from core.cache_cleanup import clear_all_caches
from core.encoding.atomic_io import PARTIAL_SUFFIX
from core.encoding.wav_encoder import WAVEncoder, delete_chunk_files


@pytest.fixture
def chunk_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "auralis_chunks"
    directory.mkdir()
    return directory


def _live_chunk(chunk_dir: Path, track_id: int, chunk_index: int, signature: str = "a1b2c3d4") -> Path:
    path = WAVEncoder(chunk_dir).get_chunk_path(
        track_id=track_id,
        file_signature=signature,
        preset="adaptive",
        intensity=1.0,
        chunk_index=chunk_index,
        targets_hash="none",
    )
    path.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    return path


def _staged_write(chunk_dir: Path, published: Path) -> Path:
    staged = chunk_dir / f"{published.stem}{PARTIAL_SUFFIX}.wav"
    staged.write_bytes(b"in flight")
    return staged


class TestDeleteChunkFiles:
    def test_track_scope_removes_only_that_tracks_published_chunks(self, chunk_dir):
        mine = [_live_chunk(chunk_dir, 1, 0), _live_chunk(chunk_dir, 1, 1)]
        legacy = chunk_dir / "track_1_a1b2c3d4_adaptive_1.0_chunk_2.wav"
        legacy.write_bytes(b"old format")
        other_track = _live_chunk(chunk_dir, 12, 0)  # "track_1" must not match "track_12"
        staged = _staged_write(chunk_dir, mine[0])

        assert delete_chunk_files(chunk_dir, 1) == 3

        assert not any(p.exists() for p in (*mine, legacy))
        assert other_track.exists()
        assert staged.exists(), "an in-flight staged write must be left to its writer"

    def test_unscoped_sweep_removes_every_published_chunk(self, chunk_dir):
        chunks = [_live_chunk(chunk_dir, 1, 0), _live_chunk(chunk_dir, 2, 0)]
        staged = _staged_write(chunk_dir, chunks[0])
        unrelated = chunk_dir / "notes.txt"
        unrelated.write_text("not a chunk")

        assert delete_chunk_files(chunk_dir) == 2

        assert not any(p.exists() for p in chunks)
        assert staged.exists() and unrelated.exists()

    def test_missing_directory_is_nothing_to_delete(self, tmp_path):
        assert delete_chunk_files(tmp_path / "never-created") == 0

    def test_cleanup_track_chunks_is_scoped_to_one_file_signature(self, chunk_dir):
        current = _live_chunk(chunk_dir, 1, 0, signature="aaaa1111")
        replaced_file = _live_chunk(chunk_dir, 1, 0, signature="bbbb2222")

        assert WAVEncoder(chunk_dir).cleanup_track_chunks(1, "aaaa1111") == 1

        assert not current.exists()
        assert replaced_file.exists()


class TestClearPathsSweepTheDirectory:
    @pytest.mark.asyncio
    async def test_clear_track_removes_chunks_the_tiers_never_recorded(self, chunk_dir):
        manager = StreamlinedCacheManager()
        manager.chunk_dir = chunk_dir
        played = [_live_chunk(chunk_dir, 1, 0), _live_chunk(chunk_dir, 1, 1)]
        other_track = _live_chunk(chunk_dir, 2, 0)

        await manager.clear_track(1)

        assert not any(p.exists() for p in played)
        assert other_track.exists()

    @pytest.mark.asyncio
    async def test_clear_all_caches_sweeps_live_chunks(self, chunk_dir, tmp_path):
        manager = AsyncMock()
        played = [_live_chunk(chunk_dir, 1, 0), _live_chunk(chunk_dir, 2, 3)]

        result = await clear_all_caches(manager, tmp_path / "artwork", chunk_dir=chunk_dir)

        manager.clear_all.assert_awaited_once_with()
        assert result.chunk_files_removed == 2
        assert not any(p.exists() for p in played)

    @pytest.mark.asyncio
    async def test_library_reset_without_a_cache_manager_still_sweeps(self, chunk_dir, tmp_path):
        """The streamlined cache can be disabled; the chunk files still exist."""
        played = _live_chunk(chunk_dir, 1, 0)

        result = await clear_all_caches(
            None, tmp_path / "artwork", clear_source_artwork=True, chunk_dir=chunk_dir
        )

        assert result.chunk_files_removed == 1
        assert not played.exists()
