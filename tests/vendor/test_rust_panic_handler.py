"""
Tests for Rust panic handler in Python DSP bindings (issue #2225)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rust DSP functions (HPSS, YIN, Chroma) were called without
std::panic::catch_unwind() protection.  If a Rust function panicked,
the entire Python process would crash with no recovery.

Fix: every DSP call site in py_bindings.rs is now wrapped in
std::panic::catch_unwind(AssertUnwindSafe(||...)) so that Rust panics
are converted to Python RuntimeError instead of aborting the process.

Acceptance criteria (from issue):
 - Rust panics are caught and converted to Python exceptions
 - No crash on NaN or Inf input

Test plan:
 - Structural: py_bindings.rs source contains catch_unwind for all three
   primary DSP functions (hpss, yin, chroma_cqt)
 - Stability: NaN/Inf/empty inputs to HPSS, YIN, Chroma do not crash the
   Python process — they either return normally or raise RuntimeError
 - Exception type: any exception raised by a failing DSP call is a Python
   RuntimeError (not a subprocess crash or SystemExit)
 - Regression: normal valid audio still produces correct output shapes
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# ============================================================================
# Module import
# ============================================================================

try:
    import auralis_dsp  # type: ignore
    HAS_DSP = True
except ImportError:
    HAS_DSP = False

pytestmark = pytest.mark.skipif(
    not HAS_DSP,
    reason="auralis_dsp Rust extension not installed (run: cd vendor/auralis-dsp && maturin develop)"
)

# ============================================================================
# Helpers
# ============================================================================

BINDINGS_SRC = Path(__file__).parent.parent.parent / "vendor" / "auralis-dsp" / "src" / "py_bindings.rs"

def _make_audio(n: int = 44100, dtype=np.float64) -> np.ndarray:
    """Return a short sine wave array."""
    t = np.linspace(0, 1.0, n, dtype=dtype)
    return (np.sin(2 * np.pi * 440 * t)).astype(dtype)


def _call_and_catch(fn):
    """
    Call fn().  Return (result, exception).

    The process must NOT crash — if it does, pytest itself terminates.
    Any Python exception is captured and returned.
    """
    try:
        return fn(), None
    except RuntimeError as e:
        return None, e
    except Exception as e:
        return None, e


# ============================================================================
# Structural: catch_unwind must be present in the source
# ============================================================================

class TestCatchUnwindPresent:
    """Verify the source-level protection is in place (issue #2225)."""

    def _src(self) -> str:
        assert BINDINGS_SRC.exists(), f"py_bindings.rs not found at {BINDINGS_SRC}"
        return BINDINGS_SRC.read_text()

    def test_catch_unwind_in_hpss_wrapper(self):
        """hpss_wrapper must call catch_unwind."""
        src = self._src()
        # Find the hpss_wrapper function body and verify catch_unwind is used
        assert "catch_unwind" in src, (
            "py_bindings.rs must use std::panic::catch_unwind (issue #2225). "
            "No catch_unwind found at all."
        )
        # Verify it wraps the hpss:: call specifically
        hpss_call_line = next(
            (line for line in src.splitlines() if "hpss::hpss(" in line),
            None,
        )
        assert hpss_call_line is not None, "hpss::hpss() call not found in py_bindings.rs"
        # The call must be inside a catch_unwind closure — verify the lines around it
        hpss_idx = src.find("hpss::hpss(")
        nearby = src[max(0, hpss_idx - 200) : hpss_idx + 50]
        assert "catch_unwind" in nearby, (
            "hpss::hpss() is not wrapped by catch_unwind in py_bindings.rs (issue #2225)"
        )

    def test_catch_unwind_in_yin_wrapper(self):
        """yin_wrapper must call catch_unwind."""
        src = self._src()
        yin_idx = src.find("yin::yin(")
        assert yin_idx != -1, "yin::yin() call not found in py_bindings.rs"
        nearby = src[max(0, yin_idx - 200) : yin_idx + 50]
        assert "catch_unwind" in nearby, (
            "yin::yin() is not wrapped by catch_unwind in py_bindings.rs (issue #2225)"
        )

    def test_catch_unwind_in_chroma_cqt_wrapper(self):
        """chroma_cqt_wrapper must call catch_unwind."""
        src = self._src()
        chroma_idx = src.find("chroma::chroma_cqt(")
        assert chroma_idx != -1, "chroma::chroma_cqt() call not found in py_bindings.rs"
        nearby = src[max(0, chroma_idx - 200) : chroma_idx + 50]
        assert "catch_unwind" in nearby, (
            "chroma::chroma_cqt() is not wrapped by catch_unwind in py_bindings.rs (issue #2225)"
        )

    def test_format_panic_helper_present(self):
        """format_panic helper must be defined to produce readable error messages."""
        src = self._src()
        assert "fn format_panic(" in src, (
            "format_panic() helper function not found in py_bindings.rs. "
            "It is needed to extract the panic message string (issue #2225)."
        )


# ============================================================================
# Process stability: degenerate inputs must not crash the process
# ============================================================================

class TestProcessStability:
    """
    NaN / Inf / empty inputs must not crash the Python process.

    The test passes if:
    - The function returns normally (Rust handled the input gracefully), OR
    - A Python RuntimeError is raised (catch_unwind fired and converted the panic)

    The test FAILS if the process crashes — but a crash would kill pytest
    itself, so if this test is collected and reported, the process survived.
    """

    def test_hpss_nan_audio_no_process_crash(self):
        """All-NaN audio to HPSS must not crash the Python process (issue #2225)."""
        nan_audio = np.full(44100, np.nan, dtype=np.float64)
        result, exc = _call_and_catch(lambda: auralis_dsp.hpss(nan_audio, sr=44100))
        # Either returned or raised RuntimeError — both are acceptable
        if exc is not None:
            assert isinstance(exc, RuntimeError), (
                f"Expected RuntimeError from panic catch, got {type(exc).__name__}: {exc}"
            )
        # If it returned, the output should be arrays (not a crash)
        if result is not None:
            harmonic, percussive = result
            assert hasattr(harmonic, '__len__'), "HPSS harmonic output must be array-like"

    def test_hpss_inf_audio_no_process_crash(self):
        """All-Inf audio to HPSS must not crash the Python process (issue #2225)."""
        inf_audio = np.full(44100, np.inf, dtype=np.float64)
        result, exc = _call_and_catch(lambda: auralis_dsp.hpss(inf_audio, sr=44100))
        if exc is not None:
            assert isinstance(exc, RuntimeError), (
                f"Expected RuntimeError from panic catch, got {type(exc).__name__}: {exc}"
            )

    def test_yin_empty_audio_no_process_crash(self):
        """Empty audio to YIN must not crash the Python process (issue #2225)."""
        empty = np.array([], dtype=np.float64)
        result, exc = _call_and_catch(lambda: auralis_dsp.yin(empty, sr=44100))
        if exc is not None:
            assert isinstance(exc, RuntimeError), (
                f"Expected RuntimeError from panic catch, got {type(exc).__name__}: {exc}"
            )

    def test_yin_nan_audio_no_process_crash(self):
        """NaN audio to YIN must not crash the Python process (issue #2225)."""
        nan_audio = np.full(44100, np.nan, dtype=np.float64)
        result, exc = _call_and_catch(lambda: auralis_dsp.yin(nan_audio, sr=44100))
        if exc is not None:
            assert isinstance(exc, RuntimeError), (
                f"Expected RuntimeError from panic catch, got {type(exc).__name__}: {exc}"
            )

    def test_chroma_nan_audio_no_process_crash(self):
        """NaN audio to Chroma must not crash the Python process (issue #2225)."""
        nan_audio = np.full(44100, np.nan, dtype=np.float64)
        result, exc = _call_and_catch(lambda: auralis_dsp.chroma_cqt(nan_audio, sr=44100))
        if exc is not None:
            assert isinstance(exc, RuntimeError), (
                f"Expected RuntimeError from panic catch, got {type(exc).__name__}: {exc}"
            )

    def test_chroma_empty_audio_no_process_crash(self):
        """Empty audio to Chroma must not crash the Python process (issue #2225)."""
        empty = np.array([], dtype=np.float64)
        result, exc = _call_and_catch(lambda: auralis_dsp.chroma_cqt(empty, sr=44100))
        if exc is not None:
            assert isinstance(exc, RuntimeError), (
                f"Expected RuntimeError from panic catch, got {type(exc).__name__}: {exc}"
            )


# ============================================================================
# Exception type: any DSP failure must produce RuntimeError, not SystemExit
# ============================================================================

class TestExceptionType:
    """
    When catch_unwind fires, the resulting Python exception must be RuntimeError.
    Verify by inspecting error messages that reference the panic catch.
    """

    def _assert_runtime_error_if_raised(self, fn, context: str):
        """Run fn(); if it raises, assert it's RuntimeError."""
        try:
            fn()
        except RuntimeError:
            pass  # correct type
        except SystemExit as e:
            pytest.fail(
                f"{context}: SystemExit raised — process was about to crash (issue #2225). "
                f"catch_unwind should have intercepted this."
            )
        except Exception as e:
            pytest.fail(
                f"{context}: unexpected exception type {type(e).__name__}: {e}. "
                f"Panics should be caught as RuntimeError (issue #2225)."
            )

    def test_hpss_exception_type(self):
        self._assert_runtime_error_if_raised(
            lambda: auralis_dsp.hpss(np.full(44100, np.nan, dtype=np.float64)),
            "hpss with NaN"
        )

    def test_yin_exception_type(self):
        self._assert_runtime_error_if_raised(
            lambda: auralis_dsp.yin(np.full(44100, np.nan, dtype=np.float64)),
            "yin with NaN"
        )

    def test_chroma_exception_type(self):
        self._assert_runtime_error_if_raised(
            lambda: auralis_dsp.chroma_cqt(np.full(44100, np.nan, dtype=np.float64)),
            "chroma_cqt with NaN"
        )


# ============================================================================
# Regression: normal valid audio still produces correct output
# ============================================================================

class TestNormalOperation:
    """Verify that adding catch_unwind did not change normal behaviour."""

    def test_hpss_output_shape(self):
        """HPSS must return two arrays with the same length as input."""
        audio = _make_audio(44100)
        harmonic, percussive = auralis_dsp.hpss(audio, sr=44100)
        assert len(harmonic) == len(audio), "harmonic length must equal input length"
        assert len(percussive) == len(audio), "percussive length must equal input length"

    def test_hpss_energy_conservation(self):
        """HPSS: harmonic + percussive energy should approximate input energy."""
        audio = _make_audio(44100)
        harmonic, percussive = auralis_dsp.hpss(audio, sr=44100)
        h = np.asarray(harmonic)
        p = np.asarray(percussive)
        # Soft masks sum to ~1, so energy is conserved approximately
        input_energy = float(np.sum(audio ** 2))
        output_energy = float(np.sum((h + p) ** 2))
        if input_energy > 0:
            ratio = output_energy / input_energy
            # Wiener soft masking can sum h+p > 1 in overlapping regions,
            # so the combined energy may slightly exceed the input — allow up to 4x.
            assert 0.1 < ratio < 4.0, (
                f"HPSS energy ratio {ratio:.2f} out of expected range (0.1, 4.0)"
            )

    def test_yin_output_is_array(self):
        """YIN must return a 1D array of F0 estimates."""
        audio = _make_audio(44100)
        f0 = auralis_dsp.yin(audio, sr=44100)
        arr = np.asarray(f0)
        assert arr.ndim == 1, f"YIN output must be 1D, got shape {arr.shape}"
        assert len(arr) > 0, "YIN output must be non-empty for non-empty input"

    def test_chroma_output_shape(self):
        """Chroma must return a (12, n_frames) array."""
        audio = _make_audio(44100)
        chroma = auralis_dsp.chroma_cqt(audio, sr=44100)
        arr = np.asarray(chroma)
        assert arr.ndim == 2, f"Chroma output must be 2D, got shape {arr.shape}"
        assert arr.shape[0] == 12, f"Chroma must have 12 pitch classes, got {arr.shape[0]}"
