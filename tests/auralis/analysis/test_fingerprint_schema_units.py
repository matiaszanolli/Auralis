"""
Regression test pinning fingerprint unit conventions.

Previously the EQ generator, continuous-space mapper, and recording-type
detector treated fingerprint band fractions as percentages and used the
wrong denormalization constant for spectral_centroid. The result was that
the "continuous space" collapsed to a single point and the EQ curve was
effectively constant across radically different source material.

These tests synthesize three contrasting fingerprints (dark / balanced /
bright) and assert that the downstream decisions vary monotonically with
the spectral character.
"""

from __future__ import annotations

import pytest

from auralis.analysis.fingerprint.schema import (
    CENTROID_NORMALIZATION_HZ,
    DIMENSION_SCHEMA,
    ROLLOFF_NORMALIZATION_HZ,
    centroid_to_hz,
    rolloff_to_hz,
)
from auralis.core.processing.continuous_space import ProcessingSpaceMapper
from auralis.core.processing.parameter_generator import ContinuousParameterGenerator
from auralis.core.recording_type_detector import RecordingType, RecordingTypeDetector


# A complete 25D fingerprint stub.  Tests vary specific dimensions only.
def _fp(
    *,
    bass_pct: float = 0.20,
    air_pct: float = 0.10,
    presence_pct: float = 0.08,
    mid_pct: float = 0.25,
    upper_mid_pct: float = 0.15,
    low_mid_pct: float = 0.15,
    sub_bass_pct: float = 0.05,
    spectral_centroid: float = 0.30,    # normalized; 0.30 * 8000 = 2.4 kHz
    spectral_rolloff: float = 0.40,
    spectral_flatness: float = 0.20,
    lufs: float = -14.0,
    crest_db: float = 12.0,
    bass_mid_ratio: float = 0.0,
    stereo_width: float = 0.45,
    phase_correlation: float = 0.75,
    tempo_bpm: float = 120.0,
    rhythm_stability: float = 0.7,
    transient_density: float = 0.4,
    silence_ratio: float = 0.02,
    harmonic_ratio: float = 0.65,
    pitch_stability: float = 0.7,
    chroma_energy: float = 0.55,
    dynamic_range_variation: float = 0.3,
    loudness_variation_std: float = 1.5,
    peak_consistency: float = 0.7,
) -> dict[str, float]:
    return dict(locals())


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def test_schema_covers_all_25_dimensions():
    """The schema must cover every dimension the fingerprint stores."""
    # 25 named dimensions per audio_fingerprint_analyzer
    assert len(DIMENSION_SCHEMA) == 25


def test_centroid_denormalization_constant_is_8khz():
    """The fingerprint clips spectral_centroid at 8 kHz; the helper must agree."""
    assert CENTROID_NORMALIZATION_HZ == 8000.0
    assert centroid_to_hz(1.0) == 8000.0
    assert centroid_to_hz(0.5) == 4000.0
    assert centroid_to_hz(0.0) == 0.0


def test_rolloff_denormalization_constant_is_10khz():
    """Rolloff is stored against 10 kHz, NOT the centroid's 8 kHz (#4863).

    `rolloff_to_hz` multiplied by CENTROID_NORMALIZATION_HZ until #4863, so it
    returned Hz values 20% low — and this assertion used to pin that bug
    (`rolloff_to_hz(0.5) == 4000.0`).
    """
    assert ROLLOFF_NORMALIZATION_HZ == 10_000.0
    assert rolloff_to_hz(1.0) == 10_000.0
    assert rolloff_to_hz(0.5) == 5000.0
    assert rolloff_to_hz(0.0) == 0.0


def test_rolloff_and_centroid_use_different_scales():
    """The two constants differing is the trap this helper fell into."""
    assert ROLLOFF_NORMALIZATION_HZ != CENTROID_NORMALIZATION_HZ
    assert rolloff_to_hz(1.0) != centroid_to_hz(1.0)


def test_rolloff_helper_inverts_what_the_rust_adapter_produces():
    """Round-trip against the producer, not against a restated constant.

    `rust_fingerprint` divides the raw Hz by ROLLOFF_NORMALIZATION_HZ; this
    helper is its inverse, so composing them must be the identity. Both now
    import the constant from `schema`, which is what makes that true by
    construction rather than by coincidence.
    """
    from auralis.analysis.fingerprint.rust_fingerprint import (
        ROLLOFF_NORMALIZATION_HZ as PRODUCER_CONSTANT,
    )

    assert PRODUCER_CONSTANT is ROLLOFF_NORMALIZATION_HZ

    for raw_hz in (0.0, 2500.0, 5000.0, 10_000.0):
        normalized = raw_hz / PRODUCER_CONSTANT
        assert rolloff_to_hz(normalized) == pytest.approx(raw_hz)


# ---------------------------------------------------------------------------
# Continuous-space spectral axis must vary
# ---------------------------------------------------------------------------

def test_spectral_axis_varies_with_source_brightness():
    """Pre-fix: spectral_balance collapsed to constant 0.35 for every source.
    Post-fix: dark sources < balanced < bright sources, strictly monotonic."""
    mapper = ProcessingSpaceMapper()

    dark = mapper.map_fingerprint_to_space(_fp(
        bass_pct=0.45, air_pct=0.02, presence_pct=0.02, spectral_centroid=0.10,
    ))
    balanced = mapper.map_fingerprint_to_space(_fp(
        bass_pct=0.25, air_pct=0.10, presence_pct=0.10, spectral_centroid=0.40,
    ))
    bright = mapper.map_fingerprint_to_space(_fp(
        bass_pct=0.12, air_pct=0.18, presence_pct=0.18, spectral_centroid=0.75,
    ))

    assert dark.spectral_balance < balanced.spectral_balance < bright.spectral_balance, (
        f"spectral axis collapsed — dark={dark.spectral_balance:.3f} "
        f"balanced={balanced.spectral_balance:.3f} bright={bright.spectral_balance:.3f}"
    )
    # And the range must be non-trivial (pre-fix it was the constant 0.35)
    assert (bright.spectral_balance - dark.spectral_balance) > 0.30


# ---------------------------------------------------------------------------
# EQ generator must vary
# ---------------------------------------------------------------------------

def test_eq_curve_varies_with_source_brightness():
    """Pre-fix: every source got ≈ +4 dB low_shelf and ≈ +3 dB high_shelf.
    Post-fix: dark sources get more lift, bright sources get less (or none)."""
    mapper = ProcessingSpaceMapper()
    generator = ContinuousParameterGenerator()

    dark_coords = mapper.map_fingerprint_to_space(_fp(
        bass_pct=0.45, air_pct=0.02, presence_pct=0.02, mid_pct=0.20,
    ))
    bright_coords = mapper.map_fingerprint_to_space(_fp(
        bass_pct=0.10, air_pct=0.20, presence_pct=0.18, mid_pct=0.30,
    ))

    dark_params = generator.generate_parameters(dark_coords)
    bright_params = generator.generate_parameters(bright_coords)

    # Signed corrections vary continuously around corpus centers.
    assert abs(dark_params.eq_curve['low_shelf_gain']) < 0.1
    assert bright_params.eq_curve['low_shelf_gain'] > 1.5
    assert dark_params.eq_curve['high_shelf_gain'] > bright_params.eq_curve['high_shelf_gain']

    # And the gains must differ
    assert dark_params.eq_curve['high_shelf_gain'] != bright_params.eq_curve['high_shelf_gain']
    assert dark_params.eq_curve['low_shelf_gain'] != bright_params.eq_curve['low_shelf_gain']


# ---------------------------------------------------------------------------
# Recording-type detector
# ---------------------------------------------------------------------------

def test_recording_type_uses_correct_centroid_denormalization():
    """Pre-fix: centroid_hz = normalized * 20000 sent every source past the
    'metal' threshold (>1000 Hz). Post-fix: the 8 kHz scale matches the
    fingerprint, so centroid_hz reflects actual brightness."""
    detector = RecordingTypeDetector()

    # spectral_centroid=0.05 → 400 Hz post-fix (bootleg territory).
    # Pre-fix this was 0.05 * 20000 = 1000 Hz (metal territory).
    bootleg_fp = _fp(
        spectral_centroid=0.05,         # 400 Hz post-fix
        bass_mid_ratio=15.0,            # very bass-heavy
        stereo_width=0.20,              # narrow
        crest_db=5.0,
    )
    rtype, _ = detector._classify(bootleg_fp)
    # We don't pin to BOOTLEG specifically because confidence thresholds
    # vary, but the type must NOT be METAL on a centroid-400Hz source.
    assert rtype != RecordingType.METAL, (
        f"Centroid 400 Hz source classified as {rtype} — denormalization is wrong"
    )

    # spectral_centroid=0.4 → 3200 Hz post-fix (modern bright pop/metal range).
    bright_fp = _fp(
        spectral_centroid=0.4,
        bass_mid_ratio=10.0,
        stereo_width=0.40,
        crest_db=5.0,
    )
    rtype_bright, _ = detector._classify(bright_fp)
    # Either METAL or UNKNOWN is acceptable; BOOTLEG would mean the
    # centroid is being misread as 8000 Hz which would fail the < 500 Hz
    # bootleg score thresholds.
    assert rtype_bright != RecordingType.BOOTLEG
