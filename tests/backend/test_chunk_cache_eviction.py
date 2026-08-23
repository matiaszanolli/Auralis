"""
Regression tests for the on-disk chunk-cache reaper (#3834).

ChunkCacheManager pointed at /tmp/auralis_chunks WAV files with no size cap, so a
long session could fill /tmp. prune_chunk_directory now bounds the directory by
bytes (deleting oldest-by-mtime first), and cache_chunk_path runs it on a
throttle shared across all manager instances.
"""

import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

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


# ============================================================================
# #4838: _prune_lock (counter) and _prune_scan_lock (the scan itself) are
# separate, so a slow scan doesn't serialise every other concurrent writer's
# throttle check behind it.
# ============================================================================


def _reset_prune_state():
    """Fresh locks + counter so a prior test's state (or a crashed mid-scan
    hold) can't bleed into these — the class-level locks are shared."""
    ChunkCacheManager._write_counter = 0
    ChunkCacheManager._prune_lock = threading.Lock()
    ChunkCacheManager._prune_scan_lock = threading.Lock()


def test_counter_check_does_not_block_on_an_in_progress_scan(tmp_path):
    """A writer whose counter check crosses the throttle while ANOTHER
    writer's scan is already running must not wait for that scan — it
    should observe the scan lock is held and return immediately (skip)."""
    _reset_prune_state()
    scan_started = threading.Event()
    release_scan = threading.Event()

    def _slow_scan(chunk_dir, max_bytes):
        scan_started.set()
        release_scan.wait(timeout=5)
        return (0, 0)

    mgr = ChunkCacheManager({}, max_disk_bytes=1, prune_every=1)

    with patch.object(ChunkCacheManager, "prune_chunk_directory", side_effect=_slow_scan):
        t = threading.Thread(target=mgr._maybe_prune, args=(tmp_path,))
        t.start()
        assert scan_started.wait(timeout=5), "first prune never started its scan"

        # Second trigger while the first scan is still in flight: must return
        # promptly (not block on the scan) — bounded wait proves it.
        start = time.monotonic()
        mgr._maybe_prune(tmp_path)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, (
            f"_maybe_prune blocked {elapsed:.2f}s waiting on an in-progress scan "
            "instead of skipping (#4838)"
        )

        release_scan.set()
        t.join(timeout=5)


def test_only_one_scan_runs_at_a_time(tmp_path):
    """Two overlapping triggers must not both enter prune_chunk_directory —
    the non-blocking scan-lock guard skips the second."""
    _reset_prune_state()
    call_count = 0
    call_lock = threading.Lock()
    scan_started = threading.Event()
    release_scan = threading.Event()

    def _slow_scan(chunk_dir, max_bytes):
        nonlocal call_count
        with call_lock:
            call_count += 1
        scan_started.set()
        release_scan.wait(timeout=5)
        return (0, 0)

    mgr = ChunkCacheManager({}, max_disk_bytes=1, prune_every=1)

    with patch.object(ChunkCacheManager, "prune_chunk_directory", side_effect=_slow_scan):
        t = threading.Thread(target=mgr._maybe_prune, args=(tmp_path,))
        t.start()
        assert scan_started.wait(timeout=5)

        mgr._maybe_prune(tmp_path)  # must skip, not run a second scan

        release_scan.set()
        t.join(timeout=5)

    assert call_count == 1, f"expected exactly 1 scan, got {call_count}"


def test_scan_lock_is_released_after_a_normal_scan_so_the_next_trigger_can_run(tmp_path):
    """The scan lock must not be left held after prune_chunk_directory
    returns normally — the NEXT throttle trigger must be able to scan."""
    _reset_prune_state()
    mgr = ChunkCacheManager({}, max_disk_bytes=1000, prune_every=1)

    call_count = 0

    def _fast_scan(chunk_dir, max_bytes):
        nonlocal call_count
        call_count += 1
        return (0, 0)

    with patch.object(ChunkCacheManager, "prune_chunk_directory", side_effect=_fast_scan):
        mgr._maybe_prune(tmp_path)
        mgr._maybe_prune(tmp_path)

    assert call_count == 2, "scan lock must be released so subsequent triggers can scan"


def test_scan_lock_is_released_even_if_the_scan_raises(tmp_path):
    """A scan that raises must still release the lock — otherwise every
    future trigger silently skips forever."""
    _reset_prune_state()
    mgr = ChunkCacheManager({}, max_disk_bytes=1000, prune_every=1)

    def _raising_scan(chunk_dir, max_bytes):
        raise RuntimeError("simulated scan failure")

    with patch.object(ChunkCacheManager, "prune_chunk_directory", side_effect=_raising_scan):
        try:
            mgr._maybe_prune(tmp_path)
        except RuntimeError:
            pass

    assert ChunkCacheManager._prune_scan_lock.acquire(blocking=False), (
        "scan lock was left held after the scan raised"
    )
    ChunkCacheManager._prune_scan_lock.release()
