"""The compression / width helpers defend themselves against odd parameters (#6117).

They stayed float32 only because every producer wrapped its values in float(); a numpy-scalar amount
promoted the blend to float64 (NEP 50), and a ratio past ~9 drove the soft-clip threshold below zero
and inverted small samples' sign.
"""

import numpy as np

from auralis.core.processing.base.compression_expansion import CompressionStrategies
from auralis.dsp.utils.stereo import adjust_stereo_width


def _tone(frames=4096):
    t = np.linspace(0, 40, frames, dtype=np.float32)
    return np.column_stack([np.sin(t) * 0.5, np.sin(t * 1.3) * 0.4]).astype(np.float32)


def test_numpy_scalar_parameters_keep_the_audio_float32():
    out = CompressionStrategies.apply_clip_blend_compression(
        _tone(), {"ratio": np.float64(2.0), "amount": np.float64(0.5)}
    )

    assert out.dtype == np.float32
    assert out.shape == (4096, 2)


def test_an_extreme_ratio_does_not_invert_any_sample():
    audio = _tone()

    out = CompressionStrategies.apply_clip_blend_compression(audio, {"ratio": 25.0, "amount": 1.0})

    audible = np.abs(audio) > 1e-3
    assert np.all(np.sign(out[audible]) == np.sign(audio[audible]))


def test_out_of_range_amount_is_clamped_not_extrapolated():
    audio = _tone()

    over = CompressionStrategies.apply_clip_blend_compression(audio, {"ratio": 2.0, "amount": 3.0})
    full = CompressionStrategies.apply_clip_blend_compression(audio, {"ratio": 2.0, "amount": 1.0})
    under = CompressionStrategies.apply_clip_blend_compression(audio, {"ratio": 2.0, "amount": -1.0})

    np.testing.assert_allclose(over, full)
    np.testing.assert_allclose(under, audio)


def test_stereo_width_with_a_numpy_scalar_stays_float32_and_sample_exact():
    audio = _tone()

    out = adjust_stereo_width(audio, np.float64(0.8))

    assert out.dtype == np.float32
    assert out.shape == audio.shape
    np.testing.assert_allclose(adjust_stereo_width(audio, 0.5), audio, atol=1e-6)
