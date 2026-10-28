"""Fingerprint fallbacks have one home (#5795)."""

import pytest

from auralis.core.utils import FINGERPRINT_DEFAULTS, FingerprintUnpacker, fingerprint_default
from auralis.dsp.utils.loudness_targets import DEFAULT_TARGET_LUFS, STREAMING_TARGET_LUFS


def test_every_unpacker_property_reads_the_shared_table():
    empty = FingerprintUnpacker.from_dict({})
    # The table also carries `spectral_centroid_hz` (#6219), a unit alias of the normalised
    # centroid for EQ-curve adapters rather than a 25th dimension, so it has no property.
    dimensions = {key: value for key, value in FINGERPRINT_DEFAULTS.items() if key != 'spectral_centroid_hz'}
    assert len(dimensions) == 25
    for key, value in dimensions.items():
        assert getattr(empty, key) == value


def test_present_values_beat_the_defaults():
    assert FingerprintUnpacker.from_dict({'lufs': -9.0}).lufs == -9.0


def test_fingerprint_default_rejects_unknown_dimensions():
    with pytest.raises(KeyError):
        fingerprint_default('not_a_dimension')


def test_loudness_constants_agree_with_the_typical_track_default():
    assert DEFAULT_TARGET_LUFS == STREAMING_TARGET_LUFS == fingerprint_default('lufs')


def test_stereo_width_fallback_follows_the_unpacker():
    from auralis.core.processing.parameter_generator_stereo import calculate_stereo_width
    from auralis.core.processing.continuous_space import ProcessingCoordinates

    def width(fingerprint):
        return calculate_stereo_width(
            ProcessingCoordinates(
                spectral_balance=0.5, dynamic_range=0.5, energy_level=0.5,
                fingerprint=fingerprint,
            ),
            None,
        )

    # Was 0.7 locally (the one site that disagreed with the unpacker's 0.5).
    assert width({}) == width({'stereo_width': fingerprint_default('stereo_width')})
    assert width({}) != width({'stereo_width': 0.7})
