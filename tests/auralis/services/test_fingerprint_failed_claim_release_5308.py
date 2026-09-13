"""A failed fingerprint extraction releases its claim, boundedly (#5308).

Both claim methods commit a sentinel before extraction runs (a lufs=-100.0
placeholder row, or fingerprint_version=0 on an outdated row). On failure
``_process_track`` only logged, so the sentinel stayed, matched neither claim
query, and the track was not retried until the next app restart.

These tests use a real SQLite library and the real scheduler repository;
only the extractor is stubbed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.library.models import Track, TrackFingerprint
from auralis.library.repositories.fingerprint_scheduler_repository import (
    FingerprintSchedulerRepository,
)
from auralis.library.repositories.fingerprint_stats_repository import (
    FingerprintStatsRepository,
)
from auralis.services.fingerprint_queue import FingerprintExtractionQueue
from auralis.services.fingerprint_worker import MAX_EXTRACTION_ATTEMPTS

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


class _Extractor:
    """extract_and_store raises for the first ``failures`` calls, then succeeds."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def extract_and_store(self, track_id: int, filepath: str) -> bool:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("decode hiccup")
        return True


def _make_track(session_factory, title: str) -> int:
    with session_factory() as s:
        track = Track(title=title, filepath=f"/tmp/{title}.flac")
        s.add(track)
        s.commit()
        return int(track.id)


def _fingerprint_row(session_factory, track_id: int) -> TrackFingerprint | None:
    with session_factory() as s:
        return s.execute(
            select(TrackFingerprint).where(TrackFingerprint.track_id == track_id)
        ).scalars().first()


@pytest.fixture
def scheduler(session_factory) -> FingerprintSchedulerRepository:
    return FingerprintSchedulerRepository(session_factory)


def _queue(extractor: _Extractor, scheduler: FingerprintSchedulerRepository) -> FingerprintExtractionQueue:
    return FingerprintExtractionQueue(
        fingerprint_extractor=extractor,
        get_repository_factory=lambda: SimpleNamespace(fingerprint_scheduler=scheduler),
        num_workers=1,
        enable_adaptive_scaling=False,
        max_workers=1,
        track_timeout=5,
    )


def test_failed_extraction_makes_track_claimable_again(session_factory, scheduler) -> None:
    track_id = _make_track(session_factory, "transient")
    queue = _queue(_Extractor(failures=1), scheduler)

    claimed = scheduler.claim_next_unfingerprinted_track()
    assert claimed is not None and claimed.id == track_id
    queue._process_track(claimed, worker_id=0)

    assert queue.stats['failed'] == 1
    assert _fingerprint_row(session_factory, track_id) is None  # placeholder gone

    retried = scheduler.claim_next_unfingerprinted_track()
    assert retried is not None and retried.id == track_id
    queue._process_track(retried, worker_id=0)

    assert queue.stats['completed'] == 1
    assert queue._failed_attempts == {}


def test_permanently_failing_track_is_retried_a_bounded_number_of_times(
    session_factory, scheduler
) -> None:
    track_id = _make_track(session_factory, "broken")
    extractor = _Extractor(failures=10**6)
    queue = _queue(extractor, scheduler)

    # The worker loop, minus threads: claim until nothing is claimable.
    for _ in range(MAX_EXTRACTION_ATTEMPTS * 5):
        track = scheduler.claim_next_unfingerprinted_track()
        if track is None:
            break
        queue._process_track(track, worker_id=0)
    else:
        pytest.fail("failing track was re-claimed without bound")

    assert extractor.calls == MAX_EXTRACTION_ATTEMPTS
    row = _fingerprint_row(session_factory, track_id)
    assert row is not None and row.lufs == -100.0  # claim left for startup cleanup


@pytest.mark.skipif(
    FINGERPRINT_ALGORITHM_VERSION <= 1,
    reason="outdated claims only exist once the algorithm version has been bumped",
)
def test_failed_outdated_refingerprint_is_released(session_factory, scheduler) -> None:
    track_id = _make_track(session_factory, "outdated")
    with session_factory() as s:
        s.add(TrackFingerprint(
            track_id=track_id, lufs=-14.0,
            fingerprint_version=FINGERPRINT_ALGORITHM_VERSION - 1, **_DIMS,
        ))
        s.commit()
    queue = _queue(_Extractor(failures=1), scheduler)

    claimed = scheduler.claim_next_outdated_fingerprint(FINGERPRINT_ALGORITHM_VERSION)
    assert claimed is not None and claimed.id == track_id
    queue._process_track(claimed, worker_id=0)

    row = _fingerprint_row(session_factory, track_id)
    assert row is not None and row.fingerprint_version == 1 and row.lufs == -14.0
    retried = scheduler.claim_next_outdated_fingerprint(FINGERPRINT_ALGORITHM_VERSION)
    assert retried is not None and retried.id == track_id


def test_release_claim_leaves_a_real_fingerprint_untouched(session_factory, scheduler) -> None:
    track_id = _make_track(session_factory, "valid")
    with session_factory() as s:
        s.add(TrackFingerprint(
            track_id=track_id, lufs=-14.0,
            fingerprint_version=FINGERPRINT_ALGORITHM_VERSION, **_DIMS,
        ))
        s.commit()

    assert scheduler.release_claim(track_id) is False

    row = _fingerprint_row(session_factory, track_id)
    assert row is not None and row.lufs == -14.0
    assert row.fingerprint_version == FINGERPRINT_ALGORITHM_VERSION


def test_release_claim_is_scoped_to_one_track(session_factory, scheduler) -> None:
    first = _make_track(session_factory, "first")
    second = _make_track(session_factory, "second")
    assert scheduler.claim_next_unfingerprinted_track().id == first
    assert scheduler.claim_next_unfingerprinted_track().id == second

    assert scheduler.release_claim(first) is True

    assert _fingerprint_row(session_factory, first) is None
    assert _fingerprint_row(session_factory, second) is not None


def test_startup_cleanup_still_releases_every_claim(session_factory, scheduler) -> None:
    placeholder = _make_track(session_factory, "placeholder")
    outdated = _make_track(session_factory, "claimed-outdated")
    assert scheduler.claim_next_unfingerprinted_track().id == placeholder
    with session_factory() as s:
        s.add(TrackFingerprint(track_id=outdated, lufs=-14.0, fingerprint_version=0, **_DIMS))
        s.commit()

    assert FingerprintStatsRepository(session_factory).cleanup_incomplete_fingerprints() == 2

    assert _fingerprint_row(session_factory, placeholder) is None
    assert _fingerprint_row(session_factory, outdated).fingerprint_version == 1
