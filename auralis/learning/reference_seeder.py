"""
Reference Cloud Seeder
~~~~~~~~~~~~~~~~~~~~~~

Programmatically select well-mastered tracks from the user's library to seed
the mastering reference cloud. The cloud feeds the soft k-NN target derivation
that drives content-aware EQ in the mastering pipeline (see Phase 3+).

Selection is purely heuristic — no genre labels, no human curation required.
We pick tracks whose objective measurements indicate a healthy modern master:
loudness in a reasonable range, dynamic range preserved, no extreme spectral
outliers. The cloud is rebuilt atomically (clear + reflag in one transaction)
so the mastering pipeline never sees a partial state.

The seeder is dependency-injected — `score_fingerprint` works on plain
dicts/objects, `refresh_cloud` orchestrates DB I/O via the repository so the
scoring logic can be tested without a live database.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Selection thresholds — tuned for modern stylistically diverse libraries.
# Tune via `SeederConfig` at the call site instead of editing these.
# ---------------------------------------------------------------------------

DEFAULT_MIN_LUFS = -18.0
DEFAULT_MAX_LUFS = -10.0
DEFAULT_MIN_CREST_DB = 9.0
DEFAULT_MAX_BAND_FRACTION = 0.65   # No single 7-band slice >65% of energy
DEFAULT_MAX_REFERENCES_ABSOLUTE = 50
DEFAULT_MAX_REFERENCES_LIBRARY_FRACTION = 0.05    # cap at 5% of library
# #3680: candidate cap to prevent OOM on very large libraries. The seeder
# only selects up to `max_references_absolute` (default 50) so the
# candidate pool only needs to be large enough that the best aren't
# missed. 10 000 covers nearly all personal libraries fully; larger
# libraries get a bounded most-recent slice.
DEFAULT_MAX_CANDIDATES = 10_000


@dataclass(frozen=True)
class SeederConfig:
    """Configuration for the reference seeder."""

    min_lufs: float = DEFAULT_MIN_LUFS
    max_lufs: float = DEFAULT_MAX_LUFS
    min_crest_db: float = DEFAULT_MIN_CREST_DB
    max_band_fraction: float = DEFAULT_MAX_BAND_FRACTION
    max_references_absolute: int = DEFAULT_MAX_REFERENCES_ABSOLUTE
    max_references_library_fraction: float = DEFAULT_MAX_REFERENCES_LIBRARY_FRACTION
    # #3680: candidate cap to prevent unbounded RAM use during cloud rebuild.
    max_candidates: int = DEFAULT_MAX_CANDIDATES


# The seven band fields whose distribution we audit for extreme outliers.
BAND_FIELDS: tuple[str, ...] = (
    'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
    'upper_mid_pct', 'presence_pct', 'air_pct',
)


def score_fingerprint(fp: Any, config: SeederConfig = SeederConfig()) -> float:
    """Score a fingerprint as a candidate reference. Higher = better.

    Returns 0.0 if the fingerprint fails any hard requirement (LUFS out of
    range, crest below floor, any band > max_band_fraction). Otherwise
    returns a continuous score in (0.0, 1.0] that prefers:
      - LUFS centered in the [min_lufs, max_lufs] range
      - Higher crest (more dynamic preservation)
      - Balanced 7-band distribution (lower max band fraction)

    Works with any object exposing the relevant attributes (TrackFingerprint
    ORM rows OR plain dicts via getattr/[] fallback).
    """
    g = _attr_getter(fp)

    lufs = g('lufs')
    crest = g('crest_db')

    # Hard requirements: zero out anything that fails.
    if lufs is None or crest is None:
        return 0.0
    if not (config.min_lufs <= lufs <= config.max_lufs):
        return 0.0
    if crest < config.min_crest_db:
        return 0.0

    raw_band_values = [g(field) for field in BAND_FIELDS]
    if any(v is None for v in raw_band_values):
        return 0.0
    # type-narrowed via the None guard above; cast for the type checker.
    band_values: list[float] = [float(v) for v in raw_band_values if v is not None]
    max_band = max(band_values)
    if max_band > config.max_band_fraction:
        return 0.0

    # Soft scoring (all components 0..1, summed then averaged).
    lufs_center = (config.min_lufs + config.max_lufs) / 2.0
    lufs_half_range = (config.max_lufs - config.min_lufs) / 2.0
    lufs_score = 1.0 - abs(lufs - lufs_center) / lufs_half_range  # 1.0 at center

    # Crest: linear ramp from min_crest_db (=0) up to 18 dB (=1, saturating).
    crest_score = min(1.0, (crest - config.min_crest_db) / (18.0 - config.min_crest_db))

    # Balance: penalize concentration. max_band=0.65 -> 0; max_band=0.20 -> 1.
    balance_score = max(0.0, 1.0 - (max_band - 0.20) / (config.max_band_fraction - 0.20))

    return (lufs_score + crest_score + balance_score) / 3.0


def select_references(
    fingerprints: list[Any],
    config: SeederConfig = SeederConfig(),
) -> list[tuple[Any, float]]:
    """Score and rank fingerprints; return the top selections.

    Returns a list of (fingerprint, score) tuples, highest score first,
    capped at min(max_references_absolute, library_size * max_references_library_fraction).
    Only candidates with score > 0 are included.
    """
    if not fingerprints:
        return []

    scored = [(fp, score_fingerprint(fp, config)) for fp in fingerprints]
    scored = [(fp, s) for fp, s in scored if s > 0.0]
    scored.sort(key=lambda t: t[1], reverse=True)

    cap = min(
        config.max_references_absolute,
        max(1, int(len(fingerprints) * config.max_references_library_fraction)),
    )
    return scored[:cap]


class _FingerprintRepoLike(Protocol):
    """Minimum protocol required from the repository for refresh_cloud."""

    def get_all(self, limit: int | None = ..., offset: int = ...) -> list[Any]: ...
    def clear_all_reference_flags(self) -> int: ...
    def set_reference_flags(self, track_ids_flagged: dict[int, bool]) -> int: ...


def refresh_cloud(
    repository: _FingerprintRepoLike,
    config: SeederConfig = SeederConfig(),
) -> tuple[int, int]:
    """Rebuild the reference cloud from current library state.

    Clears all existing is_reference flags, scores every fingerprint, and
    flags the top-N. The clear and re-flag happen in separate transactions
    but the seeder is idempotent (running it twice produces the same flags).

    Args:
        repository: FingerprintRepository instance.
        config: Selection thresholds.

    Returns:
        (cleared_count, selected_count).
    """
    cleared = repository.clear_all_reference_flags()
    # #3680: bounded candidate pool to prevent OOM on very large libraries.
    # `get_all()` returns rows ordered by created_at DESC so the cap takes
    # the most recent slice, which is the sensible default for "what should
    # the reference cloud represent right now".
    all_fps = repository.get_all(limit=config.max_candidates)
    selected = select_references(all_fps, config)
    flags = {fp.track_id: True for fp, _score in selected}
    repository.set_reference_flags(flags)
    logger.info(
        "Reference cloud rebuilt: %d cleared, %d selected from %d candidates",
        cleared, len(selected), len(all_fps),
    )
    return cleared, len(selected)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _attr_getter(fp: Any):
    """Return a function that pulls a field by name from fp (attr or dict)."""
    if hasattr(fp, '__getitem__') and not hasattr(fp, '__table__'):
        # Dict-like (but not an ORM row which can be confusingly subscriptable).
        return lambda name: fp.get(name) if hasattr(fp, 'get') else None
    return lambda name: getattr(fp, name, None)


__all__ = [
    "SeederConfig",
    "score_fingerprint",
    "select_references",
    "refresh_cloud",
    "BAND_FIELDS",
]
