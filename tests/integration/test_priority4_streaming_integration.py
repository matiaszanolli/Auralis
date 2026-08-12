"""Weighted mastering profile recommendations in the streaming pipeline.

Revived in #4282. Four of this file's tests had been permanently dead: they
imported from `auralis_web.backend.*` (underscore), a package that cannot exist
— the real directory is `auralis-web`, and a hyphen is not importable as a
Python package at all. The module names had drifted too
(`chunked_processor` -> `core.chunked_processor`, `streamlined_cache` ->
`cache.manager`). Because each import sat inside
`try/except ImportError: pytest.skip(...)`, they reported as *skipped* rather
than failing, and a dynamic skip is invisible to the `pytest.mark.skip`/xfail
greps used to baseline dead tests. Two more skipped on a hardcoded
`/tmp/test_audio.wav` that no fixture ever created.

Imports are now at module scope with no try/except: if the backend layout
drifts again this file fails loudly instead of going quietly dead.

The remaining three classes used to assert properties of dict literals defined
inside the test body — they passed without touching project code. They now
drive `AdaptiveMasteringEngine` / `MasteringRecommendation.to_response()`
directly, so the payload contract and the blending rules are really covered.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# `auralis-web/backend` is the app root: its modules import each other as
# top-level packages (`core.*`, `cache.*`), so the root goes on sys.path
# rather than being imported as a package. Same pattern as
# tests/backend/test_chunked_processor_invariants.py.
_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from cache.manager import StreamlinedCacheManager  # noqa: E402
from core.chunked_processor import ChunkedAudioProcessor  # noqa: E402

from auralis.analysis.adaptive_mastering_engine import (  # noqa: E402
    AdaptiveMasteringEngine,
)
from auralis.analysis.mastering_fingerprint import MasteringFingerprint  # noqa: E402
from auralis.io.saver import save as save_audio  # noqa: E402

SAMPLE_RATE = 44100


@pytest.fixture(scope="module")
def sample_audio_file(tmp_path_factory) -> str:
    """A real on-disk WAV, replacing the hardcoded /tmp/test_audio.wav skip.

    Harmonically rich and amplitude-modulated so the spectral features are
    non-degenerate. `save()` does not normalise, so the written peak is the
    peak computed here.
    """
    duration = 3.0
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    tone = (
        0.30 * np.sin(2 * np.pi * 220 * t)
        + 0.15 * np.sin(2 * np.pi * 440 * t)
        + 0.07 * np.sin(2 * np.pi * 1760 * t)
    ) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.7 * t))
    stereo = np.column_stack([tone, tone * 0.9]).astype(np.float32)

    path = tmp_path_factory.mktemp("priority4") / "sample.wav"
    save_audio(str(path), stereo, SAMPLE_RATE)
    return str(path)


@pytest.fixture
def reference_fingerprint() -> MasteringFingerprint:
    """A fingerprint with values in the ranges the field docstrings describe.

    Built directly rather than via `from_audio_file()` on purpose: the engine's
    ranking logic is what these tests target, and a synthetic tone ranks
    against no profile at all, which silently routes every assertion through
    `_fallback_recommendation()` instead of the code under test.
    """
    return MasteringFingerprint(
        loudness_dbfs=-18.5,
        peak_dbfs=-1.2,
        crest_db=17.3,
        spectral_centroid=3100.0,
        spectral_rolloff=9000.0,
        zero_crossing_rate=0.06,
        spectral_spread=2200.0,
    )


class TestChunkedProcessorRecommendations:
    """Mastering recommendations from a real ChunkedAudioProcessor."""

    def test_get_mastering_recommendation_returns_serialisable_recommendation(
        self, sample_audio_file
    ):
        processor = ChunkedAudioProcessor(
            track_id=1,
            filepath=sample_audio_file,
            preset=None,  # analysis only — no DSP preset needed
            intensity=1.0,
            chunk_cache={},
        )

        rec = processor.get_mastering_recommendation(confidence_threshold=0.4)

        assert rec is not None, "recommendation pipeline returned nothing for real audio"
        assert hasattr(rec, "primary_profile")
        assert hasattr(rec, "confidence_score")
        assert hasattr(rec, "weighted_profiles")
        assert 0.0 <= rec.confidence_score <= 1.0

        rec_dict = rec.to_dict()
        for key in (
            "primary_profile_id",
            "primary_profile_name",
            "confidence_score",
            "predicted_loudness_change",
            "predicted_crest_change",
            "predicted_centroid_change",
        ):
            assert key in rec_dict, f"{key} missing from to_dict()"

    def test_recommendation_is_cached_on_the_processor(self, sample_audio_file):
        """Second call must reuse the cached object, not re-analyse the file.

        Recommendation analysis extracts a fingerprint (a full decode), so a
        cache miss here is a real per-chunk performance regression.
        """
        processor = ChunkedAudioProcessor(
            track_id=1,
            filepath=sample_audio_file,
            preset=None,
            intensity=1.0,
            chunk_cache={},
        )

        first = processor.get_mastering_recommendation()
        second = processor.get_mastering_recommendation()

        assert first is not None
        assert first is second, "recommendation was recomputed instead of cached"

    def test_recommendation_does_not_require_decoding_chunks(self, sample_audio_file):
        """`get_mastering_recommendation()` works off the fingerprint alone.

        Pins the invariant the constructor's own comment relies on: a caller
        that only wants a recommendation never triggers a chunk decode, so it
        needs no `close()` cleanup.
        """
        processor = ChunkedAudioProcessor(
            track_id=1,
            filepath=sample_audio_file,
            preset=None,
            intensity=1.0,
            chunk_cache={},
        )

        assert processor.get_mastering_recommendation() is not None
        assert processor.chunk_cache == {}, "recommendation path populated the chunk cache"


class TestStreamlinedCacheRecommendations:
    """Recommendation storage in the real StreamlinedCacheManager."""

    @staticmethod
    def _rec_payload(profile_id: str = "bright-masters") -> dict:
        return {
            "primary_profile_id": profile_id,
            "primary_profile_name": "Bright Masters",
            "confidence_score": 0.43,
            "predicted_loudness_change": -1.06,
            "predicted_crest_change": 1.47,
            "predicted_centroid_change": 22.7,
            "weighted_profiles": [
                {"profile_id": "bright-masters", "profile_name": "Bright Masters", "weight": 0.43},
                {"profile_id": "hires-masters", "profile_name": "Hi-Res Masters", "weight": 0.31},
            ],
        }

    def test_set_then_get_round_trips_the_recommendation(self):
        cache = StreamlinedCacheManager()
        cache.set_mastering_recommendation(track_id=42, recommendation=self._rec_payload())

        retrieved = cache.get_mastering_recommendation(track_id=42)

        assert retrieved is not None
        assert retrieved["primary_profile_id"] == "bright-masters"
        assert len(retrieved["weighted_profiles"]) == 2

    def test_recommendations_are_keyed_per_track(self):
        """A second track's recommendation must not overwrite the first."""
        cache = StreamlinedCacheManager()
        cache.set_mastering_recommendation(1, self._rec_payload("warm-masters"))
        cache.set_mastering_recommendation(2, self._rec_payload("bright-masters"))

        assert cache.get_mastering_recommendation(1)["primary_profile_id"] == "warm-masters"
        assert cache.get_mastering_recommendation(2)["primary_profile_id"] == "bright-masters"

    def test_missing_track_returns_none(self):
        assert StreamlinedCacheManager().get_mastering_recommendation(track_id=999) is None

    def test_clear_removes_every_recommendation(self):
        cache = StreamlinedCacheManager()
        cache.set_mastering_recommendation(1, self._rec_payload())
        cache.set_mastering_recommendation(2, self._rec_payload())
        assert cache.get_mastering_recommendation(1) is not None

        cache.clear_mastering_recommendations()

        assert cache.get_mastering_recommendation(1) is None
        assert cache.get_mastering_recommendation(2) is None


class TestRecommendationResponseContract:
    """`to_response()` is the one payload shape REST and WS both serve (#3840)."""

    def test_response_declares_every_field_api_consumers_require(
        self, reference_fingerprint
    ):
        rec = AdaptiveMasteringEngine().recommend_weighted(reference_fingerprint)

        payload = rec.to_response(track_id=42)

        for key in (
            "track_id",
            "primary_profile_id",
            "primary_profile_name",
            "confidence_score",
            "predicted_loudness_change",
            "predicted_crest_change",
            "predicted_centroid_change",
            "reasoning",
            "is_hybrid",
            "weighted_profiles",
        ):
            assert key in payload, f"{key} missing from to_response()"

        assert payload["track_id"] == 42
        assert isinstance(payload["primary_profile_id"], str)
        assert isinstance(payload["confidence_score"], (int, float))
        assert isinstance(payload["is_hybrid"], bool)
        assert isinstance(payload["weighted_profiles"], list)

    def test_weighted_profiles_is_present_even_when_not_hybrid(
        self, reference_fingerprint
    ):
        """Never undefined — clients declare the field required (#3840)."""
        # threshold 0.0: any confidence clears it, so this is the single-profile path.
        rec = AdaptiveMasteringEngine().recommend_weighted(
            reference_fingerprint, confidence_threshold=0.0
        )

        payload = rec.to_response(track_id=1)

        assert payload["is_hybrid"] is False
        assert payload["weighted_profiles"] == []


class TestHybridMasteringDetection:
    """`is_hybrid` is derived from real blending, not passed in by a caller."""

    def test_low_confidence_relative_to_threshold_produces_a_blend(
        self, reference_fingerprint
    ):
        engine = AdaptiveMasteringEngine()

        # threshold 1.0 is above any achievable confidence -> always blends.
        blended = engine.recommend_weighted(reference_fingerprint, confidence_threshold=1.0)
        # threshold 0.0 is below any confidence -> never blends.
        single = engine.recommend_weighted(reference_fingerprint, confidence_threshold=0.0)

        assert blended.to_response(1)["is_hybrid"] is True
        assert single.to_response(1)["is_hybrid"] is False
        assert len(blended.weighted_profiles) > 1
        assert single.weighted_profiles == []

    def test_blend_weights_sum_to_one(self, reference_fingerprint):
        rec = AdaptiveMasteringEngine().recommend_weighted(
            reference_fingerprint, confidence_threshold=1.0
        )

        weights = [w["weight"] for w in rec.to_response(1)["weighted_profiles"]]

        assert weights, "expected a blend at threshold 1.0"
        assert abs(sum(weights) - 1.0) < 0.01, f"weights sum to {sum(weights)}"
        assert all(w > 0 for w in weights), "a zero/negative weight should be excluded"

    def test_top_k_bounds_the_blend_width(self, reference_fingerprint):
        engine = AdaptiveMasteringEngine()

        for top_k in (2, 3):
            rec = engine.recommend_weighted(
                reference_fingerprint, confidence_threshold=1.0, top_k=top_k
            )
            assert len(rec.weighted_profiles) == top_k
            weights = [pw.weight for pw in rec.weighted_profiles]
            assert abs(sum(weights) - 1.0) < 0.01


class TestConfidenceThresholds:
    """The threshold decides single vs. blended, at the documented boundary."""

    def test_confidence_at_or_above_threshold_stays_single_profile(
        self, reference_fingerprint
    ):
        engine = AdaptiveMasteringEngine()
        confidence = engine.recommend_weighted(
            reference_fingerprint, confidence_threshold=0.0
        ).confidence_score

        # Exactly at the boundary: the comparison is `>=`, so this must NOT blend.
        at_boundary = engine.recommend_weighted(
            reference_fingerprint, confidence_threshold=confidence
        )
        just_above = engine.recommend_weighted(
            reference_fingerprint, confidence_threshold=min(confidence + 1e-6, 1.0)
        )

        assert at_boundary.weighted_profiles == [], "boundary is inclusive (>=), must not blend"
        if confidence < 1.0:
            assert just_above.weighted_profiles, "just above the boundary must blend"

    def test_threshold_does_not_change_the_underlying_confidence(
        self, reference_fingerprint
    ):
        """Confidence is a property of the match, not of the threshold."""
        engine = AdaptiveMasteringEngine()

        scores = {
            engine.recommend_weighted(
                reference_fingerprint, confidence_threshold=thr
            ).confidence_score
            for thr in (0.0, 0.4, 1.0)
        }

        assert len(scores) == 1, f"threshold altered the confidence score: {scores}"
