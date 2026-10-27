"""Regression tests: the real-time chain's peak ceiling is smooth across chunks (#5721)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

RealtimeProcessor's safety peak, RealtimeLevelMatcher's 0.95 limiter and
AutoMasterProcessor's adaptive peak ceiling each scaled the WHOLE chunk by
``ceiling / max(|chunk|)``. That gain is constant inside a chunk and independent
between chunks, so it stepped (-2.8 dB in the probe: |out|/|in| 1.000 -> 0.728
on entering the hot chunk and 0.728 -> 1.000 on leaving it) at both edges of
any chunk that exceeded the ceiling. The three now share one
``StreamingPeakCeiling``: a per-sample envelope carried across chunks.

A zero-latency limiter cannot ramp ahead of a chunk that OPENS with an
over-ceiling sample (it has not seen it yet), so the entry probes start the hot
region part-way into the chunk; the ceiling is never traded for smoothness.
"""

import numpy as np
import pytest

from auralis.player.config import PlayerConfig
from auralis.player.realtime.auto_master import AutoMasterProcessor
from auralis.player.realtime.level_matcher import RealtimeLevelMatcher
from auralis.player.realtime.peak_ceiling import StreamingPeakCeiling
from auralis.player.realtime.processor import RealtimeProcessor

SR = 44100
CHUNK = 1024
MAX_STEP = 0.05          # the issue's bound on a single-sample gain step
CEILING = 0.95


def _carrier(chunks: int = 6, hot_chunk: int = 3, hot_from: int = 200,
             quiet: float = 0.4, hot: float = 1.3) -> np.ndarray:
    """Constant-level stereo signal (so gain is readable at every sample) with
    one over-ceiling region that starts ``hot_from`` samples into ``hot_chunk``."""
    audio = np.full((chunks * CHUNK, 2), quiet, dtype=np.float32)
    start = hot_chunk * CHUNK + hot_from
    audio[start:(hot_chunk + 1) * CHUNK] = hot
    return audio


def _spike_carrier(chunks: int = 6, hot_chunk: int = 3, at: int = 300,
                   width: int = 8, level: float = 0.5, spike: float = 1.3) -> np.ndarray:
    """Constant-level stereo signal with one short over-ceiling spike.

    The level matcher and the compressor both react to RMS, and a spike this
    short barely moves it, so only the peak ceiling can act on it.
    """
    audio = np.full((chunks * CHUNK, 2), level, dtype=np.float32)
    start = hot_chunk * CHUNK + at
    audio[start:start + width] = spike
    return audio


def _run(process, audio: np.ndarray) -> np.ndarray:
    return np.concatenate([process(audio[i:i + CHUNK]) for i in range(0, len(audio), CHUNK)])


def _gain(audio: np.ndarray, out: np.ndarray) -> np.ndarray:
    return out[:, 0].astype(np.float64) / audio[:, 0].astype(np.float64)


class TestStreamingPeakCeiling:
    def test_isolated_hot_chunk_has_no_step_on_either_side(self):
        audio = _carrier()
        ceiling = StreamingPeakCeiling(SR)
        out = _run(lambda c: ceiling.apply(c, CEILING), audio)

        steps = np.abs(np.diff(_gain(audio, out)))
        assert steps.max() < MAX_STEP, f"step {steps.max():.3f} at {int(steps.argmax())}"
        assert float(np.abs(out).max()) <= CEILING + 1e-6

    def test_the_old_per_chunk_scalar_steps_on_the_same_signal(self):
        """Pins what this replaces, so the bound above is not vacuous."""
        audio = _carrier()

        def old(chunk):
            peak = np.max(np.abs(chunk))
            return chunk * np.float32(CEILING / peak) if peak > CEILING else chunk

        steps = np.abs(np.diff(_gain(audio, _run(old, audio))))
        assert steps.max() > 0.2

    def test_release_is_carried_into_the_next_chunk(self):
        ceiling = StreamingPeakCeiling(SR)
        ceiling.apply(np.full((CHUNK, 2), 1.3, dtype=np.float32), CEILING)
        held = ceiling.current_gain

        after = ceiling.apply(np.full((CHUNK, 2), 0.4, dtype=np.float32), CEILING)
        first = float(after[0, 0]) / 0.4

        assert held < 0.8
        assert held < first < 1.0, "recovery must start from the carried gain, not snap to 1"
        assert ceiling.current_gain > held

    def test_a_chunk_that_opens_over_the_ceiling_is_still_capped(self):
        ceiling = StreamingPeakCeiling(SR)
        out = ceiling.apply(np.full((CHUNK, 2), 1.3, dtype=np.float32), CEILING)

        assert float(np.abs(out).max()) <= CEILING + 1e-6

    @pytest.mark.parametrize("seed", range(5))
    def test_ceiling_holds_on_dense_over_ceiling_noise(self, seed):
        rng = np.random.default_rng(seed)
        audio = (rng.standard_normal((8 * CHUNK, 2)) * 0.8).astype(np.float32)
        ceiling = StreamingPeakCeiling(SR)
        out = _run(lambda c: ceiling.apply(c, CEILING), audio)

        assert float(np.abs(out).max()) <= CEILING + 1e-6
        assert out.shape == audio.shape

    def test_below_ceiling_audio_is_returned_unchanged(self):
        audio = _carrier(hot=0.5)
        ceiling = StreamingPeakCeiling(SR)

        np.testing.assert_array_equal(ceiling.apply(audio, CEILING), audio)
        assert ceiling.current_gain == 1.0

    @pytest.mark.parametrize("dtype", [np.float32, np.float64])
    def test_dtype_and_shape_preserved(self, dtype):
        audio = _carrier().astype(dtype)
        out = StreamingPeakCeiling(SR).apply(audio[:CHUNK * 4], CEILING)

        assert out.dtype == dtype
        assert out.shape == audio[:CHUNK * 4].shape

    def test_mono_input(self):
        audio = _carrier()[:, 0].copy()
        out = _run(lambda c, k=StreamingPeakCeiling(SR): k.apply(c, CEILING), audio)

        assert out.shape == audio.shape
        assert float(np.abs(out).max()) <= CEILING + 1e-6

    def test_non_finite_samples_do_not_poison_the_envelope(self):
        audio = _carrier()[:CHUNK].copy()
        audio[10, :] = np.nan
        ceiling = StreamingPeakCeiling(SR)

        out = ceiling.apply(audio, CEILING)

        assert np.isnan(out[10]).all()
        assert np.isfinite(ceiling.current_gain)
        assert np.isfinite(np.delete(out, 10, axis=0)).all()

    def test_reset_returns_to_unity(self):
        ceiling = StreamingPeakCeiling(SR)
        ceiling.apply(np.full((CHUNK, 2), 1.3, dtype=np.float32), CEILING)
        ceiling.reset()

        assert ceiling.current_gain == 1.0


class TestRealtimeChainSites:
    def test_realtime_processor_safety_peak(self):
        config = PlayerConfig(sample_rate=SR, enable_level_matching=False,
                              enable_auto_mastering=False)
        processor = RealtimeProcessor(config)
        audio = _carrier()
        out = _run(lambda c: processor.process_chunk(c, SR), audio)

        assert np.abs(np.diff(_gain(audio, out))).max() < MAX_STEP
        assert float(np.abs(out).max()) <= config.realtime_safety_peak + 1e-6

    def test_level_matcher_ceiling(self):
        matcher = RealtimeLevelMatcher(PlayerConfig(sample_rate=SR))
        matcher.set_reference_audio(np.full((SR, 2), 0.5, dtype=np.float32))
        audio = _spike_carrier()
        out = _run(matcher.process, audio)

        assert np.abs(np.diff(_gain(audio, out))).max() < MAX_STEP
        assert float(np.abs(out).max()) <= 0.95 + 1e-6

    def test_auto_master_adaptive_peak_ceiling(self):
        master = AutoMasterProcessor(PlayerConfig(sample_rate=SR))
        master.set_enabled(True)
        master.adaptive_params = {
            'makeup_gain_db': 0.0, 'target_peak': 0.6,
            'compression_ratio': 1.0, 'reasoning': 'test',
        }
        audio = _spike_carrier()
        out = _run(master.process, audio)

        assert np.abs(np.diff(_gain(audio, out))).max() < MAX_STEP
        assert float(np.abs(out).max()) <= 0.6 + 1e-6
