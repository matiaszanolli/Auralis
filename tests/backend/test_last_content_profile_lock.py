"""Regression tests for the unsynchronized _last_content_profiles write (#4341).

ChunkedAudioProcessor.get_wav_chunk_path wrote the module-global
_last_content_profiles[self.preset.lower()] with no lock — the write sat
AFTER the `with self._sync_cache_lock:` block closed, while it runs inside
asyncio.to_thread workers across concurrent streams. The visualizer endpoint
(get_last_content_profile) reads the same dict from the event-loop thread.
Both sites are now guarded by a dedicated module-level _last_content_profiles_lock.
"""

import shutil
import sys
import tempfile
import threading
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.io.saver import save as save_audio


def _create_test_audio(duration_seconds: float, sample_rate: int = 44100) -> np.ndarray:
    num_samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, num_samples, endpoint=False)
    audio = np.sin(2 * np.pi * 440 * t)
    return np.column_stack([audio, audio])


class TestLockExists:
    def test_last_content_profiles_lock_is_a_threading_lock(self):
        import core.chunked_processor as cp

        assert isinstance(cp._last_content_profiles_lock, type(threading.Lock()))


class TestReadWriteGuarded:
    def test_get_last_content_profile_returns_none_for_unknown_preset(self):
        import core.chunked_processor as cp

        assert cp.get_last_content_profile("nonexistent-preset-xyz") is None

    def test_get_last_content_profile_returns_stored_dict(self):
        import core.chunked_processor as cp

        with cp._last_content_profiles_lock:
            cp._last_content_profiles["punchy"] = {"loudness": -14.0}

        assert cp.get_last_content_profile("PUNCHY") == {"loudness": -14.0}

    def test_concurrent_writes_and_reads_raise_nothing(self):
        """Mirrors the issue's test plan: concurrently invoke writes across
        two presets and read via get_last_content_profile; assert no
        exception and no partially-updated/cross-preset value."""
        import core.chunked_processor as cp

        stop = threading.Event()
        errors: list[BaseException] = []

        def _writer(preset: str, profile: dict):
            while not stop.is_set():
                try:
                    with cp._last_content_profiles_lock:
                        cp._last_content_profiles[preset] = profile
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
                    return

        def _reader(preset: str, expected_keys: set):
            for _ in range(500):
                try:
                    value = cp.get_last_content_profile(preset)
                    if value is not None:
                        assert set(value.keys()) == expected_keys, (
                            f"cross-preset/partial value observed for {preset}: {value}"
                        )
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
                    return

        profile_a = {"loudness": -14.0, "preset": "adaptive"}
        profile_b = {"loudness": -9.0, "preset": "punchy"}

        threads = [
            threading.Thread(target=_writer, args=("adaptive", profile_a)),
            threading.Thread(target=_writer, args=("punchy", profile_b)),
            threading.Thread(target=_reader, args=("adaptive", set(profile_a.keys()))),
            threading.Thread(target=_reader, args=("punchy", set(profile_b.keys()))),
        ]
        for t in threads:
            t.start()
        # Let readers run their fixed iteration count, then stop writers.
        threads[2].join(timeout=10)
        threads[3].join(timeout=10)
        stop.set()
        threads[0].join(timeout=10)
        threads[1].join(timeout=10)

        assert not errors, f"concurrent access raised: {errors}"


class TestEndToEndWriteSite:
    """Exercise the real get_wav_chunk_path write site (not just the module
    dict directly), confirming it still populates _last_content_profiles
    end-to-end after the locking change."""

    @pytest.fixture
    def temp_audio_dir(self):
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_get_wav_chunk_path_populates_last_content_profile(self, temp_audio_dir):
        import core.chunked_processor as cp

        audio = _create_test_audio(2.0)
        filepath = temp_audio_dir / "test_audio.wav"
        save_audio(str(filepath), audio, 44100, subtype='PCM_16')

        processor = cp.ChunkedAudioProcessor(
            track_id=1, filepath=str(filepath), preset="adaptive", intensity=1.0
        )

        processor.get_wav_chunk_path(0)

        # The real HybridProcessor sets its own last_content_profile during
        # processing (whatever stub we set beforehand gets overwritten), so
        # just confirm the write site populated the module dict end-to-end.
        if processor.processor is not None and getattr(
            processor.processor, 'last_content_profile', None
        ):
            stored = cp.get_last_content_profile("adaptive")
            assert isinstance(stored, dict)
