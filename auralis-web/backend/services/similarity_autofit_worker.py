"""
Similarity Auto-Fit Background Worker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Wraps the one-shot `FingerprintSimilarity.fit()` background pass (#4139) in
the same async `start()`/`stop()` shape every other `BACKGROUND_WORKER_KEYS`
entry uses (#4111), so lifespan shutdown and `POST /api/library/reset`
cannot diverge on it — the gap #4682 found: the fit used to run on a bare
`threading.Thread(daemon=True)` that was never stored, joined, or signalled
to stop, so a quit mid-fit tore the process down while the thread still held
a session against an engine `library_database.shutdown()` was about to
dispose, and a library reset raced it reading fingerprints from a database
being wiped out from under it.

`fit()` streams every fingerprint through a SQLAlchemy session in bounded
batches; once a batch read is in flight there is no way to forcibly cancel
the underlying OS thread (an `asyncio.to_thread` future cannot be cancelled
after it starts running), so `stop()` sets a `threading.Event` the batch
loop checks between reads (`FingerprintNormalizer.fit(stop_event=...)`) and
waits for the thread to observe it and exit.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# Bound on how long stop() waits for a cooperative exit before giving up and
# returning anyway — shutdown must not hang forever on a wedged fit. The
# thread is not forcibly killed if this expires; it keeps running until the
# process itself exits, same risk profile as any other daemon thread, but at
# least every OTHER shutdown step still runs.
_STOP_TIMEOUT_SECONDS = 10.0

# How often the worker re-checks whether an unfitted system can fit yet, or a
# fitted one has outgrown its sample (SimilarityAutoFitWorker._run, #5716).
_CHECK_INTERVAL_SECONDS = 300.0


class SimilarityAutoFitWorker:
    """Owns the similarity auto-fit pass (initial fit plus periodic refit check) as a stoppable worker."""

    def __init__(
        self,
        sim_system: Any,
        lib_mgr: Any,
        globals_dict: dict[str, Any],
        builder_cls: Any,
        check_interval: float = _CHECK_INTERVAL_SECONDS,
    ) -> None:
        self._sim_system = sim_system
        self._lib_mgr = lib_mgr
        self._globals_dict = globals_dict
        self._builder_cls = builder_cls
        self._check_interval = check_interval
        self._stop_event = threading.Event()
        self._task: 'asyncio.Task[None] | None' = None

    async def start(self) -> None:
        """Kick off the fit pass. A no-op if one is already running."""
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.ensure_future(asyncio.to_thread(self._run))

    async def stop(self) -> None:
        """Signal the fit loop to abort at its next batch boundary and wait
        (bounded) for the underlying thread to actually exit."""
        self._stop_event.set()
        if self._task is None:
            return
        try:
            await asyncio.wait_for(asyncio.shield(self._task), timeout=_STOP_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.warning(
                "Similarity auto-fit did not stop within "
                f"{_STOP_TIMEOUT_SECONDS}s of being signalled; abandoning it "
                "(the underlying thread is not forcibly killable)."
            )
        except Exception as exc:
            logger.warning(f"Similarity auto-fit task raised during stop(): {exc}")

    def _run(self) -> None:
        """Runs in a worker thread via asyncio.to_thread (started by start()).

        Fits once, then re-checks every ``check_interval`` seconds until
        stop() is signalled. The re-check is what retries a library that was
        below ``min_samples`` at startup and refits one whose fit rests on a
        small sample (#5716); ``fit()`` is a single COUNT when nothing has
        changed.
        """
        self._fit_once(first=True)
        while not self._stop_event.wait(self._check_interval):
            self._fit_once(first=False)

    def _fit_once(self, first: bool) -> None:
        try:
            if self._sim_system.fit(stop_event=self._stop_event):
                # get_component reads globals fresh per request, so this
                # late assignment is picked up. The builder shares the
                # similarity system (and so its normalizer), so a refit
                # reaches it without rebuilding the builder; an already
                # persisted K-NN graph keeps its old edges until rebuilt.
                if self._globals_dict.get('graph_builder') is None:
                    self._globals_dict['graph_builder'] = self._builder_cls(
                        similarity_system=self._sim_system,
                        session_factory=self._lib_mgr.SessionLocal,
                        graph_repo=self._lib_mgr.repositories.similarity_graph,
                    )
                    logger.info("✅ Similarity auto-fitted; K-NN Graph Builder ready")
            elif self._stop_event.is_set():
                logger.info("ℹ️  Similarity auto-fit stopped before completing")
            elif first:
                logger.info("ℹ️  Similarity auto-fit skipped (not enough fingerprints yet)")
        except Exception as fit_e:
            logger.warning(f"⚠️  Similarity auto-fit failed: {fit_e}")
