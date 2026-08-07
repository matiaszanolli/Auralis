"""
Regression test for #4928 — FFT-EQ zero-padding must preserve input rank.

Pre-fix, `apply_eq_gains` (filters.py), `apply_eq_gains_vectorized`
(vectorized_processor.py), and the now-deleted `ParallelEQProcessor`
padded a short chunk into a `(fft_size, channels_or_1)` array and called
`.squeeze()` to restore rank. For a genuinely-2-D single-channel `(N, 1)`
input with `N < fft_size`, `squeeze()` drops *every* size-1 axis — including
the channel axis — returning `(N,)` instead of `(N, 1)`. Because the
`N >= fft_size` path never pads (and so never squeezes), the same `(N, 1)`
chunk returned 2-D when long and 1-D when short: output rank depended on
chunk length.

The fix (`auralis/dsp/eq/padding.py::pad_for_fft`) tracks the input's
ndim explicitly instead of inferring it from `.squeeze()`.
"""

from __future__ import annotations

import numpy as np

from auralis.dsp.eq.filters import apply_eq_gains
from auralis.dsp.eq.padding import pad_for_fft
from auralis.dsp.eq.parallel_eq_processor.vectorized_processor import (
    VectorizedEQProcessor,
)


def _band_map_for(fft_size: int) -> np.ndarray:
    """All bins -> band 0 — enough to drive the EQ path without modelling the
    full 26-band psychoacoustic map."""
    return np.zeros(fft_size // 2 + 1, dtype=np.int64)


def test_pad_for_fft_preserves_2d_single_channel_rank() -> None:
    fft_size = 64
    short = np.random.randn(10, 1).astype(np.float32)
    padded = pad_for_fft(short, fft_size)
    assert padded.ndim == 2
    assert padded.shape == (fft_size, 1)
    assert padded.dtype == np.float32


def test_pad_for_fft_preserves_1d_rank() -> None:
    fft_size = 64
    short = np.random.randn(10).astype(np.float32)
    padded = pad_for_fft(short, fft_size)
    assert padded.ndim == 1
    assert padded.shape == (fft_size,)


def test_pad_for_fft_preserves_multichannel_rank() -> None:
    fft_size = 64
    short = np.random.randn(10, 2).astype(np.float64)
    padded = pad_for_fft(short, fft_size)
    assert padded.ndim == 2
    assert padded.shape == (fft_size, 2)


def test_apply_eq_gains_keeps_2d_output_for_short_single_channel_input() -> None:
    fft_size = 64
    short = np.random.randn(10, 1).astype(np.float32)
    gains = np.zeros(1, dtype=np.float32)
    band_map = _band_map_for(fft_size)
    out = apply_eq_gains(short, gains, band_map, fft_size)
    assert out.ndim == 2
    assert out.shape == (10, 1)


def test_apply_eq_gains_keeps_2d_output_for_long_single_channel_input() -> None:
    """Regression guard: the already-correct N >= fft_size path (no padding
    taken) must keep returning 2-D — confirm the fix didn't disturb it."""
    fft_size = 64
    long = np.random.randn(fft_size, 1).astype(np.float32)
    gains = np.zeros(1, dtype=np.float32)
    band_map = _band_map_for(fft_size)
    out = apply_eq_gains(long, gains, band_map, fft_size)
    assert out.ndim == 2
    assert out.shape == (fft_size, 1)


def test_vectorized_eq_keeps_2d_output_for_short_single_channel_input() -> None:
    fft_size = 64
    short = np.random.randn(10, 1).astype(np.float32)
    gains = np.zeros(1, dtype=np.float32)
    band_map = _band_map_for(fft_size)
    proc = VectorizedEQProcessor()
    out = proc.apply_eq_gains_vectorized(short, gains, band_map, fft_size)
    assert out.ndim == 2
    assert out.shape == (10, 1)


def test_vectorized_eq_keeps_2d_output_for_long_single_channel_input() -> None:
    fft_size = 64
    long = np.random.randn(fft_size, 1).astype(np.float32)
    gains = np.zeros(1, dtype=np.float32)
    band_map = _band_map_for(fft_size)
    proc = VectorizedEQProcessor()
    out = proc.apply_eq_gains_vectorized(long, gains, band_map, fft_size)
    assert out.ndim == 2
    assert out.shape == (fft_size, 1)
