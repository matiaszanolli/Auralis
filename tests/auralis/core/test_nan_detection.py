"""
Tests for NaN/Inf Detection in Processing Pipelines
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests that NaN and Inf values are properly detected and handled
in HybridProcessor and SimpleMasteringPipeline

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.simple_mastering import SimpleMasteringPipeline
from auralis.core.config import UnifiedConfig
from auralis.utils.logging import ModuleError, set_log_handler


class TestHybridProcessorNaNDetection:
    """Tests for NaN/Inf detection in HybridProcessor"""

    @pytest.fixture
    def processor(self):
        """Create HybridProcessor instance"""
        config = UnifiedConfig()
        config.set_processing_mode("adaptive")
        return HybridProcessor(config)

    def test_detect_nan_in_input(self, processor):
        """Test that NaN in input is detected"""
        # Create audio with NaN
        audio = np.random.randn(44100, 2).astype(np.float32) * 0.5
        audio[1000, 0] = np.nan

        # Should raise error on NaN in input
        with pytest.raises(ModuleError) as exc_info:
            processor.process(audio)

        assert "NaN" in str(exc_info.value) or "Inf" in str(exc_info.value)

    def test_detect_inf_in_input(self, processor):
        """Test that Inf in input is detected"""
        # Create audio with Inf
        audio = np.random.randn(44100, 2).astype(np.float32) * 0.5
        audio[1000, 1] = np.inf

        # Should raise error on Inf in input
        with pytest.raises(ModuleError) as exc_info:
            processor.process(audio)

        assert "NaN" in str(exc_info.value) or "Inf" in str(exc_info.value)

    def test_clean_audio_passes(self, processor):
        """Test that clean audio is processed successfully"""
        # Create clean audio
        audio = np.random.randn(44100, 2).astype(np.float32) * 0.5

        # Should process without error
        result = processor.process(audio)

        assert result is not None
        assert np.isfinite(result).all()

    def test_output_sanitization(self, processor):
        """Test that output is sanitized if processing produces NaN"""
        # Note: This test would need to inject NaN during processing
        # which is hard to do without mocking. For now, we just verify
        # that clean input produces clean output.

        audio = np.random.randn(44100, 2).astype(np.float32) * 0.5
        result = processor.process(audio)

        # Output should always be finite (sanitized if needed)
        assert np.isfinite(result).all()

    def test_realtime_chunk_nan_detection(self, processor):
        """Test that realtime chunk processing detects NaN"""
        # Create chunk with NaN
        chunk = np.random.randn(1024, 2).astype(np.float32) * 0.5
        chunk[500, 0] = np.nan

        # Should raise error on NaN in realtime chunk
        with pytest.raises(ModuleError):
            processor.process_realtime_chunk(chunk)

    def test_realtime_chunk_clean_audio(self, processor):
        """Test that clean realtime chunks are processed"""
        # Create clean chunk
        chunk = np.random.randn(1024, 2).astype(np.float32) * 0.5

        # Should process successfully
        result = processor.process_realtime_chunk(chunk)

        assert result is not None
        assert np.isfinite(result).all()


class TestSimpleMasteringNaNDetection:
    """Tests for NaN/Inf detection in SimpleMasteringPipeline"""

    @pytest.fixture
    def pipeline(self):
        """Create SimpleMasteringPipeline instance"""
        return SimpleMasteringPipeline()

    def test_detect_nan_in_input(self, pipeline):
        """Test that NaN in input is detected"""
        # Create audio with NaN
        audio = np.random.randn(2, 44100).astype(np.float32) * 0.5
        audio[0, 1000] = np.nan

        # Create dummy fingerprint
        fp = {
            'lufs': -14.0,
            'crest_db': 12.0,
            'bass_pct': 0.2,
            'sub_bass_pct': 0.05,
            'low_mid_pct': 0.15,
            'mid_pct': 0.2,
            'upper_mid_pct': 0.2,
            'presence_pct': 0.15,
            'air_pct': 0.1,
            'spectral_centroid': 0.5,
            'spectral_rolloff': 0.5,
            'spectral_flatness': 0.5,
            'transient_density': 0.5,
            'harmonic_ratio': 0.5,
            'pitch_stability': 0.5,
            'dynamic_range_variation': 0.5,
            'peak_consistency': 0.5,
            'stereo_width': 0.5,
            'phase_correlation': 1.0,
        }

        # Should raise error on NaN in input
        with pytest.raises(ModuleError) as exc_info:
            pipeline._process(audio, fp, peak_db=-6.0, intensity=1.0,
                            sample_rate=44100, verbose=False)

        assert "NaN" in str(exc_info.value) or "Inf" in str(exc_info.value)

    def test_clean_audio_passes(self, pipeline):
        """Test that clean audio is processed successfully"""
        # Create clean audio (channels, samples)
        audio = np.random.randn(2, 44100).astype(np.float32) * 0.5

        # Create dummy fingerprint
        fp = {
            'lufs': -14.0,
            'crest_db': 12.0,
            'bass_pct': 0.2,
            'sub_bass_pct': 0.05,
            'low_mid_pct': 0.15,
            'mid_pct': 0.2,
            'upper_mid_pct': 0.2,
            'presence_pct': 0.15,
            'air_pct': 0.1,
            'spectral_centroid': 0.5,
            'spectral_rolloff': 0.5,
            'spectral_flatness': 0.5,
            'transient_density': 0.5,
            'harmonic_ratio': 0.5,
            'pitch_stability': 0.5,
            'dynamic_range_variation': 0.5,
            'peak_consistency': 0.5,
            'stereo_width': 0.5,
            'phase_correlation': 1.0,
        }

        # Should process without error
        result, info = pipeline._process(audio, fp, peak_db=-6.0, intensity=1.0,
                                        sample_rate=44100, verbose=False)

        assert result is not None
        assert np.isfinite(result).all()

    def test_output_always_finite(self, pipeline):
        """Test that output is always finite (sanitized if needed)"""
        # Create clean audio
        audio = np.random.randn(2, 44100).astype(np.float32) * 0.5

        # Create fingerprint
        fp = {
            'lufs': -14.0,
            'crest_db': 12.0,
            'bass_pct': 0.2,
            'sub_bass_pct': 0.05,
            'low_mid_pct': 0.15,
            'mid_pct': 0.2,
            'upper_mid_pct': 0.2,
            'presence_pct': 0.15,
            'air_pct': 0.1,
            'spectral_centroid': 0.5,
            'spectral_rolloff': 0.5,
            'spectral_flatness': 0.5,
            'transient_density': 0.5,
            'harmonic_ratio': 0.5,
            'pitch_stability': 0.5,
            'dynamic_range_variation': 0.5,
            'peak_consistency': 0.5,
            'stereo_width': 0.5,
            'phase_correlation': 1.0,
        }

        result, info = pipeline._process(audio, fp, peak_db=-6.0, intensity=1.0,
                                        sample_rate=44100, verbose=False)

        # Output should always be finite
        assert np.isfinite(result).all()


_QUIET_FP = {
    # lufs <= -12 routes to QuietBranch (the longest stage chain).
    'lufs': -14.0, 'crest_db': 12.0, 'bass_pct': 0.2, 'sub_bass_pct': 0.05,
    'low_mid_pct': 0.15, 'mid_pct': 0.2, 'upper_mid_pct': 0.2, 'presence_pct': 0.15,
    'air_pct': 0.1, 'spectral_centroid': 0.5, 'spectral_rolloff': 0.5,
    'spectral_flatness': 0.5, 'transient_density': 0.5, 'harmonic_ratio': 0.5,
    'pitch_stability': 0.5, 'dynamic_range_variation': 0.5, 'peak_consistency': 0.5,
    'stereo_width': 0.5, 'phase_correlation': 1.0,
}


class TestSimpleMasteringInterStageGuard:
    """Inter-stage NaN/Inf guards localize the failing stage (#4099).

    Without these guards, a NaN produced by any one mid-chain stage propagated
    silently to the exit, where sanitize_audio zeroed the whole output — hiding
    which stage was at fault. The guards raise (repair=False) at stage-group
    boundaries instead, naming the group.
    """

    @pytest.fixture
    def pipeline(self):
        return SimpleMasteringPipeline()

    def _run(self, pipeline):
        audio = np.random.randn(2, 44100).astype(np.float32) * 0.5
        return pipeline._process(audio, _QUIET_FP, peak_db=-6.0, intensity=1.0,
                                 sample_rate=44100, verbose=False)

    def test_nan_from_mid_chain_stage_raises_localized_error(self, pipeline, monkeypatch):
        """A NaN injected by _apply_mid_warmth raises at the next guard, not zeros."""
        def inject_nan(processed, *args, **kwargs):
            bad = processed.copy()
            bad[0, 0] = np.nan
            return bad, {'stage': 'mid_warmth', 'injected_nan': True}

        monkeypatch.setattr(pipeline, '_apply_mid_warmth', inject_nan)

        with pytest.raises(ModuleError) as exc_info:
            self._run(pipeline)

        msg = str(exc_info.value)
        assert 'NaN' in msg or 'Inf' in msg
        # Localized to the guard right after the low-end/warmth group.
        assert 'low-end/warmth' in msg

    def test_nan_from_later_stage_localizes_to_a_different_group(self, pipeline, monkeypatch):
        """Injecting later (air enhancement) trips the spectral-group guard."""
        def inject_inf(processed, *args, **kwargs):
            bad = processed.copy()
            bad[1, 5] = np.inf
            return bad, {'stage': 'air', 'injected_inf': True}

        monkeypatch.setattr(pipeline, '_apply_air_enhancement', inject_inf)

        with pytest.raises(ModuleError) as exc_info:
            self._run(pipeline)

        assert 'Quiet after spectral' in str(exc_info.value)

    def test_guard_is_pass_through_on_finite_audio(self, pipeline):
        """Happy path is unchanged: guards return finite audio untouched."""
        result, info = self._run(pipeline)
        assert result is not None
        assert np.isfinite(result).all()

    def test_assert_finite_helper_passes_finite_and_raises_nonfinite(self):
        """Direct unit test of the shared guard helper on ProcessingBranch."""
        from auralis.core.mastering_branches import QuietBranch
        branch = QuietBranch(SimpleMasteringPipeline())

        finite = np.random.randn(2, 100).astype(np.float32)
        # Returns the same array unchanged when finite.
        assert branch._assert_finite(finite, 'unit') is finite

        bad = finite.copy()
        bad[0, 0] = np.nan
        with pytest.raises(ModuleError):
            branch._assert_finite(bad, 'unit')


class TestNaNPropagationPrevention:
    """Tests to ensure NaN doesn't propagate through pipeline"""

    def test_filter_stability_edge_case(self):
        """Test that extreme inputs don't cause filter instability"""
        # This would test actual filter operations that might produce NaN
        # For now, we verify the detection is in place
        pass  # Placeholder for integration tests

    def test_crossfade_with_clean_audio(self):
        """Test that crossfading doesn't introduce NaN"""
        # This would test the actual crossfading logic
        # For now, we verify the detection is in place
        pass  # Placeholder for integration tests
