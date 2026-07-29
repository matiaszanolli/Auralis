"""Continuous loudness-and-crest stage.

File-level loudness and crest measurements set a continuous pre-gain into a
look-ahead limiter. There are no recording labels, activation thresholds, or
content-dependent bypasses: higher source loudness simply makes the gain
asymptotically approach zero.
"""

from typing import TYPE_CHECKING

import numpy as np

from ...dsp.dynamics.brick_wall_limiter import create_brick_wall_limiter

if TYPE_CHECKING:
    from ..mastering_config import SimpleMasteringConfig


def apply(
    audio: np.ndarray,
    source_lufs: float,
    source_crest_db: float,
    sample_rate: int,
    verbose: bool,
    config: 'SimpleMasteringConfig',
) -> tuple[np.ndarray, dict[str, float | str]]:
    """Apply a continuous loudness response via pre-gain and limiting.

    The push gain is derived from FILE-LEVEL fingerprint values (source LUFS &
    crest), not the per-chunk signal, so every chunk receives the same gain and
    inter-chunk loudness stays consistent. The brick-wall limiter then holds
    peaks at the ceiling per chunk; because RMS rises ~1:1 with the push while
    peaks are held, output loudness ≈ ``source_lufs + push`` and output crest ≈
    ``source_crest - push``.

    Args:
        audio: Audio array [channels, samples].
        source_lufs: File-level integrated loudness (fingerprint).
        source_crest_db: File-level crest factor in dB (fingerprint).
        sample_rate: Audio sample rate in Hz.
        verbose: Print progress.
        config: SimpleMasteringConfig instance.

    Returns:
        Processed audio and continuous stage measurements.
    """
    # Softplus keeps the response positive and monotonic without a point where
    # processing switches on or off. At levels above the anchor it rapidly
    # approaches zero; below the anchor it approaches the measured gap.
    softness = config.LOUDNESS_RESPONSE_SOFTNESS_DB
    loudness_gap = config.LOUDNESS_TARGET_LUFS - source_lufs
    positive_gap = softness * float(
        np.logaddexp(0.0, loudness_gap / softness)
    )
    loudness_push = positive_gap * config.LOUDNESS_GAP_CLOSURE_FACTOR

    # Crest and gain limits are safety bounds, not content classifiers. A
    # second softplus makes available crest reduction continuous even around
    # the minimum-crest safety point. Tanh approaches the resulting cap
    # smoothly instead of clipping the requested gain.
    crest_margin = source_crest_db - config.LOUDNESS_MIN_CREST_DB
    crest_capacity = softness * float(
        np.logaddexp(0.0, crest_margin / softness)
    )
    push_cap = min(
        crest_capacity,
        config.LOUDNESS_MAX_PUSH_DB,
        config.LOUDNESS_MAX_CREST_REDUCTION_DB,
    )
    push_db = push_cap * float(
        np.tanh(loudness_push / max(push_cap, np.finfo(float).eps))
    )

    gained = audio * (10.0 ** (push_db / 20.0))

    # Brick-wall limiter expects (samples, channels); pipeline audio is
    # (channels, samples). Transpose in and back out. A fresh limiter per chunk
    # is fine — the push gain (not the limiter) sets loudness, and the constant
    # push keeps chunks consistent; the limiter only holds peaks.
    limiter = create_brick_wall_limiter(
        threshold_db=config.LOUDNESS_LIMITER_CEILING_DB,
        release_ms=config.LOUDNESS_LIMITER_RELEASE_MS,
        sample_rate=sample_rate,
    )
    limited = limiter.process(gained.T).T.astype(audio.dtype, copy=False)

    if verbose:
        print(
            f"   Loudness maximizer: +{push_db:.1f} dB push → limit "
            f"(source {source_lufs:.1f} LUFS / {source_crest_db:.1f} dB crest)"
        )

    return limited, {
        'stage': 'loudness_maximizer',
        'push_db': push_db,
        'level_gap_db': loudness_gap,
        'push_cap_db': push_cap,
        'source_lufs': source_lufs,
    }
