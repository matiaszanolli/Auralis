"""#5550 — the K-weighted loudness meter must accept any channel count.

#5221 moved ``calculate_loudness_units`` onto ``LoudnessMeter``, whose
multichannel branch hard-coded two columns. The backend chunk reader returns
every mono file as ``(N, 1)`` (``always_2d=True``), so each enhanced chunk of
a mono track raised ``IndexError``.
"""

import numpy as np
import pytest

from auralis.analysis.loudness_meter import LoudnessMeter
from auralis.core.config.unified_config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.dsp.utils.adaptive import calculate_loudness_units

SR = 44100


def _tone(seconds: float = 2.0, amp: float = 0.2) -> np.ndarray:
    n = int(SR * seconds)
    return (amp * np.sin(2 * np.pi * 220 * np.arange(n) / SR)).astype(np.float32)


class TestLoudnessUnitsChannelCounts:
    def test_single_column_matches_1d_mono(self) -> None:
        tone = _tone()
        assert calculate_loudness_units(tone[:, None], SR) == pytest.approx(
            calculate_loudness_units(tone, SR)
        )

    def test_single_column_matches_dual_mono_stereo(self) -> None:
        tone = _tone()
        stereo = np.column_stack([tone, tone])
        assert calculate_loudness_units(tone[:, None], SR) == pytest.approx(
            calculate_loudness_units(stereo, SR)
        )

    @pytest.mark.parametrize("channels", [3, 4, 5, 6, 8])
    def test_multichannel_does_not_raise(self, channels: int) -> None:
        audio = np.column_stack([_tone()] * channels)
        assert np.isfinite(calculate_loudness_units(audio, SR))


class TestLoudnessMeterChannelCounts:
    @pytest.mark.parametrize("channels", [1, 2, 3, 6])
    def test_apply_k_weighting_preserves_shape(self, channels: int) -> None:
        audio = np.column_stack([_tone()] * channels)
        out = LoudnessMeter(SR).apply_k_weighting(audio)
        assert out.shape == audio.shape

    def test_block_loudness_sums_channels(self) -> None:
        tone = _tone()
        meter = LoudnessMeter(SR)
        one = meter.calculate_block_loudness(tone[:, None])
        two = meter.calculate_block_loudness(np.column_stack([tone, tone]))
        assert two - one == pytest.approx(10 * np.log10(2), abs=1e-3)


class TestHybridProcessorChannelCounts:
    """The wire format declares the source channel count, so it must survive."""

    @pytest.mark.parametrize("channels", [1, 2, 3, 6])
    def test_process_preserves_shape(self, channels: int) -> None:
        rng = np.random.default_rng(0)
        base = _tone(3.0) + 0.02 * rng.standard_normal(int(SR * 3.0)).astype(np.float32)
        audio = np.column_stack([base] * channels)
        out = HybridProcessor(UnifiedConfig()).process(audio)
        assert out.shape == audio.shape
        assert np.all(np.isfinite(out))
