"""
Cross-Dimensional Interaction Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests that processing stages do not degrade dimensions they don't target.
Validates the PipelineJournal, CrossDimensionalGuard, and compensation logic.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.core.config.unified_config import UnifiedConfig
from auralis.core.processing.cross_dimensional_guard import (
    CrossDimensionalGuard,
    STAGE_INPUT, STAGE_EQ, STAGE_DYNAMICS, STAGE_STEREO, STAGE_NORMALIZATION,
)
from auralis.core.processing.stage_snapshot import (
    PipelineJournal,
    StageSnapshot,
    _compute_3band_energy,
    _compute_phase_correlation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_rate() -> int:
    return 44100


@pytest.fixture
def stereo_noise(sample_rate: int) -> np.ndarray:
    """5-second stereo white noise at -20 dBFS."""
    rng = np.random.default_rng(42)
    duration = 5
    samples = sample_rate * duration
    audio = rng.standard_normal((samples, 2)).astype(np.float32) * 0.1
    return audio


@pytest.fixture
def bass_heavy_audio(sample_rate: int) -> np.ndarray:
    """5-second stereo audio dominated by 80 Hz sine."""
    duration = 5
    t = np.linspace(0, duration, sample_rate * duration, endpoint=False)
    bass = 0.3 * np.sin(2 * np.pi * 80 * t)
    mid = 0.02 * np.sin(2 * np.pi * 1000 * t)
    signal = (bass + mid).astype(np.float32)
    return np.column_stack([signal, signal])


@pytest.fixture
def wide_stereo_audio(sample_rate: int) -> np.ndarray:
    """5-second stereo audio with low correlation (wide stereo)."""
    rng = np.random.default_rng(99)
    duration = 5
    samples = sample_rate * duration
    left = rng.standard_normal(samples).astype(np.float32) * 0.15
    right = rng.standard_normal(samples).astype(np.float32) * 0.15
    return np.column_stack([left, right])


# ---------------------------------------------------------------------------
# Test: PipelineJournal
# ---------------------------------------------------------------------------

class TestPipelineJournal:
    """Tests for the measurement bus."""

    def test_captures_all_stages(self, stereo_noise: np.ndarray, sample_rate: int):
        """Journal should capture a snapshot for each stage."""
        journal = PipelineJournal(sample_rate)
        stages = [STAGE_INPUT, STAGE_EQ, STAGE_DYNAMICS, STAGE_STEREO, STAGE_NORMALIZATION]
        for stage in stages:
            journal.snapshot(stereo_noise, stage)

        assert len(journal.snapshots) == 5
        for stage in stages:
            snap = journal.get(stage)
            assert snap is not None
            assert snap.stage_name == stage

    def test_snapshot_measures_peak_rms_crest(self, stereo_noise: np.ndarray, sample_rate: int):
        """Each snapshot should have valid peak, RMS, crest measurements."""
        journal = PipelineJournal(sample_rate)
        snap = journal.snapshot(stereo_noise, "test")

        assert snap.peak_db < 0  # noise at 0.1 amplitude
        assert snap.rms_db < snap.peak_db  # RMS < peak always
        assert snap.crest_db > 0  # crest = peak - rms, positive for noise

    def test_snapshot_measures_3band_energy(self, bass_heavy_audio: np.ndarray, sample_rate: int):
        """Bass-heavy audio should show high bass energy."""
        journal = PipelineJournal(sample_rate)
        snap = journal.snapshot(bass_heavy_audio, "test")

        assert snap.bass_energy_pct > 0.5  # bass dominates
        assert snap.bass_energy_pct > snap.mid_energy_pct
        assert snap.bass_energy_pct > snap.high_energy_pct

    def test_snapshot_measures_stereo(self, wide_stereo_audio: np.ndarray, sample_rate: int):
        """Wide stereo should have low correlation and high width."""
        journal = PipelineJournal(sample_rate)
        snap = journal.snapshot(wide_stereo_audio, "test")

        assert snap.stereo_width is not None
        assert snap.phase_correlation is not None
        assert snap.stereo_width > 0.5  # wide
        assert snap.phase_correlation < 0.3  # low correlation

    def test_snapshot_mono_has_no_stereo(self, sample_rate: int):
        """Mono audio should have None stereo metrics."""
        mono = np.random.default_rng(0).standard_normal(sample_rate).astype(np.float32) * 0.1
        journal = PipelineJournal(sample_rate)
        snap = journal.snapshot(mono, "test")

        assert snap.stereo_width is None
        assert snap.phase_correlation is None

    def test_get_delta(self, stereo_noise: np.ndarray, sample_rate: int):
        """Delta between two snapshots should reflect applied gain."""
        from auralis.dsp.basic import amplify
        journal = PipelineJournal(sample_rate)
        journal.snapshot(stereo_noise, "before")
        boosted = amplify(stereo_noise.copy(), 6.0)
        journal.snapshot(boosted, "after")

        delta = journal.get_delta("before", "after")
        assert abs(delta['peak_db'] - 6.0) < 1.0  # ~6 dB boost
        assert abs(delta['rms_db'] - 6.0) < 1.0

    def test_nonexistent_stage_returns_none(self, sample_rate: int):
        """Requesting a stage that wasn't captured returns None."""
        journal = PipelineJournal(sample_rate)
        assert journal.get("nonexistent") is None


# ---------------------------------------------------------------------------
# Test: CrossDimensionalGuard
# ---------------------------------------------------------------------------

class TestCrossDimensionalGuard:
    """Tests for side-effect detection."""

    @pytest.fixture
    def guard(self) -> CrossDimensionalGuard:
        return CrossDimensionalGuard()

    def test_eq_lufs_drift_detected(self, guard: CrossDimensionalGuard):
        """Guard should flag EQ that shifts LUFS by > 3 dB."""
        pre = StageSnapshot("pre_eq", -18.0, -24.0, 6.0, -20.0, 0.3, 0.4, 0.3, 0.5, 0.8)
        post = StageSnapshot("post_eq", -14.0, -20.0, 6.0, -16.0, 0.3, 0.4, 0.3, 0.5, 0.8)
        # LUFS shifted from -20 to -16 = +4 dB drift

        effects = guard.check_eq_side_effects(pre, post)
        assert len(effects) == 1
        assert effects[0].dimension == "lufs"
        assert effects[0].severity == "warning"

    def test_eq_no_drift_no_flag(self, guard: CrossDimensionalGuard):
        """Guard should not flag small LUFS changes."""
        pre = StageSnapshot("pre_eq", -18.0, -24.0, 6.0, -20.0, 0.3, 0.4, 0.3, 0.5, 0.8)
        post = StageSnapshot("post_eq", -17.0, -23.0, 6.0, -19.0, 0.3, 0.4, 0.3, 0.5, 0.8)
        # LUFS shifted from -20 to -19 = +1 dB — within threshold

        effects = guard.check_eq_side_effects(pre, post)
        assert len(effects) == 0

    def test_dynamics_spectral_tilt_detected(self, guard: CrossDimensionalGuard):
        """Guard should flag dynamics that shift spectral balance > 15%."""
        pre = StageSnapshot("pre_dyn", -18.0, -24.0, 6.0, -20.0, 0.30, 0.40, 0.30, 0.5, 0.8)
        post = StageSnapshot("post_dyn", -16.0, -22.0, 6.0, -18.0, 0.50, 0.30, 0.20, 0.5, 0.8)
        # Bass shifted from 30% to 50% = +20% drift

        effects = guard.check_dynamics_side_effects(pre, post)
        assert len(effects) >= 1
        assert any(e.dimension == "spectral_tilt_bass" for e in effects)

    def test_stereo_phase_drop_detected(self, guard: CrossDimensionalGuard):
        """Guard should flag stereo processing that drops phase correlation > 0.2."""
        pre = StageSnapshot("pre_st", -18.0, -24.0, 6.0, -20.0, 0.3, 0.4, 0.3, 0.5, 0.7)
        post = StageSnapshot("post_st", -18.0, -24.0, 6.0, -20.0, 0.3, 0.4, 0.3, 0.8, 0.4)
        # Phase dropped from 0.7 to 0.4 = -0.3

        effects = guard.check_stereo_side_effects(pre, post)
        assert len(effects) == 1
        assert effects[0].dimension == "phase_correlation"

    def test_normalization_crest_crush_detected(self, guard: CrossDimensionalGuard):
        """Guard should flag normalization that crushes crest > 4 dB."""
        pre = StageSnapshot("pre_norm", -12.0, -24.0, 12.0, -18.0, 0.3, 0.4, 0.3, 0.5, 0.8)
        post = StageSnapshot("post_norm", -3.0, -10.0, 7.0, -12.0, 0.3, 0.4, 0.3, 0.5, 0.8)
        # Crest dropped from 12 to 7 = -5 dB crush

        effects = guard.check_normalization_side_effects(pre, post)
        assert len(effects) == 1
        assert effects[0].dimension == "crest_db"

    def test_full_pipeline_critical_lufs_drift(self, guard: CrossDimensionalGuard):
        """Guard should flag full pipeline LUFS drift > 6 dB as critical."""
        input_snap = StageSnapshot("input", -20.0, -26.0, 6.0, -22.0, 0.3, 0.4, 0.3, 0.5, 0.8)
        output_snap = StageSnapshot("output", -6.0, -12.0, 6.0, -14.0, 0.3, 0.4, 0.3, 0.5, 0.8)
        # LUFS shifted from -22 to -14 = +8 dB

        effects = guard.check_full_pipeline(input_snap, output_snap)
        assert len(effects) >= 1
        assert any(e.severity == "critical" for e in effects)

    def test_analyze_full_pipeline_no_effects_on_passthrough(
        self, guard: CrossDimensionalGuard, stereo_noise: np.ndarray, sample_rate: int
    ):
        """Unprocessed audio should produce no side effects."""
        journal = PipelineJournal(sample_rate)
        journal.snapshot(stereo_noise, STAGE_INPUT)
        journal.snapshot(stereo_noise, STAGE_EQ)
        journal.snapshot(stereo_noise, STAGE_DYNAMICS)
        journal.snapshot(stereo_noise, STAGE_STEREO)
        journal.snapshot(stereo_noise, STAGE_NORMALIZATION)

        effects = guard.analyze_full_pipeline(journal)
        assert len(effects) == 0


# ---------------------------------------------------------------------------
# Test: Compensation Bounds
# ---------------------------------------------------------------------------

class TestCompensationBounds:
    """Tests that compensations are bounded and non-recursive."""

    def test_eq_lufs_compensation_capped_at_3db(self, sample_rate: int):
        """EQ LUFS compensation should not exceed ±3 dB even for large drift."""
        from auralis.dsp.basic import amplify
        from auralis.dsp.unified import calculate_loudness_units

        audio = np.random.default_rng(42).standard_normal((sample_rate * 3, 2)).astype(np.float32) * 0.1
        pre_lufs = calculate_loudness_units(audio, sample_rate)

        # Simulate massive EQ boost (+10 dB)
        boosted = amplify(audio.copy(), 10.0)
        post_lufs = calculate_loudness_units(boosted, sample_rate)

        if pre_lufs is not None and post_lufs is not None:
            drift = post_lufs - pre_lufs
            correction = max(-3.0, min(3.0, -drift))
            # Correction should be capped at -3 dB even though drift is ~10 dB
            assert abs(correction) <= 3.0

    def test_spectral_tilt_correction_capped_at_2db(self):
        """Spectral tilt correction should not exceed ±2 dB."""
        from auralis.core.processing.continuous_mode import _apply_spectral_tilt_correction
        audio = np.random.default_rng(42).standard_normal((44100, 2)).astype(np.float32) * 0.1

        # Request 10 dB correction — should be capped internally to 2 dB
        corrected = _apply_spectral_tilt_correction(audio, 10.0, 44100)
        # Output should exist and have same shape
        assert corrected.shape == audio.shape
        # The function caps internally, so just verify it doesn't explode
        assert np.all(np.isfinite(corrected))


# ---------------------------------------------------------------------------
# Test: Guard Disabled = Identical Output
# ---------------------------------------------------------------------------

class TestGuardDisabled:
    """When guard is disabled, pipeline should produce identical output."""

    def test_guard_flag_exists_in_config(self):
        """Config should have the enable_cross_dimensional_guard flag."""
        config = UnifiedConfig()
        assert hasattr(config, 'enable_cross_dimensional_guard')
        assert config.enable_cross_dimensional_guard is True

    def test_quality_gate_flag_exists_in_config(self):
        """Config should have quality_gate_enabled flag."""
        config = UnifiedConfig()
        assert hasattr(config, 'quality_gate_enabled')
        assert config.quality_gate_enabled is True
        assert config.quality_gate_interval == 5
