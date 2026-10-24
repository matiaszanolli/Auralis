"""
Regression: post-limiter sample-count invariants survive python -O (#5533)

Post-limiter/post-filter shape checks were bare ``assert`` statements —
compiled out under ``python -O`` / ``PYTHONOPTIMIZE``, silently removing the
last-line-of-defense check that the brick-wall limiter didn't
change the sample count (#5511 fixed the same pattern in
mastering_chunk_loop.py; its completeness grep never ran).

All of them are now ``if ...: raise RuntimeError(...)``, which `-O` cannot strip.
"""

from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[3]

# (file, mode label) for each converted site. The adaptive and hybrid
# guards live in auralis/core/processing/mode_dispatch.py (#6272) and are
# exercised behaviorally by tests/regression/test_sample_count_invariant.py.
_SITES = [
    ("auralis/core/hybrid_stage_dispatch.py", "reference"),
]


@pytest.mark.parametrize("rel,mode", _SITES)
def test_shape_invariants_are_real_raises(rel, mode):
    """The invariant must be a raise, not an assert (asserts vanish under -O)."""
    src = (_ROOT / rel).read_text()
    assert f"assert processed.shape == target_audio.shape" not in src, rel
    assert f"Sample count mismatch after limiter ({mode})" in src, rel
    assert "raise RuntimeError(" in src, rel


def test_reference_dispatch_raises_on_limiter_shape_change(monkeypatch):
    """Behavioral: a limiter that returns the wrong shape aborts with
    RuntimeError instead of silently corrupting the chunk."""
    from auralis.core import hybrid_stage_dispatch as dispatch

    class _BrokenLimiter:
        def process(self, audio):
            return audio[:, :-1].copy()  # drop one sample

    class _Processor:
        brick_wall_limiter = _BrokenLimiter()

    target = np.zeros((2, 64), dtype=np.float32)
    monkeypatch.setattr(dispatch, "apply_reference_matching", lambda t, r: t.copy())

    with pytest.raises(RuntimeError, match="Sample count mismatch after limiter"):
        dispatch.process_reference_mode(_Processor(), target.copy(), target)
