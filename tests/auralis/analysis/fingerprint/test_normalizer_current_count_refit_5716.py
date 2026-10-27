"""
Regression: the normalizer gates on current rows and refits when the library grows (#5716)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`fit()` counted every `track_fingerprints` row (claim placeholders and stale
versions included) while `get_all()` / `get_batch_after_id()` returned only
current ones, so right after an algorithm bump it published `DimensionStats`
from a handful of vectors. `FingerprintSimilarity.fit()` then returned True
forever on `self.fitted`.
"""

import numpy as np
import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.analysis.fingerprint.normalizer import FingerprintNormalizer
from auralis.analysis.fingerprint.similarity import (
    REFIT_GROWTH_FACTOR,
    FingerprintSimilarity,
)
from auralis.library.models import Track, TrackFingerprint

N_DIMS = len(FingerprintNormalizer.DIMENSION_NAMES)


def _add(db, track_id: int, *, version: int = FINGERPRINT_ALGORITHM_VERSION, spread: float = 0.0):
    """One fingerprint row; `spread` shifts lufs so refits visibly change the stats."""
    with db.SessionLocal() as session:
        session.add(Track(
            id=track_id, filepath=f"/tmp/t{track_id}.flac", title=f"T{track_id}",
            duration=120.0, sample_rate=44100, channels=2, format="FLAC",
        ))
        session.add(TrackFingerprint(
            track_id=track_id,
            sub_bass_pct=0.05, bass_pct=0.20, low_mid_pct=0.15, mid_pct=0.25,
            upper_mid_pct=0.15, presence_pct=0.10, air_pct=0.10,
            lufs=-14.0 + spread, crest_db=12.0, bass_mid_ratio=0.0,
            tempo_bpm=120.0, rhythm_stability=0.7, transient_density=0.4,
            silence_ratio=0.02, spectral_centroid=0.4, spectral_rolloff=0.5,
            spectral_flatness=0.2, harmonic_ratio=0.7, pitch_stability=0.7,
            chroma_energy=0.6, dynamic_range_variation=0.3, loudness_variation_std=1.5,
            peak_consistency=0.7, stereo_width=0.4, phase_correlation=0.8,
            fingerprint_version=version,
        ))
        session.commit()


class TestGetCountSemantics:
    def test_current_only_excludes_stale_versions(self, library_database):
        for i in range(1, 21):
            _add(library_database, i, version=0)
        for i in range(21, 24):
            _add(library_database, i)

        repo = library_database.fingerprints
        assert repo.get_count() == 23
        assert repo.get_count(current_only=True) == 3

    def test_current_only_excludes_claim_placeholders(self, library_database):
        _add(library_database, 1)
        _add(library_database, 2)
        with library_database.SessionLocal() as session:
            session.get(TrackFingerprint, 2).lufs = -100.0  # claim sentinel
            session.commit()

        assert library_database.fingerprints.get_count(current_only=True) == 1


class TestFitGate:
    def test_stale_table_with_few_current_rows_does_not_fit(self, library_database):
        for i in range(1, 21):
            _add(library_database, i, version=0)
        for i in range(21, 24):
            _add(library_database, i)

        normalizer = FingerprintNormalizer()
        assert normalizer.fit(library_database.fingerprints, min_samples=10) is False
        assert normalizer.fitted is False
        assert normalizer.stats == {}

    def test_fit_records_the_sample_it_was_computed_from(self, library_database):
        for i in range(1, 13):
            _add(library_database, i, spread=float(i))

        normalizer = FingerprintNormalizer()
        assert normalizer.fit(library_database.fingerprints, min_samples=10) is True
        assert normalizer.stats['lufs'].count == 12


class TestRefit:
    def _fitted(self, db, n: int) -> FingerprintSimilarity:
        for i in range(1, n + 1):
            _add(db, i, spread=float(i))
        sim = FingerprintSimilarity(db.fingerprints)
        assert sim.fit() is True
        return sim

    def test_no_refit_while_library_has_not_grown_enough(self, library_database):
        sim = self._fitted(library_database, 12)
        for i in range(13, 13 + 3):  # 15 < 12 * 1.5
            _add(library_database, i, spread=float(i))

        assert sim.needs_refit() is False
        assert sim.normalizer.stats['lufs'].count == 12
        assert sim.fit() is True
        assert sim.normalizer.stats['lufs'].count == 12

    def test_refit_after_growth_refreshes_the_statistics(self, library_database):
        sim = self._fitted(library_database, 12)
        before = sim.normalizer.stats['lufs'].max_val
        for i in range(13, 13 + 100):
            _add(library_database, i, spread=float(i))

        assert sim.needs_refit() is True
        assert sim.fit() is True
        assert sim.normalizer.stats['lufs'].count == 112
        assert sim.normalizer.stats['lufs'].max_val > before
        assert sim.needs_refit() is False

    def test_failed_refit_keeps_previous_statistics(self, library_database):
        sim = self._fitted(library_database, 12)
        old_stats = sim.normalizer.stats
        for i in range(13, 13 + 100):
            _add(library_database, i, spread=float(i))

        import threading
        stop = threading.Event()
        stop.set()
        assert sim.fit(stop_event=stop) is False
        assert sim.is_fitted() is True
        assert sim.normalizer.stats is old_stats

    def test_unknown_sample_never_triggers_refit(self):
        sim = FingerprintSimilarity(fingerprint_repository=object())
        sim.fitted = True
        assert sim.normalizer.stats == {}
        assert sim.needs_refit() is False

    def test_growth_factor_is_greater_than_one(self):
        assert REFIT_GROWTH_FACTOR > 1.0
