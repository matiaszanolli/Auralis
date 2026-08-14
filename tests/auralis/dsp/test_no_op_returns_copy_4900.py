# -*- coding: utf-8 -*-

"""
No-op/bypass DSP paths must never hand back the caller's own array (#4900)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Eight DSP entry points, on their "nothing to do" branch, returned the caller's
exact array object instead of ``audio.copy()`` (one of the eight,
``RealtimeAdaptiveEQ.process_realtime``, was deleted as unreachable in #4873) — the same class of bug closed
#3427 (LookaheadBuffer) and #2512 (mono_to_stereo) for. No live corruption
existed (every reachable caller already owned a copy by that point), but it
was a latent in-place-mutation bug waiting for any future caller to mutate
the "processed" result in place.

This module provides a shared ``assert_returns_copy`` helper and applies it
to the surviving sites, plus the stage-boundary fix in
``core/stages/harmonic_exciter.py`` that used to propagate an aliased array
straight past the ``no_op()`` contract every other stage honours.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, Callable

import numpy as np
import pytest

from auralis.core.dsp.harmonic_exciter import HarmonicExciter
from auralis.core.dsp.resonance_notcher import ResonanceNotcher
from auralis.core.dsp.transient_shaper import TransientShaper
from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.stages import harmonic_exciter as harmonic_exciter_stage
from auralis.dsp.dynamics.lookahead_buffer import LookaheadBuffer
from auralis.dsp.dynamics.lowmid_transient_enhancer import LowMidTransientEnhancer
from auralis.dsp.utils.stereo import adjust_stereo_width, adjust_stereo_width_multiband


def assert_returns_copy(fn: Callable[..., np.ndarray], audio: np.ndarray, *args: Any, **kwargs: Any) -> np.ndarray:
    """Call `fn(audio, *args, **kwargs)` and assert the result is a genuine
    copy, not an alias of `audio` — the shared regression guard from #4900.

    Checks both object identity (`is not`) and memory aliasing
    (`np.shares_memory`), since a view (e.g. a slice) would pass the first
    check but still corrupt the original on an in-place write.
    """
    result = fn(audio, *args, **kwargs)
    assert result is not audio, f"{fn} returned the caller's own array object"
    assert not np.shares_memory(result, audio), f"{fn} returned a view/alias of the input array"
    # Mutating the result must never touch the original input.
    original = audio.copy()
    result[:] = result + 1.0 if result.size else result
    np.testing.assert_array_equal(audio, original)
    return result


class TestHarmonicExciterReturnsCopy:
    def test_wet_db_below_floor_returns_copy(self):
        audio = np.random.randn(2, 4410).astype(np.float32)
        assert_returns_copy(
            HarmonicExciter.apply, audio,
            sample_rate=44100, wet_db=-61.0,
        )

    def test_degenerate_donor_band_returns_copy(self):
        audio = np.random.randn(2, 4410).astype(np.float32)
        # donor_low_hz == donor_high_hz collapses low_norm >= high_norm.
        assert_returns_copy(
            HarmonicExciter.apply, audio,
            sample_rate=44100, wet_db=-10.0,
            donor_low_hz=1000.0, donor_high_hz=1000.0,
        )


class TestTransientShaperReturnsCopy:
    def test_negligible_attack_boost_returns_copy(self):
        audio = np.random.randn(2, 4410).astype(np.float32)
        assert_returns_copy(
            TransientShaper.apply, audio,
            sample_rate=44100, band_low_hz=60.0, band_high_hz=250.0,
            attack_boost_db=0.01,
        )

    def test_degenerate_band_returns_copy(self):
        audio = np.random.randn(2, 4410).astype(np.float32)
        assert_returns_copy(
            TransientShaper.apply, audio,
            sample_rate=44100, band_low_hz=100.0, band_high_hz=100.0,
            attack_boost_db=6.0,
        )


class TestResonanceNotcherReturnsCopy:
    def test_no_notches_returns_copy(self):
        audio = np.random.randn(2, 4410).astype(np.float32)
        assert_returns_copy(ResonanceNotcher.apply, audio, sample_rate=44100, notches=[])


class TestAdjustStereoWidthReturnsCopy:
    def test_non_stereo_input_returns_copy(self):
        mono = np.random.randn(4410).astype(np.float32)
        assert_returns_copy(adjust_stereo_width, mono, width_factor=0.8)


class TestAdjustStereoWidthMultibandReturnsCopy:
    def test_non_stereo_input_returns_copy(self):
        mono = np.random.randn(4410).astype(np.float32)
        assert_returns_copy(adjust_stereo_width_multiband, mono, width_factor=0.8, sample_rate=44100)

    def test_no_change_width_factor_returns_copy(self):
        stereo = np.random.randn(4410, 2).astype(np.float32)
        assert_returns_copy(adjust_stereo_width_multiband, stereo, width_factor=0.5, sample_rate=44100)


class TestLookaheadBufferReturnsCopy:
    def test_zero_lookahead_returns_copy(self):
        buf = LookaheadBuffer(lookahead_samples=0)
        audio = np.random.randn(4410).astype(np.float32)
        assert_returns_copy(buf.apply, audio)


class TestLowMidTransientEnhancerReturnsCopy:
    def test_zero_intensity_returns_copy(self):
        enhancer = LowMidTransientEnhancer(sample_rate=44100)
        audio = np.random.randn(4410).astype(np.float32)
        assert_returns_copy(enhancer.enhance_transients, audio, intensity=0.0)


class TestHarmonicExciterStageRoutesThroughNoOp:
    """The stage boundary must not propagate an aliased array past no_op() (#4900)."""

    def test_wet_db_below_floor_reports_no_op(self):
        config = SimpleMasteringConfig()
        audio = np.random.randn(2, 4410).astype(np.float32)

        # intensity/hf_lift just above the eps guard at line 58, but low
        # enough that wet_db computed from config's min/max dB range still
        # lands <= -60 — the deeper bypass this issue's evidence describes.
        result, stage_info = harmonic_exciter_stage.apply(
            audio,
            presence_pct=0.0, air_pct=0.0, spectral_rolloff=0.0,
            intensity=1e-4, sample_rate=44100, verbose=False,
            config=config, hf_lift=1e-4,
        )

        assert result is not audio
        assert not np.shares_memory(result, audio)
        assert stage_info is None, "a stage that did nothing must report no_op(), not fabricated stage_info"

    def test_degenerate_donor_band_reports_no_op(self, monkeypatch: pytest.MonkeyPatch):
        config = SimpleMasteringConfig()
        monkeypatch.setattr(config, "EXCITER_DONOR_LOW_HZ", 1000.0)
        monkeypatch.setattr(config, "EXCITER_DONOR_HIGH_HZ", 1000.0)
        audio = np.random.randn(2, 4410).astype(np.float32)

        result, stage_info = harmonic_exciter_stage.apply(
            audio,
            presence_pct=0.0, air_pct=0.0, spectral_rolloff=0.0,
            intensity=1.0, sample_rate=44100, verbose=False,
            config=config, hf_lift=1.0,
        )

        assert result is not audio
        assert not np.shares_memory(result, audio)
        assert stage_info is None

    def test_normal_operation_still_processes(self):
        """Regression guard: the new stage-level guards must not swallow the
        normal, engaged path."""
        config = SimpleMasteringConfig()
        audio = np.random.randn(2, 44100).astype(np.float32) * 0.1

        result, stage_info = harmonic_exciter_stage.apply(
            audio,
            presence_pct=0.0, air_pct=0.0, spectral_rolloff=0.0,
            intensity=1.0, sample_rate=44100, verbose=False,
            config=config, hf_lift=1.0,
        )

        assert result.shape == audio.shape
        assert stage_info is not None
        assert stage_info["stage"] == "harmonic_exciter"
