#!/usr/bin/env python3

"""
Processor-config construction for a processing job (#4250 follow-up)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`create_processor_config()` was `ProcessingEngine._create_processor_config()`,
split out alongside `job_execution.py` / `job_finalize.py` when the last
~330-line job-lifecycle chunk of `processing_engine.py` was extracted.
`ProcessingEngine` keeps a thin `_create_processor_config()` delegating
method so `patch.object(engine, "_create_processor_config", ...)` in
`tests/backend/test_process_job_nonblocking.py` keeps working unmodified.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import logging

from auralis.core.config import UnifiedConfig

from core.job_models import ProcessingJob

__all__ = ["create_processor_config"]

logger = logging.getLogger(__name__)


def create_processor_config(job: ProcessingJob) -> UnifiedConfig:
    """
    Create UnifiedConfig from job settings.

    Currently supports ONLY adaptive / reference / hybrid mode selection.
    The offline-mastering pipeline (HybridProcessor.process) drives EQ /
    dynamics / level / genre from its OWN internal fingerprint analysis
    via ContinuousMode — it does NOT read from `config.adaptive.eq_gains`,
    `config.adaptive.compressor`, `config.adaptive.target_lufs`,
    `config.adaptive.gain`, or `config.adaptive.genre_override`.

    Until those readers exist (tracked as the wire-up follow-up for
    #3490), any "eq" / "dynamics" / "level_matching" / "genre_override"
    keys in `job.settings` are logged at INFO and ignored. Prior code
    silently wrote them into dynamic attributes on `AdaptiveConfig` —
    the UI looked responsive while changing nothing audible.
    """

    config = UnifiedConfig()

    # Set processing mode
    if job.mode == "adaptive":
        config.set_processing_mode("adaptive")
    elif job.mode == "reference":
        config.set_processing_mode("reference")
    elif job.mode == "hybrid":
        config.set_processing_mode("hybrid")

    # Log (don't silently drop) any UI settings the engine cannot consume.
    # The frontend should hide these controls until the engine reads them
    # (see #3490 follow-up). Logging at INFO so developers see it in dev.
    unsupported: list[str] = []
    # Guard each lookup against an explicit `None` value, not just a missing
    # key — ProcessingSettings.model_dump() always includes "eq"/"dynamics"/
    # "fingerprint" with a None default when the client doesn't set them, so
    # `"eq" in job.settings` is True while `job.settings["eq"]` is None and
    # `.get()` on it raises AttributeError (fixes #3819, found while writing
    # the first end-to-end test to drive a real ProcessingEngine — every job
    # submitted with default settings failed with "unexpected error").
    fingerprint_settings = job.settings.get("fingerprint")
    if fingerprint_settings and fingerprint_settings.get("enabled"):
        # The 25D-fingerprint-to-mastering-parameter mapper this once fed
        # (auralis/analysis/fingerprint/parameter_mapper.py) was deleted
        # as dead code (#4926) — superseded by the continuous-parameter-
        # space mastering path (auralis/core/processing/continuous_space.py).
        # No frontend control sends this setting; kept defensive in case a
        # client still submits it.
        unsupported.append("fingerprint (superseded by continuous-space mastering)")
    eq_settings = job.settings.get("eq")
    if eq_settings and eq_settings.get("enabled"):
        unsupported.append("eq")
    dynamics_settings = job.settings.get("dynamics")
    if dynamics_settings and dynamics_settings.get("enabled"):
        unsupported.append("dynamics")
    level_settings = job.settings.get("level_matching") or job.settings.get("levelMatching")
    if level_settings and level_settings.get("enabled"):
        unsupported.append("level_matching")
    # Value check, not key presence (#5060 fix): ProcessingSettings.model_dump()
    # always includes "genre_override" with a None default even when the
    # client never set it (same trap #3819 already fixed for "fingerprint"
    # above), so `"genre_override" in job.settings` was True — and thus
    # reported as ignored — on every single job, not just ones that set it.
    if job.settings.get("genre_override") is not None:
        unsupported.append("genre_override")
    # sample_rate: None means "keep original" (router default) and is a
    # legitimate no-op, not an ignored request; any other value is accepted
    # by the API but never actually applied — the offline pipeline writes
    # at the input file's rate (#5060).
    if job.settings.get("sample_rate") is not None:
        unsupported.append("sample_rate")

    # Surfaced in result_data (#5060) so a client can tell "applied" from
    # "accepted but silently ignored" instead of only via this INFO log.
    job.ignored_settings = unsupported

    if unsupported:
        logger.info(
            "Job %s: requested settings (%s) are accepted but not consumed "
            "by the offline pipeline — HybridProcessor drives these from "
            "internal fingerprint analysis. See #3490 for the wire-up plan.",
            job.job_id,
            ", ".join(unsupported),
        )

    return config
