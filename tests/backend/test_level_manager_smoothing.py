"""
Regression tests for LevelManager gain smoothing (#3831) and cache-hit level
history consistency (#3832).

#3831: smooth_transition used to multiply a chunk by a single Python-float
scalar — promoting float32 → float64 and stepping the gain at the boundary by
the full adjustment. It now applies a dtype-typed per-sample envelope that ramps
from the previous chunk's gain to the new gain over 50 ms, then holds.

#3832: cache-hit chunks bypass the processing path, so the LevelManager never
saw them and a later cache-miss chunk smoothed against the wrong previous RMS.
Cache hits are now recorded (apply_adjustment=False) so history stays in sync.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.level_manager import LevelManager, GAIN_RAMP_SECONDS


SR = 44100


def _loud(n=SR, ch=2, amp=0.5):
    return (np.ones((n, ch), dtype=np.float32) * amp)


def _quiet(n=SR, ch=2, amp=0.02):
    return (np.ones((n, ch), dtype=np.float32) * amp)


# ---------------------------------------------------------------------------
# #3831 — dtype preservation
# ---------------------------------------------------------------------------

def test_adjustment_preserves_float32():
    lm = LevelManager()
    lm.smooth_transition(_loud(), 0, sample_rate=SR)            # baseline
    out, gain_db, adjusted = lm.smooth_transition(_quiet(), 1, sample_rate=SR)
    assert adjusted, "a large quiet→loud drop must trigger adjustment"
    assert out.dtype == np.float32, f"float64 promotion regression: {out.dtype}"


def test_apply_gain_preserves_float32():
    lm = LevelManager()
    out = lm.apply_gain(np.ones((100, 2), dtype=np.float32), 3.0)
    assert out.dtype == np.float32


def test_apply_gain_preserves_float64():
    lm = LevelManager()
    out = lm.apply_gain(np.ones((100, 2), dtype=np.float64), 3.0)
    assert out.dtype == np.float64


# ---------------------------------------------------------------------------
# #3831 — audio invariants
# ---------------------------------------------------------------------------

def test_sample_count_preserved_on_adjustment():
    lm = LevelManager()
    lm.smooth_transition(_loud(), 0, sample_rate=SR)
    chunk = _quiet()
    out, _, adjusted = lm.smooth_transition(chunk, 1, sample_rate=SR)
    assert adjusted
    assert len(out) == len(chunk)
    assert out.shape == chunk.shape


def test_input_chunk_not_mutated():
    lm = LevelManager()
    lm.smooth_transition(_loud(), 0, sample_rate=SR)
    chunk = _quiet()
    original = chunk.copy()
    lm.smooth_transition(chunk, 1, sample_rate=SR)
    np.testing.assert_array_equal(chunk, original)  # smooth_transition must not mutate input


# ---------------------------------------------------------------------------
# #3831 — the core fix: ramp, not step
# ---------------------------------------------------------------------------

def test_gain_ramps_from_previous_gain_not_stepped():
    """When adjustment triggers after an unadjusted chunk, the first output
    sample stays at the previous gain (1.0) — i.e. equals the raw sample — and
    the chunk eases up to the new gain, instead of jumping to it immediately."""
    lm = LevelManager()
    lm.smooth_transition(_loud(), 0, sample_rate=SR)  # chunk 0 unadjusted → prev gain 1.0

    amp = 0.02
    chunk = _quiet(amp=amp)
    out, gain_db, adjusted = lm.smooth_transition(chunk, 1, sample_rate=SR)
    assert adjusted and gain_db > 0

    ramp_len = int(round(GAIN_RAMP_SECONDS * SR))
    first = float(out[0, 0])
    held = float(out[ramp_len + 100, 0])

    # First sample at previous gain (1.0): output ≈ raw input (continuous boundary).
    assert first == pytest.approx(amp, rel=1e-4), (
        f"ramp must START at the previous gain (≈raw {amp}), got {first}"
    )
    # Held region at the new (boosted) gain — strictly louder than the start.
    assert held > first * 2, f"held gain should boost the quiet chunk: first={first} held={held}"
    new_gain = 10 ** (gain_db / 20)
    assert held == pytest.approx(amp * new_gain, rel=1e-3)


def test_ramp_length_tracks_sample_rate():
    """The ramp region scales with sample_rate (≈ GAIN_RAMP_SECONDS)."""
    lm = LevelManager()
    lm.smooth_transition(_loud(), 0, sample_rate=SR)
    out, _, adjusted = lm.smooth_transition(_quiet(), 1, sample_rate=SR)
    assert adjusted

    # The envelope is constant after ramp_len. Find where the per-sample value
    # stops increasing.
    col = out[:, 0]
    ramp_len = int(round(GAIN_RAMP_SECONDS * SR))
    # Value at ramp_len-1 should differ from value at 0 (ramping), and value
    # past ramp_len should be flat.
    assert col[ramp_len - 1] > col[0]
    assert col[ramp_len + 500] == pytest.approx(col[ramp_len + 50], rel=1e-6)


def test_handles_1d_and_2d_chunks():
    for shape_fn in (lambda: np.ones(SR, dtype=np.float32) * 0.5,
                     lambda: np.ones((SR, 2), dtype=np.float32) * 0.5):
        lm = LevelManager()
        lm.smooth_transition(shape_fn(), 0, sample_rate=SR)
        quiet = shape_fn() * 0.04
        out, _, adjusted = lm.smooth_transition(quiet, 1, sample_rate=SR)
        assert adjusted
        assert out.shape == quiet.shape
        assert out.dtype == np.float32


# ---------------------------------------------------------------------------
# #3832 — cache-hit chunks must update history (apply_adjustment=False)
# ---------------------------------------------------------------------------

def test_record_only_does_not_modify_chunk_but_updates_history():
    lm = LevelManager()
    lm.smooth_transition(_loud(), 0, sample_rate=SR)  # baseline

    chunk = _quiet(amp=0.1)
    original = chunk.copy()
    out, gain_db, adjusted = lm.smooth_transition(chunk, 1, apply_adjustment=False, sample_rate=SR)

    assert not adjusted and gain_db == 0.0
    np.testing.assert_array_equal(out, original)  # record-only returns chunk unchanged
    # History advanced to this chunk's RMS.
    assert lm.current_rms == pytest.approx(lm.calculate_rms(chunk), rel=1e-4)


def test_cache_hit_recording_keeps_history_chronological():
    """Recording a cache-hit chunk (apply_adjustment=False) makes the NEXT
    cache-miss chunk smooth against the cache-hit chunk's RMS, not the last
    *processed* chunk's — the heart of #3832."""
    lm = LevelManager()

    c0 = _loud(amp=0.5)      # chunk 0, processed (baseline)
    c1 = _loud(amp=0.18)     # chunk 1, "cache hit" — recorded only
    c2 = _loud(amp=0.16)     # chunk 2, processed (miss)

    lm.smooth_transition(c0, 0, sample_rate=SR)
    # Cache hit: record c1's level without adjusting it.
    lm.smooth_transition(c1, 1, apply_adjustment=False, sample_rate=SR)

    # After recording, the comparison point is c1 (not c0).
    assert lm.current_rms == pytest.approx(lm.calculate_rms(c1), rel=1e-4)

    # c2 (miss) is close to c1 (≈ within 1.5 dB) → no spurious adjustment.
    # If the history had skewed to c0, c2 vs c0 would be a larger jump.
    _out, _g, adjusted_vs_c1 = lm.smooth_transition(c2, 2, sample_rate=SR)
    diff_c2_c1 = abs(lm.calculate_rms(c2) - lm.calculate_rms(c1))
    assert diff_c2_c1 < 1.5
    assert not adjusted_vs_c1, "c2 is within 1.5 dB of c1 → should not need adjustment"


# ---------------------------------------------------------------------------
# #3832 — ChunkedAudioProcessor.note_cached_chunk_level wiring
# ---------------------------------------------------------------------------

def test_note_cached_chunk_level_updates_processor_history(tmp_path):
    """The processor method records a cache-hit chunk's level (without changing
    it) and keeps the legacy history mirrors in sync."""
    import soundfile as sf
    import core.chunked_processor as cp

    # Real (tiny) WAV so the processor's metadata load succeeds.
    wav = tmp_path / "tiny.wav"
    sf.write(str(wav), np.zeros((SR // 10, 2), dtype=np.float32), SR, subtype="FLOAT")

    proc = cp.ChunkedAudioProcessor(track_id=1, filepath=str(wav), preset="adaptive")

    c0 = _loud(amp=0.5)
    c1 = _loud(amp=0.2)
    original_c1 = c1.copy()

    proc.note_cached_chunk_level(c0, 0)  # baseline
    proc.note_cached_chunk_level(c1, 1)  # cache-hit chunk recorded

    # Chunk unchanged, history advanced, mirrors synced.
    np.testing.assert_array_equal(c1, original_c1)
    assert len(proc._level_manager.history) == 2
    assert proc._level_manager.current_rms == pytest.approx(
        proc._level_manager.calculate_rms(c1), rel=1e-4
    )
    assert proc.chunk_rms_history == list(proc._level_manager.history)
