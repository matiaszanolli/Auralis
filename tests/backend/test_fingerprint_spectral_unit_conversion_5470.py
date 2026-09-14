"""
spectral_centroid/spectral_rolloff must be served in Hz, not the stored
normalized [0, 1] fraction (#5470).

`FingerprintVectorResponse` documents both fields as "(Hz)", and the
existing `centroid_to_hz()`/`rolloff_to_hz()` helpers (added for #4863)
exist for exactly this conversion -- but neither
`GET /api/tracks/{id}/fingerprint` nor `GET /api/albums/{id}/fingerprint`
called them, so a 0-1 fraction reached clients labeled and typed as Hz.
Every real track's centroid then clamped to the frontend's Hz-scale
display floor (fingerprintToGradient.ts / albumCharacterDescriptors.ts
already operate in Hz), so no album was ever tagged "Crisp".

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.analysis.fingerprint.schema import CENTROID_NORMALIZATION_HZ, ROLLOFF_NORMALIZATION_HZ

_ALL_DIMENSIONS = [
    'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
    'upper_mid_pct', 'presence_pct', 'air_pct', 'lufs',
    'crest_db', 'bass_mid_ratio', 'tempo_bpm',
    'rhythm_stability', 'transient_density', 'silence_ratio',
    'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
    'harmonic_ratio', 'pitch_stability', 'chroma_energy',
    'dynamic_range_variation', 'loudness_variation_std',
    'peak_consistency', 'stereo_width', 'phase_correlation',
]


def _fingerprint_mock(spectral_centroid=0.5, spectral_rolloff=0.5):
    fp = Mock()
    for col in _ALL_DIMENSIONS:
        setattr(fp, col, 0.5)
    fp.spectral_centroid = spectral_centroid
    fp.spectral_rolloff = spectral_rolloff
    return fp


class TestTrackFingerprintServesHz:
    """GET /api/tracks/{id}/fingerprint"""

    def test_spectral_centroid_and_rolloff_are_hz_scale(self, client):
        artist = Mock()
        artist.name = "Test Artist"
        track = Mock()
        track.id = 1
        track.title = "Test Track"
        track.artists = [artist]
        track.album = None

        repos = Mock()
        repos.tracks.get_by_id.return_value = track
        repos.fingerprints.get_by_track_id.return_value = _fingerprint_mock(
            spectral_centroid=0.5, spectral_rolloff=0.5
        )

        with patch('routers.fingerprint_status.require_repository_factory', return_value=repos):
            response = client.get("/api/tracks/1/fingerprint")

        assert response.status_code == 200
        fp = response.json()["fingerprint"]
        assert fp["spectral_centroid"] == pytest.approx(0.5 * CENTROID_NORMALIZATION_HZ)
        assert fp["spectral_rolloff"] == pytest.approx(0.5 * ROLLOFF_NORMALIZATION_HZ)
        # Confirms these are genuinely Hz-plausible, not a leftover fraction.
        assert 200 <= fp["spectral_centroid"] <= 15000
        assert 200 <= fp["spectral_rolloff"] <= 15000

    def test_other_dimensions_unaffected(self, client):
        artist = Mock()
        artist.name = "Test Artist"
        track = Mock()
        track.id = 1
        track.title = "Test Track"
        track.artists = [artist]
        track.album = None

        repos = Mock()
        repos.tracks.get_by_id.return_value = track
        repos.fingerprints.get_by_track_id.return_value = _fingerprint_mock()

        with patch('routers.fingerprint_status.require_repository_factory', return_value=repos):
            response = client.get("/api/tracks/1/fingerprint")

        fp = response.json()["fingerprint"]
        assert fp["lufs"] == 0.5
        assert fp["spectral_flatness"] == 0.5
