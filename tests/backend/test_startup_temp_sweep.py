"""
Regression tests for the startup temp-stream sweep (#3877) and the
startup temp-file age sweep (#4762).

stream_normal_audio writes a temp WAV under `auralis_stream_*` and cleans it in
its finally block, but a crash or a locked file (Windows AV / cloud-sync) can
orphan one. `reclaim_leftover_stream_temps` sweeps and counts these on startup
so any leak surfaces in the log and stays bounded — and, unlike the old
`rmtree(..., ignore_errors=True)` + `except: pass`, a removal failure is logged
rather than silently swallowed.

`auralis_processing` (rendered job outputs) and `auralis_uploads` (uploaded
inputs) are otherwise only reclaimed by `ProcessingEngine.cleanup_old_jobs()`,
which is driven off the in-memory jobs registry — empty after any crash or
restart. `reclaim_stale_temp_entries` age-sweeps those directories by mtime
instead, independent of any registry.
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.limits import CHUNK_TEMP_DIRNAME
from config.startup import reclaim_leftover_stream_temps, reclaim_stale_temp_entries


def _age_entry(path: Path, hours: float) -> Path:
    """Backdate an entry's mtime so it looks `hours` old to the sweep."""
    stale_time = time.time() - (hours * 3600)
    import os
    os.utime(path, (stale_time, stale_time))
    return path


def _make_stream_dir(root: Path, name: str) -> Path:
    d = root / name
    d.mkdir()
    (d / "stream.wav").write_bytes(b"\x00\x01\x02")  # non-empty so rmtree recurses
    return d


def test_reclaims_matching_dirs(tmp_path):
    """All orphaned auralis_stream_* dirs are removed and counted.

    #4713 backdated these: an *untagged* directory (no owning PID in its name)
    is only reclaimed once it is older than max_age_hours, because ownership is
    unknowable and a fresh one may belong to a live instance.
    """
    for name in ("auralis_stream_aaa", "auralis_stream_bbb", "auralis_stream_ccc"):
        _age_entry(_make_stream_dir(tmp_path, name), hours=2.0)

    count = reclaim_leftover_stream_temps(tmp_path)

    assert count == 3
    assert list(tmp_path.glob("auralis_stream_*")) == []


def test_ignores_non_matching_dirs(tmp_path):
    """Unrelated temp dirs (e.g. auralis_chunks) are left untouched."""
    chunks = tmp_path / CHUNK_TEMP_DIRNAME
    chunks.mkdir()
    other = tmp_path / "some_other_dir"
    other.mkdir()

    count = reclaim_leftover_stream_temps(tmp_path)

    assert count == 0
    assert chunks.exists() and other.exists()


def test_empty_sweep_returns_zero_silently(tmp_path, caplog):
    """No matches → returns 0 and emits no 'Reclaimed' info line."""
    with caplog.at_level(logging.INFO, logger="config.startup"):
        count = reclaim_leftover_stream_temps(tmp_path)

    assert count == 0
    assert not [r for r in caplog.records if "Reclaimed" in r.message]


def test_removal_failure_is_logged_not_swallowed(tmp_path, caplog):
    """A removal failure logs a WARNING and is excluded from the count instead
    of being silently swallowed (the core #3877 behaviour)."""
    # A matching *file* (not a dir): glob picks it up, rmtree raises
    # NotADirectoryError → must be caught, logged, and not counted.
    bad = tmp_path / "auralis_stream_locked"
    bad.write_bytes(b"not a directory")
    _age_entry(bad, hours=2.0)
    good = _age_entry(_make_stream_dir(tmp_path, "auralis_stream_ok"), hours=2.0)

    with caplog.at_level(logging.WARNING, logger="config.startup"):
        count = reclaim_leftover_stream_temps(tmp_path)

    assert count == 1, "only the valid dir should be reclaimed"
    assert not good.exists()
    assert bad.exists(), "the failing entry is left in place"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "a removal failure must be logged, not swallowed"
    assert "auralis_stream_locked" in warnings[0].message


def test_stale_entries_removes_only_old_files(tmp_path):
    """Files/dirs older than max_age_hours are reclaimed; fresh ones survive
    (#4762 — auralis_processing/auralis_uploads have no in-memory registry
    to fall back on after a crash, so the sweep must be mtime-driven)."""
    old_file = tmp_path / "old_job_output.wav"
    old_file.write_bytes(b"stale")
    _age_entry(old_file, hours=2.0)

    old_dir = tmp_path / "old_upload_dir"
    old_dir.mkdir()
    (old_dir / "inner.bin").write_bytes(b"x")
    _age_entry(old_dir, hours=2.0)

    fresh_file = tmp_path / "fresh_job_output.wav"
    fresh_file.write_bytes(b"fresh")

    count = reclaim_stale_temp_entries(tmp_path, max_age_hours=1.0)

    assert count == 2
    assert not old_file.exists()
    assert not old_dir.exists()
    assert fresh_file.exists()


def test_stale_entries_missing_dir_returns_zero(tmp_path):
    """A dir_path that doesn't exist (processing never ran) is a silent no-op."""
    missing = tmp_path / "does_not_exist"

    count = reclaim_stale_temp_entries(missing, max_age_hours=1.0)

    assert count == 0


def test_stale_entries_logs_reclaimed_count(tmp_path, caplog):
    old_file = tmp_path / "old.wav"
    old_file.write_bytes(b"stale")
    _age_entry(old_file, hours=2.0)

    with caplog.at_level(logging.INFO, logger="config.startup"):
        count = reclaim_stale_temp_entries(tmp_path, max_age_hours=1.0)

    assert count == 1
    assert [r for r in caplog.records if "Reclaimed" in r.message]


def test_stale_entries_removal_failure_is_logged_not_swallowed(tmp_path, caplog, monkeypatch):
    """A removal failure logs a WARNING and is excluded from the count."""
    old_file = tmp_path / "locked.wav"
    old_file.write_bytes(b"stale")
    _age_entry(old_file, hours=2.0)

    def _raise_unlink(*_args, **_kwargs):
        raise OSError("locked by another process")

    monkeypatch.setattr(Path, "unlink", _raise_unlink)

    with caplog.at_level(logging.WARNING, logger="config.startup"):
        count = reclaim_stale_temp_entries(tmp_path, max_age_hours=1.0)

    assert count == 0
    assert old_file.exists()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "a removal failure must be logged, not swallowed"
