"""#5785 — one scalar dB conversion, with the silence convention stated.

Silent input mapped to -inf, -96.0 or about -200 dB depending on the file, and the two
mastering sites that used -96.0 feed the pipeline's own peak/headroom maths. The helpers
in ``dsp/utils/conversion.py`` make the convention an argument.
"""

import math

import numpy as np
import pytest

from auralis.analysis.dynamic_range import DynamicRangeAnalyzer
from auralis.core.analysis.content_analyzer import ContentAnalyzer
from auralis.core.mastering_process_chunk import compute_peak_db
from auralis.core.processing.base.audio_measurement import AudioMeasurement
from auralis.core.processing.base.db_conversion import DBConversion
from auralis.dsp.utils.conversion import SILENCE_FLOOR_DB, amplitude_to_db, peak_db, rms_db, to_db


class TestAmplitudeToDb:
    @pytest.mark.parametrize("value,expected", [(1.0, 0.0), (0.5, -6.0206), (0.1, -20.0), (2.0, 6.0206)])
    def test_values(self, value: float, expected: float) -> None:
        assert amplitude_to_db(value) == pytest.approx(expected, abs=1e-3)

    @pytest.mark.parametrize("silent", [0.0, -0.5, float("nan")])
    def test_default_silence_is_minus_inf(self, silent: float) -> None:
        assert amplitude_to_db(silent) == -math.inf

    @pytest.mark.parametrize("silent", [0.0, -0.5, float("nan")])
    def test_explicit_silence_convention(self, silent: float) -> None:
        assert amplitude_to_db(silent, silence_db=SILENCE_FLOOR_DB) == -96.0

    def test_returns_a_python_float_and_keeps_float32_precision(self) -> None:
        out = amplitude_to_db(np.float32(0.25))
        assert type(out) is float
        assert out == pytest.approx(float(20 * np.log10(np.float32(0.25))), abs=0)


class TestPeakAndRms:
    def test_peak_db(self) -> None:
        assert peak_db(np.array([0.1, -0.5, 0.2])) == pytest.approx(-6.0206, abs=1e-3)
        assert peak_db(np.zeros(8)) == -math.inf
        assert peak_db(np.zeros(8), silence_db=SILENCE_FLOOR_DB) == -96.0

    def test_rms_db(self) -> None:
        assert rms_db(np.full(100, 0.5)) == pytest.approx(-6.0206, abs=1e-3)
        assert rms_db(np.zeros(100)) == -math.inf

    def test_stereo_input(self) -> None:
        x = np.column_stack([np.full(50, 0.5), np.full(50, 0.25)])
        assert peak_db(x) == pytest.approx(-6.0206, abs=1e-3)


class TestLegacyHelpersAgree:
    def test_dbconversion_delegates_with_its_default(self) -> None:
        assert DBConversion.to_db(0.5) == amplitude_to_db(0.5)
        assert DBConversion.to_db(0.0) == -math.inf
        assert DBConversion.to_db(0.0, default=-12.0) == -12.0

    def test_floored_to_db_keeps_its_finite_floor(self) -> None:
        assert to_db(0.0) == pytest.approx(-200.0)
        assert to_db(0.5) == pytest.approx(amplitude_to_db(0.5))


class TestMigratedSitesKeepTheirConventions:
    def test_mastering_peak_uses_the_headroom_floor(self) -> None:
        assert compute_peak_db(np.zeros(10)) == -96.0
        assert compute_peak_db(np.array([0.5])) == pytest.approx(-6.0206, abs=1e-3)

    def test_audio_measurement_silence_is_minus_inf(self) -> None:
        m = AudioMeasurement(peak=0.0, rms_val=0.0)
        assert m.peak_db == -math.inf and m.rms_db == -math.inf

    def test_audio_measurement_levels(self) -> None:
        m = AudioMeasurement(peak=0.5, rms_val=0.25)
        assert m.peak_db == pytest.approx(-6.0206, abs=1e-3)
        assert m.crest == pytest.approx(6.0206, abs=1e-3)

    def test_dynamic_range_levels(self) -> None:
        analyzer = DynamicRangeAnalyzer(44100)
        assert analyzer._calculate_peak_level(np.zeros(100)) == -math.inf
        assert analyzer._calculate_rms_level(np.zeros(100)) == -math.inf
        assert analyzer._calculate_peak_level(np.array([0.5])) == pytest.approx(-6.0206, abs=1e-3)

    def test_content_analyzer_levels(self) -> None:
        loud = np.full(4096, 0.5, dtype=np.float32)
        result = ContentAnalyzer(44100).analyze_input_level(loud)
        assert result['peak_db'] == pytest.approx(-6.0206, abs=1e-3)
        assert result['rms_db'] == pytest.approx(-6.0206, abs=1e-3)
        assert result['crest_db'] == pytest.approx(0.0, abs=1e-3)


def test_sites_no_longer_inline_the_conversion() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / 'auralis'
    for rel in (
        'core/mastering_process_chunk.py',
        'core/mastering_prepare.py',
        'core/analysis/content_analyzer.py',
        'core/processing/base/audio_measurement.py',
        'core/processing/base/db_conversion.py',
        'core/processing/adaptive_mode.py',
        'analysis/dynamic_range.py',
    ):
        src = (root / rel).read_text()
        assert 'if peak > 0' not in src and 'if rms > 0' not in src, rel
        assert '-96.0' not in src.replace('SILENCE_FLOOR_DB', ''), rel
