#!/usr/bin/env python3

"""
Job execution steps for ProcessingEngine (#4250 follow-up)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_prepare_job()` / `_execute_job()` were part of the last ~330-line chunk of
`processing_engine.py`'s job lifecycle. `create_processor_config()` and
`finalize_job()` — the other two pieces of that chunk — live in the sibling
`job_config.py` / `job_finalize.py` modules; these two stayed together here
because they're the ones that call `load_audio()` / `save()`.

`ProcessingEngine` keeps thin delegating methods of the same name so
`patch.object(engine, "_prepare_job", ...)` / `patch.object(engine,
"_execute_job", ...)` in `tests/backend/test_process_job_nonblocking.py` and
`tests/backend/test_processor_return_on_failure.py` continue to work
unmodified.

`prepare_job()` / `execute_job()` take the owning `ProcessingEngine` as their
first argument rather than duplicating its collaborators (progress
notification, the cancellation-token registry, the processor pool) — they
call back into the engine's own delegating methods (`engine._notify_progress`,
`engine._create_processor_config`, `engine._get_or_create_processor`) so a
test that patches those engine-level names still intercepts calls made from
here.

`load_audio` / `save` are imported HERE, not in `processing_engine.py` — any
`mock.patch` target that intercepts them must be
`'core.job_execution.load_audio'` / `'core.job_execution.save'`.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.io.processing import resample_audio
from auralis.io.saver import save
from auralis.io.unified_loader import load_audio

from core.job_models import ProcessingJob, ProcessingStatus

if TYPE_CHECKING:
    from core.processing_engine import ProcessingEngine

__all__ = ["prepare_job", "execute_job"]

logger = logging.getLogger(__name__)


def _reset_processor_state(processor: HybridProcessor) -> None:
    """Reset the per-job cross-call state on a pooled/cached processor.

    Run via a single `asyncio.to_thread` call (fixes #4797) rather than as
    bare synchronous calls on the event loop, since each acquires
    `_process_lock` (#3787).

    `reset_realtime_eq()` was dropped with the unwired real-time EQ path in
    #4873; `reset_psychoacoustic_eq()` below covers the EQ the live
    adaptive/continuous path actually uses.
    """
    processor.reset_dynamics()
    processor.reset_psychoacoustic_eq()
    processor.reset_limiter()


async def prepare_job(
    engine: "ProcessingEngine", job: ProcessingJob
) -> tuple[np.ndarray, int, UnifiedConfig, HybridProcessor]:
    """Mark the job started, load its input audio, build its config, and
    acquire an exclusively-owned processor (#4250). The processor is popped
    from the pool (#3201) and MUST be returned by the caller — process_job
    does so on every exit path."""
    job.status = ProcessingStatus.PROCESSING
    job.started_at = datetime.now()

    await engine._notify_progress(job.job_id, 0.0, "Loading audio file...")

    # Register a cooperative cancellation token so cancel_job() can abort an
    # in-flight FFmpeg decode running in the to_thread worker (#4496).
    cancel_event = engine._cancel_events.setdefault(job.job_id, threading.Event())

    # Load input audio — disk-bound; offload to thread (fixes #2319)
    audio, sample_rate = await asyncio.to_thread(
        load_audio, job.input_path, cancel_event=cancel_event
    )

    await engine._notify_progress(job.job_id, 20.0, "Analyzing audio content...")

    # Create processor config
    config = engine._create_processor_config(job)

    # Get or create processor — exclusively owned until returned (#3201)
    processor = await engine._get_or_create_processor(job.mode, config)

    return audio, sample_rate, config, processor


async def execute_job(
    engine: "ProcessingEngine",
    job: ProcessingJob,
    audio: np.ndarray,
    sample_rate: int,
    processor: HybridProcessor,
) -> np.ndarray:
    """Reset processor state, run the timeout-guarded DSP process, and save
    the output. Returns the processed audio array (#4250)."""
    await engine._notify_progress(job.job_id, 40.0, "Processing audio...")

    # Reset EQ state before each job so cached processors don't bleed
    # the previous track's psychoacoustic EQ curve into the new track (fixes #2400).
    # The adaptive/continuous path's main psychoacoustic EQ is the one that
    # matters here; the separate real-time EQ path this used to also reset
    # was deleted as unreachable in #4873.
    # reset_limiter() clears the brick-wall limiter's cross-call gain-reduction
    # state so a loud track doesn't leave the next one starting pre-attenuated
    # (fixes #4811).
    #
    # Each reset acquires `_process_lock` (#3787), a plain threading.RLock.
    # #4727 guarantees a timed-out job's processor is discarded rather than
    # reused, so this lock is never held by an orphaned thread by the time we
    # get here — but the acquire is still offloaded to a thread (fixes #4797)
    # so the event loop is never the thing that blocks if that guarantee is
    # ever broken by some other path in the future.
    await asyncio.to_thread(_reset_processor_state, processor)

    # Process audio — CPU-bound; offload to thread (fixes #2319)
    # Wrap with wait_for so a hung DSP/Rust call cannot hold the
    # semaphore slot indefinitely (fixes #2747).
    timeout = engine.processing_timeout
    if job.mode == "reference" or job.mode == "hybrid":
        # Load reference audio if needed
        reference_path = job.settings.get("reference_path")
        if reference_path and Path(reference_path).exists():
            # Same cooperative-cancel token as the input load (#4496 SIBLING):
            # the reference decode is the identical to_thread(load_audio)
            # pattern and must also stop its FFmpeg child on cancel.
            cancel_event = engine._cancel_events.get(job.job_id)
            reference_audio, reference_sr = await asyncio.to_thread(
                load_audio, reference_path, cancel_event=cancel_event
            )
            # Resample reference if needed — CPU-bound; offload to thread
            if reference_sr != sample_rate:
                reference_audio = await asyncio.to_thread(
                    resample_audio, reference_audio, reference_sr, sample_rate
                )
            result = await asyncio.wait_for(
                asyncio.to_thread(processor.process, audio, reference_audio),
                timeout=timeout,
            )
        else:
            # Fall back to adaptive if the reference is unavailable. The
            # config was already switched to reference/hybrid mode in
            # _build_config, and `is_reference_mode() and reference is not
            # None` is the only arm that accepts reference mode — so
            # calling process(audio) without ALSO moving the config back
            # raised ValueError instead of falling back at all (#4735).
            #
            # The router now rejects mode="reference" with no reference at
            # submit time, so this is the narrow race where the file
            # vanished between request and execution; make it degrade
            # rather than crash, and say so in the log.
            logger.warning(
                "Job %s: mode=%s but reference %r is unavailable; "
                "falling back to adaptive processing.",
                job.job_id, job.mode, reference_path,
            )
            processor.config.set_processing_mode("adaptive")
            result = await asyncio.wait_for(
                asyncio.to_thread(processor.process, audio),
                timeout=timeout,
            )
    else:
        # Adaptive mode
        result = await asyncio.wait_for(
            asyncio.to_thread(processor.process, audio),
            timeout=timeout,
        )

    await engine._notify_progress(job.job_id, 80.0, "Saving processed audio...")

    # Save output audio (output_format is recorded in finalize_job).
    bit_depth = job.settings.get("bit_depth", 16)

    # Determine subtype based on bit depth
    subtype_map: dict[int, str] = {16: 'PCM_16', 24: 'PCM_24', 32: 'PCM_32'}
    subtype = subtype_map.get(bit_depth, 'PCM_16')

    # HybridProcessor.process() returns a bare np.ndarray. Earlier
    # versions of this code accessed `result.audio` / `result.lufs` /
    # `result.processing_time` etc., which silently raised
    # AttributeError on every successful job and routed every job
    # through the catch-all "An unexpected error occurred" branch
    # (fixes #3489). Pull richer telemetry from the processor's
    # last_content_profile / get_processing_info() in finalize_job.
    if not isinstance(result, np.ndarray):
        raise TypeError(
            f"HybridProcessor.process() returned {type(result).__name__}, "
            "expected numpy.ndarray"
        )
    audio_data: np.ndarray = result

    # Disk-bound write; offload to thread (fixes #2319)
    await asyncio.to_thread(
        save,
        file_path=job.output_path,
        audio_data=audio_data,
        sample_rate=sample_rate,
        subtype=subtype,
    )

    await engine._notify_progress(job.job_id, 100.0, "Processing complete!")

    return audio_data
