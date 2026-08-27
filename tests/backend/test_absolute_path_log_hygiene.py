"""Regression tests for absolute-path logging at INFO level (#4366).

Full absolute paths (which embed the OS username via /home/<user>/... and
the user's library layout) were logged at INFO throughout the backend —
exactly what a user might paste into a public bug report. Routine INFO
lines now emit basenames/counts instead; the absolute path remains
available at DEBUG for troubleshooting.
"""

import logging
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.io.saver import save as save_audio


# #5147: a test_wav_encoder_logs_basename_not_full_path case sat here,
# covering encode_to_wav() in the standalone auralis-web/backend/encoding/
# package. That package had no production callers and was deleted.
#
# It was dropped rather than repointed at the live encoder
# (core/encoding/wav_encoder.py's WAVEncoder) because that class has exactly
# one INFO line — `Cleaned up N chunk file(s) for track T` at :270 — and it
# already emits a count, not a path, so the assertion would be vacuous. Its
# other path-bearing lines are :172 (ERROR) and :267 (WARNING), both failure
# diagnostics carrying the exception, which sit outside this file's
# INFO-level policy (#4366, see the module docstring).
#
# The four cases below are unaffected.


# ---------------------------------------------------------------------------
# core/chunked_processor.py — chunk-saved / full-audio-saved logs
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_audio_dir():
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def _create_test_audio(duration_seconds: float, sample_rate: int = 44100) -> np.ndarray:
    num_samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, num_samples, endpoint=False)
    audio = np.sin(2 * np.pi * 440 * t)
    return np.column_stack([audio, audio])


def test_chunked_processor_chunk_saved_log_uses_basename(temp_audio_dir, caplog):
    import core.chunked_processor as cp

    audio = _create_test_audio(2.0)
    filepath = temp_audio_dir / "test_audio.wav"
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')

    processor = cp.ChunkedAudioProcessor(
        track_id=1, filepath=str(filepath), preset="adaptive", intensity=1.0
    )

    with caplog.at_level(logging.INFO, logger="core.chunked_processor"):
        processor.process_chunk(0)

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    saved_logs = [r for r in info_records if "processed and saved to" in r.message]
    assert saved_logs, "expected a 'processed and saved to' INFO log"
    # The chunk cache root (a tempdir-based absolute path) must not leak.
    chunk_cache_root = str(processor._cache_manager.cache_dir) if hasattr(
        processor._cache_manager, "cache_dir"
    ) else None
    if chunk_cache_root:
        assert not any(chunk_cache_root in r.message for r in saved_logs)


# ---------------------------------------------------------------------------
# services/library_auto_scanner.py — scan_folders must not appear at INFO
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_scan_start_log_omits_full_folder_paths(caplog):
    from services.library_auto_scanner import LibraryAutoScanner

    scanner = LibraryAutoScanner.__new__(LibraryAutoScanner)
    scanner._connection_manager = Mock()
    scanner._on_scan_complete = None
    scanner._library_database = Mock()
    scanner._fingerprint_queue = None

    sensitive_folder = "/home/someuser/Music/Private Collection"

    import services.library_auto_scanner as las_mod
    from unittest.mock import patch

    with (
        caplog.at_level(logging.INFO, logger="services.library_auto_scanner"),
        patch.object(las_mod, "connection_manager_safe_broadcast", AsyncMock()),
        patch("auralis.library.scanner.LibraryScanner") as MockScanner,
    ):
        mock_scanner_instance = Mock()
        mock_scanner_instance.scan_directories = AsyncMock(
            return_value=Mock(
                tracks_added=0, tracks_updated=0, tracks_removed=0, errors=[]
            )
        )
        MockScanner.return_value = mock_scanner_instance
        try:
            await scanner._do_scan([sensitive_folder])
        except Exception:
            pass  # We only care about the log emitted before any downstream failure

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert any("Auto-scan starting" in r.message for r in info_records)
    assert not any(sensitive_folder in r.message for r in info_records), (
        "INFO log must not contain the user's absolute library folder path"
    )


# ---------------------------------------------------------------------------
# main.py — sys.path bootstrap (#4778)
#
# The three branches (PyInstaller-frozen, Electron-unfrozen, plain dev) run
# at module-import time, before uvicorn installs a root-logger handler
# (a separate finding, BE6-4) — so triggering them live and asserting on
# caplog would exercise the whole app-creation import chain for very little
# extra signal beyond a static check of the source. #4366/#4376 already
# established the pattern for this exact file (see the `frontend_path` case
# at :167-169 / :204-205): the fix is a source-shape guarantee (no
# f-string interpolating auralis_parent into logger.info), which a regex
# over the source verifies directly and cheaply.
# ---------------------------------------------------------------------------

import re as _re


def _main_py_source() -> str:
    main_py = Path(__file__).parent.parent.parent / "auralis-web" / "backend" / "main.py"
    return main_py.read_text()


def test_main_py_sys_path_bootstrap_never_logs_path_at_info():
    """None of the three sys.path bootstrap branches may interpolate
    auralis_parent into a logger.info(...) call."""
    source = _main_py_source()
    assert not _re.search(r'logger\.info\(f?["\'][^"\']*\{auralis_parent\}', source), (
        "logger.info(...) in main.py must not interpolate auralis_parent — "
        "it embeds the OS username + install layout (#4351/#4366/#4778); "
        "log it at DEBUG only"
    )


def test_main_py_sys_path_bootstrap_still_logs_path_at_debug():
    """The path must still be reachable for diagnostics, just at DEBUG —
    guards against the fix regressing to dropping the information entirely."""
    source = _main_py_source()
    debug_calls_with_path = _re.findall(
        r'logger\.debug\(f["\'][^"\']*\{auralis_parent\}[^"\']*["\']\)', source
    )
    assert len(debug_calls_with_path) == 3, (
        "expected all 3 sys.path bootstrap branches (PyInstaller-frozen, "
        "Electron-unfrozen, dev) to log auralis_parent at DEBUG; "
        f"found {len(debug_calls_with_path)}"
    )
