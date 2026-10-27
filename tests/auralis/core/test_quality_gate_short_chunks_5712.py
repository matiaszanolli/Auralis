"""
Regression: the continuous-mode quality gate cannot abort a short chunk (#5712)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``SpectrumAnalyzer.analyze_file`` returns ``{}`` for audio shorter than its FFT
(8192 samples) and ``FrequencyResponseAssessor`` then raised ``KeyError:
'spectrum'``, which the gate's ``except (ValueError, RuntimeError)`` did not
catch -- so a 1024-8191 sample chunk on a gated call aborted mastering. The
gate's result is read by nothing in production yet cost ~2 s per gated chunk,
so it is now opt-in.
"""

import numpy as np
import pytest

from auralis.analysis.quality.quality_metrics import QualityMetrics
from auralis.core.analysis.content_analyzer import ContentAnalyzer
from auralis.core.config.unified_config import UnifiedConfig
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer

SR = 44100


def _noise(frames: int) -> np.ndarray:
    return (np.random.default_rng(0).standard_normal((frames, 2)) * 0.1).astype(np.float32)


def _mode(gate: bool) -> ContinuousMode:
    config = UnifiedConfig()
    config.enable_cross_dimensional_guard = False
    config.quality_gate_enabled = gate
    config.quality_gate_interval = 1
    return ContinuousMode(config, ContentAnalyzer(), AudioFingerprintAnalyzer())


@pytest.mark.parametrize("frames", [2000, 4000, 8191])
def test_assess_quality_rejects_audio_shorter_than_the_fft_with_value_error(frames):
    with pytest.raises(ValueError, match="shorter than the analysis FFT"):
        QualityMetrics(SR).assess_quality(_noise(frames))


def test_assess_quality_still_works_at_the_fft_size():
    scores = QualityMetrics(SR).assess_quality(_noise(9000))

    assert 0 <= scores.overall_score <= 100


@pytest.mark.parametrize("frames", [1024, 4000, 8191])
def test_an_enabled_gate_skips_a_short_chunk_instead_of_raising(frames):
    mode = _mode(gate=True)
    audio = _noise(frames)

    mode._record_quality_measurements(audio, audio.copy())  # first call is always gated

    assert mode.last_quality_comparison is None


def test_the_gate_is_opt_in():
    assert UnifiedConfig().quality_gate_enabled is False


def test_a_disabled_gate_never_measures(monkeypatch):
    calls = []
    monkeypatch.setattr(
        QualityMetrics, "compare_quality", lambda *a, **k: calls.append(1) or {}
    )
    mode = _mode(gate=False)
    audio = _noise(20000)

    mode._record_quality_measurements(audio, audio.copy())

    assert calls == []


@pytest.mark.parametrize("frames", [2000, 8191])
def test_hybrid_processor_returns_a_short_chunk_with_the_gate_enabled(frames):
    from auralis.core.hybrid_processor import HybridProcessor

    config = UnifiedConfig()
    config.quality_gate_enabled = True
    processor = HybridProcessor(config)
    processor.set_fixed_mastering_targets(
        {'target_lufs': -14.0, 'target_crest_db': 12.0, 'eq_adjustments_db': {}, 'compression': {}}
    )
    audio = _noise(frames)

    out = processor.process(audio)

    assert out.shape == audio.shape
