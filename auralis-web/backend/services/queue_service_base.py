"""
Queue Service Base

The collaborators, set-queue sequencing state and ``queue_changed`` broadcast
that every QueueService operation shares. The operations live in mixins that
build on this class; ``services.queue_service.QueueService`` composes them
(#5237).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Unpack

from websocket.outbound_messages import (
    QueueChangeAction,
    QueueChangedExtras,
    QueueChangedPayload,
    TrackPayload,
    broadcast_typed,
)

from .queue_enrichment import QueueEnricher, to_track_payload
from .queue_protocols import AudioPlayerWithQueue

logger = logging.getLogger(__name__)


class QueueServiceBase:
    """State and the queue_changed broadcast shared by all queue operations."""

    def __init__(
        self,
        audio_player: AudioPlayerWithQueue,
        player_state_manager: Any,
        library_database: Any,
        connection_manager: Any,
        create_track_info_fn: Callable[[Any], Any],
    ) -> None:
        """
        Initialize QueueService.

        Args:
            audio_player: AudioPlayer instance with queue support
            player_state_manager: PlayerStateManager instance
            library_database: LibraryDatabase (or any object exposing the
                repository accessors) used to resolve track rows
            connection_manager: WebSocket connection manager for broadcasts
            create_track_info_fn: Function to convert DB track to TrackInfo

        Raises:
            ValueError: If any required component is not available
        """
        self.audio_player: AudioPlayerWithQueue = audio_player
        self.player_state_manager: Any = player_state_manager
        self.library_database: Any = library_database
        self.connection_manager: Any = connection_manager
        self.create_track_info_fn: Callable[[Any], Any] = create_track_info_fn
        # Read-model derivation lives in QueueEnricher (#4260); it needs the
        # same three collaborators and no queue state of its own.
        self._enricher = QueueEnricher(
            player_state_manager, library_database, create_track_info_fn
        )
        # #3721: serialise concurrent set_queue() calls. set_queue runs
        # 7 awaitable steps with WS broadcasts and engine I/O; without
        # a service-level lock two near-simultaneous POSTs (double-click
        # "Play album", rapid playlist switch within RTT) can interleave
        # so the state-manager publishes track-B while the engine ends
        # up loaded+playing track-A. Resolution requires manual user
        # intervention. The lock only serialises set_queue; the other
        # mutating methods (add/remove/clear/reorder) each take their
        # own narrow snapshot under the existing audio_player.queue
        # _lock and are not in the same race class.
        self._set_queue_lock = asyncio.Lock()
        self._next_set_queue_generation = 0
        self._set_queue_generation = 0
        # Player calls still need ordered execution to preserve the original
        # #3721 engine consistency guarantee, but this lock never covers a WS
        # broadcast and does not block queue-state mutation (#4825).
        self._set_queue_engine_lock = asyncio.Lock()

    async def _broadcast_queue_changed(
        self,
        action: QueueChangeAction,
        **extras: Unpack[QueueChangedExtras],
    ) -> None:
        """Emit a `queue_changed` WS message with the canonical payload that
        the frontend's QueueChangedMessage type expects (fixes #3492).

        Hydrates the engine queue through the same QueueEnricher the REST read
        path uses (#5455). The old bespoke hydration keyed on an `id` that
        queues built by POST /api/player/queue never carry (the engine stores
        bare filepaths), so after any edit it fell back to broadcasting the raw
        engine entries: absolute filepaths (#3205) and id/title-less rows that
        blanked the Redux queue. Unresolvable entries are now dropped and
        `current_index` is re-based past them; if hydration fails outright the
        payload omits `tracks`, so clients keep their last good queue.
        """
        try:
            if hasattr(self.audio_player, 'queue'):
                queue_obj = self.audio_player.queue
                if hasattr(queue_obj, 'get_queue_info'):
                    info = await asyncio.to_thread(queue_obj.get_queue_info)
                    raw_tracks = info.get('tracks', [])
                    current_index = info.get('current_index', -1)
                else:
                    raw_tracks = list(getattr(queue_obj, 'queue', []))
                    current_index = getattr(queue_obj, 'current_index', -1)
            else:
                raw_tracks = []
                current_index = -1
        except Exception as exc:
            logger.warning(f"queue_changed broadcast: failed to read queue: {exc}")
            raw_tracks = []
            current_index = -1

        tracks: list[TrackPayload] = []
        hydrated = False
        try:
            resolved = await self._enricher.resolve_tracks(list(raw_tracks))
        except Exception as exc:
            logger.warning(
                f"queue_changed broadcast: hydration failed, omitting tracks: {exc}"
            )
        else:
            hydrated = True
            tracks = [to_track_payload(ti) for ti in resolved if ti is not None]
            if len(tracks) != len(resolved):
                logger.warning(
                    f"queue_changed broadcast: dropped {len(resolved) - len(tracks)} "
                    f"queue entr(y/ies) that resolve to no library track"
                )
                if 0 <= current_index < len(resolved):
                    current_index = (
                        sum(1 for ti in resolved[:current_index] if ti is not None)
                        if resolved[current_index] is not None
                        else -1
                    )

        payload: QueueChangedPayload = {
            'tracks': tracks,
            'current_index': current_index,
            'action': action,
            **extras,
        }
        if not hydrated:
            # Omit rather than send an empty queue, which a client would apply.
            del payload['tracks']
        await broadcast_typed(self.connection_manager, "queue_changed", payload)
