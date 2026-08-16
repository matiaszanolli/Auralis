"""
Fingerprint Worker Execution Internals
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Per-worker execution mechanics for ``FingerprintExtractionQueue`` (#5039): the
per-track timeout default, the bounded ``extract_and_store`` call, the
single-track processing step, progress reporting, and the drain-wave
bookkeeping the worker loop drives.

Split out of ``fingerprint_queue.py``, which keeps the pool facade
(construction, ``start``/``stop``, the DB-claim worker loop). This is a **pure
move**: no signature, default, log message or exception type changed.

Delivered as a mixin rather than as free functions on purpose. Tests read
``inspect.getsource(FingerprintExtractionQueue._process_track)`` and assert on
the real body (#4636), so the class attribute has to stay bound to the actual
implementation rather than to a delegating stub.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import threading
import time
from typing import Any
from collections.abc import Callable

from auralis.services.fingerprint_extractor import FingerprintExtractor
from auralis.services.resizable_semaphore import ResizableSemaphore

from ..utils.logging import debug, error, info, warning


DEFAULT_TRACK_TIMEOUT_SECONDS: float = 600.0


DEFAULT_TRACK_TIMEOUT_SECONDS: float = 600.0


def _default_track_timeout() -> float:
    """Per-track wall-clock bound for `extract_and_store` (#4837).

    Analysis of a normal file takes on the order of a minute (see
    `FingerprintExtractor.extract_and_store`), so the default is deliberately
    far above that — this is a wedged-worker backstop, not a performance knob.
    Override with `AURALIS_FINGERPRINT_TRACK_TIMEOUT` (seconds); a malformed or
    non-positive value falls back to the default rather than disabling the
    bound, since an unbounded call is exactly the failure mode being fixed.
    """
    raw = os.environ.get('AURALIS_FINGERPRINT_TRACK_TIMEOUT')
    if raw is None:
        return DEFAULT_TRACK_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        warning(
            f"AURALIS_FINGERPRINT_TRACK_TIMEOUT={raw!r} is not a number; "
            f"using {DEFAULT_TRACK_TIMEOUT_SECONDS}s"
        )
        return DEFAULT_TRACK_TIMEOUT_SECONDS
    if value <= 0:
        warning(
            f"AURALIS_FINGERPRINT_TRACK_TIMEOUT={value} must be positive; "
            f"using {DEFAULT_TRACK_TIMEOUT_SECONDS}s"
        )
        return DEFAULT_TRACK_TIMEOUT_SECONDS
    return value


class FingerprintWorkerExecution:
    """Per-worker execution internals mixed into ``FingerprintExtractionQueue``.

    The state below is owned and initialised by the composing class; it is
    declared here (annotation only, never assigned) so the moved methods keep
    type-checking against it.
    """

    extractor: FingerprintExtractor
    track_timeout: float
    processing_semaphore: ResizableSemaphore
    workers: list[threading.Thread]
    initial_num_workers: int
    stats: dict[str, Any]
    stats_lock: threading.RLock
    progress_callback: Callable[[dict[str, Any]], None] | None
    on_drained: Callable[[], None] | None
    _drain_state_lock: threading.Lock
    _processed_since_drain: int
    _drained_workers: int

    def set_drained_callback(self, callback: Callable[[], None]) -> None:
        """#3479: callback fired once per drain wave (no more tracks to
        claim after at least one was processed). Used to trigger
        reference-cloud refresh when fresh fingerprints land."""
        self.on_drained = callback

    def _on_track_processed(self) -> None:
        """#3479: record that a track was processed in the current wave so a
        subsequent drain transition actually fires the callback."""
        with self._drain_state_lock:
            self._processed_since_drain += 1

    def _on_worker_drained(self) -> None:
        """#3479: a worker found no more tracks to claim. Fire on_drained
        exactly once when all workers have drained AND at least one track
        was processed in this wave."""
        fire = False
        # Threshold on the REAL thread count, not `current_num_workers` (#4596).
        # `start()` spawns exactly `initial_num_workers` threads and nothing ever
        # appends to `self.workers` afterwards, but AdaptiveResourceMonitor keeps
        # ratcheting `current_num_workers` upward as pure bookkeeping. Since
        # `_drained_workers` can only be incremented by threads that actually
        # exist, once the recommendation exceeded the real count the condition
        # became permanently unsatisfiable and on_drained stopped firing forever.
        real_workers = len(self.workers) or self.initial_num_workers
        with self._drain_state_lock:
            self._drained_workers += 1
            if (
                self._drained_workers >= max(1, real_workers)
                and self._processed_since_drain > 0
            ):
                fire = True
                self._processed_since_drain = 0
                self._drained_workers = 0
        if fire and self.on_drained is not None:
            try:
                self.on_drained()
            except Exception as cb_exc:  # noqa: BLE001
                error(f"on_drained callback raised: {cb_exc}")

    def _extract_bounded(self, track_id: int, filepath: str, worker_id: int) -> bool:
        """Run `extract_and_store` under a wall-clock bound (#4837).

        `extract_and_store` is a synchronous call into DSP analysis (and, below
        that, native/Rust code). An unbounded loop or a native call that never
        returns used to wedge the calling worker thread — and the semaphore slot
        it holds — for the lifetime of the process, so a handful of pathological
        files could starve fingerprinting permanently. The streaming path bounds
        its per-chunk DSP for exactly this reason (#3852).

        The work runs on a **daemon** thread that this method joins with a
        timeout. A hung call cannot be killed in-process, so on timeout the
        thread is abandoned rather than terminated — but the worker returns, the
        semaphore is released by `_process_track`'s `finally`, and the track is
        recorded as a failure. Daemon (rather than a `ThreadPoolExecutor`)
        because the stdlib's executor joins its threads at interpreter exit
        regardless of `cancel_futures`, so an abandoned task there would block
        process shutdown — the same hazard documented in
        `auralis-web/backend/analysis/fingerprint_generator.py`.

        Raises:
            TimeoutError: if the call exceeds `self.track_timeout`.
            Exception: whatever `extract_and_store` raised, re-raised unchanged
                so the caller's existing error handling is unaffected.
        """
        outcome: dict[str, Any] = {}

        def _run() -> None:
            try:
                outcome['result'] = self.extractor.extract_and_store(track_id, filepath)
            except BaseException as exc:  # noqa: BLE001 - re-raised on the calling thread
                outcome['error'] = exc

        thread = threading.Thread(
            target=_run,
            name=f"fingerprint-extract-{track_id}",
            daemon=True,
        )
        thread.start()
        thread.join(self.track_timeout)

        if thread.is_alive():
            warning(
                f"Worker {worker_id}: fingerprint extraction for track {track_id} "
                f"exceeded {self.track_timeout}s and was abandoned (thread left "
                f"running); releasing the worker slot: {filepath}"
            )
            raise TimeoutError(
                f"Fingerprint extraction for track {track_id} timed out after "
                f"{self.track_timeout}s"
            )

        if 'error' in outcome:
            raise outcome['error']

        return bool(outcome.get('result', False))

    def _process_track(self, track: Any, worker_id: int) -> None:
        """
        Process a single track: extract and store fingerprint.

        Acquires memory-aware semaphore to limit concurrent audio processing.
        This prevents memory bloat when loading large audio files.

        Args:
            track: Track object with id and filepath attributes
            worker_id: ID of the worker processing this track
        """
        # Acquire semaphore to limit concurrent audio processing.
        #
        # The limit is deliberately generous — at least 8, up to max_workers (see
        # the construction site) — and resizable at runtime by the adaptive
        # resource monitor (#4404). It is NOT the old "only 3 concurrent, to cap
        # memory at ~1.2GB" design; that comment survived the change and said the
        # opposite of the constructor's own two lines above it (#4636).
        #
        # Report in_use/capacity as one snapshot from the semaphore itself. No
        # literal can be right here, and pairing stats['processing'] with the
        # live capacity would be wrong in the other direction: that counter is
        # incremented only *after* the acquire below, so it excludes this worker.
        # Other workers wait here while still able to fetch from database.
        in_use, capacity = self.processing_semaphore.usage
        debug(
            f"Worker {worker_id} waiting for processing slot "
            f"(currently {in_use}/{capacity} in use)"
        )
        self.processing_semaphore.acquire()

        with self.stats_lock:
            self.stats['processing'] += 1

        job_start = time.time()
        success = False

        try:
            debug(f"Worker {worker_id} extracting fingerprint for track {track.id}")

            # Extract and store fingerprint, bounded so a hung analysis cannot
            # wedge this worker (and its semaphore slot) forever (#4837).
            success = self._extract_bounded(track.id, track.filepath, worker_id)

            if success:
                with self.stats_lock:
                    self.stats['completed'] += 1
                    self.stats['total_time'] += time.time() - job_start

                info(f"Fingerprint extracted for track {track.id}")

                self._report_progress({
                    'stage': 'fingerprinting',
                    'track_id': track.id,
                    'status': 'complete',
                    'time': time.time() - job_start
                })

            else:
                raise Exception(f"Extractor returned False for track {track.id}")

        except Exception as e:
            error(f"Error extracting fingerprint for track {track.id}: {e}")

            with self.stats_lock:
                self.stats['failed'] += 1

            self._report_progress({
                'stage': 'fingerprinting',
                'track_id': track.id,
                'status': 'error',
                'error': str(e)
            })

        finally:
            with self.stats_lock:
                self.stats['processing'] = max(0, self.stats['processing'] - 1)

            # Release semaphore to allow next worker to process
            self.processing_semaphore.release()

    def _report_progress(self, progress_data: dict[str, Any]) -> None:
        """Report progress to callback if set"""
        if self.progress_callback:
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                error(f"Progress callback error: {e}")
