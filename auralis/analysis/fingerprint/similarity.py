"""
Fingerprint Similarity API
~~~~~~~~~~~~~~~~~~~~~~~~~

High-level API for finding similar tracks using fingerprint-based similarity

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from typing import Any

import numpy as np

from ...utils.logging import debug, error, info, warning
from .dimension_weights import DimensionWeights
from .distance import FingerprintDistance
from .similarity_explanation import get_prefiltered_candidates, get_similarity_explanation
from .normalizer import FingerprintNormalizer
from .normalizer_stats import DimensionStats
from .similarity_calibration import DEFAULT_REFERENCE_DISTANCE, calibrate_reference_distance

# A fitted system refits once the current-version fingerprint count reaches
# this multiple of the sample its statistics came from (#5716).
REFIT_GROWTH_FACTOR = 1.5


class SimilarityResult:
    """Result of similarity search"""

    def __init__(self, track_id: int, distance: float, similarity_score: float):
        """A similar track: its fingerprint distance (lower = closer) and 0-1 score (higher = closer)."""
        self.track_id = track_id
        self.distance = distance
        self.similarity_score = similarity_score

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'track_id': self.track_id,
            'distance': self.distance,
            'similarity_score': self.similarity_score
        }

    def __repr__(self) -> str:
        return f"SimilarityResult(track_id={self.track_id}, distance={self.distance:.4f}, score={self.similarity_score:.4f})"


class FingerprintSimilarity:
    """
    Complete similarity calculation system

    Combines normalization, distance calculation, and pre-filtering
    for efficient similarity search.

    Usage:
        # Initialize
        similarity = FingerprintSimilarity(fingerprint_repository)
        similarity.fit()  # Calculate normalization statistics

        # Find similar tracks
        results = similarity.find_similar(track_id=123, n=10)
    """

    def __init__(
        self,
        fingerprint_repository: Any,
        weights: DimensionWeights | None = None,
        use_robust_normalization: bool = True
    ) -> None:
        """
        Initialize similarity system

        Args:
            fingerprint_repository: FingerprintRepository instance
            weights: Custom dimension weights (optional)
            use_robust_normalization: Use percentile-based normalization
        """
        self.fingerprint_repo = fingerprint_repository
        self.normalizer = FingerprintNormalizer(use_robust=use_robust_normalization)
        self.distance_calc = FingerprintDistance(weights=weights)
        self.fitted = False
        # What a score is computed with, published as ONE object after calibration: the stats every
        # vector of a call is normalised against, and the reference distance that scales the score
        # (#5923). normalizer.fit() makes its new stats live before calibration runs, so a reader
        # of the two separately could mix the old scale with the new ranges (#6573).
        self.fitted_model: tuple[dict[str, DimensionStats], float] = ({}, DEFAULT_REFERENCE_DISTANCE)
        self._fit_lock = threading.Lock()

    @property
    def reference_distance(self) -> float:
        """Scale of the 0-1 similarity score, set by fit() (#5923)."""
        return self.fitted_model[1]

    def needs_refit(self) -> bool:
        """
        True once the library has outgrown the statistics it was fitted on

        Compares the current-version fingerprint count with the number of
        vectors the normalizer was fitted from. A fit made while the library
        was young, or right after an algorithm bump when most rows are stale,
        rests on a small sample; without this the ``fitted`` flag froze those
        ranges for the life of the process (#5716).
        """
        fitted_from = max((st.count for st in self.normalizer.stats.values()), default=0)
        if not self.fitted or fitted_from <= 0:  # no known sample to outgrow
            return False
        current = self.fingerprint_repo.get_count(current_only=True)
        return bool(current >= fitted_from * REFIT_GROWTH_FACTOR)

    def fit(self, min_samples: int = 10, stop_event: threading.Event | None = None) -> bool:
        """
        Calculate normalization statistics from library

        Args:
            min_samples: Minimum fingerprints required
            stop_event: Forwarded to FingerprintNormalizer.fit() (#4682) for
                cooperative early exit from a background caller.

        Re-runs when the library has grown past ``REFIT_GROWTH_FACTOR`` times
        the fitted sample (``needs_refit``); a failed or stopped refit keeps
        the previous statistics in force.

        Returns:
            True if successful, False otherwise
        """
        # Startup auto-fit and POST /api/similarity/fit share this instance.
        # Keep their fitted check and the expensive fit in one critical
        # section so two callers cannot compute and publish competing models
        # (#5243).  A caller queued behind a successful fit reuses it.
        with self._fit_lock:
            if stop_event is not None and stop_event.is_set():
                info("Similarity fit stopped before starting")
                return False

            if self.fitted and not self.needs_refit():
                info("Similarity system already fitted")
                return True

            info("Fitting similarity system to library fingerprints...")
            success = self.normalizer.fit(
                self.fingerprint_repo, min_samples=min_samples, stop_event=stop_event
            )

            if success:
                reference = calibrate_reference_distance(
                    self.fingerprint_repo, self.normalizer, self.distance_calc
                )
                self.fitted_model = (self.normalizer.stats, reference)
                self.fitted = True
                info("Similarity system ready")
            else:
                error("Failed to fit similarity system")

            return success

    def reset(self) -> None:
        """Forget the fitted model: the library it was fitted on is gone (#6584).

        After a library reset ``needs_refit()`` compares a near-empty library with the old sample
        and stays False, so ``fit()`` kept the deleted library's ranges and calibration until the new
        one outgrew the old one 1.5x. Unfitted, the routes answer their "initialising" 503 and the
        auto-fit worker fits the new library on its own statistics.
        """
        with self._fit_lock:
            self.fitted = False
            self.fitted_model = ({}, DEFAULT_REFERENCE_DISTANCE)
            # In place: the K-NN graph builder shares this normalizer.
            self.normalizer.stats = {}
            self.normalizer.fitted = False

    def find_similar(
        self,
        track_id: int,
        n: int = 10,
        use_prefilter: bool = True,
        prefilter_factor: int = 10
    ) -> list[SimilarityResult]:
        """
        Find N most similar tracks to target track

        Args:
            track_id: ID of target track
            n: Number of similar tracks to return
            use_prefilter: Use dimension-based pre-filtering
            prefilter_factor: Pre-filter to N*factor candidates before distance calculation

        Returns:
            List of SimilarityResult objects, sorted by similarity (most similar first)
        """
        if not self.fitted:
            error("Similarity system not fitted. Call fit() first.")
            return []

        # Get target fingerprint
        target_fp = self.fingerprint_repo.get_by_track_id(track_id)
        if not target_fp:
            warning(f"No fingerprint found for track {track_id}")
            return []

        # One model for the target, every candidate and the score scale, even if a refit lands now.
        stats, reference_distance = self.fitted_model
        target_vector = self.normalizer.normalize(target_fp.to_vector(), stats)

        # Get candidates
        if use_prefilter:
            candidates = self._get_prefiltered_candidates(
                target_fp,
                max_candidates=n * prefilter_factor,
                stats=stats,
            )
            # Fall back to the non-prefiltered search when the box holds fewer than
            # the n requested: a box with 1..n-1 rows returned exactly those, however
            # far they were in 25-D and however many better matches lay outside it
            # (#5892).
            # #3705: cap at 5000 candidates so a library full of unusual
            # spectral profiles cannot degrade the similarity query into a
            # multi-second unbounded load. Distance ranking discards the
            # majority of candidates anyway. Combined with the #3683
            # root-cause fix (`limit is not None`), this guarantees
            # bounded latency.
            if len(candidates) < n:
                warning(
                    f"Prefiltering found {len(candidates)} of the {n} requested candidates, "
                    "falling back to full search"
                )
                all_fps = self.fingerprint_repo.get_all(limit=5000)
                candidates = [(fp.track_id, self.normalizer.normalize(fp.to_vector(), stats))
                             for fp in all_fps if fp.track_id != track_id]
        else:
            # Get all fingerprints (bounded — see fallback comment above)
            all_fps = self.fingerprint_repo.get_all(limit=5000)
            candidates = [(fp.track_id, self.normalizer.normalize(fp.to_vector(), stats))
                         for fp in all_fps if fp.track_id != track_id]

        if not candidates:
            warning("No candidate tracks found")
            return []

        debug(f"Finding similar tracks from {len(candidates)} candidates")

        # Calculate distances
        closest = self.distance_calc.find_closest_n(target_vector, candidates, n=n)

        # Convert to SimilarityResult objects
        results = []
        for track_id, distance in closest:
            similarity_score = self.distance_calc.calculate_similarity_score(distance, reference_distance)
            results.append(SimilarityResult(track_id, distance, similarity_score))

        info(f"Found {len(results)} similar tracks for track {track_id}")
        return results

    def calculate_similarity(self, track_id1: int, track_id2: int) -> SimilarityResult | None:
        """
        Calculate similarity between two specific tracks

        Args:
            track_id1: First track ID
            track_id2: Second track ID

        Returns:
            SimilarityResult or None if fingerprints not found
        """
        if not self.fitted:
            error("Similarity system not fitted. Call fit() first.")
            return None

        # Get fingerprints
        fp1 = self.fingerprint_repo.get_by_track_id(track_id1)
        fp2 = self.fingerprint_repo.get_by_track_id(track_id2)

        if not fp1 or not fp2:
            warning(f"Fingerprint(s) not found for tracks {track_id1}, {track_id2}")
            return None

        # Normalize both against one model, and scale with that model's reference (#6573)
        stats, reference_distance = self.fitted_model
        vec1 = self.normalizer.normalize(fp1.to_vector(), stats)
        vec2 = self.normalizer.normalize(fp2.to_vector(), stats)

        # Calculate distance
        distance = self.distance_calc.calculate(vec1, vec2)
        similarity_score = self.distance_calc.calculate_similarity_score(distance, reference_distance)

        return SimilarityResult(track_id2, distance, similarity_score)

    def is_fitted(self) -> bool:
        """Check if similarity system is fitted and ready"""
        return self.fitted

    def get_similarity_explanation(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        return get_similarity_explanation(self, *args, **kwargs)

    def _get_prefiltered_candidates(self, *args: Any, **kwargs: Any) -> list[tuple[int, np.ndarray]]:
        return get_prefiltered_candidates(self, *args, **kwargs)
