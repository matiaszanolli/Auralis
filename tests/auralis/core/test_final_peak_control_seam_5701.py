"""Regression tests: peak control must not rescale the whole buffer (#5701)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#5552 made fixed-target loudness a constant track-level gain so chunks keep
their relative levels. Step 2 of ``_apply_final_normalization`` then clamped the
buffer's peak to -0.3 dBFS with ``amplify(audio, ceiling - max_peak)`` -- one
gain for the whole 15 s buffer, set by its single loudest sample. Two renderings
of the same overlapped audio therefore differed whenever a transient sat in one
window and not the other, and because the backend trims each rendering to a
non-overlapping segment and tiles them with no crossfade, that difference
became a level step at the seam (4.14 dB RMS in the issue's probe).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.processing.continuous_dsp_ops import SAFE_CEILING_DB
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.dsp.utils.adaptive import calculate_loudness_units

SR = 44100
CEILING = 10 ** (SAFE_CEILING_DB / 20)
# Constant track-level gain of +9 dB, exactly as the fixed-target path applies it.
FIXED_GAIN_9DB = SimpleNamespace(target_lufs=-14.0, source_lufs=-23.0)


def _mode() -> ContinuousMode:
    return ContinuousMode(
        config=UnifiedConfig(), content_analyzer=MagicMock(), fingerprint_analyzer=MagicMock()
    )


def _rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2))))


def _track(seconds: float = 30.0, transient_at: float = 2.0) -> np.ndarray:
    """Stationary low-crest stereo noise with ONE brief transient that, after
    the +9 dB track gain, overshoots the ceiling by ~3 dB."""
    rng = np.random.default_rng(5701)
    audio = rng.uniform(-0.06, 0.06, (int(SR * seconds), 2)).astype(np.float32)
    i = int(transient_at * SR)
    audio[i:i + 8] = 0.5
    return audio


def _window(track: np.ndarray, start_s: float, length_s: float = 15.0) -> np.ndarray:
    return track[int(start_s * SR):int((start_s + length_s) * SR)].copy()


def _shared(rendered: np.ndarray, window_start_s: float) -> np.ndarray:
    """The overlap [10 s, 15 s) of the two windows, in track time."""
    lo = int((10.0 - window_start_s) * SR)
    return rendered[lo:lo + 5 * SR]


class TestOverlappedWindowsAgree:
    def test_a_transient_in_one_window_does_not_rescale_the_shared_region(self):
        track = _track()
        mode = _mode()
        a = mode._apply_final_normalization(_window(track, 0.0), FIXED_GAIN_9DB)
        b = mode._apply_final_normalization(_window(track, 10.0), FIXED_GAIN_9DB)

        diff = abs(_rms_db(_shared(a, 0.0)) - _rms_db(_shared(b, 10.0)))

        assert diff < 0.3, f"shared region differs by {diff:.2f} dB RMS between renderings"
        assert float(np.abs(a).max()) <= CEILING + 1e-6
        assert float(np.abs(b).max()) <= CEILING + 1e-6

    def test_the_old_whole_buffer_clamp_disagreed_on_the_same_probe(self):
        """Pins what this replaces, so the bound above is not vacuous."""
        track = _track()

        def old(window: np.ndarray) -> np.ndarray:
            gained = window * np.float32(10 ** (9.0 / 20))
            peak = float(np.abs(gained).max())
            return gained * np.float32(CEILING / peak) if peak > CEILING else gained

        diff = abs(
            _rms_db(_shared(old(_window(track, 0.0)), 0.0))
            - _rms_db(_shared(old(_window(track, 10.0)), 10.0))
        )
        assert diff > 2.0

    def test_the_track_level_gain_survives_the_peak_ceiling(self):
        """#5552's intent: material away from the transient keeps the full +9 dB."""
        track = _track()
        window = _window(track, 0.0)
        out = _mode()._apply_final_normalization(window, FIXED_GAIN_9DB)

        far = slice(5 * SR, 14 * SR)
        gain_db = _rms_db(out[far]) - _rms_db(window[far])
        assert gain_db == pytest.approx(9.0, abs=0.1)


class TestCeilingStillHolds:
    def test_a_hot_chunk_never_exceeds_the_ceiling(self):
        rng = np.random.default_rng(1)
        hot = (rng.standard_normal((5 * SR, 2)) * 0.5).astype(np.float32)

        out = _mode()._apply_final_normalization(hot, SimpleNamespace(target_lufs=-8.0, source_lufs=-14.0))

        assert float(np.abs(out).max()) <= CEILING + 1e-6
        assert out.shape == hot.shape and out.dtype == hot.dtype

    def test_per_chunk_path_holds_the_ceiling_and_leaves_the_rest_of_the_chunk_alone(self):
        audio = _track(seconds=6.0, transient_at=1.0)
        audio[int(1.0 * SR):int(1.0 * SR) + 8] = 1.4   # hot even without a track gain
        mode = _mode()
        # No source_lufs: per-chunk normalisation. Target the chunk's own
        # loudness so Step 1 is a no-op and only the peak stage acts.
        own = calculate_loudness_units(audio, SR)
        out = mode._apply_final_normalization(audio.copy(), SimpleNamespace(target_lufs=own))

        assert float(np.abs(out).max()) <= CEILING + 1e-6
        far = slice(3 * SR, 5 * SR)
        assert _rms_db(out[far]) == pytest.approx(_rms_db(audio[far]), abs=0.1)

    def test_a_buffer_shorter_than_the_lookahead_is_handled(self):
        tiny = np.full((10, 2), 1.4, dtype=np.float32)

        out = _mode()._apply_final_normalization(tiny, SimpleNamespace(target_lufs=-14.0, source_lufs=-14.0))

        assert out.shape == tiny.shape
        assert float(np.abs(out).max()) <= CEILING + 1e-6

    def test_audio_under_the_ceiling_is_untouched(self):
        audio = _track()[:5 * SR].copy()
        audio[int(2.0 * SR):int(2.0 * SR) + 8] = 0.05

        out = _mode()._apply_final_normalization(audio.copy(), SimpleNamespace(target_lufs=-14.0, source_lufs=-14.0))

        np.testing.assert_array_equal(out, audio)
