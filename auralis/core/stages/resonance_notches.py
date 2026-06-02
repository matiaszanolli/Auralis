"""Resonance Notch Stage — apply pre-detected narrow band cuts."""

import numpy as np

from ..dsp import Notch, ResonanceNotcher


def apply(
    audio: np.ndarray,
    sample_rate: int,
    notches: list[Notch],
    verbose: bool,
) -> tuple[np.ndarray, dict | None]:
    """Apply pre-detected narrow notches to tame room modes and recording resonances.

    Notches are detected once per file by the pipeline and applied to every
    chunk. Returns audio unchanged if no notches were detected.

    Args:
        audio: Audio array [channels, samples]
        sample_rate: Audio sample rate in Hz
        notches: List of Notch objects detected by ResonanceNotcher.detect()
        verbose: Print progress

    Returns:
        (processed_audio, stage_info) or (audio, None) if no notches
    """
    if not notches:
        return audio.copy(), None

    processed = ResonanceNotcher.apply(audio, sample_rate, notches)
    if verbose:
        freqs = ", ".join(f"{n.freq_hz:.0f}Hz" for n in notches)
        print(f"   Resonance notches: {len(notches)} cuts @ {freqs}")
    return processed, {
        'stage': 'resonance_notches',
        'count': len(notches),
        'notches': [(n.freq_hz, n.depth_db) for n in notches],
    }
