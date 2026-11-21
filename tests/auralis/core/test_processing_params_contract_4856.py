"""
Contract tests for the ProcessingParameters dynamics dicts — issue #4856.

Two independent producers build `compression_params` / `expansion_params`:

  * `fixed_target_params.convert_targets_to_parameters` — the fixed-targets fast
    path taken when a track has a `.25d` fingerprint sidecar, which skips
    fingerprint extraction entirely;
  * `ContinuousParameterGenerator` — the fingerprint path.

Nothing tied their schemas together, so they drifted. The fast path omitted
`target_crest_increase`, which the expansion stage (since removed, #5561)
indexed unconditionally *before* it checked `amount`. Result: a deterministic
KeyError on the primary chunked-streaming path for every sidecar-backed track.

Compression survived the same drift only by coincidence — both producers happen
to emit the two keys its reader indexes (`ratio`, `amount`) — so this pins both
dicts, not just the one that crashed.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest

from auralis.core.processing.base.compression_expansion import (
    COMPRESSION_REQUIRED_KEYS,
    EXPANSION_REQUIRED_KEYS,
    CompressionStrategies,
)
from auralis.core.processing.fixed_target_params import convert_targets_to_parameters

FIXED_TARGETS = {
    'target_lufs': -14.0,
    'compression': {'ratio': 2.5, 'amount': 0.6},
    'eq_adjustments': {'bass': 0.5, 'mid': 0.0, 'presence': 0.3},
    'stereo_width': 1.0,
}

# A complete 25D fingerprint — ContinuousParameterGenerator indexes these
# directly (e.g. `bass_pct`), so an empty dict is not a valid stand-in.
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


def _audio(seed: int = 0) -> np.ndarray:
    return (np.random.default_rng(seed).standard_normal((44100, 2)) * 0.1).astype(np.float32)


class TestFixedTargetsSchema:
    """The fast path must satisfy every key its consumers index."""

    def test_expansion_params_carry_every_required_key(self):
        params = _fixed_target_params()
        missing = EXPANSION_REQUIRED_KEYS - params.expansion_params.keys()
        assert not missing, f"fixed-targets expansion_params missing {missing}"

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


class TestExpansionStaysDisabled:
    """Adding the key must not switch expansion on for this path."""

    def test_expansion_is_reported_disabled(self):
        # The expansion stage itself is gone (#5561); the params remain reporting data.
        params = _fixed_target_params()
        assert params.expansion_params['amount'] == 0.0
        assert params.expansion_params['target_crest_increase'] == 0.0

class TestGeneratorPathSchema:
    """The fingerprint producer must satisfy the same contract."""

    @pytest.fixture
    def generator_params(self):
        from auralis.core.processing.continuous_space import ProcessingCoordinates
        from auralis.core.processing.parameter_generator import (
            ContinuousParameterGenerator,
        )

        gen = ContinuousParameterGenerator()
        coords = ProcessingCoordinates(
            spectral_balance=0.5, dynamic_range=0.5, fingerprint=FINGERPRINT_25D
        )
        return gen.generate_parameters(coords)

    def test_generator_expansion_carries_every_required_key(self, generator_params):
        missing = EXPANSION_REQUIRED_KEYS - generator_params.expansion_params.keys()
        assert not missing, f"generator expansion_params missing {missing}"

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
        from auralis.core.processing.continuous_space import ProcessingCoordinates
        from auralis.core.processing.parameter_generator import (
            ContinuousParameterGenerator,
        )

        gen = ContinuousParameterGenerator()
        produced = [
            _fixed_target_params(),
            gen.generate_parameters(
                ProcessingCoordinates(
                    spectral_balance=0.2, dynamic_range=0.8,
                    fingerprint=FINGERPRINT_25D,
                )
            ),
        ]

        for params in produced:
            assert EXPANSION_REQUIRED_KEYS <= params.expansion_params.keys()
            assert COMPRESSION_REQUIRED_KEYS <= params.compression_params.keys()
