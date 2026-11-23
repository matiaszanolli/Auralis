"""
Contract tests for the ProcessingParameters compression dict — issue #4856.

Two independent producers used to build `compression_params`:

  * `fixed_target_params.convert_targets_to_parameters` — the fixed-targets fast
    path taken when a track has a `.25d` fingerprint sidecar, which skips
    fingerprint extraction entirely;
  * `ContinuousParameterGenerator` — the fingerprint path.

Nothing tied their schemas together, so they drifted. Since #6356 the fingerprint
path builds its targets with `mastering_targets.generate_targets_from_fingerprint`
and converts them through the same function, so the dicts it may receive -- a
hand-written or legacy sidecar dict, and the targets law's own -- are what is
pinned here. The fast path's expansion dict omitted
`target_crest_increase`, which the expansion stage indexed unconditionally: a deterministic
KeyError for every sidecar-backed track. That stage (#5561) and its params (#6650) are gone;
compression had survived the same drift only by coincidence, so its keys stay pinned here.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest

from auralis.core.processing.base.compression_expansion import (
    COMPRESSION_REQUIRED_KEYS,
    CompressionStrategies,
)
from auralis.core.processing.fixed_target_params import convert_targets_to_parameters

FIXED_TARGETS = {
    'target_lufs': -14.0,
    'compression': {'ratio': 2.5, 'amount': 0.6},
    'eq_adjustments': {'bass': 0.5, 'mid': 0.0, 'presence': 0.3},
    'stereo_width': 1.0,
}

# A complete 25D fingerprint, as the fingerprint path hands the targets law.
FINGERPRINT_25D = {
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


def _fixed_target_params():
    """Build params via the fast path (a free function since #4254)."""
    return convert_targets_to_parameters(FIXED_TARGETS)


def _fingerprint_params(fingerprint=FINGERPRINT_25D):
    """Build params the way ContinuousMode's fingerprint path does."""
    from auralis.core.processing.mastering_targets import generate_targets_from_fingerprint

    return convert_targets_to_parameters(generate_targets_from_fingerprint(fingerprint))


def _audio(seed: int = 0) -> np.ndarray:
    return (np.random.default_rng(seed).standard_normal((44100, 2)) * 0.1).astype(np.float32)


class TestFixedTargetsSchema:
    """The fast path must satisfy every key its consumers index."""

    def test_compression_params_carry_every_required_key(self):
        params = _fixed_target_params()
        missing = COMPRESSION_REQUIRED_KEYS - params.compression_params.keys()
        assert not missing, f"fixed-targets compression_params missing {missing}"

    def test_compression_does_not_raise_on_the_fixed_targets_path(self):
        params = _fixed_target_params()
        result = CompressionStrategies.apply_clip_blend_compression(
            _audio(), params.compression_params.copy()
        )
        assert isinstance(result, np.ndarray)


class TestGeneratorPathSchema:
    """The fingerprint producer must satisfy the same contract."""

    @pytest.fixture
    def generator_params(self):
        return _fingerprint_params()

    def test_generator_compression_carries_every_required_key(self, generator_params):
        missing = COMPRESSION_REQUIRED_KEYS - generator_params.compression_params.keys()
        assert not missing, f"generator compression_params missing {missing}"

    def test_generator_params_survive_their_consumers(self, generator_params):
        CompressionStrategies.apply_clip_blend_compression(
            _audio(), generator_params.compression_params.copy()
        )


class TestBothProducersAgree:
    """The regression guard: one consumer, two producers, one schema."""

    def test_every_producer_satisfies_every_consumer(self):
        produced = [
            _fixed_target_params(),
            _fingerprint_params(),
            _fingerprint_params({**FINGERPRINT_25D, 'lufs': -30.0, 'crest_db': 20.0}),
        ]

        for params in produced:
            assert COMPRESSION_REQUIRED_KEYS == params.compression_params.keys()
