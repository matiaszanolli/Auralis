"""
Regression: post-limiter sample-count invariants survive python -O (#5533)

Four post-limiter/post-filter shape checks were bare ``assert`` statements —
compiled out under ``python -O`` / ``PYTHONOPTIMIZE``, silently removing the
last-line-of-defense check that the brick-wall / HF-aware limiter didn't
change the sample count (#5511 fixed the same pattern in
mastering_chunk_loop.py; its completeness grep never ran).

All four are now ``if ...: raise RuntimeError(...)``, which `-O` cannot strip.
"""

from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[3]

# (file, mode label) for each of the four converted sites.
_SITES = [
    ("auralis/core/hybrid_processor.py", "adaptive"),
    ("auralis/core/hybrid_processor.py", "hybrid"),
    ("auralis/core/hybrid_stage_dispatch.py", "reference"),
    ("auralis/core/processing/hf_aware_limiter.py", "hf-aware"),
]


@pytest.mark.parametrize("rel,mode", _SITES)
def test_shape_invariants_are_real_raises(rel, mode):
    """The invariant must be a raise, not an assert (asserts vanish under -O)."""
    src = (_ROOT / rel).read_text()
    if mode == "hf-aware":
        assert "assert restored.shape == in_shape" not in src, rel
        assert 'raise RuntimeError(\n            f"HF-aware limiter shape changed' in src, rel
    else:
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
        dispatch.process_reference_mode(_Processor(), target.copy(), target, results=None)


def test_hf_aware_limiter_raises_on_shape_change(monkeypatch):
    """Behavioral: a stage that changes the sample count aborts with
    RuntimeError instead of returning a reshaped buffer."""
    from auralis.core.processing import hf_aware_limiter as hf

    # Loud enough to get past the pass-through short-circuit (threshold is
    # -0.1 dBFS, i.e. peak >= 0.989 amplitude); the patched safety limiter
    # then returns a buffer with one extra sample, which the final shape
    # check must catch. Layout is (samples, channels).
    mono = (0.999 * np.sin(2 * np.pi * 1000 * np.arange(4096) / 44100)).astype(np.float32)
    audio = np.column_stack([mono, mono])

    def _growing(_audio):
        grown = np.concatenate(
            [_audio, np.zeros((1, _audio.shape[1]), dtype=_audio.dtype)], axis=0
        )
        return grown, True

    monkeypatch.setattr(hf.SafetyLimiter, "apply_if_needed", staticmethod(_growing))

    with pytest.raises(RuntimeError, match="HF-aware limiter shape changed"):
        hf.apply_hf_aware_limiter(audio, 44100)
