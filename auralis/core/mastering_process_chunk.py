"""
Mastering Per-Chunk Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Core per-chunk DSP dispatch for SimpleMasteringPipeline: adaptive intensity,
clip-prevention peak reduction, continuous mastering, and output normalization.

Extracted from simple_mastering.py's _process/_calculate_intensity/
_reduce_peaks/_peak_db (#4072). `SimpleMasteringPipeline._process` keeps its
exact signature as a thin delegate — it is called directly by
tests/auralis/core/test_nan_detection.py, so the public contract is
preserved.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import TYPE_CHECKING, Any

import numpy as np

from ..dsp.basic import normalize
from ..dsp.dynamics.soft_clipper import soft_clip
from ..utils.audio_validation import sanitize_audio, validate_audio_finite
from .mastering_branches import ContinuousMasteringBranch
from .utils import FingerprintUnpacker, SmoothCurveUtilities

if TYPE_CHECKING:
    from .simple_mastering import SimpleMasteringPipeline


def compute_peak_db(audio: np.ndarray) -> float:
    """Calculate peak level in dB."""
    peak = np.max(np.abs(audio))
    return 20 * np.log10(peak) if peak > 0 else -96.0


def calculate_intensity(base: float, lufs: float, crest_db: float) -> float:
    """
    Calculate effective intensity from base + audio characteristics.

    Crest factor and LUFS contribute through smooth corpus-calibrated curves.
    No region selects a different formula or material type.
    """
    crest_coordinate = 0.5 + 0.5 * np.tanh(
        (crest_db - 13.4207) / (2.0 * 1.7884)
    )
    loudness_coordinate = 0.5 + 0.5 * np.tanh(
        (lufs + 14.3887) / (2.0 * 2.7732)
    )
    multiplier = 0.5 + 0.7 * crest_coordinate * (
        1.0 - 0.65 * loudness_coordinate
    )
    return float(base * multiplier)


def reduce_peaks(
    audio: np.ndarray, current_db: float, target_db: float
) -> tuple[np.ndarray, float]:
    """Surgical peak reduction via soft clipping."""
    if current_db <= target_db:
        # Copy on bypass, matching stages.no_op()'s contract (#5107).
        return audio.copy(), current_db

    threshold = 10 ** (target_db / 20.0)
    processed = soft_clip(audio, threshold=threshold, ceiling=min(0.99, threshold * 1.05))
    return processed, compute_peak_db(processed)


def process_chunk(
    pipeline: 'SimpleMasteringPipeline',
    audio: np.ndarray,
    fp: dict[str, float],
    peak_db: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Core processing logic using all 25D fingerprint dimensions."""

    # Unpack fingerprint using type-safe unpacker
    unpacker = FingerprintUnpacker.from_dict(fp)

    info: dict[str, Any] = {'stages': []}
    processed = audio.copy()

    # Validate input audio for NaN/Inf (fail fast on corrupted input)
    processed = validate_audio_finite(processed, context="simple mastering input", repair=False)

    # Adaptive intensity based on dynamics + loudness
    effective_intensity = calculate_intensity(intensity, unpacker.lufs, unpacker.crest_db)

    config = pipeline.config

    # STAGE 1: Gentle peak reduction for clipping prevention only
    # Only intervene when peak is dangerously close to or above 0 dBFS
    # Uses smooth S-curve to avoid filtering effect - just prevents actual clipping
    if peak_db > config.PEAK_REDUCTION_THRESHOLD_DB:
        # Smooth curve: gentle near threshold, stronger for severe clipping
        # clip_severity: 0 at threshold, 1 at threshold + range
        smooth_factor = SmoothCurveUtilities.ramp_to_s_curve(
            peak_db,
            config.PEAK_REDUCTION_THRESHOLD_DB,
            config.PEAK_REDUCTION_THRESHOLD_DB + config.PEAK_CLIP_SEVERITY_RANGE_DB
        )

        # Target: threshold to max_target based on severity
        peak_range = abs(config.MAX_TARGET_PEAK_REDUCTION_DB - config.PEAK_REDUCTION_THRESHOLD_DB)
        target_peak = config.PEAK_REDUCTION_THRESHOLD_DB - smooth_factor * peak_range

        if verbose:
            print(f"   Peak reduction: {peak_db:.1f} → {target_peak:.1f} dB")

        processed, peak_db = reduce_peaks(processed, peak_db, target_peak)
        info['stages'].append({'stage': 'peak_reduction', 'target': target_peak, 'result': peak_db})

    # STAGE 2: One continuous processing path for every source.
    mastering_path = ContinuousMasteringBranch(pipeline)

    # Branches receive the WHOLE-SONG peak here, not the per-chunk
    # `peak_db` used above for Stage 1's clip prevention. The only
    # consumer is the makeup-gain headroom clamp, and using a
    # per-chunk value there made a quiet verse chunk get its full gain
    # while a loud chorus chunk (same song, same target) got clamped
    # down hard purely because its own peak was high — an audible
    # inconsistency between sections rather than one consistent gain for
    # the whole song. Falls back to the local peak_db when unset (the
    # direct _process() test path, which never runs the pre-scan).
    gain_reference_peak_db = (
        pipeline._song_peak_db if pipeline._song_peak_db is not None else peak_db
    )

    processed, path_info = mastering_path.apply(
        processed, unpacker, gain_reference_peak_db, effective_intensity,
        sample_rate, config, verbose
    )

    info['stages'].extend(path_info.get('stages', []))
    needs_output_normalize = path_info.get('needs_output_normalize', False)

    # STAGE 3: Optional unified output normalization.
    if needs_output_normalize:
        # Target slightly below 0 dBFS to leave headroom for playback
        output_target = 0.95

        current_peak = np.max(np.abs(processed))
        # Normalize in both directions — boost quiet material AND reduce hot
        # peaks above the target ceiling (fixes #2306: was only normalizing UP).
        if current_peak > 0:
            processed = normalize(processed, output_target)
            if verbose:
                gain_db = 20 * np.log10(output_target / current_peak)
                direction = "+" if gain_db >= 0 else ""
                print(f"   Output normalize: {direction}{gain_db:.1f} dB → {output_target*100:.0f}% peak")
            info['stages'].append({'stage': 'output_normalize', 'target_peak': output_target})

    # Validate output for NaN/Inf (graceful handling for production resilience)
    processed = sanitize_audio(processed, context="simple mastering output")

    info['effective_intensity'] = effective_intensity
    return processed, info
