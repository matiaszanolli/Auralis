"""
Regression tests for #4822 — placeholder/stale fingerprints leaking into reads
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

FingerprintSchedulerRepository.claim_next_unfingerprinted_track() inserts a
placeholder TrackFingerprint row (all dimensions zeroed, lufs=-100.0 sentinel)
the moment a track is claimed for processing; claim_next_outdated_fingerprint()
marks re-fingerprinting claims with a fingerprint_version below the current
algorithm version. Before the fix, only FingerprintService's mastering-path
cache lookup filtered these out — every FingerprintRepository read method
(exists, get_by_track_id, get_all, get_by_track_ids,
get_by_multi_dimension_range) served them as if they were valid, feeding
all-zero vectors into similarity search, the K-NN graph builder, and the
normalizer's percentile fit.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.library.models import Track
from auralis.library.repositories.fingerprint_repository import is_current_fingerprint

_DIMS: dict = {
    'sub_bass_pct': 0.1, 'bass_pct': 0.2, 'low_mid_pct': 0.15,
    'mid_pct': 0.25, 'upper_mid_pct': 0.1, 'presence_pct': 0.1, 'air_pct': 0.1,
    'crest_db': 6.0, 'bass_mid_ratio': 0.8,
    'tempo_bpm': 120.0, 'rhythm_stability': 0.9, 'transient_density': 0.5,
    'silence_ratio': 0.05, 'spectral_centroid': 3000.0, 'spectral_rolloff': 8000.0,
    'spectral_flatness': 0.3, 'harmonic_ratio': 0.7, 'pitch_stability': 0.85,
    'chroma_energy': 0.6, 'dynamic_range_variation': 3.0,
    'loudness_variation_std': 1.5, 'peak_consistency': 0.9,
    'stereo_width': 0.5, 'phase_correlation': 0.95,
}


def _make_track(session_factory, title: str) -> int:
    with session_factory() as s:
        track = Track(title=title, filepath=f"/tmp/{title}.flac")
        s.add(track)
        s.commit()
        return int(track.id)


def _insert_fingerprint(session_factory, track_id: int, *, lufs: float, version: int) -> None:
    """Insert a raw TrackFingerprint row via the ORM, bypassing the repository
    under test so the fixture setup can't accidentally rely on the guard."""
    from auralis.library.models import TrackFingerprint

    with session_factory() as s:
        fp = TrackFingerprint(
            track_id=track_id,
            lufs=lufs,
            fingerprint_version=version,
            **_DIMS,
        )
        s.add(fp)
        s.commit()


@pytest.fixture
def valid_track_id(session_factory) -> int:
    tid = _make_track(session_factory, "valid")
    _insert_fingerprint(session_factory, tid, lufs=-14.0, version=FINGERPRINT_ALGORITHM_VERSION)
    return tid


@pytest.fixture
def placeholder_track_id(session_factory) -> int:
    """Mirrors claim_next_unfingerprinted_track()'s placeholder row exactly."""
    tid = _make_track(session_factory, "placeholder")
    _insert_fingerprint(session_factory, tid, lufs=-100.0, version=FINGERPRINT_ALGORITHM_VERSION)
    return tid


@pytest.fixture
def stale_version_track_id(session_factory) -> int:
    tid = _make_track(session_factory, "stale")
    _insert_fingerprint(session_factory, tid, lufs=-12.0, version=FINGERPRINT_ALGORITHM_VERSION - 1)
    return tid


class TestIsCurrentFingerprint:
    """Unit tests for the shared Python-level predicate."""

    def test_none_is_not_current(self):
        assert is_current_fingerprint(None) is False

    def test_placeholder_sentinel_is_not_current(self, session_factory, placeholder_track_id):
        with session_factory() as s:
            from auralis.library.models import TrackFingerprint
            fp = s.query(TrackFingerprint).filter_by(track_id=placeholder_track_id).one()
            assert is_current_fingerprint(fp) is False

    def test_stale_version_is_not_current(self, session_factory, stale_version_track_id):
        with session_factory() as s:
            from auralis.library.models import TrackFingerprint
            fp = s.query(TrackFingerprint).filter_by(track_id=stale_version_track_id).one()
            assert is_current_fingerprint(fp) is False

    def test_valid_row_is_current(self, session_factory, valid_track_id):
        with session_factory() as s:
            from auralis.library.models import TrackFingerprint
            fp = s.query(TrackFingerprint).filter_by(track_id=valid_track_id).one()
            assert is_current_fingerprint(fp) is True


class TestExistsExcludesPlaceholderAndStale:
    def test_placeholder_reports_not_exists(self, fingerprint_repository, placeholder_track_id):
        assert fingerprint_repository.exists(placeholder_track_id) is False

    def test_stale_version_reports_not_exists(self, fingerprint_repository, stale_version_track_id):
        assert fingerprint_repository.exists(stale_version_track_id) is False

    def test_valid_reports_exists(self, fingerprint_repository, valid_track_id):
        assert fingerprint_repository.exists(valid_track_id) is True


class TestGetByTrackIdExcludesPlaceholderAndStale:
    def test_placeholder_returns_none(self, fingerprint_repository, placeholder_track_id):
        assert fingerprint_repository.get_by_track_id(placeholder_track_id) is None

    def test_stale_version_returns_none(self, fingerprint_repository, stale_version_track_id):
        assert fingerprint_repository.get_by_track_id(stale_version_track_id) is None

    def test_valid_returns_row(self, fingerprint_repository, valid_track_id):
        fp = fingerprint_repository.get_by_track_id(valid_track_id)
        assert fp is not None
        assert fp.track_id == valid_track_id


class TestGetByTrackIdsExcludesPlaceholderAndStale:
    def test_mixed_batch_only_returns_valid(
        self, fingerprint_repository, valid_track_id, placeholder_track_id, stale_version_track_id
    ):
        results = fingerprint_repository.get_by_track_ids(
            [valid_track_id, placeholder_track_id, stale_version_track_id]
        )
        returned_ids = {fp.track_id for fp in results}
        assert returned_ids == {valid_track_id}


class TestGetAllExcludesPlaceholderAndStale:
    def test_only_valid_rows_returned(
        self, fingerprint_repository, valid_track_id, placeholder_track_id, stale_version_track_id
    ):
        results = fingerprint_repository.get_all()
        returned_ids = {fp.track_id for fp in results}
        assert valid_track_id in returned_ids
        assert placeholder_track_id not in returned_ids
        assert stale_version_track_id not in returned_ids


class TestGetByMultiDimensionRangeExcludesPlaceholderAndStale:
    def test_wide_open_range_still_excludes_placeholder_and_stale(
        self, fingerprint_repository, valid_track_id, placeholder_track_id, stale_version_track_id
    ):
        # A deliberately wide lufs range that WOULD include the -100.0
        # placeholder sentinel by value alone — the version/placeholder
        # guard must still exclude it.
        results = fingerprint_repository.get_by_multi_dimension_range(
            {'lufs': (-200.0, 0.0)}
        )
        returned_ids = {fp.track_id for fp in results}
        assert valid_track_id in returned_ids
        assert placeholder_track_id not in returned_ids
        assert stale_version_track_id not in returned_ids
