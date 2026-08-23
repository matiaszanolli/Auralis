"""
Queue Enrichment

The read half of the queue endpoint: turning the engine queue's filepath-only
entries into the canonical TrackInfo shape GET /api/player/queue is typed
against, and resolving the fields the engine cannot express on its own.

Extracted from queue_service.py in #4260. The split follows the real seam in
that file: the engine queue is authoritative for order and contents but stores
impoverished entries, so every read has to reconcile it against the player
state manager and the library. That reconciliation is pure derivation with no
mutation, no locking and no broadcasts, which makes it both the largest
self-contained block in the service and the easiest part to test in isolation.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from player_state import TrackInfo

logger = logging.getLogger(__name__)


def entry_filepath(entry: Any) -> str | None:
    """Extract a filepath from an engine queue entry (dict or TrackInfo)."""
    if isinstance(entry, TrackInfo):
        return entry.filepath
    if isinstance(entry, dict):
        fp = entry.get("filepath") or entry.get("file_path")
        return fp if isinstance(fp, str) else None
    fp = getattr(entry, "filepath", None)
    return fp if isinstance(fp, str) else None


class QueueEnricher:
    """Derives the queue read model from the engine queue plus its collaborators.

    Holds no queue state of its own — every method takes what the engine
    reported and reconciles it against the state manager and library.
    """

    def __init__(
        self,
        player_state_manager: Any,
        library_manager: Any,
        create_track_info_fn: Callable[[Any], Any],
    ) -> None:
        self.player_state_manager: Any = player_state_manager
        self.library_manager: Any = library_manager
        self.create_track_info_fn: Callable[[Any], Any] = create_track_info_fn

    async def enrich_tracks(self, entries: list[Any]) -> list[TrackInfo]:
        """Resolve engine queue entries (filepath dicts) to full TrackInfo.

        Uses the player state manager's TrackInfo queue as an in-memory
        filepath map (it covers the whole queue right after set_queue), and
        falls back to a single batched library lookup for any filepath it does
        not cover (e.g. a track appended via add-track since the last
        set_queue). Entries that resolve to neither are dropped rather than
        emitted as schema-invalid partial dicts (#4374).
        """
        if not entries:
            return []

        # 1) Build filepath -> TrackInfo from the state manager snapshot.
        by_fp: dict[str, TrackInfo] = {}
        if self.player_state_manager is not None:
            try:
                state = self.player_state_manager.get_state()
            except Exception as e:
                logger.debug(f"player_state_manager.get_state() failed; falling back to engine-order-only queue: {e}", exc_info=True)
                state = None
            for ti in getattr(state, "queue", None) or []:
                fp = getattr(ti, "filepath", None)
                if fp:
                    by_fp[fp] = ti

        filepaths = [entry_filepath(e) for e in entries]

        # 2) Resolve filepaths missing from the state map via the library.
        missing = list(dict.fromkeys(fp for fp in filepaths if fp and fp not in by_fp))
        if missing and self.library_manager is not None:
            def _lookup() -> dict[str, TrackInfo]:
                found: dict[str, TrackInfo] = {}
                tracks = self.library_manager.tracks.get_by_paths(missing)
                for fp, track in tracks.items():
                    ti = self.create_track_info_fn(track) if track else None
                    if ti is not None:
                        found[fp] = ti
                return found
            by_fp.update(await asyncio.to_thread(_lookup))

        # 3) Emit resolved TrackInfo in engine order; drop unresolvable ones.
        resolved: list[TrackInfo] = []
        for entry, fp in zip(entries, filepaths):
            if isinstance(entry, TrackInfo):
                resolved.append(entry)
            elif fp is not None and fp in by_fp:
                resolved.append(by_fp[fp])
        return resolved

    def resolve_repeat_mode(self, info: dict[str, Any]) -> str:
        """Resolve the three-valued repeat mode for the queue response (#3896).

        Mirrors the #4374 enrichment split: the engine queue is authoritative
        for order and contents, but it only tracks a boolean `repeat_enabled`
        and cannot distinguish "all" from "one". The three-valued
        `PlayerState.repeat_mode` lives on the state manager, so prefer that and
        fall back to widening the engine bool when no state manager is attached
        (the bool means "repeat the queue", i.e. "all").

        `repeat_enabled` is popped rather than left in place: QueueInfoResponse
        sets `extra='allow'`, so a stale key would otherwise still be emitted
        alongside the new one and the rename would not actually land.
        """
        engine_repeat = bool(info.pop("repeat_enabled", False))

        if self.player_state_manager is not None:
            try:
                state = self.player_state_manager.get_state()
            except Exception as e:
                logger.debug(f"player_state_manager.get_state() failed; falling back to the engine's boolean repeat flag: {e}", exc_info=True)
                state = None
            mode = getattr(state, "repeat_mode", None)
            if mode in ("off", "all", "one"):
                return str(mode)

        return "all" if engine_repeat else "off"

    def resolve_current_track(
        self, tracks: list[TrackInfo], raw_current: Any, current_index: int
    ) -> TrackInfo | None:
        """Pick the current track from the enriched list.

        Matches on the engine's reported current filepath so it stays correct
        even if an unresolvable entry was dropped; falls back to current_index.
        """
        cur_fp = entry_filepath(raw_current) if raw_current is not None else None
        if cur_fp is not None:
            match = next((t for t in tracks if t.filepath == cur_fp), None)
            if match is not None:
                return match
        if 0 <= current_index < len(tracks):
            return tracks[current_index]
        return None
