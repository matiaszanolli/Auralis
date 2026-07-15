"""
Regression: FingerprintGenerator docstrings match the ThreadPool reality (#4377)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The docstrings claimed fingerprinting runs "in a subprocess, completely isolated"
via ProcessPoolExecutor, but the code uses a ThreadPoolExecutor. Guard against the
doc/reality drift returning: the constructed executor must be a ThreadPoolExecutor
and no docstring may claim process/subprocess isolation.
"""

import inspect
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from analysis import fingerprint_generator as fg


def test_executor_is_threadpool():
    executor = fg._get_fingerprint_executor()
    try:
        assert isinstance(executor, ThreadPoolExecutor)
    finally:
        fg.shutdown_fingerprint_executor()


def test_no_docstring_claims_process_isolation():
    """No docstring may claim a separate process / subprocess isolation."""
    targets = [
        fg,  # module docstring
        fg.FingerprintGenerator,
        fg._compute_fingerprint_in_thread,
        fg.FingerprintGenerator._generate_via_rust,
    ]
    forbidden = ("in a subprocess", "separate process", "completely isolated",
                 "runs in a separate")
    for obj in targets:
        doc = (inspect.getdoc(obj) or "").lower()
        for phrase in forbidden:
            assert phrase not in doc, (
                f"{getattr(obj, '__name__', obj)} docstring still claims process "
                f"isolation ({phrase!r}) but the executor is a ThreadPool (#4377)"
            )


def test_in_thread_helper_named_and_callable():
    """The former _compute_fingerprint_in_process is renamed to _in_thread."""
    assert hasattr(fg, "_compute_fingerprint_in_thread")
    assert not hasattr(fg, "_compute_fingerprint_in_process")
