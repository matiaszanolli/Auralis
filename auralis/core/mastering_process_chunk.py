"""
Mastering Per-Chunk Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Core per-chunk DSP dispatch for SimpleMasteringPipeline: adaptive intensity,
clip-prevention peak reduction, material classification + branch dispatch,
and output normalization.

Extracted from simple_mastering.py's _process/_calculate_intensity/
_reduce_peaks/_peak_db (#4072). `SimpleMasteringPipeline._process` keeps its
exact signature as a thin delegate — it is called directly by
tests/auralis/core/test_nan_detection.py, so the public contract is
preserved.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import TYPE_CHECKING

import numpy as np

from ..dsp.basic import normalize
from ..dsp.dynamics.soft_clipper import soft_clip
from ..utils.audio_validation import sanitize_audio, validate_audio_finite
from .mastering_branches import MaterialClassifier
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

    Uses smooth interpolation instead of hard thresholds:
    - Crest factor determines dynamic range preservation needs
    - LUFS determines how much room we have to work with
    """
    # Smooth crest factor curve: 8 dB (compressed) → 15 dB (dynamic)
    # Maps to multiplier range based on material type
    crest_norm = np.clip((crest_db - 8.0) / 7.0, 0.0, 1.0)  # 0=compressed, 1=dynamic

    # LUFS factor: -13 (quiet) → -11 (loud)
    # Quiet material can handle more processing, loud needs preservation
    lufs_norm = np.clip((lufs + 13.0) / 2.0, 0.0, 1.0)  # 0=quiet, 1=loud

    # Intensity multiplier based on 2D space:
    # - Compressed (low crest): always reduce intensity (0.5-0.7)
    # - Dynamic + quiet: boost intensity (up to 1.2)
    # - Dynamic + loud: preserve (reduce to 0.6-0.8)
    if crest_norm < 0.3:
        # Compressed material: gentle processing regardless of loudness
        multiplier = 0.5 + crest_norm * 0.67  # 0.5 → 0.7
    else:
        # Dynamic material: depends on loudness
        # Quiet (lufs_norm=0): multiplier up to 1.2
        # Loud (lufs_norm=1): multiplier down to 0.6
        dynamic_range = 0.7 + (1.0 - crest_norm) * 0.5  # Base for dynamic material
        quiet_boost = (1.0 - lufs_norm) * 0.5  # Extra boost for quiet
        loud_reduction = lufs_norm * 0.4  # Reduction for loud
        multiplier = dynamic_range + quiet_boost - loud_reduction

    return base * np.clip(multiplier, 0.5, 1.2)


def reduce_peaks(
    audio: np.ndarray, current_db: float, target_db: float
) -> tuple[np.ndarray, float]:
    """Surgical peak reduction via soft clipping."""
    if current_db <= target_db:
        return audio, current_db

    threshold = 10 ** (target_db / 20.0)
    processed = soft_clip(audio, threshold=threshold, ceiling=min(0.99, threshold * 1.05))
    return processed, compute_peak_db(processed)


def process_chunk(
    pipeline: 'SimpleMasteringPipeline',
    audio: np.ndarray,
    fp: dict,
    peak_db: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
) -> tuple[np.ndarray, dict]:
    """Core processing logic using all 25D fingerprint dimensions."""

    # Unpack fingerprint using type-safe unpacker
    unpacker = FingerprintUnpacker.from_dict(fp)

    info = {'stages': []}
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

    # STAGE 2: Classify material and dispatch to appropriate processing branch
    material_type = MaterialClassifier.classify(unpacker.lufs, unpacker.crest_db, config)
    branch = MaterialClassifier.get_branch(material_type, pipeline)

    if verbose:
        print(f"   Material type: {material_type}")

    # Branches receive the WHOLE-SONG peak here, not the per-chunk
    # `peak_db` used above for Stage 1's clip prevention. The only
    # consumer is QuietBranch's makeup-gain headroom clamp, and using a
    # per-chunk value there made a quiet verse chunk get its full gain
    # while a loud chorus chunk (same song, same target) got clamped
    # down hard purely because its own peak was high — an audible
    # inconsistency between sections rather than one consistent gain for
    # the whole song. Falls back to the local peak_db when unset (the
    # direct _process() test path, which never runs the pre-scan).
    gain_reference_peak_db = (
        pipeline._song_peak_db if pipeline._song_peak_db is not None else peak_db
    )

    # Delegate to branch-specific processing
    processed, branch_info = branch.apply(
        processed, unpacker, gain_reference_peak_db, effective_intensity,
        sample_rate, config, verbose
    )

    # Merge branch stages into main info
    info['stages'].extend(branch_info.get('stages', []))
    needs_output_normalize = branch_info.get('needs_output_normalize', False)

    # STAGE 3: Unified output normalization for loud material
    # Always normalize to compensate for pre-EQ headroom and RMS expansion
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
