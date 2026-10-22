"""#5784 — one downmix, with the channel layout stated, not guessed.

The engine uses both ``(samples, channels)`` (I/O, analysis) and
``(channels, samples)`` (librosa-style code), and each analyzer re-decided the layout
with its own ``np.mean(audio, axis=N)`` idiom (#2452 and #5746 are the same bug class).
``to_mono(audio, layout)`` is the single implementation.
"""

import re
from pathlib import Path

import numpy as np
import pytest

from auralis.analysis.quality_assessors.base_assessor import BaseAssessor
from auralis.core.dsp.resonance_notcher import ResonanceNotcher
from auralis.dsp.utils.audio_info import to_mono

ROOT = Path(__file__).resolve().parents[3]


class TestToMono:
    def test_mono_passes_through_unchanged(self) -> None:
        x = np.arange(5, dtype=np.float32)
        assert to_mono(x) is x
        assert to_mono(x, 'channels_samples') is x

    def test_samples_channels_averages_axis_1(self) -> None:
        x = np.array([[1.0, 3.0], [2.0, 6.0], [0.0, 4.0]])
        np.testing.assert_allclose(to_mono(x), [2.0, 4.0, 2.0])

    def test_channels_samples_averages_axis_0(self) -> None:
        x = np.array([[1.0, 3.0, 5.0], [3.0, 5.0, 7.0]])
        np.testing.assert_allclose(to_mono(x, 'channels_samples'), [2.0, 4.0, 6.0])

    def test_layouts_agree_on_the_same_signal(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.standard_normal((1000, 2))
        np.testing.assert_allclose(to_mono(x), to_mono(x.T, 'channels_samples'))

    @pytest.mark.parametrize("channels", [1, 2, 3, 6])
    def test_any_channel_count(self, channels: int) -> None:
        x = np.ones((50, channels))
        out = to_mono(x)
        assert out.shape == (50,)
        np.testing.assert_allclose(out, 1.0)

    def test_two_samples_is_not_misread_as_two_channels(self) -> None:
        """The shape-guessing resonance notcher read a 2-sample (2, C) array as
        channels-first; the layout is now explicit."""
        x = np.array([[1.0, 3.0, 5.0], [2.0, 4.0, 6.0]])  # 2 samples x 3 channels
        np.testing.assert_allclose(to_mono(x), [3.0, 4.0])

    def test_rejects_an_unknown_layout(self) -> None:
        with pytest.raises(ValueError):
            to_mono(np.ones((4, 2)), 'interleaved')  # type: ignore[arg-type]

    def test_float32_is_preserved(self) -> None:
        assert to_mono(np.ones((8, 2), dtype=np.float32)).dtype == np.float32


def test_resonance_notcher_sees_a_stereo_signal_as_its_mono_mean() -> None:
    sr = 44100
    t = np.arange(sr * 2) / sr
    left = 0.3 * np.sin(2 * np.pi * 300 * t) + 0.01 * np.random.default_rng(1).standard_normal(t.size)
    stereo = np.column_stack([left, left]).astype(np.float32)
    assert [n.freq_hz for n in ResonanceNotcher.detect(stereo, sr)] == [
        n.freq_hz for n in ResonanceNotcher.detect(stereo.mean(axis=1), sr)
    ]


def test_base_assessor_has_no_private_downmix_left() -> None:
    assert not hasattr(BaseAssessor, '_to_mono')


DOWNMIX_SITES = [
    'auralis/analysis/quality_assessors/utilities/estimation_ops.py',
    'auralis/dsp/eq/psychoacoustic_eq.py',
    'auralis/core/analysis/content_analyzer.py',
    'auralis/core/mastering_prepare.py',
    'auralis/core/dsp/resonance_notcher.py',
    'auralis/analysis/ml/feature_extractor.py',
    'auralis/analysis/fingerprint/windowed_compute.py',
    'auralis/analysis/fingerprint/audio_fingerprint_analyzer.py',
]


@pytest.mark.parametrize("rel", DOWNMIX_SITES)
def test_site_uses_the_shared_downmix(rel: str) -> None:
    src = (ROOT / rel).read_text()
    assert re.search(r"audio_info import [^\n]*\bto_mono\b", src), rel
    # No inline "if x.ndim == 2: ... np.mean(x, axis=N)" downmix idiom left.
    assert not re.search(r"ndim == 2:\s*(?:#[^\n]*\n\s*)*\w+ = (?:np|audio\w*)\.mean\([^)]*axis=\d\)", src), rel
