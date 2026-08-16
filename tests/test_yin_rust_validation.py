"""
YIN Rust Implementation Validation Test

Validates the Rust YIN (pitch detection) binding at `auralis_dsp.yin` against
the librosa reference implementation.

History (#5146): every test here used to call librosa and assign
``f0_rust = f0_librosa``, so a 361-LOC suite named "rust validation" compared
librosa against itself and could not have failed if the Rust module were
deleted outright. It also drove its "real audio" cases off a hardcoded
``/mnt/Musica/Musica/Blind Guardian`` path that skipped on every machine but
one. Both are gone; the tests below call the real binding on synthetic signals
whose true pitch is known by construction.

What that rewrite immediately exposed is filed as #5169: the Rust `yin` does
not track pitch at all, returning a near-constant ~1150-1660 Hz regardless of
input. The accuracy tests here are therefore `xfail` — they assert the contract
that *should* hold, and will XPASS once #5169 is fixed. The structural tests
(shape, dtype, finiteness, determinism) are live and passing.
"""

import numpy as np
import pytest

librosa = pytest.importorskip("librosa")
auralis_dsp = pytest.importorskip(
    "auralis_dsp", reason="Rust DSP module not built (cd vendor/auralis-dsp && maturin develop)"
)

SR = 44100
FMIN = 65.4      # librosa.note_to_hz('C2')
FMAX = 2093.0    # librosa.note_to_hz('C7')

# yin.rs:45 frames as (len - FRAME_LENGTH) / HOP_LENGTH + 1 with no centring,
# while librosa defaults to center=True and pads. The two therefore disagree on
# frame count by a fixed margin for the same input; that is a convention
# difference, not the #5169 defect, so comparisons truncate to the shorter.
FRAME_LENGTH = 2048
HOP_LENGTH = 512


def sine(freq: float, duration: float = 1.0, sr: int = SR) -> np.ndarray:
    """A pure tone of known fundamental, as float64 C-contiguous (PyO3 dtype)."""
    t = np.arange(int(sr * duration)) / sr
    return np.ascontiguousarray(np.sin(2 * np.pi * freq * t), dtype=np.float64)


def chirp(f_start: float, f_end: float, duration: float = 2.0, sr: int = SR) -> np.ndarray:
    """A linear frequency sweep, as float64 C-contiguous."""
    t = np.arange(int(sr * duration)) / sr
    freq_t = f_start + (f_end - f_start) * t / duration
    return np.ascontiguousarray(np.sin(2 * np.pi * np.cumsum(freq_t) / sr), dtype=np.float64)


def yin_rust(audio: np.ndarray) -> np.ndarray:
    return auralis_dsp.yin(audio, SR, FMIN, FMAX)


def yin_librosa(audio: np.ndarray) -> np.ndarray:
    return librosa.yin(audio, fmin=FMIN, fmax=FMAX, sr=SR)


def median_cents_error(f0_ref: np.ndarray, f0_test: np.ndarray) -> float:
    """Median absolute pitch error in cents over frames both call voiced.

    Cents rather than Hz because pitch error is perceptually logarithmic:
    100 cents is one semitone at any absolute frequency.
    """
    n = min(len(f0_ref), len(f0_test))
    ref, test = f0_ref[:n], f0_test[:n]
    voiced = (ref > 0.0) & (test > 0.0)
    if not voiced.any():
        return float("inf")
    return float(np.median(np.abs(1200.0 * np.log2(test[voiced] / ref[voiced]))))


# --------------------------------------------------------------------------
# Structural contract at the PyO3 boundary — live, and the reason this file
# stays rather than being deleted: a wrong dtype or shape here is the
# HIGH-severity class per _audit-severity.md, and nothing else asserts it
# (tests/test_phase5_rust_benchmark.py:134 checks only ndim, on a benchmark).
# --------------------------------------------------------------------------

def test_yin_returns_1d_float64_contour():
    f0 = yin_rust(sine(440.0))
    assert f0.ndim == 1, f"expected a 1-D F0 contour, got shape {f0.shape}"
    assert f0.dtype == np.float64, f"expected float64 at the PyO3 boundary, got {f0.dtype}"


def test_yin_frame_count_matches_documented_framing():
    """yin.rs:45 — n_frames = (len - FRAME_LENGTH) / HOP_LENGTH + 1, uncentred."""
    audio = sine(440.0, duration=1.0)
    expected = (len(audio) - FRAME_LENGTH) // HOP_LENGTH + 1
    assert len(yin_rust(audio)) == expected


def test_yin_output_is_finite_and_non_negative():
    """No NaN/Inf may cross the boundary, and F0 is a frequency: never negative.

    Checks the whole contour, not a summary statistic — the pre-#5146 version
    asserted np.isfinite() on the *mean*, which a single +inf and a single
    -inf would have passed.
    """
    for name, audio in [
        ("sine", sine(440.0)),
        ("chirp", chirp(200.0, 1000.0)),
        ("silence", np.zeros(SR, dtype=np.float64)),
        ("white noise", np.ascontiguousarray(
            np.random.default_rng(42).standard_normal(SR) * 0.1, dtype=np.float64)),
    ]:
        f0 = yin_rust(audio)
        assert np.isfinite(f0).all(), f"{name}: non-finite value in F0 contour"
        assert (f0 >= 0.0).all(), f"{name}: negative frequency in F0 contour"


def test_yin_is_deterministic():
    audio = sine(440.0)
    np.testing.assert_array_equal(yin_rust(audio), yin_rust(audio))


def test_yin_handles_audio_shorter_than_one_frame():
    """Must not panic across the boundary on sub-frame input."""
    f0 = yin_rust(np.ascontiguousarray(np.zeros(FRAME_LENGTH // 2), dtype=np.float64))
    assert np.isfinite(f0).all()


# --------------------------------------------------------------------------
# Accuracy — xfail pending #5169. These are the assertions the binding is
# supposed to satisfy; they are what makes the defect visible instead of
# silently green. Non-strict so a fix does not fail the suite, but an XPASS
# in the report is the signal that #5169 can be closed.
# --------------------------------------------------------------------------

@pytest.mark.xfail(
    reason="#5169: Rust yin returns a near-constant ~1150-1660 Hz regardless of input pitch",
    strict=False,
)
@pytest.mark.parametrize("freq", [110.0, 220.0, 440.0, 880.0])
def test_yin_detects_known_sine_pitch(freq):
    """A pure tone's median F0 should land within a semitone of its true pitch."""
    median = float(np.median(yin_rust(sine(freq))))
    error_cents = abs(1200.0 * np.log2(median / freq))
    assert error_cents < 100.0, (
        f"true {freq:.1f} Hz, Rust reported {median:.1f} Hz "
        f"({error_cents:.0f} cents off)"
    )


@pytest.mark.xfail(reason="#5169: Rust yin pitch estimate is not tied to the input", strict=False)
def test_yin_agrees_with_librosa_on_chirp():
    """Within a quarter-tone of librosa over a 200->1000 Hz sweep.

    Correlation alone is not enough here and is why this went unnoticed: the
    Rust contour correlates 0.994 with librosa while sitting ~1550 cents high,
    because it tracks the sweep's *shape* without tracking its pitch.
    """
    audio = chirp(200.0, 1000.0)
    assert median_cents_error(yin_librosa(audio), yin_rust(audio)) < 50.0
