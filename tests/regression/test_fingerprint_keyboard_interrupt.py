"""
Regression: Ctrl-C propagates out of AudioFingerprintAnalyzer.analyze() (#2514)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#2514, #2668 and #3701 hardened a ThreadPoolExecutor that ran the Python
sub-analyzers in parallel, so a KeyboardInterrupt neither blocked on shutdown
nor left futures writing into the result. Since #13 Stage 3 (871356f75) the
whole fingerprint is one in-process Rust call, compute_fingerprint_schema():
no executor, no futures, and close() is a no-op. The tests that pinned that
machinery asserted code that no longer exists.

What still holds is the point of #2514: an interrupt reaches the caller as
itself. analyze() converts every Exception into FingerprintUnavailable (#6107);
KeyboardInterrupt is a BaseException and must not be converted, or a Ctrl-C
during a scan would read as "fingerprint unavailable" and the scan would go on.
"""

from unittest.mock import patch

import numpy as np
import pytest

from auralis.analysis.fingerprint import audio_fingerprint_analyzer as module
from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
    FingerprintUnavailable,
)
from auralis.analysis.fingerprint.windows import FINGERPRINT_SAMPLE_RATE


def _one_second_stereo() -> np.ndarray:
    return np.random.default_rng(0).standard_normal((FINGERPRINT_SAMPLE_RATE, 2)).astype(np.float32) * 0.1


@pytest.mark.regression
def test_keyboard_interrupt_in_the_engine_reaches_the_caller_as_itself():
    with patch.object(module, "compute_fingerprint_schema", side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            AudioFingerprintAnalyzer().analyze(_one_second_stereo(), FINGERPRINT_SAMPLE_RATE)


@pytest.mark.regression
def test_an_engine_error_is_still_reported_as_fingerprint_unavailable():
    """The contrast that makes the test above meaningful: ordinary errors are converted."""
    with patch.object(module, "compute_fingerprint_schema", side_effect=RuntimeError("engine")):
        with pytest.raises(FingerprintUnavailable, match="engine"):
            AudioFingerprintAnalyzer().analyze(_one_second_stereo(), FINGERPRINT_SAMPLE_RATE)
