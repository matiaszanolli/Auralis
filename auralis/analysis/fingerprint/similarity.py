# -*- coding: utf-8 -*-

"""
Fingerprint Similarity API
~~~~~~~~~~~~~~~~~~~~~~~~~

High-level API for finding similar tracks using fingerprint-based similarity

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from .normalizer import FingerprintNormalizer
from .distance import FingerprintDistance, DimensionWeights
from ...utils.logging import info, warning, error, debug


class SimilarityResult:
    """Result of similarity search"""

    def __init__(self, track_id: int, distance: float, similarity_score: float):
        """
        Initialize similarity result

        Args:
            track_id: ID of the similar track
            distance: Fingerprint distance (lower = more similar)
            similarity_score: Similarity score 0-1 (higher = more similar)
        """
        self.track_id = track_id
        self.distance = distance
        self.similarity_score = similarity_score

    def to_dict(self) -> dict:
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

        # Save/load normalizer
        similarity.save_normalizer('stats.json')
        similarity.load_normalizer('stats.json')
    """

    def __init__(
        self,
        fingerprint_repository,
        weights: Optional[DimensionWeights] = None,
        use_robust_normalization: bool = True
    ):
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

    def fit(self, min_samples: int = 10) -> bool:
        """
        Calculate normalization statistics from library

        Args:
            min_samples: Minimum fingerprints required

        Returns:
            True if successful, False otherwise
        """
        info("Fitting similarity system to library fingerprints...")
        success = self.normalizer.fit(self.fingerprint_repo, min_samples=min_samples)

        if success:
            self.fitted = True
            info("Similarity system ready")
        else:
            error("Failed to fit similarity system")

        return success

    def find_similar(
        self,
        track_id: int,
        n: int = 10,
        use_prefilter: bool = True,
        prefilter_factor: int = 10
    ) -> List[SimilarityResult]:
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

        # Normalize target
        target_vector = self.normalizer.normalize(target_fp.to_vector())

        # Get candidates
        if use_prefilter:
            candidates = self._get_prefiltered_candidates(
                target_fp,
                max_candidates=n * prefilter_factor
            )
        else:
            # Get all fingerprints
            all_fps = self.fingerprint_repo.get_all()
            candidates = [(fp.track_id, self.normalizer.normalize(fp.to_vector()))
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
            similarity_score = self.distance_calc.calculate_similarity_score(distance)
            results.append(SimilarityResult(track_id, distance, similarity_score))

        info(f"Found {len(results)} similar tracks for track {track_id}")
        return results

    def calculate_similarity(self, track_id1: int, track_id2: int) -> Optional[SimilarityResult]:
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

        # Normalize
        vec1 = self.normalizer.normalize(fp1.to_vector())
        vec2 = self.normalizer.normalize(fp2.to_vector())

        # Calculate distance
        distance = self.distance_calc.calculate(vec1, vec2)
        similarity_score = self.distance_calc.calculate_similarity_score(distance)

        return SimilarityResult(track_id2, distance, similarity_score)

    def get_similarity_explanation(
        self,
        track_id1: int,
        track_id2: int,
        top_n: int = 5
    ) -> Optional[Dict]:
        """
        Get detailed explanation of why two tracks are similar/different

        Args:
            track_id1: First track ID
            track_id2: Second track ID
            top_n: Number of top contributing dimensions to return

        Returns:
            Dictionary with similarity details and top contributors
        """
        if not self.fitted:
            error("Similarity system not fitted. Call fit() first.")
            return None

        # Get fingerprints
        fp1 = self.fingerprint_repo.get_by_track_id(track_id1)
        fp2 = self.fingerprint_repo.get_by_track_id(track_id2)

        if not fp1 or not fp2:
            return None

        # Normalize
        vec1 = self.normalizer.normalize(fp1.to_vector())
        vec2 = self.normalizer.normalize(fp2.to_vector())

        # Calculate overall similarity
        distance = self.distance_calc.calculate(vec1, vec2)
        similarity_score = self.distance_calc.calculate_similarity_score(distance)

        # Get dimension contributions
        contributions = self.distance_calc.get_dimension_contributions(vec1, vec2)

        # Sort by contribution
        sorted_dims = sorted(contributions.items(), key=lambda x: x[1], reverse=True)

        return {
            'track_id1': track_id1,
            'track_id2': track_id2,
            'distance': distance,
            'similarity_score': similarity_score,
            'top_differences': [
                {'dimension': dim, 'contribution': float(contrib)}
                for dim, contrib in sorted_dims[:top_n]
            ],
            'all_contributions': {dim: float(contrib) for dim, contrib in contributions.items()}
        }

    def _get_prefiltered_candidates(
        self,
        target_fp,
        max_candidates: int = 100
    ) -> List[Tuple[int, np.ndarray]]:
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
            'bass_pct': (target_fp.bass_pct - 8.0, target_fp.bass_pct + 8.0),  # ±8%
            'tempo_bpm': (target_fp.tempo_bpm - 15.0, target_fp.tempo_bpm + 15.0)  # ±15 BPM
        }

        # Get candidates within ranges
        candidates_fps = self.fingerprint_repo.get_by_multi_dimension_range(
            ranges,
            limit=max_candidates
        )

        # Normalize and convert to (track_id, vector) tuples
        candidates = [
            (fp.track_id, self.normalizer.normalize(fp.to_vector()))
            for fp in candidates_fps
            if fp.track_id != target_fp.track_id  # Exclude target itself
        ]

        debug(f"Pre-filtering: {len(candidates)} candidates (from ranges)")
        return candidates

    def save_normalizer(self, filepath: str) -> bool:
        """
        Save normalization statistics to file

        Args:
            filepath: Path to save statistics

        Returns:
            True if successful, False otherwise
        """
        return self.normalizer.save(filepath)

    def load_normalizer(self, filepath: str) -> bool:
        """
        Load normalization statistics from file

        Args:
            filepath: Path to load statistics from

        Returns:
            True if successful, False otherwise
        """
        success = self.normalizer.load(filepath)
        if success:
            self.fitted = True
        return success

    def is_fitted(self) -> bool:
        """Check if similarity system is fitted and ready"""
        return self.fitted
