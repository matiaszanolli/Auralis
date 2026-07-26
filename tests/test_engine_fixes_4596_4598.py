"""Regression tests for engine fixes #4596, #4597, #4598.

Three independent defects from the 2026-07-25 engine audit:

  #4596 — FingerprintExtractionQueue's drain threshold used the ADVISORY
          `current_num_workers` (which AdaptiveResourceMonitor ratchets upward
          without spawning threads) instead of the real thread count, so once
          the recommendation passed the real count `on_drained` stopped firing
          forever.
  #4597 — load_with_ffmpeg passed `-ac 2` unconditionally, up-mixing genuine
          mono into fake stereo while get_audio_info() reported the true
          channel count — so the two disagreed and load_audio()'s
          dimensionality depended on file extension, not audio content.
  #4598 — Track.fingerprint / Track.similar_tracks lacked passive_deletes=True,
          so deleting any fingerprinted track raised IntegrityError (swallowed
          as a plain False by TrackRepository.delete()).
"""

import shutil
import subprocess
import threading
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# #4596 — drain threshold must track real threads, not the advisory count
# ---------------------------------------------------------------------------

class TestFingerprintQueueDrainThreshold:
    """`on_drained` must keep firing after adaptive scaling inflates the count."""

    @staticmethod
    def _make_queue(num_workers: int):
        from auralis.services.fingerprint_queue import FingerprintExtractionQueue

        # enable_adaptive_scaling=False keeps the monitor from mutating state
        # under us; we drive current_num_workers by hand to model its effect.
        return FingerprintExtractionQueue.__new__(FingerprintExtractionQueue)

    def _bare_queue(self, real_workers: int, advisory: int):
        """Build a queue with only the drain-related state initialised."""
        q = self._make_queue(real_workers)
        q.initial_num_workers = real_workers
        q.current_num_workers = advisory
        q.workers = [object() for _ in range(real_workers)]  # stand-ins for threads
        q._drain_state_lock = threading.Lock()
        q._processed_since_drain = 0
        q._drained_workers = 0
        q.on_drained = None
        return q

    def test_fires_when_advisory_count_matches_reality(self):
        fired = []
        q = self._bare_queue(real_workers=2, advisory=2)
        q.on_drained = lambda: fired.append(1)
        q._processed_since_drain = 1

        q._on_worker_drained()
        assert fired == []          # only 1 of 2 workers drained
        q._on_worker_drained()
        assert fired == [1]

    def test_still_fires_after_adaptive_count_ratchets_past_real_threads(self):
        """The #4596 regression: advisory count inflated well beyond reality."""
        fired = []
        # 2 real threads, but AdaptiveResourceMonitor has pushed the
        # recommendation to 8 — previously making the threshold unreachable
        # since _drained_workers can only be incremented by real threads.
        q = self._bare_queue(real_workers=2, advisory=8)
        q.on_drained = lambda: fired.append(1)
        q._processed_since_drain = 1

        q._on_worker_drained()
        q._on_worker_drained()

        assert fired == [1], "on_drained must fire on real thread count, not the advisory one"

    def test_does_not_fire_without_processed_work(self):
        """A drain wave that processed nothing must not fire the callback."""
        fired = []
        q = self._bare_queue(real_workers=1, advisory=8)
        q.on_drained = lambda: fired.append(1)
        q._processed_since_drain = 0

        q._on_worker_drained()
        assert fired == []

    def test_state_resets_between_waves(self):
        fired = []
        q = self._bare_queue(real_workers=1, advisory=4)
        q.on_drained = lambda: fired.append(1)

        q._processed_since_drain = 1
        q._on_worker_drained()
        assert fired == [1]
        assert q._drained_workers == 0
        assert q._processed_since_drain == 0

        # Second wave must fire again rather than being wedged.
        q._processed_since_drain = 1
        q._on_worker_drained()
        assert fired == [1, 1]

    def test_falls_back_to_initial_count_when_workers_list_is_empty(self):
        """Before start(), self.workers is empty — must not divide by zero."""
        fired = []
        q = self._bare_queue(real_workers=3, advisory=9)
        q.workers = []
        q.on_drained = lambda: fired.append(1)
        q._processed_since_drain = 1

        for _ in range(2):
            q._on_worker_drained()
        assert fired == []          # 2 < initial_num_workers (3)
        q._on_worker_drained()
        assert fired == [1]


# ---------------------------------------------------------------------------
# #4597 — FFmpeg channel handling must agree with get_audio_info()
# ---------------------------------------------------------------------------

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _synth(path: Path, channels: int, codec: str = "libmp3lame") -> Path:
    subprocess.run(
        ["ffmpeg", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=2:sample_rate=44100",
         "-ac", str(channels), "-c:a", codec, "-y", str(path)],
        check=True, capture_output=True,
    )
    return path


@pytest.mark.skipif(not _HAS_FFMPEG, reason="requires ffmpeg + ffprobe")
class TestFFmpegChannelAgreement:
    """get_audio_info() and load_audio() must describe the same file the same way."""

    def test_mono_source_is_not_upmixed_to_fake_stereo(self, tmp_path):
        from auralis.io.unified_loader import get_audio_info, load_audio

        p = _synth(tmp_path / "mono.mp3", 1)

        assert get_audio_info(p)["channels"] == 1
        audio, _sr = load_audio(p)
        # The #4597 regression: this used to come back as (N, 2) — a duplicated
        # mono channel — disagreeing with the channel count reported above.
        assert audio.ndim == 1, f"mono source should load 1-D, got shape {audio.shape}"

    def test_stereo_source_is_unchanged(self, tmp_path):
        from auralis.io.unified_loader import get_audio_info, load_audio

        p = _synth(tmp_path / "stereo.mp3", 2)

        assert get_audio_info(p)["channels"] == 2
        audio, _sr = load_audio(p)
        assert audio.ndim == 2 and audio.shape[1] == 2

    def test_surround_source_is_still_downmixed_to_stereo(self, tmp_path):
        """#3672 must be preserved — gating the downmix must not disable it."""
        from auralis.io.unified_loader import get_audio_info, load_audio

        p = _synth(tmp_path / "surround.m4a", 6, codec="aac")

        assert get_audio_info(p)["channels"] == 6
        audio, _sr = load_audio(p)
        assert audio.ndim == 2 and audio.shape[1] == 2, "5.1 must still downmix to stereo"

    def test_mono_matches_the_soundfile_routed_path(self, tmp_path):
        """The contract must not depend on file extension (#4597)."""
        from auralis.io.unified_loader import load_audio

        mp3 = _synth(tmp_path / "m.mp3", 1)          # FFmpeg-routed
        wav = _synth(tmp_path / "m.wav", 1, codec="pcm_s16le")  # soundfile-routed

        a_mp3, _ = load_audio(mp3)
        a_wav, _ = load_audio(wav)
        assert a_mp3.ndim == a_wav.ndim == 1


# ---------------------------------------------------------------------------
# #4598 — deleting a fingerprinted track must succeed
# ---------------------------------------------------------------------------

class TestTrackDeleteCascade:
    """ORM delete must defer child removal to the DB CASCADE."""

    @staticmethod
    def _session_factory():
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker
        from auralis.library.models import Base

        engine = create_engine("sqlite:///:memory:")

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine)

    def _populate(self, session):
        """One track with a fingerprint row and a similarity edge."""
        from auralis.library.models import Track
        from auralis.library.models.fingerprint import SimilarityGraph, TrackFingerprint

        t1 = Track(title="A", filepath="/a.wav", duration=10.0)
        t2 = Track(title="B", filepath="/b.wav", duration=10.0)
        session.add_all([t1, t2])
        session.commit()

        dims = {
            'sub_bass_pct': 1.0, 'bass_pct': 1.0, 'low_mid_pct': 1.0, 'mid_pct': 1.0,
            'upper_mid_pct': 1.0, 'presence_pct': 1.0, 'air_pct': 1.0,
            'lufs': -14.0, 'crest_db': 8.0, 'bass_mid_ratio': 1.0,
            'tempo_bpm': 120.0, 'rhythm_stability': 0.5, 'transient_density': 0.5,
            'silence_ratio': 0.1, 'spectral_centroid': 1000.0, 'spectral_rolloff': 5000.0,
            'spectral_flatness': 0.5, 'harmonic_ratio': 0.5, 'pitch_stability': 0.5,
            'chroma_energy': 0.5, 'stereo_width': 0.5, 'phase_correlation': 0.5,
            'dynamic_range_variation': 0.5, 'loudness_variation_std': 0.5,
            'peak_consistency': 0.5,
        }
        session.add(TrackFingerprint(track_id=t1.id, **dims))
        session.add(SimilarityGraph(
            track_id=t1.id, similar_track_id=t2.id,
            distance=0.1, similarity_score=0.9, rank=1,
        ))
        session.commit()
        return t1.id, t2.id

    def test_orm_delete_of_fingerprinted_track_succeeds(self):
        """The #4598 regression: this raised IntegrityError, reported as False."""
        from auralis.library.models import Track
        from auralis.library.models.fingerprint import SimilarityGraph, TrackFingerprint

        Session = self._session_factory()
        session = Session()
        t1_id, _t2_id = self._populate(session)

        track = session.get(Track, t1_id)
        session.delete(track)
        session.commit()      # previously: IntegrityError NOT NULL track_id

        assert session.get(Track, t1_id) is None
        assert session.query(TrackFingerprint).filter_by(track_id=t1_id).count() == 0
        assert session.query(SimilarityGraph).filter_by(track_id=t1_id).count() == 0
        session.close()

    def test_repository_delete_returns_true_for_fingerprinted_track(self):
        """TrackRepository.delete() must report success, not a swallowed False."""
        from auralis.library.repositories.track_repository import TrackRepository

        Session = self._session_factory()
        seed = Session()
        t1_id, _ = self._populate(seed)
        seed.close()

        repo = TrackRepository.__new__(TrackRepository)
        repo.get_session = Session          # type: ignore[method-assign]

        assert repo.delete(t1_id) is True, (
            "delete() returned False — the IntegrityError swallow is back"
        )

        check = Session()
        from auralis.library.models import Track
        assert check.get(Track, t1_id) is None
        check.close()

    def test_delete_of_missing_track_still_returns_false(self):
        """The not-found path must be unchanged."""
        from auralis.library.repositories.track_repository import TrackRepository

        Session = self._session_factory()
        repo = TrackRepository.__new__(TrackRepository)
        repo.get_session = Session          # type: ignore[method-assign]

        assert repo.delete(999_999) is False

    def test_passive_deletes_declared_on_both_child_relationships(self):
        """Guard the fix itself — both parent-side collections must declare it."""
        from auralis.library.models import Track

        mapper = Track.__mapper__
        for rel_name in ("fingerprint", "similar_tracks"):
            rel = mapper.relationships[rel_name]
            assert rel.passive_deletes is True, (
                f"Track.{rel_name} lost passive_deletes=True — deleting a "
                f"fingerprinted track will raise IntegrityError again (#4598)"
            )
