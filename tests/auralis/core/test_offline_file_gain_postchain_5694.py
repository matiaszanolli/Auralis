"""
Offline CLI file-level gain bounded by a measured pre-pass (#5694)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The offline path multiplied every chunk by a constant file_gain keyed to
the INPUT peak (``_song_peak_db`` from prepare_file's pre-scan), but the
stages in between — makeup gain, EQ shelves, exciter, loudness maximizer —
do not preserve the peak. For quiet sources the chain already lifted the
peak toward the limiter ceiling and the input-keyed gain was applied on
top, leaving the final ``np.clip(-1, 1)`` before the PCM_24 write as the
only protection: hard clipping (0.2-1.1 % of samples at full scale for
input peaks 0.05-0.3 in the audit's probes).

The render is now two-pass: an identical no-sink measurement pass derives
ONE uniform correction from the actual final (post-assembly, pre-clip)
signal, bounding sample peak at 0.99 and true peak at -0.5 dBFS by
construction. The correction is constant, so #5559's macro-dynamics
invariant — a quiet movement is not raised to the loudest section's level
— is untouched.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from auralis.core import mastering_chunk_loop
from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.simple_mastering import SimpleMasteringPipeline

SR = 44100


def _make_config() -> SimpleMasteringConfig:
    config = SimpleMasteringConfig()
    config.CROSSFADE_DURATION_SEC = 0.05
    config.CHUNK_DURATION_SEC = 2
    return config


def _make_pipeline() -> SimpleMasteringPipeline:
    pipeline = SimpleMasteringPipeline(config=_make_config())
    mock_fs = MagicMock()
    mock_fs.get_or_compute.return_value = {
        'lufs': -18.0, 'crest_db': 14.0, 'bass_mid_ratio': 0.5,
        'sub_bass_pct': 0.10, 'bass_pct': 0.30, 'low_mid_pct': 0.10,
        'mid_pct': 0.20, 'upper_mid_pct': 0.12, 'presence_pct': 0.10,
        'air_pct': 0.03, 'spectral_centroid': 0.5, 'spectral_rolloff': 0.5,
        'spectral_flatness': 0.3, 'tempo_bpm': 120.0,
        'rhythm_stability': 0.5, 'transient_density': 0.5,
        'silence_ratio': 0.0, 'harmonic_ratio': 0.5,
        'pitch_stability': 0.7, 'chroma_energy': 0.5,
        'dynamic_range_variation': 0.3, 'loudness_variation_std': 2.0,
        'peak_consistency': 0.8, 'stereo_width': 0.5,
        'phase_correlation': 0.8,
    }
    pipeline._fingerprint_service = mock_fs
    return pipeline


def _music_like(seconds: float = 12.0, peak: float = 0.5) -> np.ndarray:
    """Pink-ish noise plus 55 Hz kicks, scaled to the requested input peak."""
    rng = np.random.default_rng(5694)
    n = int(SR * seconds)
    white = rng.standard_normal(n)
    # crude pinkening: cumulative-average filter
    pink = np.convolve(white, np.ones(64) / 64, mode='same')
    t = np.arange(n) / SR
    kick = np.zeros(n)
    for beat in range(0, n, SR // 2):
        edge = slice(beat, min(beat + int(0.08 * SR), n))
        kick[edge] = np.sin(2 * np.pi * 55 * t[edge]) * np.exp(-t[edge] * 18)
    mono = pink * 0.6 + kick * 2.0
    stereo = np.column_stack([mono, np.roll(mono, 131)]).astype(np.float32)
    return (stereo / np.max(np.abs(stereo)) * peak).astype(np.float32)


class _PreclipProbe:
    """Records the max |x| reaching the pre-write np.clip(write, -1, 1).

    Only the write clamp's exact bounds are recorded — intermediate stages
    clip with other bounds (e.g. adapted_peak's 0.84..0.89) and are not the
    signal the PCM write sees.
    """

    def __init__(self) -> None:
        self.max_abs = 0.0
        self._original = np.clip

    def __call__(self, a, a_min, a_max, **kwargs):
        if (a_min, a_max) == (-1.0, 1.0):
            self.max_abs = max(self.max_abs, float(np.max(np.abs(a))))
        return self._original(a, a_min, a_max, **kwargs)


def _master(pipeline: SimpleMasteringPipeline, src: Path, dst: Path, probe: _PreclipProbe):
    with patch.object(mastering_chunk_loop.np, "clip", probe):
        pipeline.master_file(
            input_path=str(src), output_path=str(dst), intensity=1.0, verbose=False
        )


@pytest.mark.parametrize("input_peak", [0.05, 0.3, 0.5, 0.7, 0.9])
def test_preclip_signal_never_reaches_the_write_clamp(tmp_path: Path, input_peak: float) -> None:
    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    sf.write(str(src), _music_like(peak=input_peak), SR, subtype='FLOAT')

    probe = _PreclipProbe()
    _master(_make_pipeline(), src, dst, probe)

    assert probe.max_abs <= 1.0, (
        f"input peak {input_peak}: pre-clip signal reached {probe.max_abs:.3f} — "
        f"the write clamp hard-clipped the master (#5694)"
    )

    written, _ = sf.read(str(dst), dtype='float64')
    at_full_scale = float(np.mean(np.abs(written) >= 0.999999))
    assert at_full_scale < 1e-5, (
        f"{at_full_scale * 100:.3f}% of written samples at full scale"
    )


@pytest.mark.parametrize("input_peak", [0.1, 0.5])
def test_written_true_peak_holds_the_ceiling(tmp_path: Path, input_peak: float) -> None:
    from scipy.signal import resample_poly

    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    sf.write(str(src), _music_like(peak=input_peak), SR, subtype='FLOAT')

    _master(_make_pipeline(), src, dst, _PreclipProbe())

    written, _ = sf.read(str(dst), dtype='float64')
    oversampled = resample_poly(written, 4, 1, axis=0)
    tp_db = 20 * np.log10(max(float(np.max(np.abs(oversampled))), 1e-12))
    assert tp_db <= -0.5 + 0.1, f"true peak {tp_db:.2f} dBFS exceeds -0.5 (#5694)"


def test_macro_dynamics_survive_the_constant_correction(tmp_path: Path) -> None:
    """#5559 invariant: a 20 dB quieter second half is NOT raised to the
    first half's level by the file-level gain (it stays ~15+ dB apart)."""
    loud = _music_like(seconds=6.0, peak=0.5)
    quiet = _music_like(seconds=6.0, peak=0.05)  # 20 dB below the loud half
    track = np.concatenate([loud, quiet]).astype(np.float32)

    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    sf.write(str(src), track, SR, subtype='FLOAT')

    _master(_make_pipeline(), src, dst, _PreclipProbe())

    written, _ = sf.read(str(dst), dtype='float64')
    half = len(written) // 2
    rms = lambda x: float(20 * np.log10(max(np.sqrt(np.mean(x ** 2)), 1e-12)))
    section_gap_db = rms(written[:half]) - rms(written[half:])
    assert section_gap_db >= 15.0, (
        f"section gap collapsed to {section_gap_db:.1f} dB — the constant-gain "
        f"macro-dynamics invariant (#5559) regressed"
    )
