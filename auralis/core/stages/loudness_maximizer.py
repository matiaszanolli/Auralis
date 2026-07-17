"""Loudness Maximizer Stage — competitive loudness for under-mastered material.

Genuinely quiet, high-dynamic-range sources (vintage / lo-fi / raw rock
recordings such as Patricio Rey's *Oktubre*, ~-22 LUFS at ~18 dB crest) used to
pass through the QuietBranch almost untreated on the loudness axis: the makeup
gain was capped then zeroed for high-crest material, and the final peak-normalize
mathematically pins loudness to ``peak - crest``. The fix is to REDUCE the crest
factor — the only lever that moves loudness once peaks sit at the ceiling — via a
transparent pre-gain into a look-ahead brick-wall limiter.

Discrimination is by absolute loudness, NOT crest: crest alone cannot tell a
finished dynamic master (already loud) from a raw under-mastered one (quiet).
Material at/above ``LOUDNESS_COMPETITIVE_LUFS`` is a strict no-op, so the
well-mastered 'good' tier is byte-identical to before.
"""

from typing import TYPE_CHECKING

import numpy as np

from . import no_op

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
) -> tuple[np.ndarray, dict | None]:
    """Restore competitive loudness to under-mastered material via push + limit.

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
        config: SimpleMasteringConfig instance for thresholds.

    Returns:
        (processed_audio, stage_info) or (audio.copy(), None) if the stage did
        not fire (already-competitive source, or push below the audible floor).
    """
    # Under-mastered ramp: 0.0 at/above COMPETITIVE_LUFS, 1.0 at
    # (COMPETITIVE - RANGE). Keys on absolute loudness — the only signal that
    # separates "quiet & needs work" from "dynamic & already competitive".
    undermastered = float(np.clip(
        (config.LOUDNESS_COMPETITIVE_LUFS - source_lufs)
        / config.LOUDNESS_UNDERMASTER_RANGE_DB,
        0.0,
        1.0,
    ))
    if undermastered <= 0.0:
        return no_op(audio)

    # Push toward the loudness target, scaled by how under-mastered the source
    # is so borderline-quiet dynamic tracks get only a gentle lift. Also scaled
    # by LOUDNESS_GAP_CLOSURE_FACTOR (< 1.0) so the maximizer only closes part
    # of the gap to the target instead of converging every quiet source to the
    # same anchor — preserves the natural loudness spread between recordings
    # (e.g. a genuinely quiet vintage record should end up noticeably quieter
    # than a moderately quiet one, not the same).
    loudness_push = (
        (config.LOUDNESS_TARGET_LUFS - source_lufs)
        * undermastered
        * config.LOUDNESS_GAP_CLOSURE_FACTOR
    )

    # Crest-floor clamp: never push so hard that output crest drops below the
    # dynamic floor. output_crest ≈ source_crest - push, so cap the push at
    # (source_crest - MIN_CREST). Guarantees the result stays clearly dynamic.
    crest_headroom = source_crest_db - config.LOUDNESS_MIN_CREST_DB
    # Transient-preservation cap: the push IS crest reduction, so bound it to a
    # musical amount ('preserve punch') even when the source is very quiet —
    # trading a little loudness to keep the kick/snare dynamics intact.
    push_db = float(np.clip(
        loudness_push,
        0.0,
        min(crest_headroom, config.LOUDNESS_MAX_PUSH_DB,
            config.LOUDNESS_MAX_CREST_REDUCTION_DB),
    ))

    # Below ~0.5 dB the push is inaudible and not worth the limiter pass.
    if push_db < 0.5:
        return no_op(audio)

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
            f"(source {source_lufs:.1f} LUFS / {source_crest_db:.1f} dB crest, "
            f"undermastered {undermastered:.2f})"
        )

    return limited, {
        'stage': 'loudness_maximizer',
        'push_db': push_db,
        'undermastered': undermastered,
        'source_lufs': source_lufs,
    }
