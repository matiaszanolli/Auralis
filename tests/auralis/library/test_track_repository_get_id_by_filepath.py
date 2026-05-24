"""
Regression test for TrackRepository.get_id_by_filepath (#3475).

Confirms the id-only lookup used by FingerprintService returns the matching
Track.id, or None when no track exists at that path. Added when
fingerprint_service.py was migrated off direct ``session.execute(select(Track.id))``.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def _seed_track(track_repository):
    track = track_repository.add({
        'title': 'Seed',
        'filepath': '/audio/seed.wav',
        'duration': 1.0,
        'sample_rate': 44100,
        'channels': 2,
        'format': 'WAV',
        'artists': ['Seed Artist'],
    })
    assert track is not None
    return track


def test_returns_id_for_existing_track(track_repository, _seed_track):
    assert track_repository.get_id_by_filepath('/audio/seed.wav') == _seed_track.id


def test_returns_none_for_missing_track(track_repository):
    assert track_repository.get_id_by_filepath('/audio/missing.wav') is None


def test_returns_none_for_empty_string(track_repository, _seed_track):
    assert track_repository.get_id_by_filepath('') is None
