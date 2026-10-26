"""Process-wide ordering for discrete playback WebSocket events.

FastAPI creates a fresh :class:`PlaybackService` for each request, while the
WebSocket-native pause/resume/stop handlers bypass that service entirely.  A
sequencer owned by either path therefore cannot order the other one.  This
module-level singleton is the shared ordering boundary for both paths (#5294).
"""

import asyncio

from .loop_bound_lock import LoopBoundLock


class PlaybackEventSequencer:
    """Serialize transport mutations and stamp discrete event domains."""

    def __init__(self) -> None:
        self._transition_lock = LoopBoundLock()
        self._transport_seq = 0
        self._volume_seq = 0

    @property
    def transition_lock(self) -> asyncio.Lock:
        """Return the process-wide lock bound to the current event loop."""
        return self._transition_lock.get()

    def next_transport_seq(self) -> int:
        """Return the next play/pause/resume/stop sequence number."""
        self._transport_seq += 1
        return self._transport_seq

    def next_volume_seq(self) -> int:
        """Return the next volume-change sequence number."""
        self._volume_seq += 1
        return self._volume_seq


playback_event_sequencer = PlaybackEventSequencer()
