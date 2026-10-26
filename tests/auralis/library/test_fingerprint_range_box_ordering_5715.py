"""
Regression: get_by_multi_dimension_range orders the box, so `limit` keeps the nearest (#5715)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The query had no ORDER BY, so `limit=n * prefilter_factor` returned the lowest
rowids -- the oldest fingerprints -- and dropped the true nearest neighbours of
any box holding more than `limit` rows.
"""

import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.library.models import Track, TrackFingerprint

BOX = {
    'lufs': (-17.0, -11.0),          # centre -14, half-width 3
    'crest_db': (10.0, 14.0),        # centre 12, half-width 2
    'bass_pct': (0.12, 0.28),        # centre 0.20
    'tempo_bpm': (105.0, 135.0),     # centre 120
}


def _insert(db, track_id: int, offset: float) -> None:
    """Fingerprint whose four filtered dimensions sit `offset` box-widths off centre."""
    with db.SessionLocal() as session:
        session.add(Track(
            id=track_id, filepath=f"/tmp/t{track_id}.flac", title=f"T{track_id}",
            duration=120.0, sample_rate=44100, channels=2, format="FLAC",
        ))
        session.add(TrackFingerprint(
            track_id=track_id,
            sub_bass_pct=0.05, bass_pct=0.20 + 0.08 * offset, low_mid_pct=0.15, mid_pct=0.25,
            upper_mid_pct=0.15, presence_pct=0.10, air_pct=0.10,
            lufs=-14.0 + 3.0 * offset, crest_db=12.0 + 2.0 * offset, bass_mid_ratio=0.0,
            tempo_bpm=120.0 + 15.0 * offset, rhythm_stability=0.7, transient_density=0.4,
            silence_ratio=0.02, spectral_centroid=0.4, spectral_rolloff=0.5,
            spectral_flatness=0.2, harmonic_ratio=0.7, pitch_stability=0.7,
            chroma_energy=0.6, dynamic_range_variation=0.3, loudness_variation_std=1.5,
            peak_consistency=0.7, stereo_width=0.4, phase_correlation=0.8,
            fingerprint_version=FINGERPRINT_ALGORITHM_VERSION,
        ))
        session.commit()


def _populate(db, order: list[int]) -> None:
    # offset = id / 300 of a box half-width, so id 1 is the nearest to centre
    for track_id in order:
        _insert(db, track_id, offset=0.9 * track_id / 300)


class TestRangeBoxOrdering:
    def test_limit_keeps_nearest_even_when_inserted_last(self, library_database):
        _populate(library_database, list(range(300, 0, -1)))  # nearest inserted last

        got = library_database.fingerprints.get_by_multi_dimension_range(BOX, limit=100)

        assert [fp.track_id for fp in got] == list(range(1, 101))

    def test_result_independent_of_insertion_order(self, library_database):
        _populate(library_database, list(range(1, 301)))
        forward = [fp.track_id for fp in
                   library_database.fingerprints.get_by_multi_dimension_range(BOX, limit=100)]
        assert forward == list(range(1, 101))

    def test_unlimited_query_is_ordered_too(self, library_database):
        _populate(library_database, [5, 3, 9, 1, 7])

        got = library_database.fingerprints.get_by_multi_dimension_range(BOX)

        assert [fp.track_id for fp in got] == [1, 3, 5, 7, 9]

    def test_dimensions_are_scaled_by_tolerance(self, library_database):
        """A tempo gap of 14 BPM (0.93 of its tolerance) is farther than a 1 dB
        lufs gap (0.33 of its), though 14 > 1 in raw units."""
        _insert(library_database, 1, 0.0)
        with library_database.SessionLocal() as session:
            for tid, field, delta in ((2, 'tempo_bpm', 14.0), (3, 'lufs', 1.0)):
                _insert(library_database, tid, 0.0)
                fp = session.get(TrackFingerprint, tid)
                setattr(fp, field, getattr(fp, field) + delta)
            session.commit()

        got = library_database.fingerprints.get_by_multi_dimension_range(BOX)

        assert [fp.track_id for fp in got] == [1, 3, 2]

    def test_ties_break_on_track_id(self, library_database):
        for tid in (4, 2, 3):
            _insert(library_database, tid, 0.0)

        got = library_database.fingerprints.get_by_multi_dimension_range(BOX)

        assert [fp.track_id for fp in got] == [2, 3, 4]

    def test_box_tolerances_unchanged(self, library_database):
        _insert(library_database, 1, 0.99)
        _insert(library_database, 2, 1.01)  # just outside on every dimension

        got = library_database.fingerprints.get_by_multi_dimension_range(BOX)

        assert [fp.track_id for fp in got] == [1]


@pytest.mark.parametrize("limit", [1, 10])
def test_find_similar_prefilter_returns_nearest(library_database, limit):
    """End to end through the prefilter: the true neighbour is a candidate."""
    from auralis.analysis.fingerprint.similarity_explanation import get_prefiltered_candidates
    _populate(library_database, list(range(120, 0, -1)))

    class _Sim:
        fingerprint_repo = library_database.fingerprints

        class normalizer:
            @staticmethod
            def normalize(vec):
                return vec

    target = library_database.fingerprints.get_by_track_id(1)
    cands = get_prefiltered_candidates(_Sim, target, max_candidates=limit + 1)

    assert [tid for tid, _ in cands][:limit] == list(range(2, 2 + limit))
