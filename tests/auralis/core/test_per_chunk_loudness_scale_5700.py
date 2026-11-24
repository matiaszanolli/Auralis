"""Regression tests: intended and realised loudness lift agree (#5700)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The per-chunk target was built as ``fp['lufs'] + lift`` on the fingerprint's RMS
proxy (``20*log10(rms of the mono mean) - 0.7``), but ``_normalize_chunk_loudness``
chased it with the K-weighted, channel-summed meter, which reads ~3-4 dB higher
on the same audio. The realised gain was ``lift - offset``: loud masters were
attenuated although the generator never intended attenuation, and quiet material
got about half its lift.

#5700 measured that offset per chunk and added it to the target. Since #6356 the
fingerprint path uses the streaming targets law, which carries ``source_lufs`` on
the same proxy scale, so normalisation applies only ``target - source`` and the
offset cancels. These tests pin that the planned lift is the realised one.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
from auralis.core.config import UnifiedConfig
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.core.processing.mastering_targets import plan_level
from auralis.dsp.utils.adaptive import calculate_loudness_units

SR = 44100


def _correlated_noise(k_lufs: float, seconds: float = 5.0) -> np.ndarray:
    """Correlated stereo uniform noise (low crest, so the -0.3 dBFS clamp stays
    out of the way) scaled to the requested K-weighted loudness."""
    rng = np.random.default_rng(5700)
    mono = rng.uniform(-1.0, 1.0, int(SR * seconds)).astype(np.float32)
    audio = np.stack([mono, mono], axis=1)
    measured = calculate_loudness_units(audio, SR)
    return (audio * 10 ** ((k_lufs - measured) / 20)).astype(np.float32)


def _correlated_pink(k_lufs: float, seconds: float = 5.0) -> np.ndarray:
    """Correlated stereo pink noise at the requested K-weighted loudness."""
    rng = np.random.default_rng(5700)
    spectrum = np.fft.rfft(rng.standard_normal(int(SR * seconds)))
    bins = np.arange(len(spectrum), dtype=np.float64)
    bins[0] = 1.0
    mono = np.fft.irfft(spectrum / np.sqrt(bins), int(SR * seconds))
    audio = np.stack([mono, mono], axis=1).astype(np.float32)
    measured = calculate_loudness_units(audio, SR)
    return (audio * 10 ** ((k_lufs - measured) / 20)).astype(np.float32)


@pytest.fixture(scope="module")
def mode() -> ContinuousMode:
    return ContinuousMode(
        config=UnifiedConfig(),
        content_analyzer=MagicMock(),
        fingerprint_analyzer=AudioFingerprintAnalyzer(),
    )


def _intended_lift(mode: ContinuousMode, audio: np.ndarray) -> float:
    """The plan's own lift, on the proxy scale it was computed on."""
    fp = mode.fingerprint_analyzer.analyze(audio, SR)
    target_lufs, _crest = plan_level(fp["lufs"], fp["crest_db"])
    return target_lufs - fp["lufs"]


def _realised_lift(mode: ContinuousMode, audio: np.ndarray) -> float:
    params = mode._resolve_parameters(audio.copy(), None)
    out = mode._apply_final_normalization(audio.copy(), params)
    return calculate_loudness_units(out, SR) - calculate_loudness_units(audio, SR)


class TestIntendedLiftIsRealised:
    @pytest.mark.parametrize("k_lufs", [-31.0, -27.0, -23.0, -19.0, -15.0, -10.0, -8.5])
    def test_realised_lift_matches_the_plan_across_a_level_sweep(self, mode, k_lufs):
        audio = _correlated_noise(k_lufs)

        intended = _intended_lift(mode, audio)
        realised = _realised_lift(mode, audio)

        assert realised == pytest.approx(intended, abs=0.5)

    def test_the_plan_is_not_shifted_onto_the_k_meter_scale(self, mode):
        """The K-weighted meter reads ~3-4 dB above the proxy on this audio; a
        target moved onto its scale would show up as that much extra lift."""
        audio = _correlated_pink(-22.0)
        fp = mode.fingerprint_analyzer.analyze(audio, SR)
        assert calculate_loudness_units(audio, SR) - fp["lufs"] > 2.0

        params = mode._resolve_parameters(audio.copy(), None)

        assert params.source_lufs == pytest.approx(fp["lufs"])
        assert params.target_lufs - params.source_lufs == pytest.approx(_intended_lift(mode, audio))
