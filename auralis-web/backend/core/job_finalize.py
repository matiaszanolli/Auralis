#!/usr/bin/env python3

"""
Job-completion telemetry and result recording (#4250 follow-up)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`finalize_job()` was `ProcessingEngine._finalize_job()`, split out alongside
`job_execution.py` / `job_config.py` when the last ~330-line job-lifecycle
chunk of `processing_engine.py` was extracted. `ProcessingEngine` keeps a
thin `_finalize_job()` delegating method so `patch.object(engine,
"_finalize_job", ...)` in `tests/backend/test_processor_return_on_failure.py`
keeps working unmodified.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np

from auralis.core.hybrid_processor import HybridProcessor

from core.job_models import ProcessingJob, ProcessingStatus

__all__ = ["finalize_job"]


def finalize_job(
    job: ProcessingJob,
    audio_data: np.ndarray,
    sample_rate: int,
    processor: HybridProcessor,
) -> None:
    """Collect best-effort telemetry and record the completed result (#4250).

    #4757: get_processing_info() returns a fixed 7-key dict of static
    config (mode/sample_rate/fft_size/...) — it never has "processing_time"
    or "lufs" keys, so those two lookups always missed. And
    last_content_profile is a dict (either ContinuousMode's
    {'fingerprint', 'coordinates', 'parameters'} or, on the legacy
    AdaptiveMode path, ContentAnalyzer.analyze_content()'s dict), so
    getattr(dict_instance, "genre", None) could never succeed either —
    dicts don't expose keys as attributes. All three fields were
    permanently null.
    """
    genre_detected: str | None = None
    lufs: float | None = None
    try:
        content_profile = getattr(processor, "last_content_profile", None)
        if isinstance(content_profile, dict):
            # Legacy AdaptiveMode path (use_continuous_space=False, or the
            # adaptive component of hybrid/reference modes): genre lives
            # under genre_info.primary, not a top-level "genre" key.
            genre_info = content_profile.get("genre_info")
            if isinstance(genre_info, dict):
                genre_detected = genre_info.get("primary")
            estimated_lufs = content_profile.get("estimated_lufs")
            if estimated_lufs is not None:
                lufs = float(estimated_lufs)

        # Default/production path (use_continuous_space=True, the only
        # value the app ever sets): ContinuousMode never runs genre
        # classification, but its 25D fingerprint carries a real measured
        # LUFS — prefer it over the legacy estimate above when present.
        continuous_mode = getattr(processor, "continuous_mode", None)
        fingerprint = getattr(continuous_mode, "last_fingerprint", None)
        if isinstance(fingerprint, dict) and fingerprint.get("lufs") is not None:
            lufs = float(fingerprint["lufs"])
    except Exception:
        # Telemetry is non-critical; never let it fail the job.
        pass

    output_format = job.settings.get("output_format", "wav")
    bit_depth = job.settings.get("bit_depth", 16)

    # Real wall-clock duration from job.started_at (set in prepare_job) to
    # now — covers load + analysis + DSP, not just the DSP call, which is
    # what "processing_time" for a submitted job actually means to a
    # caller. Reuse the same timestamp for completed_at so the two never
    # disagree.
    completed_at = datetime.now()
    processing_time = (
        (completed_at - job.started_at).total_seconds()
        if job.started_at is not None else None
    )

    # Store result metadata — use filename-only for output_file so
    # the absolute temp path never appears in API responses (#3848,
    # sibling of the input_file sanitisation in #3322).
    job.result_data = {
        "output_file": Path(job.output_path).name,
        "sample_rate": int(sample_rate),
        "duration": float(len(audio_data) / sample_rate),
        "format": output_format,
        "bit_depth": bit_depth,
        "processing_time": processing_time,
        "genre_detected": genre_detected,
        "lufs": lufs,
        # Settings accepted at submit time but not consumed by the
        # offline pipeline (#5060) — see job_config.create_processor_config.
        "ignored_settings": job.ignored_settings,
    }

    job.status = ProcessingStatus.COMPLETED
    job.completed_at = completed_at
