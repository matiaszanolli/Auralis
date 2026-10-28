"""A chunk cache disk hit cannot hand back a file the reaper just deleted (#5967).

Every new processor starts with an empty in-memory cache, so a reused chunk is a
disk hit. ``lookup_cached`` validated the WAV and then called
``cache_chunk_path``, whose write-count reaper could delete the oldest WAV in
the shared directory, including the one about to be returned. The hit path now
re-records without counting toward the reaper, refreshes the mtime so the
oldest-first reaper is really LRU, and ``process_chunk`` re-renders when the
file still vanishes between lookup and read.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import chunk_streaming  # noqa: E402
from core.chunk_cache_manager import ChunkCacheManager  # noqa: E402
from core.chunk_path_cache import ChunkPathCache  # noqa: E402


def _write_wav(path: Path) -> None:
    from auralis.io.saver import save as save_audio
    path.parent.mkdir(parents=True, exist_ok=True)
    save_audio(str(path), np.zeros((100, 2), dtype=np.float32), 44100, subtype="PCM_16")


def _path_cache(tmp_path, prune_every=1):
    wav_encoder = MagicMock()
    wav_encoder.get_chunk_path.side_effect = (
        lambda track_id, file_signature, preset, intensity, chunk_index, targets_hash: str(
            tmp_path / f"c{chunk_index}.wav"
        )
    )
    manager = ChunkCacheManager({}, prune_every=prune_every)
    return ChunkPathCache(1, "sig", "adaptive", 1.0, wav_encoder, manager), manager


@pytest.fixture(autouse=True)
def _reset_prune_counter():
    ChunkCacheManager._write_counter = 0
    yield
    ChunkCacheManager._write_counter = 0


def test_a_disk_hit_does_not_run_the_reaper(tmp_path):
    cache, manager = _path_cache(tmp_path)
    _write_wav(tmp_path / "c0.wav")

    with patch.object(ChunkCacheManager, "prune_chunk_directory") as prune:
        assert cache.lookup_cached(0) == tmp_path / "c0.wav"

    prune.assert_not_called()


def test_a_disk_hit_refreshes_the_mtime(tmp_path):
    cache, _ = _path_cache(tmp_path)
    wav = tmp_path / "c0.wav"
    _write_wav(wav)
    os.utime(wav, (1_000_000, 1_000_000))

    cache.lookup_cached(0)

    assert wav.stat().st_mtime > 1_000_000


def test_the_hit_is_recorded_so_the_next_lookup_is_in_memory(tmp_path):
    cache, manager = _path_cache(tmp_path)
    _write_wav(tmp_path / "c0.wav")
    cache.lookup_cached(0)
    assert manager.get_cached_chunk_path(cache.cache_key(0)) == tmp_path / "c0.wav"


def test_a_real_write_still_counts_toward_the_reaper(tmp_path):
    cache, _ = _path_cache(tmp_path)
    wav = tmp_path / "c1.wav"
    _write_wav(wav)

    with patch.object(ChunkCacheManager, "prune_chunk_directory") as prune:
        cache.store(1, wav)

    prune.assert_called_once()


def test_process_chunk_re_renders_when_the_cached_file_vanishes(tmp_path):
    """The file passes lookup but is gone by read time: fall through to the
    render path instead of failing the stream."""
    processor = MagicMock()
    processor._lookup_cached_chunk.return_value = tmp_path / "gone.wav"
    reached_render = RuntimeError("reached the render path")

    with patch.object(chunk_streaming, "_raise_if_cancelled", side_effect=reached_render):
        with pytest.raises(RuntimeError, match="reached the render path"):
            chunk_streaming.process_chunk(processor, 0, False, locked=False)
