"""
Similarity Explanation
~~~~~~~~~~~~~~~~~~~~~~

The human-readable explanation path (``get_similarity_explanation`` and its
pre-filtered candidate helper), split from similarity.py (#6273). The
similarity method stays a thin delegator; the backend router
(``routers/similarity_explain.py``) reaches it through the class API, which
is unchanged.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .similarity import FingerprintSimilarity


def get_similarity_explanation(similarity, 
    self,
    track_id1: int,
    track_id2: int,
    top_n: int = 5
) -> dict[str, Any] | None:
    """
    Get detailed explanation of why two tracks are similar/different

    Args:
        track_id1: First track ID
        track_id2: Second track ID
        top_n: Number of top contributing dimensions to return

    Returns:
        Dictionary with similarity details and top contributors
    """
    if not similarity.fitted:
        error("Similarity system not fitted. Call fit() first.")
        return None

    # Get fingerprints
    fp1 = similarity.fingerprint_repo.get_by_track_id(track_id1)
    fp2 = similarity.fingerprint_repo.get_by_track_id(track_id2)

    if not fp1 or not fp2:
        return None

    # Normalize
    vec1 = similarity.normalizer.normalize(fp1.to_vector())
    vec2 = similarity.normalizer.normalize(fp2.to_vector())

    # Calculate overall similarity
    distance = similarity.distance_calc.calculate(vec1, vec2)
    similarity_score = similarity.distance_calc.calculate_similarity_score(distance)

    # Get dimension contributions
    contributions = similarity.distance_calc.get_dimension_contributions(vec1, vec2)

    # Raw (denormalized) per-dimension values for display. fp.to_vector()
    # produces the 25 dimensions in FingerprintNormalizer.DIMENSION_NAMES
    # order (the same order normalize() consumes above), so index i maps to
    # DIMENSION_NAMES[i].
    raw1 = fp1.to_vector()
    raw2 = fp2.to_vector()
    dim_index = {name: i for i, name in enumerate(similarity.normalizer.DIMENSION_NAMES)}

    def _entry(dim: str, contrib: float) -> dict[str, Any]:
        idx = dim_index.get(dim)
        v1 = float(raw1[idx]) if idx is not None and idx < len(raw1) else 0.0
        v2 = float(raw2[idx]) if idx is not None and idx < len(raw2) else 0.0
        return {
            'dimension': dim,
            'contribution': float(contrib),
            'value1': v1,
            'value2': v2,
            'difference': v1 - v2,
        }

    # Sort by contribution (descending)
    sorted_dims = sorted(contributions.items(), key=lambda x: x[1], reverse=True)

    return {
        'track_id1': track_id1,
        'track_id2': track_id2,
        'distance': distance,
        'similarity_score': similarity_score,
        'top_differences': [_entry(dim, contrib) for dim, contrib in sorted_dims[:top_n]],
        'all_contributions': [_entry(dim, contrib) for dim, contrib in sorted_dims],
    }


def get_prefiltered_candidates(similarity, 
    self,
    target_fp: Any,
    max_candidates: int = 100
) -> list[tuple[int, np.ndarray]]:
    """
    Pre-filter candidates using dimension ranges

    Uses the most distinctive dimensions (lufs, crest_db, bass_pct, tempo_bpm)
    to quickly filter down to promising candidates.

    Args:
        target_fp: Target TrackFingerprint object
        max_candidates: Maximum number of candidates to return

    Returns:
        List of (track_id, normalized_vector) tuples
    """
    # Define tolerance ranges for pre-filtering
    # These are in original (non-normalized) scale
    ranges = {
        'lufs': (target_fp.lufs - 3.0, target_fp.lufs + 3.0),              # ±3 LUFS
        'crest_db': (target_fp.crest_db - 2.0, target_fp.crest_db + 2.0),  # ±2 dB
        'bass_pct': (target_fp.bass_pct - 0.08, target_fp.bass_pct + 0.08),  # ±8% (bass_pct is a 0-1 fraction, not 0-100 -- #5471)
        'tempo_bpm': (target_fp.tempo_bpm - 15.0, target_fp.tempo_bpm + 15.0)  # ±15 BPM
    }

    # Get candidates within ranges
    candidates_fps = similarity.fingerprint_repo.get_by_multi_dimension_range(
        ranges,
        limit=max_candidates
    )

    # Normalize and convert to (track_id, vector) tuples
    candidates = [
        (fp.track_id, similarity.normalizer.normalize(fp.to_vector()))
        for fp in candidates_fps
        if fp.track_id != target_fp.track_id  # Exclude target itself
    ]

    debug(f"Pre-filtering: {len(candidates)} candidates (from ranges)")
    return candidates

def is_fitted(self) -> bool:
    """Check if similarity system is fitted and ready"""
    return similarity.fitted
