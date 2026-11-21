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

# The three mode bodies end in one helper, finish_mode_output (#6618), so the
# invariant lives in a single raise. (file, mode label) names each caller; the
# adaptive and hybrid ones are also exercised behaviorally by
# tests/regression/test_sample_count_invariant.py.
_HELPER_FILE = "auralis/core/hybrid_stage_dispatch.py"
_CALLERS = [
    ("auralis/core/hybrid_stage_dispatch.py", "reference"),
    ("auralis/core/processing/mode_dispatch.py", "adaptive"),
    ("auralis/core/processing/mode_dispatch.py", "hybrid"),
]


def test_shape_invariant_is_a_real_raise():
    """The invariant must be a raise, not an assert (asserts vanish under -O)."""
    src = (_ROOT / _HELPER_FILE).read_text()
    assert "assert processed.shape == target_audio.shape" not in src
    assert "Sample count mismatch after limiter ({mode})" in src
    assert "raise RuntimeError(" in src


@pytest.mark.parametrize("rel,mode", _CALLERS)
def test_every_mode_ends_in_the_shared_tail(rel, mode):
    """A mode that stopped calling the helper would silently lose the guard."""
    src = (_ROOT / rel).read_text()
    assert f'finish_mode_output(processor, processed, target_audio, "{mode}")' in src, rel


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
