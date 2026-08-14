"""
HybridProcessor returns a consistent rank on every path (#4976)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_process_impl` handled empty audio *before* the mono->stereo
`np.column_stack` conversion, while the all-zeros early return a few lines
later ran *after* it. From one entry point, a mono input therefore came back
1-D `(0,)` when empty and 2-D `(N, 2)` otherwise — so a caller indexing
`result[:, 0]`, reasonable given the shape this processor otherwise always
guarantees, hit an IndexError only on the empty-mono path.

The length invariant (`0 == 0`) and copy semantics both held, so this was a
shape-contract inconsistency rather than corruption. Fixed by hoisting the
mono->stereo conversion above the empty check.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor


@pytest.fixture
def processor() -> HybridProcessor:
    return HybridProcessor(UnifiedConfig())


@pytest.mark.parametrize(
    "label, audio",
    [
        ("empty mono", np.array([], dtype=np.float32)),
        ("empty stereo", np.empty((0, 2), dtype=np.float32)),
        ("below MIN_SAMPLES mono", np.zeros(512, dtype=np.float32)),
        ("below MIN_SAMPLES stereo", np.zeros((512, 2), dtype=np.float32)),
        ("silent mono", np.zeros(2048, dtype=np.float32)),
        ("normal mono", (np.random.default_rng(0).standard_normal(2048) * 0.1).astype(np.float32)),
    ],
)
def test_every_return_path_is_2d_stereo(processor, label, audio):
    """Every early return and the full path agree on rank and channel count."""
    result = processor.process(audio)

    assert result is not None, f"{label}: processor returned None"
    assert result.ndim == 2, (
        f"{label}: got {result.ndim}-D {result.shape}; every path must return "
        f"2-D (N, 2) so callers can index result[:, 0] unconditionally"
    )
    assert result.shape[1] == 2, f"{label}: expected 2 channels, got {result.shape[1]}"
    # The load-bearing invariant for gapless playback.
    assert result.shape[0] == audio.shape[0], f"{label}: sample count changed"


def test_empty_mono_is_indexable_like_every_other_result(processor):
    """The concrete failure mode the shape inconsistency produced (#4976)."""
    result = processor.process(np.array([], dtype=np.float32))

    # Pre-fix this raised `IndexError: too many indices for array`.
    left = result[:, 0]
    assert left.shape == (0,)


def test_empty_input_still_copies(processor):
    """Hoisting the conversion must not turn the empty return into a view."""
    audio = np.array([], dtype=np.float32)
    result = processor.process(audio)
    assert result is not audio
    assert not np.shares_memory(result, audio)
