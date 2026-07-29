"""Regression tests for the continuous loudness-and-crest response."""

from itertools import pairwise

import numpy as np

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.stages import loudness_maximizer


def _apply(source_lufs: float) -> tuple[np.ndarray, dict]:
    sample_rate = 48_000
    t = np.arange(4_800, dtype=np.float64) / sample_rate
    mono = 0.1 * np.sin(2.0 * np.pi * 440.0 * t)
    audio = np.vstack((mono, mono))

    output, info = loudness_maximizer.apply(
        audio,
        source_lufs=source_lufs,
        source_crest_db=16.0,
        sample_rate=sample_rate,
        verbose=False,
        config=SimpleMasteringConfig(),
    )
    assert info is not None
    return output, info


def test_response_never_uses_a_loudness_bypass():
    pushes = [_apply(lufs)[1]['push_db'] for lufs in (-24.0, -18.0, -14.0, -8.0)]

    assert all(push > 0.0 for push in pushes)
    assert all(left > right for left, right in pairwise(pushes))


def test_response_is_continuous_around_former_cutoff():
    pushes = [_apply(lufs)[1]['push_db'] for lufs in (-14.01, -14.0, -13.99)]

    assert all(push > 0.0 for push in pushes)
    assert max(abs(left - right) for left, right in pairwise(pushes)) < 0.01


def test_stage_preserves_shape_dtype_and_finiteness():
    output, _ = _apply(-18.0)
    _, reference = _apply(-18.0)

    assert output.shape == (2, 4_800)
    assert output.dtype == np.float64
    assert np.isfinite(output).all()
    assert reference['stage'] == 'loudness_maximizer'
