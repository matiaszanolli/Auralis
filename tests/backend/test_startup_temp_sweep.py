"""
Regression tests for the startup temp-stream sweep (#3877).

stream_normal_audio writes a temp WAV under `auralis_stream_*` and cleans it in
its finally block, but a crash or a locked file (Windows AV / cloud-sync) can
orphan one. `reclaim_leftover_stream_temps` sweeps and counts these on startup
so any leak surfaces in the log and stays bounded — and, unlike the old
`rmtree(..., ignore_errors=True)` + `except: pass`, a removal failure is logged
rather than silently swallowed.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import reclaim_leftover_stream_temps


def _make_stream_dir(root: Path, name: str) -> Path:
    d = root / name
    d.mkdir()
    (d / "stream.wav").write_bytes(b"\x00\x01\x02")  # non-empty so rmtree recurses
    return d


def test_reclaims_matching_dirs(tmp_path):
    """All auralis_stream_* dirs are removed and counted."""
    for name in ("auralis_stream_aaa", "auralis_stream_bbb", "auralis_stream_ccc"):
        _make_stream_dir(tmp_path, name)

    count = reclaim_leftover_stream_temps(tmp_path)

    assert count == 3
    assert list(tmp_path.glob("auralis_stream_*")) == []


def test_ignores_non_matching_dirs(tmp_path):
    """Unrelated temp dirs (e.g. auralis_chunks) are left untouched."""
    chunks = tmp_path / "auralis_chunks"
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
    good = _make_stream_dir(tmp_path, "auralis_stream_ok")

    with caplog.at_level(logging.WARNING, logger="config.startup"):
        count = reclaim_leftover_stream_temps(tmp_path)

    assert count == 1, "only the valid dir should be reclaimed"
    assert not good.exists()
    assert bad.exists(), "the failing entry is left in place"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "a removal failure must be logged, not swallowed"
    assert "auralis_stream_locked" in warnings[0].message
