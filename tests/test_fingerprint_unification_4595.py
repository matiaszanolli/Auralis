"""Regression tests for #4595 — unified fingerprint windowing.

Two live implementations used to compute the 25D fingerprint with materially
different sampling strategies:

  * batch (`services/fingerprint_extractor.py`): first 90 s from the START,
    single-window analysis;
  * on-demand (`analysis/fingerprint/fingerprint_service.py`): body window at
    50 % of duration plus 30 s probes at 25 %/75 %, median lufs/crest_db.

Whichever path wrote the DB row first won permanently, and the background queue
almost always ran first — so essentially every scanned track carried the
empirically less accurate fingerprint (single-window LUFS RMSE 1.96 dB / max
9.2 dB vs 1.07 / 3.6 for body+probe).

Both now delegate to `windowed_compute.compute_windowed_fingerprint`, and
FINGERPRINT_ALGORITHM_VERSION was bumped so existing rows are recomputed.
"""

import inspect
import shutil
import subprocess
from pathlib import Path

import pytest

_HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _synth(path: Path, seconds: float = 200.0) -> Path:
    """A file long enough that body/probe windows land in distinct places."""
    subprocess.run(
        ["ffmpeg", "-f", "lavfi",
         "-i", f"sine=frequency=220:duration={seconds}:sample_rate=44100",
         "-ac", "2", "-y", str(path)],
        check=True, capture_output=True,
    )
    return path


# ---------------------------------------------------------------------------
# The two paths must share ONE implementation
# ---------------------------------------------------------------------------

class TestSingleImplementation:

    def test_service_delegates_to_shared_function(self):
        from auralis.analysis.fingerprint.fingerprint_service import FingerprintService

        src = inspect.getsource(FingerprintService._compute_fingerprint)
        assert "compute_windowed_fingerprint" in src, (
            "FingerprintService._compute_fingerprint no longer delegates — the "
            "windowing has been re-inlined (#4595)"
        )

    def test_extractor_delegates_to_shared_function(self):
        from auralis.services import fingerprint_extractor as fx

        src = inspect.getsource(fx.FingerprintExtractor.extract_and_store)
        assert "compute_windowed_fingerprint" in src, (
            "FingerprintExtractor no longer uses the shared windowing (#4595)"
        )

    def test_no_windowing_constants_remain_in_either_old_site(self):
        """#4595 SIBLING check: only one place may do the crop/window selection."""
        from auralis.analysis.fingerprint import fingerprint_service
        from auralis.services import fingerprint_extractor

        for mod in (fingerprint_service, fingerprint_extractor):
            src = Path(mod.__file__).read_text()
            for marker in ("_body_offset", "_probe_fracs", "max_samples"):
                assert marker not in src, (
                    f"{Path(mod.__file__).name} still performs its own window "
                    f"selection ({marker}) — the paths can drift again (#4595)"
                )

    def test_extractor_no_longer_imports_load_audio(self):
        """The local load+crop is gone; the shared function does bounded loading."""
        from auralis.services import fingerprint_extractor

        src = Path(fingerprint_extractor.__file__).read_text()
        assert "load_audio" not in src


# ---------------------------------------------------------------------------
# Both paths must produce identical output
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _HAS_FFMPEG, reason="requires ffmpeg")
class TestPathsAgree:

    def test_batch_and_on_demand_produce_identical_fingerprints(self, tmp_path):
        """The whole point of the unification (#4595)."""
        from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
            AudioFingerprintAnalyzer,
        )
        from auralis.analysis.fingerprint.windowed_compute import (
            compute_windowed_fingerprint,
        )
        from auralis.analysis.fingerprint.fingerprint_service import FingerprintService

        audio = _synth(tmp_path / "track.wav")

        # Batch path's computation, as the extractor now performs it.
        batch = compute_windowed_fingerprint(AudioFingerprintAnalyzer(), audio)

        # On-demand path, via the service's own method.
        svc = FingerprintService.__new__(FingerprintService)
        svc.analyzer = AudioFingerprintAnalyzer()
        on_demand = svc._compute_fingerprint(audio)

        assert batch is not None and on_demand is not None
        assert set(batch) == set(on_demand)
        for key in batch:
            assert batch[key] == pytest.approx(on_demand[key], rel=1e-6, abs=1e-9), (
                f"{key} differs between the batch and on-demand paths"
            )

    def test_shared_function_returns_25_dimensions(self, tmp_path):
        from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
            AudioFingerprintAnalyzer,
        )
        from auralis.analysis.fingerprint.windowed_compute import (
            compute_windowed_fingerprint,
        )

        fp = compute_windowed_fingerprint(AudioFingerprintAnalyzer(), _synth(tmp_path / "t.wav"))
        assert fp is not None and len(fp) == 25
        assert all(isinstance(v, (int, float)) for v in fp.values())


# ---------------------------------------------------------------------------
# The version bump must actually invalidate old rows
# ---------------------------------------------------------------------------

class TestVersionInvalidation:

    def test_algorithm_version_is_at_least_4(self):
        """v4 is what forces recomputation of pre-unification rows (#4595).

        Lowering this without a migration plan would silently serve
        mixed-vintage fingerprints into similarity and mastering.
        """
        from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION

        assert FINGERPRINT_ALGORITHM_VERSION >= 4

    def test_database_read_rejects_outdated_row(self):
        """On-demand reads must not serve a pre-unification fingerprint."""
        from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
        from auralis.analysis.fingerprint.fingerprint_service import FingerprintService

        svc = FingerprintService.__new__(FingerprintService)

        class _Path:
            def exists(self):
                return True

        class _TrackRepo:
            def get_id_by_filepath(self, _fp):
                return 1

        class _Row:
            lufs = -14.0
            fingerprint_version = FINGERPRINT_ALGORITHM_VERSION - 1

            def __getattr__(self, _name):
                return 0.1

        class _FpRepo:
            def get_by_track_id(self, _tid):
                return _Row()

        svc.db_path = _Path()            # type: ignore[assignment]
        svc._track_repo = _TrackRepo()   # type: ignore[assignment]
        svc._fingerprint_repo = _FpRepo()  # type: ignore[assignment]

        assert svc._load_from_database("/x.wav") is None, (
            "an outdated fingerprint row was served from the DB cache — the "
            "version bump cannot self-heal the on-demand path (#4595)"
        )

    def test_database_read_accepts_current_row(self):
        """A current-version row must still be a cache hit (no perf regression)."""
        from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
        from auralis.analysis.fingerprint.fingerprint_service import FingerprintService

        svc = FingerprintService.__new__(FingerprintService)

        class _Path:
            def exists(self):
                return True

        class _TrackRepo:
            def get_id_by_filepath(self, _fp):
                return 1

        class _Row:
            """A plausible current-version row whose band pcts sum to 1.0."""
            lufs = -14.0
            fingerprint_version = FINGERPRINT_ALGORITHM_VERSION

            def __getattr__(self, name):
                bands = {
                    'sub_bass_pct': 0.1, 'bass_pct': 0.2, 'low_mid_pct': 0.2,
                    'mid_pct': 0.2, 'upper_mid_pct': 0.15, 'presence_pct': 0.1,
                    'air_pct': 0.05,
                }
                return bands.get(name, 0.5)

        class _FpRepo:
            def get_by_track_id(self, _tid):
                return _Row()

        svc.db_path = _Path()            # type: ignore[assignment]
        svc._track_repo = _TrackRepo()   # type: ignore[assignment]
        svc._fingerprint_repo = _FpRepo()  # type: ignore[assignment]

        result = svc._load_from_database("/x.wav")
        assert result is not None and result['lufs'] == -14.0

    def test_queue_rewrites_outdated_rows(self):
        """The background re-fingerprint pass must key off the same constant."""
        from auralis.services import fingerprint_queue

        src = Path(fingerprint_queue.__file__).read_text()
        assert "claim_next_outdated_fingerprint(FINGERPRINT_ALGORITHM_VERSION)" in src, (
            "the queue's Phase 2 outdated-fingerprint pass is what actually "
            "recomputes old rows after a version bump (#4595)"
        )
