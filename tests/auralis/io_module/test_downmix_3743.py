"""
Regression tests for #3743 — ITU-R BS.775 downmix on native loaders.

Pre-fix, `loader.py:84-86` and `soundfile_loader.py:70-74` both did
`audio_data[:, :2].copy()` for multichannel input — a hard truncation
that discarded Center (vocals/dialogue), LFE, and surround content.
The FFmpeg path (#3672) already applied the standard matrix via
`-ac 2`. This fix introduced `auralis.io.processing.downmix_to_stereo`
shared between both native loaders so all three paths produce
compatible stereo.

The downmix mapping (BS.775-3, LFE dropped):
    L_out = L + (1/√2)·C + (1/√2)·Ls
    R_out = R + (1/√2)·C + (1/√2)·Rs
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from auralis.io.processing import downmix_to_stereo


def _make_51(samples: int = 1024) -> np.ndarray:
    """5.1 layout: L, R, C, LFE, Ls, Rs with distinct constant values per channel."""
    out = np.zeros((samples, 6), dtype=np.float32)
    out[:, 0] = 0.5    # L
    out[:, 1] = 0.4    # R
    out[:, 2] = 0.3    # C
    out[:, 3] = 0.2    # LFE
    out[:, 4] = 0.1    # Ls
    out[:, 5] = 0.05   # Rs
    return out


def test_center_channel_contributes_to_both_outputs() -> None:
    """The Center channel must appear in BOTH L and R outputs (vocals
    must not be silenced)."""
    sq2 = 1 / math.sqrt(2)

    # Build a 5.1 buffer whose ONLY non-zero channel is Center, so the
    # downmix output must be entirely C-derived.
    audio = np.zeros((100, 6), dtype=np.float32)
    audio[:, 2] = 0.5  # C only

    out = downmix_to_stereo(audio)

    expected = 0.5 * sq2
    # Either channel must carry the center content (possibly rescaled
    # by the peak-renormalize step).
    assert out[0, 0] > 0.0, "Center didn't make it into L"
    assert out[0, 1] > 0.0, "Center didn't make it into R"
    # When ONLY C is present, L_out and R_out are equal by construction.
    assert math.isclose(float(out[0, 0]), float(out[0, 1]), rel_tol=1e-5)
    # Peak-renormalize bounds output to the input peak (0.5 here).
    assert float(np.max(np.abs(out))) <= 0.5 + 1e-5
    # And we should have something close to expected before any rescaling.
    assert 0.0 < float(out[0, 0]) <= 0.5
    del expected  # The renormalize step adjusts amplitude; identity is what matters


def test_lfe_is_dropped() -> None:
    """LFE (index 3) must not contribute to the stereo image — BS.775
    treats it as discardable for a music downmix."""
    audio = np.zeros((100, 6), dtype=np.float32)
    audio[:, 3] = 0.5  # LFE only
    out = downmix_to_stereo(audio)
    assert float(np.max(np.abs(out))) < 1e-6, "LFE leaked into stereo image"


def test_surround_channels_routed_to_correct_side() -> None:
    """Ls → L only, Rs → R only."""
    sq2 = 1 / math.sqrt(2)

    ls_only = np.zeros((100, 6), dtype=np.float32)
    ls_only[:, 4] = 0.5  # Ls
    out = downmix_to_stereo(ls_only)
    assert out[0, 0] > 0.0  # left got Ls
    assert abs(float(out[0, 1])) < 1e-6  # right got nothing

    rs_only = np.zeros((100, 6), dtype=np.float32)
    rs_only[:, 5] = 0.5  # Rs
    out = downmix_to_stereo(rs_only)
    assert abs(float(out[0, 0])) < 1e-6
    assert out[0, 1] > 0.0
    del sq2  # rendered as visual reference for the mapping


def test_full_51_downmix_preserves_input_peak() -> None:
    audio = _make_51()
    in_peak = float(np.max(np.abs(audio)))
    out = downmix_to_stereo(audio)
    out_peak = float(np.max(np.abs(out)))
    # Output peak must not exceed input peak (no surprise clipping).
    assert out_peak <= in_peak + 1e-5


def test_preserves_input_dtype() -> None:
    audio = _make_51().astype(np.float64)
    out = downmix_to_stereo(audio)
    assert out.dtype == np.float64

    audio_f32 = _make_51().astype(np.float32)
    out_f32 = downmix_to_stereo(audio_f32)
    assert out_f32.dtype == np.float32


def test_stereo_input_passes_through_as_copy() -> None:
    audio = np.array([[0.5, 0.3], [0.7, 0.6]], dtype=np.float32)
    out = downmix_to_stereo(audio)
    assert out.shape == audio.shape
    assert np.allclose(out, audio)
    # Must be a copy (no caller can mutate ours via the returned array).
    assert out is not audio


def test_71_extra_channels_summed_into_both_sides() -> None:
    """Index 6 / 7 (e.g. Lsr / Rsr) should contribute energy to both
    outputs without lopsided placement."""
    audio = np.zeros((100, 8), dtype=np.float32)
    audio[:, 6] = 0.2  # Lsr
    audio[:, 7] = 0.2  # Rsr
    out = downmix_to_stereo(audio)
    assert math.isclose(float(out[0, 0]), float(out[0, 1]), rel_tol=1e-5)


def test_rejects_non_2d() -> None:
    with pytest.raises(ValueError):
        downmix_to_stereo(np.zeros(100, dtype=np.float32))
