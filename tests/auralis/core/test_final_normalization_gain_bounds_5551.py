"""#5551 — final LUFS normalisation needs a silence floor and a gain cap.

After #5221 ``calculate_loudness_units`` floors silence at a finite -70 LUFS,
so the ``isfinite`` guard in ``_apply_final_normalization`` (#4104) could never
fire. A quiet-but-not-zero chunk (dither, room tone, a decoded-MP3 gap) was
raised by +47 to +140 dB to programme loudness.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.dsp.utils.adaptive import (
    MAX_NORMALIZATION_GAIN_DB,
    SILENCE_FLOOR_LUFS,
    calculate_loudness_units,
)

SR = 44100
PARAMS = SimpleNamespace(target_lufs=-14.0)


def _mode() -> ContinuousMode:
    return ContinuousMode(
        config=UnifiedConfig(),
        content_analyzer=MagicMock(),
        fingerprint_analyzer=MagicMock(),
    )


def _noise(rms_db: float, seconds: float = 5.0) -> np.ndarray:
    rng = np.random.default_rng(1)
    x = rng.standard_normal((int(SR * seconds), 2)).astype(np.float32)
    return (x * (10 ** (rms_db / 20)) / x.std()).astype(np.float32)


def _rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2))))


@pytest.mark.parametrize("level_db", [-60.0, -80.0, -100.0, -140.0])
def test_quiet_chunk_is_not_raised_to_programme_loudness(level_db: float) -> None:
    audio = _noise(level_db)
    assert calculate_loudness_units(audio, SR) <= SILENCE_FLOOR_LUFS
    out = _mode()._apply_final_normalization(audio, PARAMS)
    assert np.all(np.isfinite(out))
    assert _rms_db(out) - _rms_db(audio) <= MAX_NORMALIZATION_GAIN_DB + 1e-3
    # Below the floor the chunk is left alone, not re-levelled.
    np.testing.assert_array_equal(out, audio)


def test_applied_gain_never_exceeds_the_cap() -> None:
    # Just above the floor, the target is far away: the gain must be capped.
    audio = _noise(-45.0)
    lufs = calculate_loudness_units(audio, SR)
    assert lufs > SILENCE_FLOOR_LUFS
    out = _mode()._apply_final_normalization(audio, SimpleNamespace(target_lufs=0.0))
    assert _rms_db(out) - _rms_db(audio) <= MAX_NORMALIZATION_GAIN_DB + 0.1


@pytest.mark.parametrize("level_db", [-26.0, -20.0, -12.0])
def test_normal_material_still_reaches_target(level_db: float) -> None:
    audio = _noise(level_db)
    out = _mode()._apply_final_normalization(audio, PARAMS)
    assert calculate_loudness_units(out, SR) == pytest.approx(-14.0, abs=0.5) or (
        # a loud chunk is brought down; the -0.3 dBFS peak clamp may stop it
        # short only when it would otherwise clip.
        np.max(np.abs(out)) == pytest.approx(10 ** (-0.3 / 20), rel=1e-3)
    )


def test_silence_still_produces_finite_output() -> None:
    audio = np.zeros((8192, 2), dtype=np.float32)
    out = _mode()._apply_final_normalization(audio, PARAMS)
    assert np.all(np.isfinite(out))
    assert out.shape == audio.shape
