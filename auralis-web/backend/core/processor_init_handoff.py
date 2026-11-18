"""
Return the processor of an abandoned stream init (#6430).

``ChunkedAudioProcessor.__init__`` takes an exclusive HybridProcessor lease and
runs in a worker thread under ``asyncio.wait_for``. A timeout or cancellation
gives up the *await*, not the thread: it finishes constructing, its result goes
nowhere, and the lease it took is never returned. Each side below writes first
and reads second, so whichever of "construction finished" and "stream gave up"
happens last closes the processor, whatever their interleaving.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from typing import Any


class ProcessorInitHandoff:
    """Builds a processor off-thread and closes it if the stream abandoned the init."""

    def __init__(self, cancel_event: threading.Event) -> None:
        self._cancel_event = cancel_event
        self._built: Any | None = None

    def build(self, processor_class: Any, **kwargs: Any) -> Any:
        """Worker-thread entry: construct, publish, then close if already abandoned."""
        processor = processor_class(cancel_event=self._cancel_event, **kwargs)
        self._built = processor
        if self._cancel_event.is_set():
            processor.close()
        return processor

    def abandon(self) -> None:
        """Event-loop side: cancel the stream and close whatever the thread built.

        Idempotent; ``ChunkedAudioProcessor.close()`` is safe to call twice.
        """
        self._cancel_event.set()
        built = self._built
        if built is not None:
            built.close()
