#!/usr/bin/env python3

"""
Chunk crossfade math
~~~~~~~~~~~~~~~~~~~~~

Equal-power (sin²/cos²) overlap-add crossfade between adjacent processed audio
chunks. Extracted from chunked_processor.py (#4245) as a standalone, stateless
function; re-exported from chunked_processor so existing
`from core.chunked_processor import apply_crossfade_between_chunks` imports keep
working.

NOTE (#4245 CONSISTENCY / #4071): audio_stream_controller.py performs its own
boundary handling for the live stream path; if that god-file is later split, its
crossfade helper and this one should be reconciled against a single source of
truth rather than duplicated.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np


def apply_crossfade_between_chunks(chunk1: np.ndarray, chunk2: np.ndarray, overlap_samples: int) -> np.ndarray:
    """
    Apply crossfade between two audio chunks and return concatenated result.

    Uses overlap-add: the last N samples of chunk1 are mixed with the first N samples
    of chunk2, then we keep all of chunk1 + the non-overlapping part of chunk2.
    This preserves total duration without losing audio.

    Args:
        chunk1: First audio chunk
        chunk2: Second audio chunk
        overlap_samples: Number of samples to crossfade

    Returns:
        Concatenated audio with crossfade applied at boundary (no audio lost)
    """
    # Ensure we don't try to overlap more than available
    actual_overlap = min(overlap_samples, len(chunk1), len(chunk2))

    if actual_overlap <= 0:
        # No overlap possible, just concatenate
        result: np.ndarray = np.concatenate([chunk1, chunk2], axis=0)
        return result

    # Get overlap regions
    chunk1_tail = chunk1[-actual_overlap:]
    chunk2_head = chunk2[:actual_overlap]

    # Create equal-power fade curves (sin²/cos²) to avoid energy dip at midpoint (fixes #2080)
    t = np.linspace(0.0, np.pi / 2, actual_overlap)
    fade_out = np.cos(t) ** 2
    fade_in = np.sin(t) ** 2

    # Handle stereo
    if chunk1_tail.ndim == 2:
        fade_out = fade_out[:, np.newaxis]
        fade_in = fade_in[:, np.newaxis]

    # Apply fades and mix the overlap region
    crossfade = chunk1_tail * fade_out + chunk2_head * fade_in

    # IMPORTANT: Don't lose audio!
    # Result = full chunk1 (except last overlap) + crossfaded overlap + rest of chunk2
    result = np.concatenate([
        chunk1[:-actual_overlap],  # Chunk1 without the tail that will be mixed
        crossfade,                  # The mixed overlap region
        chunk2[actual_overlap:]     # Chunk2 without the head that was mixed
    ], axis=0)

    return result
