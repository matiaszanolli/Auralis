"""
Regression test for #3742 — EQ functions must reject buffers longer than
fft_size instead of silently truncating.

Pre-fix, both `apply_eq_mono` (filters.py:85,103) and
`VectorizedEQProcessor._apply_eq_mono_vectorized`
(vectorized_processor.py:102,124) did:

    spectrum = fft(audio_mono[:fft_size])
    ...
    return processed_audio[:len(audio_mono)]

When `len(audio_mono) > fft_size`, the IFFT output is `fft_size` long
and the final slice silently drops everything past fft_size — the
return value is the same length as `fft_size`, NOT the same length as
the input. Upstream `assert chunk.shape[1] == input.shape[1]` would
only fire downstream after the bug shipped.

The fix raises `ValueError` immediately so any future bypass-the-
chunker caller (unit test, fast path, external integration) gets a
clean signal.
"""

from __future__ import annotations

import numpy as np
import pytest

from auralis.dsp.eq.filters import apply_eq_mono
from auralis.dsp.eq.parallel_eq_processor.vectorized_processor import (
    VectorizedEQProcessor,
)


def _band_map_for(fft_size: int) -> np.ndarray:
    """All bins → band 0 — enough to drive the EQ path without modelling the
    full 26-band psychoacoustic map."""
    return np.zeros(fft_size // 2 + 1, dtype=np.int64)


def test_apply_eq_mono_raises_when_input_exceeds_fft_size() -> None:
    fft_size = 4096
    too_long = np.zeros(fft_size * 2, dtype=np.float32)
    gains = np.zeros(1, dtype=np.float32)
    band_map = _band_map_for(fft_size)
    with pytest.raises(ValueError, match="exceeds fft_size"):
        apply_eq_mono(too_long, gains, band_map, fft_size)


def test_apply_eq_mono_accepts_input_at_fft_size() -> None:
    fft_size = 4096
    exact = np.zeros(fft_size, dtype=np.float32)
    gains = np.zeros(1, dtype=np.float32)
    band_map = _band_map_for(fft_size)
    out = apply_eq_mono(exact, gains, band_map, fft_size)
    assert len(out) == fft_size


def test_apply_eq_gains_pads_input_below_fft_size() -> None:
    """The public wrapper `apply_eq_gains` pads inputs shorter than
    fft_size, so it accepts them. The `apply_eq_mono` worker, by
    contrast, expects the caller to have padded already — passing it a
    short buffer trips the band-mask shape mismatch by design."""
    from auralis.dsp.eq.filters import apply_eq_gains
    fft_size = 4096
    short = np.zeros((1024, 2), dtype=np.float32)
    gains = np.zeros(1, dtype=np.float32)
    band_map = _band_map_for(fft_size)
    out = apply_eq_gains(short, gains, band_map, fft_size)
    assert out.shape[0] == 1024


def test_vectorized_eq_raises_when_input_exceeds_fft_size() -> None:
    fft_size = 4096
    too_long = np.zeros(fft_size * 2, dtype=np.float32)
    gains = np.zeros(1, dtype=np.float32)
    band_map = _band_map_for(fft_size)
    proc = VectorizedEQProcessor()
    with pytest.raises(ValueError, match="exceeds fft_size"):
        proc._apply_eq_mono_vectorized(too_long, gains, band_map, fft_size)


def test_vectorized_eq_accepts_input_at_fft_size() -> None:
    fft_size = 4096
    exact = np.zeros(fft_size, dtype=np.float32)
    gains = np.zeros(1, dtype=np.float32)
    band_map = _band_map_for(fft_size)
    proc = VectorizedEQProcessor()
    out = proc._apply_eq_mono_vectorized(exact, gains, band_map, fft_size)
    assert len(out) == fft_size
