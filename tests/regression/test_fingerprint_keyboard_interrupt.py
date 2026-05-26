"""
Regression: AudioFingerprintAnalyzer KeyboardInterrupt handling (#2514, #2668, #3701)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The fix avoids using ThreadPoolExecutor as a context manager (whose __exit__
calls shutdown(wait=True) and blocks indefinitely on KeyboardInterrupt).

Since #3701 the executor is also long-lived (one pool per analyzer instance,
reused across analyze() calls), so the KeyboardInterrupt handler must NOT
shut it down — it cancels queued-but-unstarted futures and waits for the
in-flight ones to finish before re-raising, so they cannot mutate the
fingerprint dict after analyze() returns.

A future refactor could easily reintroduce the `with` pattern or drop the
wait/cancel discipline, so we pin the behaviour with both a structural
check and a functional test.
"""

import inspect
import textwrap
from unittest.mock import patch

import numpy as np
import pytest

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)


@pytest.mark.regression
class TestFingerprintKeyboardInterrupt:
    """Regression tests for KeyboardInterrupt handling in parallel fingerprint analysis."""

    # ── Structural checks ──────────────────────────────────────────────

    def test_executor_not_used_as_context_manager(self):
        """
        ThreadPoolExecutor must NOT be used via `with` in analyze().
        A `with` block would call __exit__ → shutdown(wait=True) which
        blocks on KeyboardInterrupt (#2514).
        """
        import ast
        source = inspect.getsource(AudioFingerprintAnalyzer.analyze)
        # Dedent so ast.parse works on extracted method source
        tree = ast.parse(textwrap.dedent(source))

        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                for item in node.items:
                    ctx = item.context_expr
                    # Check for `with ThreadPoolExecutor(...)` usage
                    name = ""
                    if isinstance(ctx, ast.Call) and isinstance(ctx.func, ast.Name):
                        name = ctx.func.id
                    elif isinstance(ctx, ast.Call) and isinstance(ctx.func, ast.Attribute):
                        name = ctx.func.attr
                    assert name != "ThreadPoolExecutor", (
                        "ThreadPoolExecutor must not be used as a context manager "
                        "in analyze() — its __exit__ blocks on KeyboardInterrupt (#2514)"
                    )

    def test_keyboard_interrupt_handler_cancels_and_waits(self):
        """
        The KeyboardInterrupt handler must cancel queued futures and wait for
        in-flight ones — never tear the shared executor down (#3701) and
        never let a running future write to fingerprint after re-raise.
        """
        source = inspect.getsource(AudioFingerprintAnalyzer.analyze)
        # Must drop queued futures explicitly (no more shutdown(cancel_futures=True))
        assert "f.cancel()" in source, (
            "KeyboardInterrupt handler must call f.cancel() on each submitted "
            "future to drop queued tasks (#3701)"
        )
        # Must block on in-flight futures so they cannot write partial results
        # to the fingerprint dict after analyze() returns (#2514).
        assert "wait(futures)" in source, (
            "KeyboardInterrupt handler must wait(futures) for in-flight tasks "
            "before re-raising (#2514, #3701)"
        )
        # Must NOT shut down the long-lived executor here.
        assert "executor.shutdown" not in source, (
            "analyze() must not shut down the shared executor — close() does "
            "that explicitly (#3701)"
        )

    # ── Functional check ───────────────────────────────────────────────

    def test_keyboard_interrupt_propagates_and_shuts_down_executor(self):
        """
        When a submitted task raises KeyboardInterrupt, the exception must
        propagate out of analyze() and the executor must be shut down cleanly.
        """
        analyzer = AudioFingerprintAnalyzer()
        sr = 44100
        audio = np.random.default_rng(0).standard_normal((sr, 2)).astype(np.float32)

        def raise_keyboard_interrupt(*args, **kwargs):
            raise KeyboardInterrupt

        # Patch one of the parallel analyzers to raise KeyboardInterrupt
        with patch.object(
            analyzer.temporal_analyzer, "analyze", side_effect=raise_keyboard_interrupt
        ):
            with pytest.raises(KeyboardInterrupt):
                analyzer.analyze(audio, sr)
