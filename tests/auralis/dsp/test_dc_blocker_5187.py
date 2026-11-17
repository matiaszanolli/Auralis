"""DC blocker ahead of mastering (#5187)."""

import numpy as np
import pytest

from auralis.dsp.dc_blocker import DC_BLOCK_CUTOFF_HZ, remove_dc

SR = 44100


def _music(seconds: float, dc: float = 0.02) -> np.ndarray:
    rng = np.random.default_rng(5187)
    t = np.arange(int(SR * seconds)) / SR
    tone = 0.3 * np.sin(2 * np.pi * 110 * t) + 0.05 * rng.standard_normal(len(t))
    return (np.column_stack([tone, np.roll(tone, 50)]) + dc).astype(np.float32)


def test_shape_dtype_and_input_are_preserved():
    audio = _music(2.0)
    before = audio.copy()
    out = remove_dc(audio, SR)
    assert out.shape == audio.shape and out.dtype == audio.dtype
    np.testing.assert_array_equal(audio, before)
    assert remove_dc(audio[:, 0].astype(np.float64), SR).dtype == np.float64


def test_offset_is_removed_after_settling():
    out = remove_dc(_music(3.0, dc=0.05), SR)
    assert abs(float(np.mean(out[int(0.2 * SR):]))) < 1e-3


def test_audible_band_is_left_alone():
    t = np.arange(SR * 4) / SR
    tone = np.sin(2 * np.pi * 20.0 * t)
    out = remove_dc(tone, SR)[SR:]
    gain_db = 20 * np.log10(np.std(out) / np.std(tone[SR:]))
    assert DC_BLOCK_CUTOFF_HZ <= 10.0
    assert gain_db == pytest.approx(0.0, abs=0.05)


def test_a_chunk_rendered_with_its_context_matches_the_whole_track():
    """Streaming renders each chunk with 5 s of preceding context (chunk_boundaries.CONTEXT_DURATION);
    a causal filter has settled by the core, so independently rendered chunks agree at their seams."""
    track = _music(25.0)
    whole = remove_dc(track, SR)
    core_start, core_end = 10 * SR, 20 * SR
    chunk = remove_dc(track[core_start - 5 * SR:core_end], SR)[5 * SR:]
    np.testing.assert_allclose(chunk, whole[core_start:core_end], atol=1e-6)
