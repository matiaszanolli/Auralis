"""A .25d sidecar with `{}` targets must not become "fixed targets" (#5951).

The player's FingerprintService writes ``~/.auralis/fingerprints/<hash>.25d`` with
``targets={}``. ``load_from_file`` re-derived targets only when they were truthy,
so ``{}`` passed straight through as "derived later" - but nobody derived them -
and ``set_fixed_mastering_targets({})`` made ContinuousMode take its fast path with
``convert_targets_to_parameters({})``: flat EQ, -14 LUFS, default compression, and
no fingerprint analysis, silently, under a chunk-cache key of its own.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.fingerprint_loading import load_from_file  # noqa: E402
from core.mastering_target_service import MasteringTargetService  # noqa: E402
from core.targets_hash import NO_TARGETS, get_targets_hash  # noqa: E402

from auralis.analysis.fingerprint import FingerprintStorage  # noqa: E402


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
def sidecar_with_empty_targets(tmp_path, monkeypatch):
    """A real .25d written exactly as FingerprintService writes it: targets={}."""
    monkeypatch.setattr(FingerprintStorage, "_get_cache_dir", staticmethod(lambda: tmp_path / "fp"))
    (tmp_path / "fp").mkdir()
    audio = tmp_path / "track.flac"
    audio.write_bytes(b"fLaC" + b"\x00" * 64)
    FingerprintStorage.save(audio, _fingerprint_25d(), {}, sample_rate=44100, duration=180.0)
    return audio


def test_load_from_file_derives_targets_for_an_empty_dict(sidecar_with_empty_targets):
    derived = {"target_lufs": -14.0, "marker": "derived"}
    derive = MagicMock(return_value=derived)

    result = load_from_file(str(sidecar_with_empty_targets), derive)

    assert result is not None
    fingerprint, targets = result
    assert targets == derived
    derive.assert_called_once()
    assert derive.call_args.args[0]["lufs"] == pytest.approx(-16.5)


def test_load_fingerprint_returns_real_derived_targets(sidecar_with_empty_targets):
    service = MasteringTargetService()

    fingerprint, targets = service.load_fingerprint(
        1, str(sidecar_with_empty_targets), extract_if_missing=False
    )

    assert targets == service.generate_targets_from_fingerprint(fingerprint)
    assert targets, "derived targets must be non-empty"
    assert get_targets_hash(targets) != NO_TARGETS


def test_a_non_dict_fingerprint_with_empty_targets_yields_none_not_empty_dict():
    with patch.object(FingerprintStorage, "load", return_value=(object(), {})):
        result = load_from_file("/music/track.flac", MagicMock())

    assert result is not None
    assert result[1] is None


def test_empty_targets_hash_like_no_targets():
    """So the processor pool and chunk cache treat {} and None as one key."""
    assert get_targets_hash({}) == NO_TARGETS == get_targets_hash(None)
    assert get_targets_hash({"a": 1}) != NO_TARGETS


def test_a_new_processor_is_never_given_empty_fixed_targets():
    from core.processor_factory import ProcessorFactory

    created = []

    class _Recorder:
        def __init__(self, *_a, **_kw):
            created.append(self)
            self.fixed = "unset"

        def set_fixed_mastering_targets(self, targets):
            self.fixed = targets

    with patch("auralis.core.hybrid_processor.HybridProcessor", _Recorder):
        factory = ProcessorFactory()
        factory.get_or_create(track_id=1, mastering_targets={})
        factory.get_or_create(track_id=2, mastering_targets={"target_lufs": -14.0})

    assert created[0].fixed == "unset", "{} must not be applied as fixed targets"
    assert created[1].fixed == {"target_lufs": -14.0}
