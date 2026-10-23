"""
Tests for Rust panic handler in Python DSP bindings (issue #2225)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rust DSP functions were called without std::panic::catch_unwind() protection.
If a Rust function panicked, the entire Python process would crash with no
recovery.

Fix: every DSP call site in py_bindings.rs is wrapped in
std::panic::catch_unwind(AssertUnwindSafe(||...)) so that Rust panics
are converted to Python RuntimeError instead of aborting the process.

Only two bindings remain since #5764 removed hpss/yin/chroma_cqt and the rest:
``compute_fingerprint`` (the live one) and ``process_chunks`` (dead, #5738).

Test plan:
 - Structural: py_bindings.rs source wraps both remaining DSP calls in
   catch_unwind (runs without the Rust extension built)
 - Stability: NaN/Inf inputs do not crash the Python process — they either
   return normally or raise a Python exception
 - Regression: normal valid audio still produces a 25D fingerprint
"""

from pathlib import Path

import numpy as np
import pytest

try:
    import auralis_dsp  # type: ignore
    HAS_DSP = True
except ImportError:
    HAS_DSP = False

requires_dsp = pytest.mark.skipif(
    not HAS_DSP,
    reason="auralis_dsp Rust extension not installed (run: cd vendor/auralis-dsp && maturin develop)"
)

BINDINGS_SRC = Path(__file__).parent.parent.parent / "vendor" / "auralis-dsp" / "src" / "py_bindings.rs"


def _make_audio(n: int = 44100, dtype=np.float32) -> np.ndarray:
    """Return a short sine wave array."""
    t = np.linspace(0, 1.0, n, dtype=dtype)
    return (np.sin(2 * np.pi * 440 * t)).astype(dtype)


def _call_and_catch(fn):
    """
    Call fn().  Return (result, exception).

    The process must NOT crash — if it does, pytest itself terminates.
    """
    try:
        return fn(), None
    except Exception as e:
        return None, e


class TestCatchUnwindPresent:
    """Verify the source-level protection is in place (issue #2225)."""

    def _src(self) -> str:
        assert BINDINGS_SRC.exists(), f"py_bindings.rs not found at {BINDINGS_SRC}"
        return BINDINGS_SRC.read_text()

    @pytest.mark.parametrize(
        "call",
        ["fingerprint_compute::compute_complete_fingerprint(", "processor.process_chunks("],
    )
    def test_dsp_call_is_wrapped_by_catch_unwind(self, call):
        src = self._src()
        idx = src.find(call)
        assert idx != -1, f"{call} call not found in py_bindings.rs"
        nearby = src[max(0, idx - 300) : idx + 50]
        assert "catch_unwind" in nearby, (
            f"{call} is not wrapped by catch_unwind in py_bindings.rs (issue #2225)"
        )

    def test_removed_bindings_stay_removed(self):
        """#5764: hpss/yin/chroma_cqt/... had no production caller."""
        src = self._src()
        for name in ("hpss_wrapper", "yin_wrapper", "chroma_cqt_wrapper",
                     "detect_tempo_wrapper", "envelope_follow_wrapper",
                     "compress_wrapper", "limit_wrapper",
                     "apply_multiband_eq_wrapper", "detect_onsets_wrapper"):
            assert name not in src

    def test_format_panic_helper_present(self):
        """format_panic helper must be defined to produce readable error messages."""
        assert "fn format_panic(" in self._src(), (
            "format_panic() helper function not found in py_bindings.rs. "
            "It is needed to extract the panic message string (issue #2225)."
        )


@requires_dsp
class TestProcessStability:
    """Degenerate inputs must not crash the process."""

    def test_fingerprint_nan_audio_no_process_crash(self):
        nan_audio = np.full(44100, np.nan, dtype=np.float32)
        _call_and_catch(lambda: auralis_dsp.compute_fingerprint(nan_audio, 44100, 1))

    def test_fingerprint_inf_audio_no_process_crash(self):
        inf_audio = np.full(44100, np.inf, dtype=np.float32)
        _call_and_catch(lambda: auralis_dsp.compute_fingerprint(inf_audio, 44100, 1))

    def test_fingerprint_empty_audio_no_process_crash(self):
        empty = np.array([], dtype=np.float32)
        _call_and_catch(lambda: auralis_dsp.compute_fingerprint(empty, 44100, 1))


@requires_dsp
class TestNormalOperation:
    """Valid audio still works — the guard must not break the happy path."""

    def test_fingerprint_has_25_dimensions(self):
        result = auralis_dsp.compute_fingerprint(_make_audio(), 44100, 1)
        assert len(result) == 25
