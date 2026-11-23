"""
Fingerprint single-flight
~~~~~~~~~~~~~~~~~~~~~~~~~

One Tier-3 whole-track extraction per (track, file signature), however many callers ask (#6504).

Every play and seek builds a new ChunkedAudioProcessor, which runs
``MasteringTargetService.load_fingerprint(extract_if_missing=True)``. The service lock covered only
its cache dict and the analysis gate admits jobs by memory budget, not identity, so a seek or the
init-timeout retry during first play started a second decode and analysis of the same file (about
85 MB per minute of audio each). The same ``ChunkSingleFlight`` as chunk renders (#5258), keyed on
the service's cache key: the leader extracts and caches, followers wait and read the cache. A
follower never inherits the leader's failure: it finds no result and extracts itself.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .chunk_single_flight import ChunkSingleFlight

if TYPE_CHECKING:
    from .mastering_target_service import MasteringTargetService

extraction_flights = ChunkSingleFlight()


class _Abandoned(Exception):
    """The caller's should_stop fired while it waited for another caller's extraction."""


def extract_once(
    service: MasteringTargetService,
    cache_key: str,
    filepath: str,
    save_extracted: bool,
    should_stop: Callable[[], bool] | None,
) -> tuple[Any, dict[str, Any] | None] | None:
    """The Tier-3 result for ``cache_key``: extracted here as the leader, or a waited-for leader's."""
    def check_cancelled() -> None:
        if should_stop is not None and should_stop():
            raise _Abandoned

    while True:
        flight = extraction_flights.claim(cache_key)
        if flight.leader:
            break
        try:
            flight.wait_for_leader(check_cancelled)
        except _Abandoned:
            return None
        cached = service.cached(cache_key)
        if cached is not None:
            return cached
        # The leader failed or was abandoned: claim the key and try ourselves.

    try:
        result = service.extract_fingerprint_from_audio(filepath, save_to_file=save_extracted, should_stop=should_stop)
        if result is not None:
            service.store(cache_key, result)
        return result
    finally:
        extraction_flights.release(flight)
