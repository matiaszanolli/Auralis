# -*- coding: utf-8 -*-

"""
Tests for FingerprintRepository SQLAlchemy-only DB access (issue #2298)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Previously these tests verified that raw sqlite3 writes respected a custom
db_path.  After the fix (#2431 / #2298) all three write methods (upsert,
store_fingerprint, update_status) use the SQLAlchemy session exclusively.

Key invariants verified:
- No db_path parameter accepted (would raise TypeError)
- No _db_path attribute on the repository instance
- upsert, store_fingerprint, update_status all call session.execute() + commit()
- No hardcoded ~/.auralis path can be reached by any method

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
from unittest.mock import MagicMock, call

from auralis.library.repositories.fingerprint_repository import FingerprintRepository


_SAMPLE_FINGERPRINT: dict = {
    'sub_bass_pct': 0.1, 'bass_pct': 0.2, 'low_mid_pct': 0.15,
    'mid_pct': 0.25, 'upper_mid_pct': 0.1, 'presence_pct': 0.1, 'air_pct': 0.1,
    'lufs': -14.0, 'crest_db': 6.0, 'bass_mid_ratio': 0.8,
    'tempo_bpm': 120.0, 'rhythm_stability': 0.9, 'transient_density': 0.5,
    'silence_ratio': 0.05, 'spectral_centroid': 3000.0, 'spectral_rolloff': 8000.0,
    'spectral_flatness': 0.3, 'harmonic_ratio': 0.7, 'pitch_stability': 0.85,
    'chroma_energy': 0.6, 'dynamic_range_variation': 3.0,
    'loudness_variation_std': 1.5, 'peak_consistency': 0.9,
    'stereo_width': 0.5, 'phase_correlation': 0.95,
}


@pytest.fixture
def session():
    """Mocked SQLAlchemy session."""
    s = MagicMock()
    s.execute.return_value = MagicMock()
    return s


@pytest.fixture
def repo(session):
    factory = MagicMock(return_value=session)
    return FingerprintRepository(factory), session


# ---------------------------------------------------------------------------
# Constructor — no db_path
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_no_db_path_parameter(self):
        """Passing db_path must raise TypeError (parameter removed in #2298)."""
        from pathlib import Path
        with pytest.raises(TypeError):
            FingerprintRepository(MagicMock(), db_path=Path("/tmp/test.db"))

    def test_no_db_path_attribute(self):
        """Instance must not expose _db_path (no hardcoded path)."""
        r = FingerprintRepository(MagicMock())
        assert not hasattr(r, '_db_path')

    def test_accepts_session_factory_only(self):
        """Constructor with only session_factory must succeed."""
        r = FingerprintRepository(MagicMock())
        assert r is not None


# ---------------------------------------------------------------------------
# upsert — uses SQLAlchemy session
# ---------------------------------------------------------------------------

class TestUpsertUsesSession:
    def test_calls_session_execute(self, repo):
        r, session = repo
        r.upsert(track_id=1, fingerprint_data=_SAMPLE_FINGERPRINT)
        session.execute.assert_called_once()

    def test_calls_session_commit(self, repo):
        r, session = repo
        r.upsert(track_id=1, fingerprint_data=_SAMPLE_FINGERPRINT)
        session.commit.assert_called_once()

    def test_calls_session_close(self, repo):
        r, session = repo
        r.upsert(track_id=1, fingerprint_data=_SAMPLE_FINGERPRINT)
        session.close.assert_called_once()

    def test_rollback_on_execute_failure(self, repo):
        r, session = repo
        session.execute.side_effect = RuntimeError("db error")
        result = r.upsert(track_id=1, fingerprint_data=_SAMPLE_FINGERPRINT)
        assert result is None
        session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# store_fingerprint — uses SQLAlchemy session
# ---------------------------------------------------------------------------

class TestStoreFingerprintUsesSession:
    def _call(self, repo):
        fp = _SAMPLE_FINGERPRINT
        repo.store_fingerprint(
            track_id=2,
            sub_bass_pct=fp['sub_bass_pct'], bass_pct=fp['bass_pct'],
            low_mid_pct=fp['low_mid_pct'], mid_pct=fp['mid_pct'],
            upper_mid_pct=fp['upper_mid_pct'], presence_pct=fp['presence_pct'],
            air_pct=fp['air_pct'], lufs=fp['lufs'], crest_db=fp['crest_db'],
            bass_mid_ratio=fp['bass_mid_ratio'], tempo_bpm=fp['tempo_bpm'],
            rhythm_stability=fp['rhythm_stability'], transient_density=fp['transient_density'],
            silence_ratio=fp['silence_ratio'], spectral_centroid=fp['spectral_centroid'],
            spectral_rolloff=fp['spectral_rolloff'], spectral_flatness=fp['spectral_flatness'],
            harmonic_ratio=fp['harmonic_ratio'], pitch_stability=fp['pitch_stability'],
            chroma_energy=fp['chroma_energy'],
            dynamic_range_variation=fp['dynamic_range_variation'],
            loudness_variation_std=fp['loudness_variation_std'],
            peak_consistency=fp['peak_consistency'],
            stereo_width=fp['stereo_width'], phase_correlation=fp['phase_correlation'],
        )

    def test_calls_session_execute(self, repo):
        r, session = repo
        self._call(r)
        session.execute.assert_called_once()

    def test_calls_session_commit(self, repo):
        r, session = repo
        self._call(r)
        session.commit.assert_called_once()

    def test_rollback_on_failure(self, repo):
        r, session = repo
        session.execute.side_effect = RuntimeError("db error")
        self._call(r)
        session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# update_status — uses SQLAlchemy session
# ---------------------------------------------------------------------------

class TestUpdateStatusUsesSession:
    def test_completed_calls_execute_and_commit(self, repo):
        r, session = repo
        result = r.update_status(track_id=3, status='completed', completed_at='2026-01-01T00:00:00')
        assert result is True
        session.execute.assert_called_once()
        session.commit.assert_called_once()

    def test_failed_calls_execute_and_commit(self, repo):
        r, session = repo
        result = r.update_status(track_id=3, status='failed')
        assert result is True
        session.execute.assert_called_once()
        session.commit.assert_called_once()

    def test_returns_false_on_failure(self, repo):
        r, session = repo
        session.execute.side_effect = RuntimeError("db error")
        result = r.update_status(track_id=3, status='completed')
        assert result is False
        session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# SQL injection guard — column whitelist (#2286)
# ---------------------------------------------------------------------------

class TestSqlInjectionGuard:
    """Verify that f-string column interpolation is protected by whitelist."""

    def test_upsert_rejects_injected_column_name(self, repo):
        """upsert() must raise ValueError for non-whitelisted keys."""
        r, session = repo
        bad_data = {**_SAMPLE_FINGERPRINT, "') OR 1=1--": 0.0}
        with pytest.raises(ValueError, match="Invalid fingerprint column"):
            r.upsert(track_id=1, fingerprint_data=bad_data)
        # Session must NOT have been touched when validation fails
        session.execute.assert_not_called()

    def test_upsert_rejects_unknown_column(self, repo):
        r, session = repo
        with pytest.raises(ValueError, match="Invalid fingerprint column"):
            r.upsert(track_id=1, fingerprint_data={"evil_col": 1.0})
        session.execute.assert_not_called()

    def test_upsert_accepts_all_valid_columns(self, repo):
        r, session = repo
        r.upsert(track_id=1, fingerprint_data=_SAMPLE_FINGERPRINT)
        session.execute.assert_called_once()

    def test_validate_fingerprint_columns_raises_on_bad_name(self):
        from auralis.library.repositories.fingerprint_repository import (
            _validate_fingerprint_columns,
        )
        with pytest.raises(ValueError):
            _validate_fingerprint_columns(["sub_bass_pct", "DROP TABLE tracks--"])

    def test_validate_fingerprint_columns_passes_for_valid_names(self):
        from auralis.library.repositories.fingerprint_repository import (
            _validate_fingerprint_columns,
        )
        # Should not raise for the 25 known dimension columns
        _validate_fingerprint_columns(list(_SAMPLE_FINGERPRINT.keys()))

    def test_whitelist_excludes_pk_and_timestamps(self):
        from auralis.library.repositories.fingerprint_repository import (
            _FINGERPRINT_WRITABLE_COLS,
        )
        assert 'id' not in _FINGERPRINT_WRITABLE_COLS
        assert 'created_at' not in _FINGERPRINT_WRITABLE_COLS
        assert 'updated_at' not in _FINGERPRINT_WRITABLE_COLS

    def test_whitelist_includes_all_25_dimensions(self):
        from auralis.library.repositories.fingerprint_repository import (
            _FINGERPRINT_WRITABLE_COLS,
        )
        for col in _SAMPLE_FINGERPRINT:
            assert col in _FINGERPRINT_WRITABLE_COLS, f"{col} missing from whitelist"
