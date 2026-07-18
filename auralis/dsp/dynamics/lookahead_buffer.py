"""
Lookahead Ring Buffer
~~~~~~~~~~~~~~~~~~~~~

Ring-buffer delay line shared by AdaptiveCompressor and AdaptiveLimiter to
implement lookahead: delaying the signal by `lookahead_samples` so the
gain-computer can react to a transient before it reaches the output.

Extracted from two byte-identical ~15-line implementations (#4309) — a #3427
fix (an explicit .copy() before the ring buffer's slice assignment) had only
been ported to one of the two copies, and the underlying duplication left
both at risk of the same kind of drift recurring.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import cast

import numpy as np


class LookaheadBuffer:
    """Delays audio by `lookahead_samples` using a ring buffer, mirror-padded
    from the start of the first chunk so the gain-computer sees valid signal
    context instead of silence at track start (#3291)."""

    def __init__(self, lookahead_samples: int) -> None:
        self.lookahead_samples = lookahead_samples
        self.buffer: np.ndarray | None = None

    def apply(self, audio: np.ndarray) -> np.ndarray:
        """Delay `audio` by `lookahead_samples`, returning an array of the
        same length (a no-op when lookahead_samples == 0)."""
        if self.lookahead_samples == 0:
            return audio

        # Reset buffer if ndim changed (e.g., mono → stereo across tracks)
        if self.buffer is not None and self.buffer.ndim != audio.ndim:
            self.buffer = None

        # Initialize buffer on first use — mirror-pad from the start of the
        # audio so the gain-computer sees valid signal context instead of
        # silence, avoiding a zero-sample artifact at track start (#3291).
        if self.buffer is None:
            if audio.ndim == 1:
                pad = audio[:self.lookahead_samples]
                self.buffer = np.pad(pad, (self.lookahead_samples - len(pad), 0), mode='reflect')
            else:
                pad = audio[:self.lookahead_samples]
                deficit = self.lookahead_samples - len(pad)
                self.buffer = np.pad(pad, ((deficit, 0), (0, 0)), mode='reflect')

        # Buffer is guaranteed to be non-None after initialization
        buffer_size = self.buffer.shape[0]
        audio_len = len(audio)

        if audio_len >= buffer_size:
            # Replace buffer with end of current audio
            delayed_audio = np.concatenate([self.buffer, audio[:-buffer_size]], axis=0)
            self.buffer = audio[-buffer_size:].copy()
        else:
            # Partial buffer update
            delayed_audio = np.concatenate([
                self.buffer[:audio_len],
                audio
            ], axis=0)
            self.buffer = np.roll(self.buffer, -audio_len, axis=0)
            # #3427: explicit .copy() before the slice assignment. numpy slice
            # assignment already copies values, so the ring buffer was never
            # actually aliased to the caller's array — but a defensive .copy()
            # matches the copy-before-modify discipline used by the
            # >= buffer_size branch above and everywhere else in the engine.
            self.buffer[-audio_len:, ...] = audio.copy()

        return cast(np.ndarray, delayed_audio[:audio_len])

    def reset(self) -> None:
        """Zero the buffer contents in place, if allocated."""
        if self.buffer is not None:
            self.buffer.fill(0)
