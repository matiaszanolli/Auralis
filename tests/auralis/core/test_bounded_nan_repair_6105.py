"""
Bounded in-stage NaN repair (#6105)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ContinuousMode / AdaptiveMode / HybridMode ran
``validate_audio_finite(..., repair=True)`` on whole buffers before the
output reached the ``repair=False`` boundary guards or the pipeline's
unprocessed-audio fallback (#4672). A non-finite stage parameter made the
whole buffer NaN, and the unconditional repair zero-replaced it into a
silent 10-second chunk that was then cached — with only a WARNING.

The repair is now bounded by ``MAX_IN_STAGE_REPAIR_FRACTION``: a tiny
non-finite fraction is zeroed, a mostly non-finite buffer raises
ModuleError so the fail-fast policy (#2520) and the pipeline fallback can
fire. A non-finite ``reference`` also fails fast at the
HybridProcessor.process boundary, like ``target`` always has.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.processing.base.db_conversion import DBConversion
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.utils.audio_validation import (
    MAX_IN_STAGE_REPAIR_FRACTION,
    validate_audio_finite,
)
from auralis.utils.logging import ModuleError


def test_tiny_non_finite_fraction_is_repaired():
    """A handful of stray NaN samples is repaired to zeros with no raise."""
    audio = np.ones((8192, 2), dtype=np.float32)
    audio[100, 0] = np.nan
    audio[200, 1] = np.inf

    out = validate_audio_finite(
        audio, context="test", repair=True,
        repair_max_fraction=MAX_IN_STAGE_REPAIR_FRACTION,
    )

    assert np.all(np.isfinite(out))
    assert out[100, 0] == 0.0 and out[200, 1] == 0.0
    assert out[0, 0] == 1.0


def test_mostly_non_finite_buffer_raises_instead_of_zeroing():
    """A whole-buffer NaN — the signature of a broken stage, not stray
    samples — must raise, not ship digital silence."""
    audio = np.full((8192, 2), np.nan, dtype=np.float32)

    with pytest.raises(ModuleError):
        validate_audio_finite(
            audio, context="test stage", repair=True,
            repair_max_fraction=MAX_IN_STAGE_REPAIR_FRACTION,
        )


def test_unbounded_repair_unchanged_for_last_boundary():
    """Without a fraction limit the repair stays unconditional — the
    saver/realtime last-boundary behaviour (#5507) must not change."""
    audio = np.full((8192, 2), np.nan, dtype=np.float32)

    out = validate_audio_finite(audio, context="last boundary", repair=True)

    assert np.all(out == 0.0)


def _mode() -> ContinuousMode:
    return ContinuousMode(
        config=UnifiedConfig(),
        content_analyzer=MagicMock(),
        fingerprint_analyzer=MagicMock(),
    )


def test_continuous_mode_all_nan_buffer_raises():
    """ContinuousMode._apply_final_normalization must not turn a fully
    non-finite buffer into a zero chunk (the old silent-mute path)."""
    mode = _mode()
    params = SimpleNamespace(target_lufs=-14.0)
    audio = np.full((8192, 2), np.nan, dtype=np.float32)

    with pytest.raises(ModuleError):
        mode._apply_final_normalization(audio, params)


def test_continuous_mode_stray_nan_still_repaired():
    """A couple of stray NaN samples in an otherwise good buffer are still
    repaired (the #4237 behaviour is preserved for the bounded case)."""
    mode = _mode()
    params = SimpleNamespace(target_lufs=-14.0)
    rng = np.random.default_rng(5)
    audio = (rng.standard_normal((8192, 2)) * 0.1).astype(np.float32)
    audio[10, 0] = np.nan
    audio[20, 1] = -np.inf

    out = mode._apply_final_normalization(audio, params)

    assert np.all(np.isfinite(out))
    assert out.shape == audio.shape
    assert out.dtype == np.float32


def test_adaptive_normalization_all_nan_buffer_raises():
    """AdaptiveMode's final normalization shares the bounded repair."""
    from auralis.core.processing.adaptive_normalization import apply_final_normalization

    mode = _mode()
    audio = np.full((8192, 2), np.nan, dtype=np.float32)

    with pytest.raises(ModuleError):
        apply_final_normalization(mode, audio, SimpleNamespace())


def test_hybrid_mode_nan_reference_raises_at_boundary():
    """A NaN reference in hybrid mode fails fast at the
    HybridProcessor.process boundary, exactly like a NaN target does —
    instead of blending it in and zeroing the whole output."""
    processor = HybridProcessor(UnifiedConfig())
    processor.set_processing_mode("hybrid")

    rng = np.random.default_rng(7)
    target = (rng.standard_normal((44100, 2)) * 0.1).astype(np.float32)
    reference = target.copy()
    reference[5000, 0] = np.nan

    with pytest.raises(ModuleError):
        processor.process(target, reference=reference)


def test_hybrid_mode_clean_reference_still_processes():
    """The new reference validation must not break the normal hybrid path."""
    processor = HybridProcessor(UnifiedConfig())
    processor.set_processing_mode("hybrid")

    rng = np.random.default_rng(7)
    target = (rng.standard_normal((44100, 2)) * 0.1).astype(np.float32)

    result = processor.process(target, reference=target.copy())

    assert result is not None
    assert result.shape == target.shape
    assert np.all(np.isfinite(result))
    # Silence stays finite through the pipeline (guard for the guard).
    assert np.isfinite(DBConversion.to_db(1.0))
