"""
Bounded execution of one track's fingerprint extraction (split out of fingerprint_worker.py,
#6273).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from collections.abc import Callable
from typing import Any

from auralis.services.fingerprint_extractor import FingerprintExtractor

from ..utils.logging import warning


def run_bounded(
    extractor: FingerprintExtractor,
    track_id: int,
    filepath: str,
    worker_id: int,
    *,
    timeout: float,
    should_stop: Callable[[], bool],
) -> bool:
    """Run `extract_and_store` under a wall-clock bound (#4837).

    `extract_and_store` is a synchronous call into DSP analysis (and, below that, native/Rust code).
    An unbounded loop or a native call that never returns used to wedge the calling worker thread,
    and the semaphore slot it holds, for the life of the process, so a handful of pathological files
    could starve fingerprinting permanently. The streaming path bounds its per-chunk DSP for the same
    reason (#3852).

    The work runs on a **daemon** thread joined with a timeout. A hung call cannot be killed
    in-process, so on timeout the thread is abandoned, the worker returns (the caller's `finally`
    releases the semaphore) and the track is recorded as a failure. Daemon rather than a
    `ThreadPoolExecutor`, whose threads the stdlib joins at interpreter exit, so an abandoned task
    there would block shutdown (the hazard documented in
    `auralis-web/backend/analysis/fingerprint_generator.py`).

    Raises:
        TimeoutError: if the call exceeds `timeout`.
        Exception: whatever `extract_and_store` raised, re-raised unchanged.
    """
    outcome: dict[str, Any] = {}

    def _run() -> None:
        try:
            # A worker queued on the analysis gate must still honour stop() (#6338).
            outcome['result'] = extractor.extract_and_store(track_id, filepath, should_stop=should_stop)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the calling thread
            outcome['error'] = exc

    thread = threading.Thread(target=_run, name=f"fingerprint-extract-{track_id}", daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        warning(
            f"Worker {worker_id}: fingerprint extraction for track {track_id} exceeded {timeout}s "
            f"and was abandoned (thread left running); releasing the worker slot: {filepath}"
        )
        raise TimeoutError(f"Fingerprint extraction for track {track_id} timed out after {timeout}s")

    if 'error' in outcome:
        raise outcome['error']

    return bool(outcome.get('result', False))
