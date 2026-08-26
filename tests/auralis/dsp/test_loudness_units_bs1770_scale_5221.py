"""#5221 — calculate_loudness_units() must report true LUFS, not RMS - 23 dB.

The old implementation returned ``to_db(rms(audio)) - 23.0``: unweighted RMS,
offset by the EBU R128 *target* level as if it were a dBFS->LUFS conversion.
That put it ~25 LU below the scale every one of its consumers is calibrated
in, so `continuous_dsp_ops`'s ``target_lufs - current_lufs`` normalization
became a systematic ~+25 dB over-boost.
"""

import numpy as np
import pytest

from auralis.analysis.loudness_meter import LoudnessMeter
from auralis.core.config.preset_profiles import create_preset_profiles
from auralis.dsp.utils.adaptive import calculate_loudness_units

SR = 44100


def _tone(freq: float, amplitude: float, seconds: float = 4.0) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    mono = amplitude * np.sin(2 * np.pi * freq * t)
    return np.column_stack([mono, mono])


@pytest.mark.parametrize("freq", [50.0, 1000.0, 8000.0])
def test_matches_bs1770_meter(freq: float) -> None:
    """Agrees with the codebase's BS.1770-4 meter to within 0.1 LU."""
    audio = _tone(freq, 0.1)

    meter = LoudnessMeter(SR)
    meter.measure_chunk(audio)
    reference = meter.finalize_measurement().integrated_lufs

    assert calculate_loudness_units(audio, SR) == pytest.approx(reference, abs=0.1)


def test_is_k_weighted_not_flat_rms() -> None:
    """Equal-RMS tones at different frequencies must NOT read equally loud.

    This is the property the old RMS approximation could not have: it returned
    the same number for all three, because it never applied K-weighting.
    """
    readings = [calculate_loudness_units(_tone(f, 0.1), SR) for f in (50.0, 1000.0, 8000.0)]

    # K-weighting boosts highs and rolls off lows, so 8 kHz > 1 kHz > 50 Hz.
    assert readings[2] > readings[1] > readings[0]
    assert readings[2] - readings[0] > 3.0


def test_no_23db_offset_against_preset_targets() -> None:
    """A track mastered to a preset's target must read back near that target.

    The regression: with the -23.0 offset, `adjustment = target_lufs -
    current_lufs` in continuous_dsp_ops._apply_final_normalization came out
    ~25 dB too high on every pass.
    """
    target = create_preset_profiles()["adaptive"].target_lufs  # -14.0 LUFS

    audio = _tone(1000.0, 0.1)
    measured = calculate_loudness_units(audio, SR)
    audio_at_target = audio * (10.0 ** ((target - measured) / 20.0))

    assert calculate_loudness_units(audio_at_target, SR) == pytest.approx(target, abs=0.1)


def test_silence_and_empty_return_finite_floor() -> None:
    """Callers subtract from this value and feed it to tanh curves."""
    assert calculate_loudness_units(np.zeros((SR, 2)), SR) == -70.0
    assert calculate_loudness_units(np.zeros((0, 2)), SR) == -70.0


def test_no_filter_state_bleeds_between_calls() -> None:
    """A loud buffer must not colour the next measurement.

    LoudnessMeter.apply_k_weighting() carries filter state across calls, so
    this pins that calculate_loudness_units does not share one instance.
    """
    quiet = _tone(1000.0, 0.01)
    first = calculate_loudness_units(quiet, SR)

    calculate_loudness_units(_tone(1000.0, 0.9), SR)

    assert calculate_loudness_units(quiet, SR) == pytest.approx(first, abs=1e-9)


def test_mono_input_accepted() -> None:
    mono = _tone(1000.0, 0.1)[:, 0]
    assert np.isfinite(calculate_loudness_units(mono, SR))
