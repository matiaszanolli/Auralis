"""Regression: centroid denormalization is shared, not re-derived (#4538).

Commit 7f937cca fixed `_classify()` to denormalize the 0-1 `spectral_centroid`
dimension with `centroid_to_hz()` (CENTROID_NORMALIZATION_HZ = 8000), but the
three parameter generators in the same file kept a hand-rolled `* 20000`. Every
per-recording-type EQ fine-tuning decision was therefore driven by a value 2.5x
too large: a real 700 Hz centroid is stored as 0.0875 and came out as 1750 Hz,
so realistic content never landed in the branch its thresholds were tuned for.

Re-deriving Hz at four call sites inside one class is the mechanism, so these
tests pin the shared derivation rather than only the three literals.
"""

import pytest

from auralis.analysis.fingerprint.schema import (
    CENTROID_NORMALIZATION_HZ,
    centroid_to_hz,
)
from auralis.core.recording_type_detector import (
    RecordingType,
    RecordingTypeDetector,
    _centroid_hz,
)


def _fp(centroid_hz: float, **overrides) -> dict[str, float]:
    """Fingerprint whose centroid dimension encodes a given TRUE Hz value."""
    fingerprint = {
        'spectral_centroid': centroid_hz / CENTROID_NORMALIZATION_HZ,
        'bass_mid_ratio': 1.0,
        'stereo_width': 0.5,
        'crest_db': 8.0,
    }
    fingerprint.update(overrides)
    return fingerprint


@pytest.fixture
def detector():
    return RecordingTypeDetector()


# ---------------------------------------------------------------------------
# The derivation itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hz", [0.0, 300.0, 450.0, 700.0, 1340.0, 4000.0, 8000.0])
def test_centroid_helper_matches_schema(hz):
    normalized = hz / CENTROID_NORMALIZATION_HZ
    assert _centroid_hz({'spectral_centroid': normalized}) == pytest.approx(hz)


def test_helper_does_not_use_the_old_20000_factor():
    """0.0875 must yield 700 Hz, not 1750."""
    assert _centroid_hz({'spectral_centroid': 0.0875}) == pytest.approx(700.0)
    assert _centroid_hz({'spectral_centroid': 0.0875}) != pytest.approx(1750.0)


def test_missing_key_without_default_is_none():
    assert _centroid_hz({}) is None


def test_default_is_interpreted_as_normalized_not_hz():
    """The bootleg generator's 0.3 default is a NORMALIZED value: 2400 Hz."""
    assert _centroid_hz({}, default_normalized=0.3) == pytest.approx(2400.0)


# ---------------------------------------------------------------------------
# All four call sites agree
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "generator",
    ["_parameters_studio", "_parameters_bootleg", "_parameters_metal"],
)
def test_generators_and_classify_agree_on_hz(detector, generator, monkeypatch):
    """Parametrized so a future fourth call site that re-derives Hz is caught.

    Captures the Hz value each generator actually computes and asserts it
    equals what _classify() derives from the same fingerprint.
    """
    fingerprint = _fp(700.0)
    seen: list[float] = []

    import auralis.core.recording_type_detector as mod

    real = mod._centroid_hz

    def spy(fp, default_normalized=None):
        value = real(fp, default_normalized)
        if value is not None:
            seen.append(value)
        return value

    monkeypatch.setattr(mod, "_centroid_hz", spy)
    getattr(detector, generator)(fingerprint, 0.9)

    assert seen, f"{generator} did not go through the shared derivation"
    assert all(v == pytest.approx(700.0) for v in seen)
    assert seen[0] == pytest.approx(centroid_to_hz(fingerprint['spectral_centroid']))


# ---------------------------------------------------------------------------
# Branch selection at true-Hz thresholds — these fail on the old code
# ---------------------------------------------------------------------------

def test_studio_dark_recording_takes_the_below_600_branch(detector):
    """A ~450 Hz recording must reduce the bass boost to 1.0.

    On the old `* 20000` path this yielded 1125 Hz, overshooting the > 800
    branch instead — the acceptance criterion for this issue.
    """
    params = detector._parameters_studio(_fp(450.0), 0.9)
    assert params.bass_adjustment_db == pytest.approx(1.0)


def test_studio_bright_recording_takes_the_above_800_branch(detector):
    params = detector._parameters_studio(_fp(1200.0), 0.9)
    assert params.treble_adjustment_db == pytest.approx(1.5)


def test_studio_midband_keeps_base_parameters(detector):
    """700 Hz is between the thresholds: neither branch fires."""
    params = detector._parameters_studio(_fp(700.0), 0.9)
    assert params.bass_adjustment_db == pytest.approx(1.5)
    assert params.treble_adjustment_db == pytest.approx(2.0)


def test_bootleg_dark_recording_takes_the_below_450_branch(detector):
    params = detector._parameters_bootleg(_fp(400.0), 0.9)
    assert params.treble_adjustment_db == pytest.approx(4.5)


def test_bootleg_bright_recording_keeps_base_treble(detector):
    params = detector._parameters_bootleg(_fp(600.0), 0.9)
    assert params.treble_adjustment_db == pytest.approx(4.0)


def test_metal_brighter_than_reference_takes_the_above_1340_branch(detector):
    params = detector._parameters_metal(_fp(1500.0), 0.9)
    assert params.treble_adjustment_db == pytest.approx(-1.5)


def test_metal_less_bright_takes_the_below_1200_branch(detector):
    params = detector._parameters_metal(_fp(1000.0), 0.9)
    assert params.treble_adjustment_db == pytest.approx(-0.95)


def test_metal_between_thresholds_keeps_base(detector):
    params = detector._parameters_metal(_fp(1250.0), 0.9)
    assert params.treble_adjustment_db == pytest.approx(-1.22)


# ---------------------------------------------------------------------------
# CONSISTENCY guard on the fix itself
# ---------------------------------------------------------------------------

def test_no_hardcoded_denormalization_remains():
    """The literal is the bug; assert it cannot come back."""
    from pathlib import Path

    source = Path(
        RecordingTypeDetector.__module__.replace('.', '/') + '.py'
    )
    text = source.read_text() if source.exists() else None
    if text is None:  # pragma: no cover - path resolution fallback
        import inspect
        import auralis.core.recording_type_detector as mod
        text = inspect.getsource(mod)

    # Only the docstring reference to the historical bug may mention it.
    code_lines = [
        line for line in text.splitlines()
        if '* 20000' in line and not line.strip().startswith(('#', '``', '*'))
        and '``* 20000``' not in line
    ]
    assert not code_lines, f"hardcoded centroid denormalization returned: {code_lines}"


def test_classification_still_works_end_to_end(detector):
    """The shared helper did not break _classify's own path."""
    rec_type, confidence = detector._classify(_fp(700.0))
    assert isinstance(rec_type, RecordingType)
    assert 0.0 <= confidence <= 1.0
