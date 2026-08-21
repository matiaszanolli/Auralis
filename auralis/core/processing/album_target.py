"""
Album-Consistent Target Derivation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Derive ONE target spectrum for a whole album, so tracks mastered as a set land
on a common tonality instead of each drifting to its own k-NN destination.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Phase 1 of #3481. Per-track derivation is right for shuffle and queue playback;
it is wrong for listening to a record top to bottom, where a quiet intro and a
loud closer can end up with measurably different tonal destinations the original
engineer specifically avoided.

Strategy: run the soft k-NN per track, then average the resulting *targets* —
the issue's option (b). Averaging the fingerprints first and matching once would
hand the cloud a source that no track actually sounds like; matching per track
keeps each track's own character in the interpolation and unifies only where
they are all headed.

What this unifies is the DESTINATION, not the EQ curve. `delta_eq` computes a
symmetric delta from (source, target), so tracks starting from different places
still receive different curves — that is the mechanism by which they converge,
not a bug. Per-track dynamics, loudness and stereo width are untouched: only the
target spectrum is shared.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ...utils.logging import debug
from .target_derivation import TARGET_FEATURES, DistanceStats, derive_target


@dataclass(frozen=True)
class AlbumTarget:
    """Result of :func:`derive_album_target`, with diagnostics for debugging/UI."""

    target: dict[str, float]        # The shared target, one value per TARGET_FEATURE
    n_tracks: int                   # Tracks that contributed a target
    n_skipped: int                  # Tracks whose own derivation returned None
    top_ref_ids: tuple[int, ...]    # References that fed any contributing track


def average_targets(
    targets: Sequence[Mapping[str, float]],
) -> dict[str, float] | None:
    """Average per-track target spectra feature-wise.

    Every track counts equally — an album is a set of tracks, not a pool of
    samples, so a seven-minute closer does not outvote a ninety-second intro.

    Returns None for an empty sequence. Missing features default to 0.0, which
    matches how ``derive_target`` reads absent fields off a reference row.
    """
    if not targets:
        return None

    n = len(targets)
    return {
        feat: sum(float(t.get(feat, 0.0)) for t in targets) / n
        for feat in TARGET_FEATURES
    }


def derive_album_target(
    fingerprints: Sequence[Any],
    references: list[Any],
    stats: DistanceStats,
    *,
    k: int = 10,
    use_reference_weights: bool = True,
) -> AlbumTarget | None:
    """Derive one shared target spectrum for an album.

    Args:
        fingerprints: One fingerprint per album track (ORM rows or dicts), in
            any order — the result does not depend on it.
        references: Reference cloud, as passed to :func:`derive_target`.
        stats: Per-feature normalization stats for that cloud.
        k: Neighbours weighted per track. Applied per track, not per album:
            each track still matches against its own k nearest references.
        use_reference_weights: Forwarded to :func:`derive_target`.

    Returns:
        AlbumTarget, or None when no track yielded a target (empty album, empty
        cloud). The caller falls back to per-track derivation, which is the
        behaviour album mode is an override of.
    """
    if not fingerprints or not references:
        return None

    per_track: list[dict[str, float]] = []
    ref_ids: list[int] = []
    skipped = 0

    for fingerprint in fingerprints:
        result = derive_target(
            fingerprint, references, stats,
            k=k, use_reference_weights=use_reference_weights,
        )
        if result is None:
            skipped += 1
            continue
        per_track.append(result.target)
        ref_ids.extend(result.top_ref_ids)

    averaged = average_targets(per_track)
    if averaged is None:
        debug("[Album] No track yielded a target — falling back to per-track mode")
        return None

    # De-duplicated but order-stable, so the diagnostic reads the same way twice.
    unique_refs = tuple(dict.fromkeys(ref_ids))
    debug(
        f"[Album] Shared target derived from {len(per_track)} tracks "
        f"({skipped} skipped) over {len(unique_refs)} references"
    )
    return AlbumTarget(
        target=averaged,
        n_tracks=len(per_track),
        n_skipped=skipped,
        top_ref_ids=unique_refs,
    )
