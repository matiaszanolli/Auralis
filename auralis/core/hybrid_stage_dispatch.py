"""
Hybrid Processor Stage Dispatch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Input validation and the reference-mode processing path, split out of
hybrid_processor.py (#5463). The adaptive/hybrid mode bodies live in
processing/mode_dispatch.py (#6272), not here.

Each function takes the owning `HybridProcessor` as its first argument and
reads its collaborators (`processor.brick_wall_limiter`, etc.) directly —
same pattern as job_execution.py's `prepare_job()` / `execute_job()` for
ProcessingEngine (#4250).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import TYPE_CHECKING

import numpy as np

from ..utils.audio_validation import validate_audio_finite
from ..utils.logging import debug, info, warning
from .processors import apply_reference_matching

if TYPE_CHECKING:
    from .hybrid_processor import HybridProcessor

#: Audio shorter than one analysis window (1024 samples, ~23ms at 44.1kHz) is
#: returned unprocessed rather than rejected (#4520). See
#: validate_and_normalize_input()'s docstring for the full rationale.
MIN_SAMPLES = 1024


def validate_and_normalize_input(
    processor: "HybridProcessor", target: np.ndarray
) -> tuple[np.ndarray, np.ndarray | None]:
    """Validate/normalize `target` for `HybridProcessor._process_impl()`.

    Returns `(target_audio, early_result)`. When `early_result` is not
    `None`, the caller must return it immediately without further
    processing — mirrors the early-return branches (empty, too-short,
    silent) the inline `_process_impl` body used to have.

    Mono-to-stereo conversion runs BEFORE the empty-audio check (#4976).
    With the order reversed, an empty mono buffer returned 1-D `(0,)` while
    every other path — including these same early returns — returned 2-D
    `(N, 2)`. A caller that indexes `result[:, 0]`, reasonable given the
    shape this processor otherwise always guarantees, hit an IndexError only
    on the empty-mono path.

    The too-short guard used to `raise ValueError`, which broke the
    pipeline's core invariant — `len(output) == len(input)`, load-bearing
    for gapless playback — for any short buffer. Returning it untouched is
    what the empty-audio and silence branches already do, and no meaningful
    mastering decision can be made from 23ms anyway: the fingerprint stage
    alone needs 11025 samples. The Rust FFT paths short-circuit below one
    FFT frame (verified for n=0..2048), so there is no panic to guard
    against and this returns the input untouched.
    """
    target_audio = target

    if not isinstance(target_audio, np.ndarray):
        raise ValueError(f"Target audio must be a NumPy array, got {type(target_audio)}")

    if not np.issubdtype(target_audio.dtype, np.floating):
        raise ValueError(f"Audio must be a float array in [-1, 1], got dtype {target_audio.dtype} (#6118)")
    if target_audio.ndim not in (1, 2):
        raise ValueError(f"Audio must be (samples,) or (samples, channels), got shape {target_audio.shape}")
    # A librosa-style (channels, samples) array has shape[0] == 2, so it used to look "too short" and
    # come back unprocessed with a warning about milliseconds: refuse it by name instead (#6118).
    if target_audio.ndim == 2 and target_audio.shape[0] <= 2 and target_audio.shape[1] >= MIN_SAMPLES:
        raise ValueError(
            f"Audio looks channels-first {target_audio.shape}; expected (samples, channels). "
            "Transpose it (audio.T)."
        )
    if target_audio.ndim == 1:
        target_audio = np.column_stack([target_audio, target_audio])
        debug(f"Converted mono audio to stereo: shape now {target_audio.shape}")

    # Handle empty audio. Post-conversion this returns (0, 2) for mono and
    # stereo alike.
    if len(target_audio) == 0:
        return target_audio, target_audio.copy()

    # Fail fast on NaN/Inf before the short and silence early returns: they hand the buffer back
    # untouched, which would pass corrupted samples through as if they were audio (#5191).
    target_audio = validate_audio_finite(target_audio, context="input audio", repair=False)

    if target_audio.shape[0] < MIN_SAMPLES:
        warning(
            f"Audio too short to master ({target_audio.shape[0]} samples, "
            f"~{target_audio.shape[0] / processor.config.internal_sample_rate * 1000:.1f}ms "
            f"at {processor.config.internal_sample_rate / 1000:.1f}kHz); "
            f"returning it unprocessed (need {MIN_SAMPLES} samples)"
        )
        return target_audio, target_audio.copy()

    # Handle silence (all zeros) - return as-is to avoid NaN production in downstream processing
    if np.allclose(target_audio, 0.0, atol=1e-10):
        return target_audio, target_audio.copy()

    return target_audio, None


def process_reference_mode(
    processor: "HybridProcessor",
    target_audio: np.ndarray,
    reference: np.ndarray,
) -> np.ndarray:
    """Process using traditional reference-based matching."""
    info("Processing in reference mode")

    # Reference is a pre-loaded NumPy array (#4035).
    reference_audio = reference

    # Delegate to reference matching
    processed = apply_reference_matching(target_audio, reference_audio)

    # Apply brick-wall limiter for final peak control (same as adaptive/hybrid)
    processed = processor.brick_wall_limiter.process(processed)
    # raise, not assert — asserts vanish under python -O (#5533, cf. #5511).
    if processed.shape != target_audio.shape:
        raise RuntimeError(
            f"Sample count mismatch after limiter (reference): "
            f"expected {target_audio.shape}, got {processed.shape}"
        )

    # Fail fast on NaN/Inf in mastering output — surface DSP bugs rather than
    # silently masking them with zero-replacement (fixes #2520).
    processed = validate_audio_finite(processed, context="reference mode output", repair=False)

    return processed
