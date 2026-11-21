"""One guarded peak/RMS/crest measurement for the processing stages (#6597).

``peak = max|x|, rms = sqrt(mean(x^2)), crest = peak_db - rms_db`` was re-implemented at eight
processing sites; only ``spectral.crest_factor`` guarded silence, where ``-inf - -inf`` is NaN.
"""

import math

import numpy as np
import pytest

from auralis.core.processing.base.audio_measurement import AudioMeasurement, MeasurementUtilities
from auralis.core.processing.base.full_audio_measurement import FullAudioMeasurement
from auralis.core.processing.base.normalization_step import NormalizationStep
from auralis.dsp.utils.conversion import amplitude_to_db, crest_db, level_stats
from auralis.dsp.utils.spectral import crest_factor

SILENCE = np.zeros((4410, 2), dtype=np.float32)


def _tone() -> np.ndarray:
    t = np.arange(4410) / 44100.0
    mono = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    return np.stack([mono, mono], axis=1).astype(np.float32)


def test_level_stats_matches_the_formula_it_replaces():
    audio = _tone()
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))

    stats = level_stats(audio)

    assert stats.peak == pytest.approx(peak)
    assert stats.rms == pytest.approx(rms, rel=1e-6)
    assert stats.crest_db == pytest.approx(amplitude_to_db(peak) - amplitude_to_db(rms), abs=1e-6)
    assert stats.crest_db == pytest.approx(3.0103, abs=0.01)  # a sine's peak-to-RMS ratio, sqrt(2)


def test_silence_has_no_crest_rather_than_nan():
    stats = level_stats(SILENCE)

    assert stats.peak_db == -math.inf
    assert stats.rms_db == -math.inf
    assert stats.crest_db == 0.0
    assert crest_db(-math.inf, -math.inf) == 0.0


@pytest.mark.parametrize(
    "measure",
    [
        lambda a: AudioMeasurement(0.0, 0.0).crest,
        lambda a: MeasurementUtilities.measure_audio(a).crest,
        lambda a: FullAudioMeasurement(a).crest,
        lambda a: NormalizationStep("x").measure_before(a)["crest"],
        lambda a: NormalizationStep("x").measure_after(a)["crest"],
        crest_factor,
    ],
    ids=["AudioMeasurement", "measure_audio", "FullAudioMeasurement", "measure_before", "measure_after", "crest_factor"],
)
def test_every_measurement_agrees_on_silence(measure):
    assert measure(SILENCE) == 0.0


def test_the_measurements_agree_on_real_audio():
    audio = _tone()
    expected = level_stats(audio).crest_db

    assert MeasurementUtilities.measure_audio(audio).crest == pytest.approx(expected)
    assert FullAudioMeasurement(audio).crest == pytest.approx(expected)
    assert NormalizationStep("x").measure_before(audio)["crest"] == pytest.approx(expected)
    assert crest_factor(audio) == pytest.approx(expected, abs=1e-6)
