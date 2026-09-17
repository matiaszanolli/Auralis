"""
Hybrid Processor Stage Dispatch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Input validation and the reference-mode processing path, split out of
hybrid_processor.py (#5463). `_process_adaptive_mode()` / `_process_hybrid_mode()`
stay inline in hybrid_processor.py rather than moving here:
tests/regression/test_sample_count_invariant.py asserts on
`inspect.getsource(HybridProcessor._process_adaptive_mode)` /
`._process_hybrid_mode` directly, so the sample-count assertion has to remain
in the source of those bound methods themselves, not a helper they call.

Each function takes the owning `HybridProcessor` as its first argument and
reads its collaborators (`processor.brick_wall_limiter`, etc.) directly —
same pattern as job_execution.py's `prepare_job()` / `execute_job()` for
ProcessingEngine (#4250).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import TYPE_CHECKING, Any

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
    alone needs 11025 samples. The raise was originally defensive against
    Rust FFT panics on tiny audio; those are fixed at the source
    (vendor/auralis-dsp hpss.rs short-circuits below one FFT frame, verified
    for n=0..2048), so this guard now only blocks work the DSP layer handles
    correctly.
    """
    target_audio = target

    if not isinstance(target_audio, np.ndarray):
        raise ValueError(f"Target audio must be a NumPy array, got {type(target_audio)}")

    if target_audio.ndim == 1:
        target_audio = np.column_stack([target_audio, target_audio])
        debug(f"Converted mono audio to stereo: shape now {target_audio.shape}")

    # Handle empty audio. Post-conversion this returns (0, 2) for mono and
    # stereo alike.
    if len(target_audio) == 0:
        return target_audio, target_audio.copy()

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

    # Validate input audio for NaN/Inf (fail fast on corrupted input)
    target_audio = validate_audio_finite(target_audio, context="input audio", repair=False)
    debug("Input audio validated: no NaN/Inf detected")

    return target_audio, None


def process_reference_mode(
    processor: "HybridProcessor",
    target_audio: np.ndarray,
    reference: np.ndarray,
    results: Any,
) -> np.ndarray:
    """Process using traditional reference-based matching."""
    info("Processing in reference mode")

    # Reference is a pre-loaded NumPy array (#4035).
    reference_audio = reference

    # Delegate to reference matching
    processed = apply_reference_matching(target_audio, reference_audio)

    # Apply brick-wall limiter for final peak control (same as adaptive/hybrid)
    processed = processor.brick_wall_limiter.process(processed)
    assert processed.shape == target_audio.shape, (
        f"Sample count mismatch after limiter (reference): "
        f"expected {target_audio.shape}, got {processed.shape}"
    )

    # Fail fast on NaN/Inf in mastering output — surface DSP bugs rather than
    # silently masking them with zero-replacement (fixes #2520).
    processed = validate_audio_finite(processed, context="reference mode output", repair=False)

    return processed
