"""
Regression tests: AdaptiveMode / ContinuousMode final-normalization NaN/Inf guard (#4237)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

HybridMode._apply_hybrid_processing() calls validate_audio_finite(..., repair=True)
before normalize() (#3429), but AdaptiveMode._apply_final_normalization() — which
is ALSO HybridMode's own no-reference fallback path (the common case: no
reference track set) — had zero validate_audio_finite calls. ContinuousMode's
_apply_final_normalization() only guarded the narrower silence-induced -inf
LUFS case (#4104), not a general NaN/Inf already present in the audio itself.

Both now guard with validate_audio_finite(repair=True) at the top of their
final-normalization method, matching HybridMode.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from auralis.core.config import UnifiedConfig
from auralis.core.processing.adaptive_mode import AdaptiveMode
from auralis.core.processing.continuous_mode import ContinuousMode


def _adaptive_mode() -> AdaptiveMode:
    # _apply_final_normalization only touches self.config.internal_sample_rate
    # and self.last_content_profile; the analyzers are irrelevant for this path.
    mode = AdaptiveMode(
        config=UnifiedConfig(),
        content_analyzer=MagicMock(),
        target_generator=MagicMock(),
        spectrum_mapper=MagicMock(),
    )
    mode.last_content_profile = {}
    return mode


def _continuous_mode() -> ContinuousMode:
    return ContinuousMode(
        config=UnifiedConfig(),
        content_analyzer=MagicMock(),
        fingerprint_analyzer=MagicMock(),
    )


class TestAdaptiveModeFinalNormalizationNaNGuard:
    """Fixes #4237: AdaptiveMode._apply_final_normalization must self-heal
    NaN/Inf instead of silently propagating it into makeup gain / peak
    normalization / the safety limiter."""

    def _params(self):
        return SimpleNamespace(expansion_amount=0.0, intensity=1.0)

    def test_nan_input_repaired_to_finite(self):
        mode = _adaptive_mode()
        audio = np.random.randn(8192, 2).astype(np.float32) * 0.1
        audio[100, 0] = np.nan
        audio[200, 1] = np.inf

        out = mode._apply_final_normalization(audio, self._params())

        assert np.all(np.isfinite(out)), "NaN/Inf must be repaired, not propagated"
        assert out.shape == audio.shape
        # Pre-existing, unrelated to the NaN guard: the makeup-gain branch's
        # arithmetic promotes float32 -> float64. Both are valid per the
        # project's audio dtype invariant (CLAUDE.md); this test only cares
        # that it's still a float dtype, not exact-match with the input.
        assert out.dtype in (np.float32, np.float64)

    def test_all_nan_input_repaired_to_finite(self):
        """Worst case: every sample is NaN — must not crash, must self-heal."""
        mode = _adaptive_mode()
        audio = np.full((4096, 2), np.nan, dtype=np.float32)

        out = mode._apply_final_normalization(audio, self._params())

        assert np.all(np.isfinite(out))
        assert out.shape == audio.shape

    def test_clean_audio_still_normalized_finite(self):
        """The guard must not break the normal (finite) path."""
        mode = _adaptive_mode()
        rng = np.random.default_rng(7)
        audio = (rng.standard_normal((mode.config.internal_sample_rate, 2)) * 0.1).astype(np.float32)

        out = mode._apply_final_normalization(audio, self._params())

        assert np.all(np.isfinite(out))
        assert out.shape == audio.shape
        assert out.dtype == np.float32

    def test_reachable_via_hybrid_mode_no_reference_fallback(self):
        """HybridMode.process() with reference_audio=None delegates straight
        to AdaptiveMode.process() (auralis/core/processing/hybrid_mode.py:68)
        — this is the common no-reference case and was completely unguarded
        before #4237, unlike the reference-blend path #3429 fixed."""
        from auralis.core.hybrid_processor import HybridProcessor

        config = UnifiedConfig()
        config.set_processing_mode("adaptive")
        processor = HybridProcessor(config)

        audio = np.random.randn(processor.config.internal_sample_rate, 2).astype(np.float32) * 0.3
        result = processor.process(audio)

        assert np.all(np.isfinite(result))
        assert result.shape == audio.shape


class TestContinuousModeFinalNormalizationGeneralNaNGuard:
    """Fixes #4237: ContinuousMode._apply_final_normalization's #4104 guard
    only covered silence-induced -inf LUFS. A general NaN/Inf already
    present in `audio` (e.g. from an upstream DSP bug) must also self-heal."""

    def _params(self):
        return SimpleNamespace(target_lufs=-14.0)

    def test_nan_input_repaired_to_finite(self):
        mode = _continuous_mode()
        audio = np.random.randn(8192, 2).astype(np.float32) * 0.1
        audio[50, 0] = np.nan
        audio[75, 1] = -np.inf

        out = mode._apply_final_normalization(audio, self._params())

        assert np.all(np.isfinite(out)), "NaN/Inf must be repaired, not propagated"
        assert out.shape == audio.shape
        assert out.dtype == audio.dtype

    def test_silence_guard_4104_still_works(self):
        """The pre-existing #4104 silence guard must be unaffected by the
        new general NaN guard added ahead of it."""
        mode = _continuous_mode()
        audio = np.zeros((8192, 2), dtype=np.float32)

        out = mode._apply_final_normalization(audio, self._params())

        assert np.all(np.isfinite(out))
        assert np.max(np.abs(out)) == 0.0  # silence stays silence, no +inf gain

    def test_nonsilent_audio_still_normalized_finite(self):
        mode = _continuous_mode()
        rng = np.random.default_rng(11)
        audio = (rng.standard_normal((mode.config.internal_sample_rate, 2)) * 0.1).astype(np.float32)

        out = mode._apply_final_normalization(audio, self._params())

        assert np.all(np.isfinite(out))
        assert out.shape == audio.shape
        assert out.dtype == np.float32
