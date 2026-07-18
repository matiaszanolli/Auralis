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


# ---------------------------------------------------------------------------
# encoding/wav_encoder.py — encode_to_wav
# ---------------------------------------------------------------------------

def test_wav_encoder_logs_basename_not_full_path(tmp_path, caplog):
    from encoding.wav_encoder import encode_to_wav

    output_path = tmp_path / "deeply" / "nested" / "chunk.wav"
    output_path.parent.mkdir(parents=True)
    audio = np.zeros((1000, 2), dtype=np.float32)

    with caplog.at_level(logging.INFO, logger="encoding.wav_encoder"):
        encode_to_wav(audio, sample_rate=44100, output_path=str(output_path))

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert any("chunk.wav" in r.message for r in info_records)
    assert not any(str(tmp_path) in r.message for r in info_records), (
        "INFO log must not contain the absolute path"
    )


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
    scanner._library_manager = Mock()
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
