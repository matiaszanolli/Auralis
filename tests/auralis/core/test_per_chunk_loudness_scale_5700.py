"""Regression tests: intended and realised loudness lift agree (#5700)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``calculate_target_lufs`` builds ``fp['lufs'] + lift`` on the fingerprint's RMS
proxy (``20*log10(rms of the mono mean) - 0.7``), but ``_normalize_chunk_loudness``
chases it with the K-weighted, channel-summed meter, which reads ~3-4 dB higher
on the same audio. The realised gain was ``lift - offset``: loud masters were
attenuated although the generator never intends attenuation, and quiet material
got about half its lift.

``ContinuousMode._resolve_parameters`` now converts the target onto the meter's
scale with the offset measured on the chunk itself.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
from auralis.core.config import UnifiedConfig
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.core.processing.parameter_generator_dynamics import calculate_target_lufs
from auralis.dsp.utils.adaptive import (
    MAX_PROXY_TO_K_OFFSET_DB,
    calculate_loudness_units,
    proxy_to_k_offset_db,
)

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
    """The generator's own lift, on the proxy scale it was computed on."""
    fp = mode.fingerprint_analyzer.analyze(audio, SR)
    coords = mode.space_mapper.map_fingerprint_to_space(fp)
    return calculate_target_lufs(coords, None) - fp["lufs"]


def _realised_lift(mode: ContinuousMode, audio: np.ndarray) -> float:
    params = mode._resolve_parameters(audio.copy(), None)
    out = mode._apply_final_normalization(audio.copy(), params)
    return calculate_loudness_units(out, SR) - calculate_loudness_units(audio, SR)


class TestProxyToKOffset:
    def test_correlated_stereo_reads_a_few_db_above_the_proxy(self):
        """The issue measured +4.0 dB on correlated stereo pink noise."""
        audio = _correlated_pink(-20.0)
        fp = AudioFingerprintAnalyzer().analyze(audio, SR)

        offset = proxy_to_k_offset_db(audio, fp["lufs"], SR)

        assert 1.5 < offset < 6.0

    def test_the_offset_depends_on_the_spectrum_so_it_must_be_measured(self):
        """White noise reads ~7 dB further above its proxy than pink does; a
        constant would be wrong for one of them."""
        analyzer = AudioFingerprintAnalyzer()
        pink, white = _correlated_pink(-20.0), _correlated_noise(-20.0)

        pink_offset = proxy_to_k_offset_db(pink, analyzer.analyze(pink, SR)["lufs"], SR)
        white_offset = proxy_to_k_offset_db(white, analyzer.analyze(white, SR)["lufs"], SR)

        assert white_offset - pink_offset > 3.0

    def test_silence_and_non_finite_inputs_give_no_offset(self):
        silence = np.zeros((SR, 2), dtype=np.float32)
        audio = _correlated_noise(-16.0)

        assert proxy_to_k_offset_db(silence, -70.0, SR) == 0.0
        assert proxy_to_k_offset_db(audio, float("nan"), SR) == 0.0
        assert proxy_to_k_offset_db(audio, float("inf"), SR) == 0.0

    def test_offset_is_bounded(self):
        audio = _correlated_pink(-20.0)

        assert proxy_to_k_offset_db(audio, -100.0, SR) == MAX_PROXY_TO_K_OFFSET_DB
        assert proxy_to_k_offset_db(audio, 100.0, SR) == -MAX_PROXY_TO_K_OFFSET_DB


class TestIntendedLiftIsRealised:
    @pytest.mark.parametrize("k_lufs", [-31.0, -27.0, -23.0, -19.0, -15.0])
    def test_realised_lift_matches_the_generator_across_a_level_sweep(self, mode, k_lufs):
        audio = _correlated_noise(k_lufs)

        intended = _intended_lift(mode, audio)
        realised = _realised_lift(mode, audio)

        assert intended >= 0.0
        assert realised == pytest.approx(intended, abs=0.5)

    @pytest.mark.parametrize("k_lufs", [-10.0, -8.5])
    def test_a_loud_master_is_never_attenuated(self, mode, k_lufs):
        audio = _correlated_noise(k_lufs)

        assert _intended_lift(mode, audio) >= 0.0
        assert _realised_lift(mode, audio) >= -0.5

    def test_per_chunk_and_fixed_target_paths_land_the_same_loudness(self, mode):
        """Same audio through both normalisation branches: the fixed-target
        branch applies target - source on the proxy scale (#5552), the
        per-chunk branch re-measures. They must agree on the lift."""
        audio = _correlated_noise(-22.0)
        fp = mode.fingerprint_analyzer.analyze(audio, SR)
        coords = mode.space_mapper.map_fingerprint_to_space(fp)
        proxy_target = calculate_target_lufs(coords, None)

        per_chunk = mode._apply_final_normalization(
            audio.copy(), mode._resolve_parameters(audio.copy(), None)
        )
        fixed = mode._apply_final_normalization(
            audio.copy(), SimpleNamespace(target_lufs=proxy_target, source_lufs=fp["lufs"])
        )

        assert calculate_loudness_units(per_chunk, SR) == pytest.approx(
            calculate_loudness_units(fixed, SR), abs=1.0
        )
