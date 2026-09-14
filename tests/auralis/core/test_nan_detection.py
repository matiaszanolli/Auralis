"""
Tests for NaN/Inf Detection in Processing Pipelines
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests that NaN and Inf values are properly detected and handled
in HybridProcessor and SimpleMasteringPipeline

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.simple_mastering import SimpleMasteringPipeline
from auralis.utils.logging import ModuleError


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

    def test_chunk_sized_input_nan_detection(self, processor):
        """NaN detection must hold for chunk-sized inputs too.

        These two cases used to run through ``process_realtime_chunk``, which
        #4873 deleted with the rest of the unreachable real-time path. The
        NaN-guard contract they cover is not realtime-specific — it is
        ``validate_audio_finite`` at the ``process()`` entry point — so they are
        re-pointed at the live path rather than dropped.
        """
        chunk = np.random.randn(1024, 2).astype(np.float32) * 0.5
        chunk[500, 0] = np.nan

        with pytest.raises(ModuleError):
            processor.process(chunk)

    def test_chunk_sized_clean_audio(self, processor):
        """A clean chunk-sized input processes successfully."""
        chunk = np.random.randn(1024, 2).astype(np.float32) * 0.5

        result = processor.process(chunk)

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


_CONTINUOUS_FP = {
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
        return pipeline._process(audio, _CONTINUOUS_FP, peak_db=-6.0, intensity=1.0,
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

        assert 'continuous path after spectral' in str(exc_info.value)

    def test_guard_is_pass_through_on_finite_audio(self, pipeline):
        """Happy path is unchanged: guards return finite audio untouched."""
        result, info = self._run(pipeline)
        assert result is not None
        assert np.isfinite(result).all()

    def test_assert_finite_helper_passes_finite_and_raises_nonfinite(self):
        """Direct unit test of the shared guard helper on ProcessingBranch."""
        from auralis.core.mastering_branches import ContinuousMasteringBranch
        branch = ContinuousMasteringBranch(SimpleMasteringPipeline())

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
        """Extreme inputs (#5428) -- was a bare `pass` claiming this "would
        test actual filter operations". sosfiltfilt_safe (dsp/utils/filters.py)
        is exactly that target: it exists specifically to handle signals too
        short for scipy's sosfiltfilt without crashing or corrupting output,
        the concrete "filter instability" case this test's docstring names.
        """
        from scipy.signal import butter

        from auralis.dsp.utils.filters import (
            sosfiltfilt_padlen,
            sosfiltfilt_safe,
        )

        sos = butter(4, 0.3, output='sos')
        padlen = sosfiltfilt_padlen(sos)

        # Shorter than the filter's own pad length -- the exact edge case
        # this helper exists to guard, per its module docstring.
        too_short = np.random.randn(padlen - 1).astype(np.float32) * 0.5
        result_short = sosfiltfilt_safe(sos, too_short, context='test')
        assert np.isfinite(result_short).all()
        assert result_short.shape == too_short.shape

        # Extreme amplitude, long enough to actually filter -- the filter
        # itself must not produce NaN/Inf under a large-magnitude input.
        extreme = (np.random.randn(padlen * 4).astype(np.float32) * 1e6)
        result_extreme = sosfiltfilt_safe(sos, extreme, context='test')
        assert np.isfinite(result_extreme).all(), (
            "sosfiltfilt_safe produced non-finite output for an extreme-"
            "amplitude input"
        )

        # A single impulse -- the classic filter-instability stress case.
        impulse = np.zeros(padlen * 4, dtype=np.float32)
        impulse[padlen * 2] = 1.0
        result_impulse = sosfiltfilt_safe(sos, impulse, context='test')
        assert np.isfinite(result_impulse).all()

    def test_crossfade_with_clean_audio(self):
        """Crossfading doesn't introduce NaN (#5428) -- was a bare `pass`
        claiming this "would test the actual crossfading logic". The engine's
        chunk-boundary crossfade lives in mastering_chunk_loop.process_chunks
        (equal-gain raised-cosine blend, #4966); this drives it end-to-end
        with a real multi-chunk clean signal through a passthrough pipeline
        stub, isolating the crossfade math itself from full DSP (already
        covered by the other classes in this file).
        """
        import tempfile
        from pathlib import Path

        import soundfile as sf

        from auralis.core import mastering_chunk_loop

        sr = 8000

        class _TinyConfig:
            CROSSFADE_DURATION_SEC = 0.1
            CHUNK_DURATION_SEC = 1
            PROGRESS_REPORT_INTERVAL_CHUNKS = 1000
            TRUE_PEAK_CEILING_DB = -0.3

        class _PassthroughPipeline:
            def _process(self, audio, fp, peak_db, intensity, sample_rate, verbose):
                return audio.copy(), {'stages': ['stub']}

        def _make_wav(tmp_path):
            duration_s = 5.0
            frames = int(sr * duration_s)
            t = np.linspace(0, duration_s, frames, endpoint=False, dtype=np.float32)
            tone = 0.3 * np.sin(2 * np.pi * 220 * t)
            stereo = np.stack([tone, tone], axis=1)
            path = tmp_path / 'crossfade_source.wav'
            sf.write(str(path), stereo, sr)
            return path, frames

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_path, total_frames = _make_wav(tmp_path)
            out_path = tmp_path / 'crossfade_out.wav'

            # CHUNK_DURATION_SEC=1 against a 5s source forces several chunk
            # boundaries -- the crossfade code path in process_chunks only
            # runs when there is more than one chunk.
            mastering_chunk_loop.process_chunks(
                _PassthroughPipeline(), source_path, str(out_path), sr,
                total_frames, {'lufs': -14.0}, 1.0, _TinyConfig(), False,
            )

            output, out_sr = sf.read(str(out_path))

        assert out_sr == sr
        assert np.isfinite(output).all(), (
            "Crossfading between chunks produced non-finite samples"
        )
