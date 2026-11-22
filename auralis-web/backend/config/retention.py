"""
Retention and max-age windows (#6643).

How long finished jobs and leftover temp files live before a sweep reclaims them. The defaults were
typed independently at each site (the job-cleanup 24 h in both the engine and the router's query
default, the 1 h temp age in two startup helpers) with ``* 3600`` conversions inline. These ages are
in hours because the public interfaces that take them (the cleanup endpoint's ``max_age_hours``,
the engine and sweep functions) are; ``SECONDS_PER_HOUR`` is the one conversion.

Short-lived, module-owned windows keep their own names next to the code they bound:
``core/encoding/atomic_io.PARTIAL_MAX_AGE_SECONDS`` (an in-flight staging write) and
``core/thumbnail_cache.TEMP_FILE_MAX_AGE_SECONDS`` (an in-progress thumbnail render).
"""

SECONDS_PER_HOUR = 3600

#: A finished processing job's record and outputs are kept this long (the worker's periodic
#: cleanup, the restore-time expiry and the startup sweep of the job temp dirs).
COMPLETED_JOB_TTL_HOURS = 1.0

#: Default age for an on-demand job cleanup (POST cleanup endpoint and ProcessingEngine).
JOB_CLEANUP_DEFAULT_AGE_HOURS = 24.0

#: Stream / decode temp WAVs a crashed run left behind are reclaimed at startup past this age.
STALE_TEMP_MAX_AGE_HOURS = 1.0
