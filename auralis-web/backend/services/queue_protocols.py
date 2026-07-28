"""
Queue Protocols

Structural types for the audio-player queue surface that QueueService drives.
Pure typing: no behaviour, no imports from the service layer, nothing to
execute. Extracted from queue_service.py in #4260 so the mutation logic is not
read past 60 lines of interface declarations, and so anything else needing to
describe a queue-capable player can depend on the shape without importing the
service.

The engine's real QueueManager (auralis/player/components/queue_manager.py) has
a wider surface than this; only the members QueueService actually calls are
declared, which keeps the Protocol honest about the coupling that exists.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from typing import Any, Protocol


class QueueManager(Protocol):
    """Protocol for queue manager interface."""

    def get_queue(self) -> list[Any]:
        """Get current queue."""
        ...

    def get_queue_size(self) -> int:
        """Get queue size."""
        ...

    def set_queue(self, queue: list[Any], index: int) -> None:
        """Set queue with start index."""
        ...

    def add_to_queue(self, item: Any) -> None:
        """Add item to queue."""
        ...

    def remove_track(self, index: int) -> bool:
        """Remove track at index."""
        ...

    def reorder_tracks(self, new_order: list[int]) -> bool:
        """Reorder tracks."""
        ...

    def shuffle(self) -> None:
        """Shuffle queue."""
        ...

    def clear(self) -> None:
        """Clear queue."""
        ...

    @property
    def current_index(self) -> int:
        """Get current index."""
        ...


class AudioPlayerWithQueue(Protocol):
    """Protocol for audio player with queue support."""

    @property
    def queue(self) -> QueueManager:
        """Get queue manager."""
        ...

    def load_file(self, path: str) -> None:
        """Load audio file."""
        ...

    def play(self) -> None:
        """Start playback."""
        ...

    def stop(self) -> None:
        """Stop playback."""
        ...
