"""
Mastering fingerprint loudness must be real dBFS — issue #5099
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`MasteringFingerprint.from_audio_file()` returned `loudness_dbfs == 0.0`,
`peak_dbfs == 0.0` and `crest_db == 0.0` for *every* file. Three of the
fingerprint's seven dimensions carried no information at all.

`AudioMetrics.rms_to_db()` defaults its reference to the max of its own input,
which is correct for an array of per-frame RMS values (normalise to the loudest
frame). `from_audio_file` passed a single-element array, so the reference *was*
the value and `amplitude_to_db(x, ref=x)` is identically 0.0.

The downstream consequence is what makes this more than a cosmetic zero:
`classify_quality()` branches entirely on `loudness_dbfs`/`crest_db`, so it could
never reach its premium/professional/commercial arms, and
`AdaptiveMasteringEngine.recommend_weighted()` ranks against these dimensions.
"""

from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

soundfile = pytest.importorskip("soundfile")

from auralis.analysis.fingerprint.metrics.audio_metrics import AudioMetrics
from auralis.analysis.mastering_fingerprint import MasteringFingerprint

SAMPLE_RATE = 44100


def _write_tone(path: Path, amplitude: float, seconds: float = 3.0) -> Path:
    """A 440 Hz tone plus a little noise, scaled to `amplitude`."""
    t = np.linspace(0, seconds, int(SAMPLE_RATE * seconds), endpoint=False)
    rng = np.random.default_rng(0)
    signal = (0.7 * np.sin(2 * np.pi * 440 * t) + 0.06 * rng.standard_normal(t.size))
    signal = np.clip(signal * amplitude, -1.0, 1.0).astype(np.float32)
    soundfile.write(str(path), signal, SAMPLE_RATE)
    return path


# ---------------------------------------------------------------------------
# The helper itself
# ---------------------------------------------------------------------------

class TestRmsToDbSingleValue:
    def test_explicit_full_scale_reference_gives_real_dbfs(self):
        for amplitude, expected in [(1.0, 0.0), (0.5, -6.02), (0.05, -26.02), (0.001, -60.0)]:
            result = AudioMetrics.rms_to_db(np.array([amplitude]), ref=1.0)[0]
            assert result == pytest.approx(expected, abs=0.01), amplitude

    def test_without_a_reference_a_single_value_is_still_degenerate(self):
        """Documenting the trap, not endorsing it — the default is unchanged.

        Changing the default would silently alter the array-valued callers
        (`spectrum_operations.py`, `dynamic_range.py` x2), which rely on
        normalise-to-loudest and are correct as they stand.
        """
        for amplitude in (0.5, 0.05, 0.001, 0.9):
            assert AudioMetrics.rms_to_db(np.array([amplitude]))[0] == 0.0

    def test_the_degenerate_call_now_warns(self):
        """It used to pass silently, which is how this survived."""
        with patch('auralis.analysis.fingerprint.metrics.audio_metrics.warning') as warn:
            AudioMetrics.rms_to_db(np.array([0.5]))
        warn.assert_called_once()
        assert '5099' in warn.call_args[0][0]

    def test_an_explicit_reference_does_not_warn(self):
        with patch('auralis.analysis.fingerprint.metrics.audio_metrics.warning') as warn:
            AudioMetrics.rms_to_db(np.array([0.5]), ref=1.0)
        warn.assert_not_called()

    def test_array_input_does_not_warn(self):
        """The normalise-to-loudest default is right here and must stay quiet."""
        with patch('auralis.analysis.fingerprint.metrics.audio_metrics.warning') as warn:
            AudioMetrics.rms_to_db(np.array([0.5, 0.25, 1.0]))
        warn.assert_not_called()

    def test_array_normalisation_behaviour_is_unchanged(self):
        result = AudioMetrics.rms_to_db(np.array([0.5, 0.25, 1.0]))
        assert result[2] == pytest.approx(0.0)          # the loudest is the reference
        assert result[0] == pytest.approx(-6.02, abs=0.01)
        assert result[1] == pytest.approx(-12.04, abs=0.01)


# ---------------------------------------------------------------------------
# from_audio_file
# ---------------------------------------------------------------------------

class TestFingerprintCarriesInformation:
    def test_loudness_and_peak_are_not_zero(self, tmp_path):
        """The regression, at its plainest."""
        fingerprint = MasteringFingerprint.from_audio_file(
            str(_write_tone(tmp_path / "tone.wav", 0.5))
        )

        assert fingerprint is not None
        assert fingerprint.loudness_dbfs != 0.0
        assert fingerprint.peak_dbfs != 0.0
        assert fingerprint.crest_db != 0.0

    def test_values_are_negative_dbfs_and_finite(self, tmp_path):
        fingerprint = MasteringFingerprint.from_audio_file(
            str(_write_tone(tmp_path / "tone.wav", 0.5))
        )

        assert fingerprint is not None
        assert math.isfinite(fingerprint.loudness_dbfs)
        assert math.isfinite(fingerprint.peak_dbfs)
        # Nothing above full scale, and RMS is never above peak.
        assert fingerprint.peak_dbfs <= 0.0
        assert fingerprint.loudness_dbfs <= fingerprint.peak_dbfs
        assert fingerprint.crest_db > 0.0

    def test_a_quieter_file_reads_quieter(self, tmp_path):
        """The property the constant 0.0 destroyed: it varies with content."""
        loud = MasteringFingerprint.from_audio_file(
            str(_write_tone(tmp_path / "loud.wav", 0.9))
        )
        quiet = MasteringFingerprint.from_audio_file(
            str(_write_tone(tmp_path / "quiet.wav", 0.05))
        )

        assert loud is not None and quiet is not None
        assert quiet.loudness_dbfs < loud.loudness_dbfs
        assert quiet.peak_dbfs < loud.peak_dbfs

    def test_crest_is_level_independent(self, tmp_path):
        """Scaling a signal moves loudness and peak together, not crest."""
        loud = MasteringFingerprint.from_audio_file(
            str(_write_tone(tmp_path / "loud.wav", 0.9))
        )
        quiet = MasteringFingerprint.from_audio_file(
            str(_write_tone(tmp_path / "quiet.wav", 0.05))
        )

        assert loud is not None and quiet is not None
        assert loud.crest_db == pytest.approx(quiet.crest_db, abs=0.1)


class TestQualityClassificationIsReachable:
    def test_a_quiet_dynamic_file_is_no_longer_forced_into_the_bad_arms(self, tmp_path):
        """`classify_quality()` branches on loudness/crest.

        With both pinned at 0.0 the first three arms were unreachable — every
        track landed in "damaged"/"poor" regardless of what it sounded like.
        """
        fingerprint = MasteringFingerprint.from_audio_file(
            str(_write_tone(tmp_path / "quiet.wav", 0.05))
        )

        assert fingerprint is not None
        assert fingerprint.classify_quality() in {"premium", "professional", "commercial"}

    def test_the_classification_responds_to_level(self, tmp_path):
        loud = MasteringFingerprint.from_audio_file(
            str(_write_tone(tmp_path / "loud.wav", 0.95))
        )
        quiet = MasteringFingerprint.from_audio_file(
            str(_write_tone(tmp_path / "quiet.wav", 0.05))
        )

        assert loud is not None and quiet is not None
        assert loud.classify_quality() != quiet.classify_quality()
