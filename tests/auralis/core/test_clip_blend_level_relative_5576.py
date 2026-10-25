"""
Clip-blend compression is relative to the material's own level (#5576)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``apply_clip_blend_compression`` used an absolute soft-clip threshold
(0.8 - (ratio - 1) * 0.1, about 0.72 at 1.8:1), so it did nothing for
material peaking below that and only shaved peaks above it: what a track got
depended on how loud the file was, not on the dynamics coordinate that
produced ``ratio`` and ``amount``. Audit probe at peaks 0.5 / 0.7 / 0.95 gave a
max abs difference of 0.0000 / 0.0000 / 0.0551.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest

from auralis.core.processing.base.compression_expansion import CompressionStrategies

PARAMS = {'ratio': 1.8, 'amount': 0.55}


def _program(seed: int = 0) -> np.ndarray:
    """Stereo noise burst train: loud transients over a quieter bed, peak 0.95."""
    rng = np.random.default_rng(seed)
    audio = rng.standard_normal((44100, 2)) * 0.08
    audio[::2205] *= 7.0
    return (audio * (0.95 / np.max(np.abs(audio)))).astype(np.float64)


def _crest_db(audio: np.ndarray) -> float:
    return 20 * np.log10(np.max(np.abs(audio)) / np.sqrt(np.mean(audio ** 2)))


@pytest.mark.parametrize("gain_db", [0.0, -6.0, -12.0, -20.0])
def test_crest_reduction_does_not_depend_on_level(gain_db):
    base = _program()
    scaled = base * 10 ** (gain_db / 20)

    reduction_base = _crest_db(base) - _crest_db(
        CompressionStrategies.apply_clip_blend_compression(base, PARAMS))
    reduction_scaled = _crest_db(scaled) - _crest_db(
        CompressionStrategies.apply_clip_blend_compression(scaled, PARAMS))

    assert reduction_base > 0.05  # the stage does something at all
    assert reduction_scaled == pytest.approx(reduction_base, abs=1e-6)


def test_output_scales_with_input():
    base = _program()
    gain = 10 ** (-9.0 / 20)

    full = CompressionStrategies.apply_clip_blend_compression(base, PARAMS)
    quiet = CompressionStrategies.apply_clip_blend_compression(base * gain, PARAMS)

    np.testing.assert_allclose(quiet, full * gain, atol=1e-9)


@pytest.mark.parametrize("peak", [0.5, 0.7])
def test_material_below_the_old_absolute_threshold_is_now_compressed(peak):
    audio = _program() * (peak / 0.95)

    out = CompressionStrategies.apply_clip_blend_compression(audio, PARAMS)

    assert np.max(np.abs(out - audio)) > 1e-3
    assert np.max(np.abs(out)) < np.max(np.abs(audio))


def test_over_range_peaks_are_still_pulled_under_the_ceiling():
    audio = _program() * (1.4 / 0.95)

    out = CompressionStrategies.apply_clip_blend_compression(
        audio, {'ratio': 1.8, 'amount': 1.0})

    assert np.max(np.abs(out)) <= 0.95 + 1e-9


def test_shape_dtype_and_input_are_preserved():
    audio = _program().astype(np.float32)
    original = audio.copy()

    out = CompressionStrategies.apply_clip_blend_compression(audio, PARAMS)

    assert out.shape == audio.shape
    assert out.dtype == audio.dtype
    np.testing.assert_array_equal(audio, original)


@pytest.mark.parametrize("fill", [0.0, 1e-9, np.nan])
def test_silence_and_non_finite_input_pass_through_without_new_nans(fill):
    audio = np.full((1024, 2), fill, dtype=np.float32)

    out = CompressionStrategies.apply_clip_blend_compression(audio, PARAMS)

    np.testing.assert_array_equal(out, audio)
