"""
Regression test: ContinuousMode silence normalization does not produce NaN (#4104)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For pure silence the LUFS measurement is non-finite, the RMS fallback computes
to_db(0.0) == -inf, and (before the fix) adjustment = target_lufs - (-inf) =
+inf, so amplify(silence, +inf) = 0.0 * inf = NaN across the whole buffer —
which trips validate_audio_finite(repair=False) downstream and crashes the
stream. _apply_final_normalization now short-circuits on the non-finite fallback.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from auralis.core.config import UnifiedConfig
from auralis.core.processing.base.db_conversion import DBConversion
from auralis.core.processing.continuous_mode import ContinuousMode


def _mode() -> ContinuousMode:
    # _apply_final_normalization only touches self.config.internal_sample_rate;
    # the analyzers are irrelevant for this path.
    return ContinuousMode(
        config=UnifiedConfig(),
        content_analyzer=MagicMock(),
        fingerprint_analyzer=MagicMock(),
    )


def test_to_db_zero_is_neg_inf():
    """Pins the upstream behavior that makes the guard necessary."""
    assert DBConversion.to_db(0.0) == -np.inf


def test_silence_produces_finite_output():
    mode = _mode()
    params = SimpleNamespace(target_lufs=-14.0)
    audio = np.zeros((8192, 2), dtype=np.float32)

    out = mode._apply_final_normalization(audio, params)

    assert np.all(np.isfinite(out)), "silence normalization must not produce NaN/Inf"
    assert not np.any(np.isnan(out))
    assert out.shape == audio.shape
    assert out.dtype == audio.dtype
    # Silence stays silence (no +inf gain applied).
    assert np.max(np.abs(out)) == 0.0


def test_nonsilent_audio_still_normalized_finite():
    """The guard must not break the normal (finite-LUFS) path."""
    mode = _mode()
    params = SimpleNamespace(target_lufs=-14.0)
    rng = np.random.default_rng(3)
    audio = (rng.standard_normal((mode.config.internal_sample_rate, 2)) * 0.1).astype(np.float32)

    out = mode._apply_final_normalization(audio, params)

    assert np.all(np.isfinite(out))
    assert out.shape == audio.shape
    assert out.dtype == np.float32
