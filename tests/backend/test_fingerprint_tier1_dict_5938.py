"""
Tier-1 DB fingerprint load returns the 25D dict (#5938)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``load_from_database()`` constructed ``MasteringFingerprint(**fp_dict)``
with the 25 fingerprint columns against a 7-field dataclass of *different*
names — TypeError, swallowed by the blanket except at DEBUG, so the
database tier of the three-tier hierarchy always missed silently
(regression of #4578's wiring fix). Every library-fingerprinted track
streamed without DB-derived fixed mastering targets and nothing logged it.

The fix returns the dict itself — the shape Tiers 2/3 already return and
``generate_targets_from_fingerprint`` consumes — and logs tier failures at
WARNING. The recommendation path (chunk_mastering) now extracts its own
7-field MasteringFingerprint instead of receiving the dict (#5952 sibling).
"""

import sys
from pathlib import Path

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.fingerprint_loading import load_from_database  # noqa: E402
from core.mastering_target_service import MasteringTargetService  # noqa: E402

from auralis.library.database import LibraryDatabase  # noqa: E402


def _track_info(path: Path) -> dict:
    return {
        'title': 'Tier One', 'filepath': str(path), 'sample_rate': 44100,
        'channels': 2, 'format': 'FLAC', 'artists': ['Artist'],
        'genres': ['Rock'], 'album': 'Album',
    }


def _fingerprint_25d() -> dict[str, float]:
    return {
        'sub_bass_pct': 0.10, 'bass_pct': 0.30, 'low_mid_pct': 0.10,
        'mid_pct': 0.20, 'upper_mid_pct': 0.12, 'presence_pct': 0.10,
        'air_pct': 0.03, 'lufs': -16.5, 'crest_db': 13.2,
        'bass_mid_ratio': 0.5, 'tempo_bpm': 120.0, 'rhythm_stability': 0.5,
        'transient_density': 0.5, 'silence_ratio': 0.02,
        'spectral_centroid': 2400.0, 'spectral_rolloff': 8000.0,
        'spectral_flatness': 0.3, 'harmonic_ratio': 0.5,
        'pitch_stability': 0.7, 'chroma_energy': 0.5,
        'dynamic_range_variation': 0.3, 'loudness_variation_std': 2.0,
        'peak_consistency': 0.8, 'stereo_width': 0.5,
        'phase_correlation': 0.8,
    }


@pytest.fixture
def db_with_fingerprint(tmp_path: Path):
    db = LibraryDatabase(database_path=str(tmp_path / 'lib.db'))
    track = db.tracks.add(_track_info(tmp_path / 'one.flac'))
    row = db.fingerprints.upsert(int(track.id), _fingerprint_25d())
    assert row is not None
    yield db, int(track.id), str(tmp_path / 'one.flac')
    db.shutdown()


def test_load_from_database_returns_the_25d_dict(db_with_fingerprint):
    """The real row path — no patched loader, no stub repository."""
    db, track_id, _ = db_with_fingerprint

    result = load_from_database(lambda: db.fingerprints, track_id)

    assert result is not None, "Tier 1 must hit for a track with a row (#5938)"
    assert result['lufs'] == pytest.approx(-16.5)
    assert result['crest_db'] == pytest.approx(13.2)
    assert 'sub_bass_pct' in result
    # Same shape as Tier 2/3: a plain dict, not MasteringFingerprint.
    assert isinstance(result, dict)


def test_load_fingerprint_tier1_end_to_end(db_with_fingerprint):
    """MasteringTargetService.load_fingerprint answers from Tier 1 with
    derived targets and never touches the .25d store."""
    from unittest.mock import patch

    from auralis.analysis.fingerprint import FingerprintStorage

    db, track_id, filepath = db_with_fingerprint
    service = MasteringTargetService(
        get_fingerprints_repository=lambda: db.fingerprints
    )

    with patch.object(FingerprintStorage, 'load', side_effect=AssertionError(
        "Tier 2 must not be consulted when Tier 1 hits"
    )):
        result = service.load_fingerprint(
            track_id=track_id, filepath=filepath, extract_if_missing=False
        )

    assert result is not None
    fingerprint, targets = result
    assert fingerprint['lufs'] == pytest.approx(-16.5)
    # generate_targets_from_fingerprint consumes the dict: derived targets
    # exist and are track-wide constants.
    assert targets is not None and targets != {}
    assert 'target_lufs' in targets


def test_missing_row_returns_none(db_with_fingerprint):
    db, _, _ = db_with_fingerprint
    assert load_from_database(lambda: db.fingerprints, 424242) is None


def test_recommendation_path_handles_a_dict_fingerprint(tmp_path, monkeypatch):
    """#5952 sibling: with Tier 1 live, processor.fingerprint is the 25D dict;
    the recommendation path must extract its own 7-field object instead of
    crashing on attribute access."""
    from core import chunk_mastering as cm
    from auralis.analysis.mastering_fingerprint import MasteringFingerprint

    def _mf() -> MasteringFingerprint:
        return MasteringFingerprint(
            loudness_dbfs=-16.0, peak_dbfs=-1.0, crest_db=15.0,
            spectral_centroid=2000.0, spectral_rolloff=9000.0,
            zero_crossing_rate=0.05, spectral_spread=1200.0,
        )

    class FakeEngine:
        def recommend_weighted(self, fingerprint, confidence_threshold=0.4):
            # Proves the engine received the 7-field object, not the dict.
            assert isinstance(fingerprint, MasteringFingerprint)
            rec = type('Rec', (), {})()
            rec.primary_profile = type('P', (), {'name': 'balanced'})()
            rec.confidence_score = 0.9
            rec.weighted_profiles = []
            return rec

    class FakeProcessor:
        filepath = str(tmp_path / 'x.flac')
        fingerprint = _fingerprint_25d()  # the dict — the crash input
        mastering_recommendation = None
        adaptive_mastering_engine = FakeEngine()

    called = {}

    def _fake_from_file(cls, path, sr=44100):
        called['path'] = path
        return _mf()

    monkeypatch.setattr(
        cm.MasteringFingerprint, 'from_audio_file',
        classmethod(_fake_from_file),
    )

    processor = FakeProcessor()
    rec = cm.compute_mastering_recommendation(processor)
    assert rec is not None
    assert called['path'] == processor.filepath
    # The 25D dict is preserved for the fixed-target path.
    assert isinstance(processor.fingerprint, dict)
