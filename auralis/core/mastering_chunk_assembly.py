"""
Per-chunk helpers for the mastering chunk loop (split from
mastering_chunk_loop.py, #5839): reading an overlapped chunk, the True Peak
guard, and the crossfaded assembly of the region to write. Pure functions of
their arguments; the loop owns all state.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import TYPE_CHECKING, Any

import numpy as np

from ..dsp.utils.conversion import db_to_amplitude
from ..utils.logging import warning

if TYPE_CHECKING:
    from .simple_mastering import SimpleMasteringPipeline

# Measured 4x-oversample reconstruction overshoot the TP guard absorbs
# (#4970). The June 2026 study measured outputs averaging +0.77 dBTP when
# unguarded; ~0.27 dB of headroom above the -0.5 dBFS ceiling covers it.
_TRUE_PEAK_OVERSHOOT_RATIO = db_to_amplitude(0.27)


def read_chunk(
    audio_file: Any,
    read_pos: int,
    core_samples: int,
    total_frames: int,
    crossfade_samples: int,
    is_last: bool,
) -> np.ndarray | None:
    """Read core + overlap and return it as float32 (channels, samples), or None at EOF."""
    # Read core + overlap so both chunks process the boundary
    audio_file.seek(read_pos)
    if is_last:
        chunk = audio_file.read(core_samples)
    else:
        overlap_after = min(crossfade_samples, total_frames - read_pos - core_samples)
        chunk = audio_file.read(core_samples + overlap_after)

    if chunk.size == 0:
        return None

    # Ensure float32
    chunk = chunk.astype(np.float32)

    # Ensure stereo (channels, samples) format
    if chunk.ndim == 1:
        chunk = np.stack([chunk, chunk]).T
    elif chunk.ndim == 2 and chunk.shape[1] > 2:
        # Defensive only (#5569): _master_file_impl pre-downmixes multichannel
        # sources, so this branch should be unreachable. Warn rather than
        # silently dropping Center/LFE/surround.
        warning(
            f"Chunk has {chunk.shape[1]} channels; taking L+R — "
            "multichannel sources should have been downmixed "
            "before the chunk loop (#5569)"
        )
        chunk = chunk[:, :2]

    # Convert to (channels, samples) for processing. soundfile always yields
    # (samples, channels), as does the mono→stereo path above, so we always
    # need to transpose here. The old heuristic `shape[0] > shape[1]` silently
    # failed for square arrays like (2, 2) — 2-sample stereo — because 2 > 2 is
    # False (issue #2292).
    return np.asarray(chunk.T)


def apply_true_peak_guard(pipeline: 'SimpleMasteringPipeline', processed_chunk: np.ndarray) -> np.ndarray:
    """Cap True Peak at -0.5 dBFS.

    Empirically validated (June 2026 study): 74 % of outputs exceeded 0 dBFS
    True Peak (avg +0.77 dBFS) because the harmonic exciter generates
    near-Nyquist content that causes intersample reconstruction peaks even when
    sample peaks are held at 0.97. 4× oversampled peak measurement + gain
    reduction caps True Peak at -0.5 dBFS.

    #4970: the gain is derived from the whole-song peak (_song_peak_db,
    measured by prepare_file's pre-scan) rather than the per-chunk 4x peak — a
    per-chunk ratio varied between adjacent chunks and produced soft level
    steps at boundaries. Because the song peak can exceed any single chunk's
    peak, the fixed -0.5 dBFS overshoot term is applied on top:
    gain = song_ceiling / (song_peak * 4x overshoot ratio), constant across
    all chunks.
    """
    _tp_ceiling = db_to_amplitude(-0.5)  # −0.5 dBFS = 0.9441
    _tp_overshoot = _TRUE_PEAK_OVERSHOOT_RATIO
    if pipeline._song_peak_db is not None:
        _song_peak_linear = db_to_amplitude(pipeline._song_peak_db)
        _tp_gain = _tp_ceiling / (_song_peak_linear * _tp_overshoot)
        if _tp_gain < 1.0:
            processed_chunk = processed_chunk * _tp_gain
    else:
        # No pre-scan (direct _process() test path): keep the per-chunk
        # measurement so the ceiling still holds, and surface any failure
        # instead of swallowing it (#4970).
        try:
            from scipy.signal import resample_poly as _rsp
            _chunk_4x = _rsp(processed_chunk, 4, 1, axis=1)
            _tp = float(np.max(np.abs(_chunk_4x)))
            if _tp > _tp_ceiling:
                processed_chunk = processed_chunk * (_tp_ceiling / _tp)
        except Exception as e:
            warning(f"True-peak guard failed; ceiling not enforced: {e}")
    return processed_chunk


def true_peak_4x(write_region: np.ndarray) -> float:
    """4x-oversampled peak of a final (samples, channels) signal (#5694).

    Same measurement the guard's no-pre-scan branch uses; on a resampler
    failure the sample peak times the #4970 overshoot ratio is the
    conservative fallback (it slightly over-estimates, which only makes a
    correction derived from it safer).
    """
    try:
        from scipy.signal import resample_poly as _rsp
        return float(np.max(np.abs(_rsp(write_region, 4, 1, axis=0))))
    except Exception:
        return float(np.max(np.abs(write_region))) * _TRUE_PEAK_OVERSHOOT_RATIO


def merge_stage_info(info: dict[str, Any] | None, chunk_info: dict[str, Any]) -> dict[str, Any]:
    """Retain the first chunk's metadata, but report every stage that ran anywhere in the file.

    Stages are de-duplicated in execution order so a stage run on several
    chunks is still represented once in this diagnostic summary.
    """
    if info is None:
        return chunk_info
    for stage in chunk_info.get('stages', []):
        if stage not in info['stages']:
            info['stages'].append(stage)
    return info


def split_core_and_tail(
    processed_chunk: np.ndarray, core_samples: int, is_last: bool
) -> tuple[np.ndarray, np.ndarray | None]:
    """The region to write as-is and the overlap tail to carry (None on the last chunk)."""
    if is_last:
        return processed_chunk, None
    return processed_chunk[:, :core_samples], processed_chunk[:, core_samples:].copy()


def assemble_write_region(
    processed_chunk: np.ndarray,
    prev_tail: np.ndarray | None,
    first_chunk: bool,
    core_samples: int,
    is_last: bool,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Crossfade this chunk's head with the previous tail; returns (write_region, new_tail).

    new_tail stages the next prev_tail value; the caller commits it only after
    the write succeeds (#2429).
    """
    if first_chunk or prev_tail is None:
        # First chunk (or the no-previous-tail safety fallback): write core,
        # save overlap tail.
        return split_core_and_tail(processed_chunk, core_samples, is_last)

    # Crossfade head of this chunk with previous tail
    head_len = min(prev_tail.shape[1], processed_chunk.shape[1])

    if head_len == 0:
        # Empty overlap tail — skip crossfade, concatenate directly
        # (fixes #2157: np.linspace(..., 0) produces empty array
        # and silently drops samples at the chunk boundary)
        return split_core_and_tail(processed_chunk, core_samples, is_last)

    head = processed_chunk[:, :head_len]

    # Equal-gain (raised-cosine) crossfade: correct for this correlated overlap
    # region (adjacent chunks process the same source samples). NOT
    # equal-power — see #4966.
    # #3684: compute the fade ramps in the chunk's dtype so the multiply with
    # prev_tail/head does not promote crossfaded → float64.
    chunk_dtype = processed_chunk.dtype
    t = np.linspace(0.0, np.pi / 2, head_len, dtype=chunk_dtype)
    fade_in = np.sin(t) ** 2
    fade_out = np.cos(t) ** 2
    crossfaded = prev_tail[:, :head_len] * fade_out + head * fade_in

    if is_last:
        body = processed_chunk[:, head_len:]
        return np.concatenate([crossfaded, body], axis=1), None

    body = processed_chunk[:, head_len:core_samples]
    write_region = np.concatenate([crossfaded, body], axis=1)
    # Guard against silent sample drift at chunk boundaries (#2515)
    if write_region.shape[1] != core_samples:
        raise RuntimeError(
            f"Crossfade write_region mismatch: expected {core_samples} "
            f"samples, got {write_region.shape[1]}"
        )
    return write_region, processed_chunk[:, core_samples:].copy()


def two_pass_correction_gain(
    measured_sample_peak: float, measured_true_peak: float, verbose: bool
) -> float:
    """The one uniform gain (<= 1.0) that brings the measured pass's final
    signal under 0.99 full scale and the -0.5 dBTP ceiling (#5694)."""
    correction_gain = min(
        1.0,
        0.99 / max(measured_sample_peak, 1e-9),
        db_to_amplitude(-0.5) / max(measured_true_peak, 1e-9),
    )
    if verbose and correction_gain < 1.0:
        print(
            f"   Two-pass peak correction: {20 * np.log10(correction_gain):+.2f} dB "
            f"(measured sample peak {measured_sample_peak:.3f}, "
            f"true peak {measured_true_peak:.3f})"
        )
    return correction_gain
