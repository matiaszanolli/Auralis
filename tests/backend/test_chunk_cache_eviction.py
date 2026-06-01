"""
Regression tests for the on-disk chunk-cache reaper (#3834).

ChunkCacheManager pointed at /tmp/auralis_chunks WAV files with no size cap, so a
long session could fill /tmp. prune_chunk_directory now bounds the directory by
bytes (deleting oldest-by-mtime first), and cache_chunk_path runs it on a
throttle shared across all manager instances.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_cache_manager import ChunkCacheManager


def _make_file(d: Path, name: str, size: int, mtime: float) -> Path:
    p = d / name
    p.write_bytes(b"\x00" * size)
    os.utime(p, (mtime, mtime))
    return p


def test_prune_deletes_oldest_until_under_cap(tmp_path):
    for i in range(5):
        _make_file(tmp_path, f"chunk_{i}.wav", 100, mtime=1000 + i)  # ascending mtime

    deleted, reclaimed = ChunkCacheManager.prune_chunk_directory(tmp_path, max_bytes=250)

    assert deleted == 3 and reclaimed == 300
    remaining = sorted(p.name for p in tmp_path.iterdir())
    # The two NEWEST survive (mtime-LRU); total 200 <= 250.
    assert remaining == ["chunk_3.wav", "chunk_4.wav"]


def test_prune_under_cap_is_noop(tmp_path):
    _make_file(tmp_path, "a.wav", 50, mtime=1000)
    assert ChunkCacheManager.prune_chunk_directory(tmp_path, max_bytes=1000) == (0, 0)
    assert (tmp_path / "a.wav").exists()


def test_prune_missing_dir_is_safe(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert ChunkCacheManager.prune_chunk_directory(missing, max_bytes=10) == (0, 0)


def test_prune_keeps_just_written_chunk(tmp_path):
    """The newest file must never be the one evicted when others can satisfy the cap."""
    old = _make_file(tmp_path, "old.wav", 200, mtime=1000)
    new = _make_file(tmp_path, "new.wav", 200, mtime=2000)
    ChunkCacheManager.prune_chunk_directory(tmp_path, max_bytes=200)
    assert new.exists() and not old.exists()


def test_cache_chunk_path_triggers_prune_on_throttle(tmp_path):
    """cache_chunk_path runs the reaper every `prune_every` writes; the shared
    counter trips on the configured boundary and bounds the directory."""
    # Reset the class-level throttle so this test is deterministic regardless of
    # other tests that exercised cache_chunk_path.
    ChunkCacheManager._write_counter = 0

    mgr = ChunkCacheManager({}, max_disk_bytes=250, prune_every=3)
    for i in range(3):
        p = _make_file(tmp_path, f"c{i}.wav", 100, mtime=2000 + i)
        mgr.cache_chunk_path(f"k{i}", p)  # 3rd write hits the throttle → prune

    remaining = sorted(p.name for p in tmp_path.iterdir())
    # 300 bytes > 250 cap → oldest (c0) evicted, c1+c2 (200) kept.
    assert remaining == ["c1.wav", "c2.wav"], remaining


def test_cache_chunk_path_no_prune_before_threshold(tmp_path):
    ChunkCacheManager._write_counter = 0
    mgr = ChunkCacheManager({}, max_disk_bytes=50, prune_every=10)
    for i in range(3):
        p = _make_file(tmp_path, f"c{i}.wav", 100, mtime=3000 + i)
        mgr.cache_chunk_path(f"k{i}", p)
    # Threshold (10) not reached → nothing pruned yet even though over cap.
    assert len(list(tmp_path.iterdir())) == 3
