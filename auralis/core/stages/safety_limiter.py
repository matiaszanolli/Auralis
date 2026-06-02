"""Safety Limiter Stage — transparent peak limiting after spectral enhancements."""

import numpy as np

from ...dsp.dynamics.soft_clipper import soft_clip


def apply(
    audio: np.ndarray,
    verbose: bool,
    ceiling: float = 0.98,
) -> np.ndarray:
    """Apply transparent safety limiting after spectral enhancements.

    Uses soft clipping for more musical limiting than simple scaling.
    Only affects peaks above the threshold — leaves the rest untouched.

    Args:
        audio: Audio array [channels, samples]
        verbose: Print progress
        ceiling: Maximum output level (default 0.98 = -0.18 dBFS)

    Returns:
        Limited audio array (same shape and dtype as input)
    """
    current_peak = np.max(np.abs(audio))

    if current_peak <= ceiling:
        return audio.copy()  # No limiting needed

    # Use soft clip with threshold slightly below ceiling for smooth knee
    threshold = ceiling * 0.95  # Start limiting ~0.4 dB before ceiling
    processed = soft_clip(audio, threshold=threshold, ceiling=ceiling)

    if verbose:
        reduction_db = 20 * np.log10(ceiling / current_peak)
        print(f"   Safety limiter: {reduction_db:.1f} dB reduction")

    return processed
