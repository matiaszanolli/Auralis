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
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, Unpack

from websocket.outbound.player import TrackPayload
from websocket.outbound.queue import (
    QueueChangeAction,
    QueueChangedExtras,
    QueueChangedPayload,
)
from websocket.outbound_messages import broadcast_typed

from .errors import ServiceUnavailable
from .queue_enrichment import QueueEnricher, rebase_index, to_track_payload
from .queue_protocols import AudioPlayerWithQueue
from .queue_set_sequencer import queue_set_sequencer

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

    # #3721: concurrent set_queue() calls are serialised, and a later one (or a
    # queue-shape mutator, #5320) supersedes an in-flight one, through a
    # process-wide sequencer. FastAPI builds a fresh QueueService per request, so
    # a lock or counter on `self` would never contend across requests (#5944).
    # These names stay as the service's own view of that shared state.
    @property
    def _set_queue_lock(self) -> asyncio.Lock:
        """Generation bookkeeping and the sequenced state mutation (#4825)."""
        return queue_set_sequencer.state_lock

    @property
    def _set_queue_engine_lock(self) -> asyncio.Lock:
        """Ordered player calls; never covers a WS broadcast (#4825)."""
        return queue_set_sequencer.engine_lock

    @property
    def _next_set_queue_generation(self) -> int:
        return queue_set_sequencer.next_generation

    @_next_set_queue_generation.setter
    def _next_set_queue_generation(self, value: int) -> None:
        queue_set_sequencer.next_generation = value

    @property
    def _set_queue_generation(self) -> int:
        return queue_set_sequencer.generation

    @_set_queue_generation.setter
    def _set_queue_generation(self, value: int) -> None:
        queue_set_sequencer.generation = value

    async def _invalidate_set_queue_generation(self) -> None:
        """Supersede any in-flight set_queue request (#5320).

        clear_queue and the other queue-shape mutators (add/remove/reorder/
        move/shuffle/unshuffle) bypassed set_queue's generation protocol
        entirely — a mutator landing while _set_queue_impl was between its
        generation check and its engine-mutating steps still ran
        load_file()/play() afterward against a queue the mutator had just
        changed out from under it.

        Bumping _next_set_queue_generation AND setting _set_queue_generation
        to that new value (rather than just incrementing the latter) means
        no future set_queue() call can accidentally reuse a generation
        number this invalidation already claimed. Every one of
        _set_queue_impl's `generation != self._set_queue_generation` /
        `generation < self._set_queue_generation` checkpoints then correctly
        sees itself as superseded and returns before its next engine call —
        including a checkpoint reached while _set_queue_impl is still
        inside `_set_queue_engine_lock`, since this only takes the narrower
        `_set_queue_lock` and does not contend with it.

        Callers should call this before touching the engine (or before
        acquiring `_set_queue_engine_lock`, whichever comes first in their
        method), so an in-flight set_queue sees the staleness at its very
        next checkpoint rather than one call later.
        """
        async with self._set_queue_lock:
            self._next_set_queue_generation += 1
            self._set_queue_generation = self._next_set_queue_generation

    def _require_queue(self) -> None:
        """Raise ServiceUnavailable unless the audio player exposes a queue."""
        if not self.audio_player or not hasattr(self.audio_player, 'queue'):
            raise ServiceUnavailable("Queue manager not available")

    @asynccontextmanager
    async def _queue_mutation(self) -> AsyncIterator[None]:
        """Scope for one engine-queue mutation (#5320).

        Supersedes any in-flight set_queue request before the engine is
        touched, then serialises the mutation itself against set_queue's own
        engine section. Every queue-shape mutator (add/remove/clear/reorder/
        move/shuffle/unshuffle) runs its engine calls inside this, so a new one
        gets the protocol by using it rather than by remembering to copy it.

        The engine lock never covers a broadcast (#4825): do state-manager
        updates and ``_broadcast_queue_changed`` after leaving the block.
        Invalidating even on a "nothing to do" path is harmless (a no-op
        generation bump).
        """
        await self._invalidate_set_queue_generation()
        async with self._set_queue_engine_lock:
            yield

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

        The read, hydration and send run under one process-wide lock (#5935):
        each frame then describes the engine queue as of its own read, and a
        later edit's frame cannot be overtaken by an earlier edit's slower
        hydration. The edit itself stays outside the lock (#4825).
        """
        async with queue_set_sequencer.broadcast_lock:
            engine_shuffled = await self._broadcast_queue_changed_locked(action, **extras)
        await self._follow_engine_shuffle_off(engine_shuffled)

    async def _record_shuffle_state(self, enabled: bool) -> None:
        """Mirror the engine's shuffle flag into PlayerState.

        Nothing wrote ``shuffle_enabled`` there, so every ``player_state`` snapshot carried
        False and the next one (a repeat toggle, a reconnect push) switched the UI's shuffle
        off while the queue stayed shuffled (#5899). Best-effort: a failed state update must
        not fail the shuffle that already happened.
        """
        if self.player_state_manager is None:
            return
        try:
            await self.player_state_manager.update_state(shuffle_enabled=enabled)
        except Exception as e:
            logger.warning(f"Could not record shuffle state in PlayerState: {e}")

    async def _follow_engine_shuffle_off(self, engine_shuffled: bool) -> None:
        """Follow an engine whose shuffle flag a queue replacement reset (#6592).

        ``QueueManager.clear()`` (set_queue, clear_queue, load_playlist) turns shuffle off (#5728),
        but only the shuffle endpoints wrote ``PlayerState.shuffle_enabled`` and told clients, so
        the UI kept showing shuffle on over an ordered queue. Only that on-to-off transition is
        handled here; the shuffle endpoints record their own changes. Never under the engine lock.
        """
        psm = self.player_state_manager
        if engine_shuffled or psm is None or getattr(psm.get_state(), 'shuffle_enabled', None) is not True:
            return
        await broadcast_typed(self.connection_manager, "queue_shuffled", {"is_shuffled": False})
        await self._record_shuffle_state(False)

    async def _broadcast_queue_changed_locked(
        self,
        action: QueueChangeAction,
        **extras: Unpack[QueueChangedExtras],
    ) -> bool:
        """Read, hydrate, mirror and send; returns the engine's shuffle flag (True when unknown)."""
        engine_shuffled = True
        try:
            if hasattr(self.audio_player, 'queue'):
                queue_obj = self.audio_player.queue
                if hasattr(queue_obj, 'get_queue_info'):
                    info = await asyncio.to_thread(queue_obj.get_queue_info)
                    engine_shuffled = bool(info.get('shuffle_enabled', True))
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
        resolved: list[Any] = []
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
                current_index = rebase_index(resolved, current_index)

        # #5460: every queue edit ends here, and the state manager's copy of the
        # queue must follow it. Only set_queue used to update it, so the next
        # unrelated player_state (volume, pause, navigation) carried the pre-edit
        # queue and the frontend applied it, undoing the edit on screen. Its
        # current track follows the engine's (the successor after removing the
        # playing track, none after a clear). Not broadcast: queue_changed below
        # is this edit's message. Best-effort like the read and hydration above:
        # the engine edit already happened, and its broadcast must still go out.
        if hydrated and self.player_state_manager is not None:
            try:
                await self.player_state_manager.set_queue(
                    [ti for ti in resolved if ti is not None], current_index, broadcast=False
                )
            except Exception as exc:
                logger.warning(f"queue_changed: could not mirror the queue into player state: {exc}")

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
        return engine_shuffled
