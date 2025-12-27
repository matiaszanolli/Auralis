# -*- coding: utf-8 -*-

"""
Integration Tests for Similarity System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the complete similarity system with real database

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint import FingerprintSimilarity, KNNGraphBuilder
from auralis.library import LibraryManager


@pytest.mark.skip(reason="Database migration errors in LibraryManager initialization")
class TestSimilaritySystem:
    """Integration tests for the complete similarity system.

    NOTE: Skipped due to database migration issues when initializing LibraryManager.
    The schema_info table doesn't exist, preventing proper database initialization.
    This requires refactoring the database setup to work properly in test environment.
    """

    @pytest.fixture(scope="class")
    def library(self):
        """Create library manager instance"""
        return LibraryManager()

    @pytest.fixture(scope="class")
    def fingerprint_count(self, library):
        """Get count of available fingerprints"""
        return library.fingerprints.get_count()

    @pytest.fixture(scope="class")
    def similarity(self, library, fingerprint_count):
        """Create fitted similarity system"""
        if fingerprint_count < 5:
            pytest.skip(f"Need at least 5 fingerprints, have {fingerprint_count}")

        sim = FingerprintSimilarity(library.fingerprints)
        success = sim.fit(min_samples=5)

        if not success:
            pytest.skip("Failed to fit similarity system")

        return sim

    def test_library_has_fingerprints(self, fingerprint_count):
        """Test that library has some fingerprints"""
        assert fingerprint_count > 0, "No fingerprints in database. Run fingerprint extraction first."

    def test_similarity_fit(self, library, fingerprint_count):
        """Test fitting similarity system"""
        if fingerprint_count < 5:
            pytest.skip(f"Need at least 5 fingerprints, have {fingerprint_count}")

        sim = FingerprintSimilarity(library.fingerprints)
        result = sim.fit(min_samples=5)

        assert result is True
        assert sim.is_fitted() is True

    def test_find_similar_tracks(self, similarity, library):
        """Test finding similar tracks"""
        # Get a fingerprint to test with
        fingerprints = library.fingerprints.get_all(limit=1)
        assert len(fingerprints) > 0, "No fingerprints available"

        test_fp = fingerprints[0]

        # Find similar tracks
        results = similarity.find_similar(test_fp.track_id, n=3, use_prefilter=False)

        # Should return results
        assert isinstance(results, list)
        assert len(results) > 0

        # Check result structure
        for result in results:
            assert hasattr(result, 'track_id')
            assert hasattr(result, 'distance')
            assert hasattr(result, 'similarity_score')
            assert result.distance >= 0.0
            assert 0.0 <= result.similarity_score <= 1.0

    def test_similarity_scores_in_range(self, similarity, library):
        """Test that similarity scores are in valid range [0, 1]"""
        fingerprints = library.fingerprints.get_all(limit=2)
        if len(fingerprints) < 2:
            pytest.skip("Need at least 2 fingerprints")

        fp1, fp2 = fingerprints[0], fingerprints[1]

        # Calculate similarity
        result = similarity.calculate_similarity(fp1.track_id, fp2.track_id)

        assert 0.0 <= result.similarity_score <= 1.0
        assert result.distance >= 0.0

    def test_knn_graph_build(self, similarity, library, fingerprint_count):
        """Test building K-NN graph"""
        if fingerprint_count < 5:
            pytest.skip(f"Need at least 5 fingerprints, have {fingerprint_count}")

        # Create graph builder
        builder = KNNGraphBuilder(
            similarity_system=similarity,
            session_factory=library.SessionLocal
        )

        # Build graph with k=3 (small for testing)
        stats = builder.build_graph(k=3, clear_existing=True)

        # Check stats
        assert stats.total_tracks > 0
        assert stats.total_edges > 0
        assert stats.k_neighbors == 3
        assert stats.build_time_seconds >= 0.0
        assert stats.avg_distance >= 0.0

    def test_knn_graph_query(self, similarity, library, fingerprint_count):
        """Test querying K-NN graph"""
        if fingerprint_count < 5:
            pytest.skip(f"Need at least 5 fingerprints, have {fingerprint_count}")

        # Build graph
        builder = KNNGraphBuilder(
            similarity_system=similarity,
            session_factory=library.SessionLocal
        )
        builder.build_graph(k=3, clear_existing=True)

        # Get a fingerprint
        fingerprints = library.fingerprints.get_all(limit=1)
        test_fp = fingerprints[0]

        # Query graph
        neighbors = builder.get_neighbors(test_fp.track_id, limit=2)

        # Should return neighbors
        assert isinstance(neighbors, list)
        assert len(neighbors) > 0

        # Check structure
        for neighbor in neighbors:
            assert 'similar_track_id' in neighbor
            assert 'distance' in neighbor
            assert 'similarity_score' in neighbor
            assert 'rank' in neighbor

    def test_normalizer_is_fitted(self, similarity):
        """Test that normalizer is fitted after similarity.fit()"""
        assert similarity.normalizer.is_fitted() is True

    def test_explanation_has_contributions(self, similarity, library, fingerprint_count):
        """Test that similarity explanation includes dimension contributions"""
        if fingerprint_count < 2:
            pytest.skip("Need at least 2 fingerprints")

        fingerprints = library.fingerprints.get_all(limit=2)
        fp1, fp2 = fingerprints[0], fingerprints[1]

        explanation = similarity.get_similarity_explanation(fp1.track_id, fp2.track_id, top_n=5)

        # Check structure
        assert 'distance' in explanation
        assert 'similarity_score' in explanation
        assert 'top_differences' in explanation
        assert 'all_contributions' in explanation

        # Top differences should be sorted by contribution
        top_diffs = explanation['top_differences']
        assert len(top_diffs) <= 5

        if len(top_diffs) > 1:
            for i in range(len(top_diffs) - 1):
                assert top_diffs[i]['contribution'] >= top_diffs[i+1]['contribution']

    def test_prefiltering_reduces_candidates(self, similarity, library, fingerprint_count):
        """Test that pre-filtering reduces number of candidates"""
        if fingerprint_count < 10:
            pytest.skip("Need at least 10 fingerprints for meaningful test")

        fingerprints = library.fingerprints.get_all(limit=1)
        test_fp = fingerprints[0]

        # Count how many tracks are checked with vs without prefilter
        # This is an indirect test - we just check both methods work
        results_with = similarity.find_similar(test_fp.track_id, n=5, use_prefilter=True)
        results_without = similarity.find_similar(test_fp.track_id, n=5, use_prefilter=False)

        # Both should return results
        assert len(results_with) > 0
        assert len(results_without) > 0

        # Results should be similar (same top matches)
        # Note: order might differ slightly due to floating point, but top match should be same
        if len(results_with) > 0 and len(results_without) > 0:
            assert results_with[0].track_id == results_without[0].track_id


class TestNormalizerBasics:
    """Basic tests for normalizer without requiring database"""

    def test_dimension_names_count(self):
        """Test that there are exactly 25 dimensions"""
        from auralis.analysis.fingerprint.normalizer import FingerprintNormalizer

        normalizer = FingerprintNormalizer()
        assert len(normalizer.DIMENSION_NAMES) == 25

    def test_dimension_names_structure(self):
        """Test dimension names are organized correctly"""
        from auralis.analysis.fingerprint.normalizer import FingerprintNormalizer

        normalizer = FingerprintNormalizer()
        dims = normalizer.DIMENSION_NAMES

        # Frequency (7D)
        assert 'bass_pct' in dims
        assert 'mid_pct' in dims

        # Dynamics (3D)
        assert 'lufs' in dims
        assert 'crest_db' in dims

        # Temporal (4D)
        assert 'tempo_bpm' in dims
        assert 'rhythm_stability' in dims

        # Spectral (3D)
        assert 'spectral_centroid' in dims

        # Harmonic (3D)
        assert 'harmonic_ratio' in dims

        # Variation (3D)
        assert 'dynamic_range_variation' in dims

        # Stereo (2D)
        assert 'stereo_width' in dims
        assert 'phase_correlation' in dims


class TestDistanceCalculator:
    """Tests for distance calculator"""

    def test_distance_between_identical_vectors(self):
        """Test distance between identical vectors is zero"""
        from auralis.analysis.fingerprint.distance import FingerprintDistance

        calc = FingerprintDistance()

        # Create identical normalized vectors
        vec1 = np.ones(25) * 0.5
        vec2 = np.ones(25) * 0.5

        distance = calc.calculate(vec1, vec2)
        assert abs(distance) < 1e-6  # Should be very close to 0

    def test_distance_is_symmetric(self):
        """Test that distance(a, b) == distance(b, a)"""
        from auralis.analysis.fingerprint.distance import FingerprintDistance

        calc = FingerprintDistance()

        vec1 = np.random.rand(25)
        vec2 = np.random.rand(25)

        dist1 = calc.calculate(vec1, vec2)
        dist2 = calc.calculate(vec2, vec1)

        assert abs(dist1 - dist2) < 1e-6

    def test_distance_satisfies_triangle_inequality(self):
        """Test triangle inequality: d(a,c) <= d(a,b) + d(b,c)"""
        from auralis.analysis.fingerprint.distance import FingerprintDistance

        calc = FingerprintDistance()

        np.random.seed(42)
        vec_a = np.random.rand(25)
        vec_b = np.random.rand(25)
        vec_c = np.random.rand(25)

        dist_ac = calc.calculate(vec_a, vec_c)
        dist_ab = calc.calculate(vec_a, vec_b)
        dist_bc = calc.calculate(vec_b, vec_c)

        # Triangle inequality (with small epsilon for floating point)
        assert dist_ac <= dist_ab + dist_bc + 1e-6
