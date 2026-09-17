#!/usr/bin/env python3
"""Regression tests: every ChunkedAudioProcessor cache-hit branch must record
the served chunk's level into the LevelManager (#4669).

#3832 established that a cache HIT still has to be recorded, or ``rms_history``
holds a stale, non-adjacent chunk when the next cache-MISS chunk is smoothed
and ``smooth_transition`` steps the boundary by a correction that is either
unnecessary or missing. That recording was wired only into the in-memory tier
(``core/stream_chunk_ops.process_chunk_only``). The path-cache hit branches in
``core/chunk_streaming`` — ``process_chunk`` and ``get_wav_chunk_path`` —
returned early without it.

The issue names three branches; ``_lookup_cached_chunk`` collapsed
``get_wav_chunk_path``'s dict hit and its on-disk hit into a single branch in
#4792, so the three map onto two call sites here and both are covered below
(plus both tiers of the collapsed lookup, exercised through
``ChunkPathCache.lookup_cached``).

Also covers the #4367 gain convention (record the TRUE trailing gain, never
0.0 when it is known) and the no-double-counting requirement.
"""

import inspect
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))

from auralis.io.saver import save as save_audio  # noqa: E402

from core import chunk_render, chunk_streaming  # noqa: E402
from core.chunk_boundaries import CHUNK_DURATION  # noqa: E402
from core.chunked_processor import ChunkedAudioProcessor  # noqa: E402
from core.level_manager import MAX_LEVEL_CHANGE_DB  # noqa: E402

SR = 44100
DURATION = 60.0


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolated_chunk_dir(tmp_path, monkeypatch):
    """Render into a per-test chunk directory and start from an empty level
    registry — the registry is process-wide by design (#4669), so a test that
    asserts on a cache-hit recording must not inherit another test's entries."""
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir(parents=True, exist_ok=True)
    # getattr so a pre-fix tree (no registry yet) still runs the behavioural
    # assertions below instead of erroring out in fixture setup.
    reset = getattr(chunk_render, "reset_chunk_levels", lambda: None)
    reset()
    yield
    reset()


@pytest.fixture
def audio_file(tmp_path):
    """A real (short) WAV so the processor's metadata load succeeds."""
    t = np.linspace(0, DURATION, int(DURATION * SR), endpoint=False)
    tone = 0.3 * np.sin(2 * np.pi * 440.0 * t)
    path = tmp_path / "track.wav"
    save_audio(str(path), np.column_stack([tone, tone]), SR, subtype="PCM_16")
    return str(path)


# Per-chunk amplitudes. Chunk 4 is deliberately far louder than chunk 3 so the
# MAX_LEVEL_CHANGE_DB clamp has to fire across the hit/miss boundary.
AMPS = {0: 0.30, 1: 0.28, 2: 0.26, 3: 0.05, 4: 0.50, 5: 0.40}


def _synthetic(chunk_index: int, sample_rate: int) -> np.ndarray:
    """Deterministic noise at this chunk's amplitude (stable, known RMS)."""
    n = int(CHUNK_DURATION * sample_rate)
    rng = np.random.default_rng(1000 + chunk_index)
    amp = AMPS.get(chunk_index, 0.3)
    return (rng.standard_normal((n, 2)) * amp).astype(np.float32)


def _make_processor(audio_file):
    """A real processor whose DSP is replaced by synthetic audio, but whose
    level bookkeeping (_smooth_level_transition -> LevelManager) is the real
    thing — that bookkeeping is what this issue is about."""
    proc = ChunkedAudioProcessor(
        track_id=4669,
        filepath=audio_file,
        preset="adaptive",
        intensity=1.0,
        chunk_cache={},
    )

    def fake_core(chunk_index: int, fast_start: bool = False) -> np.ndarray:
        assert proc.sample_rate is not None
        return proc._smooth_level_transition(
            _synthetic(chunk_index, proc.sample_rate), chunk_index
        )

    proc._process_chunk_core = fake_core  # type: ignore[method-assign]
    return proc


def _rms_of_cached_wav(path: str) -> float:
    from auralis.io.unified_loader import load_audio
    audio, _ = load_audio(path)
    from core.level_manager import LevelManager
    return LevelManager().calculate_rms(audio)


# ---------------------------------------------------------------------------
# WIRING — the helper must actually be called from both branches
# ---------------------------------------------------------------------------

def test_both_cache_hit_branches_call_the_recording_helper():
    """WIRING completeness check: the recording hook must have callers, not
    just a definition."""
    for fn in (chunk_streaming.process_chunk, chunk_streaming.get_wav_chunk_path):
        src = inspect.getsource(fn)
        assert "_record_cache_hit_level" in src, (
            f"{fn.__name__} returns a cached chunk without recording its level "
            "into the LevelManager (#4669)"
        )


# ---------------------------------------------------------------------------
# process_chunk — the cache-hit branch that already holds the decoded audio
# ---------------------------------------------------------------------------

def test_process_chunk_cache_hit_records_level_exactly_once(audio_file):
    proc = _make_processor(audio_file)
    proc.process_chunk(0)
    proc.process_chunk(1)
    before = len(proc._level_manager.history)

    path, _audio = proc.process_chunk(1)  # cache HIT

    assert len(proc._level_manager.history) == before + 1, (
        "a cache hit must contribute exactly one entry to rms_history"
    )
    assert proc._level_manager.current_rms == pytest.approx(
        _rms_of_cached_wav(path), abs=0.05
    ), "the recorded RMS must be the level of the bytes actually served"


def test_process_chunk_cache_hit_records_the_true_trailing_gain(audio_file):
    """#4367: never record 0.0 when the real trailing gain is known."""
    proc = _make_processor(audio_file)
    proc.process_chunk(0)
    proc.process_chunk(3)  # big level drop -> smoothing kicks in, gain != 0
    real_gain = proc._level_manager.gain_history[-1]
    assert real_gain != 0.0, "fixture must produce a non-zero trailing gain"

    before = len(proc._level_manager.gain_history)

    proc.process_chunk(3)  # cache HIT on the same chunk

    assert len(proc._level_manager.gain_history) == before + 1, (
        "the cache hit must be recorded at all (#4669) before its gain value "
        "can be asserted on"
    )
    assert proc._level_manager.gain_history[-1] == pytest.approx(real_gain), (
        "the cache-hit recording must restore the chunk's true trailing gain, "
        "not silently record unity (#4367)"
    )


def test_cache_hit_keeps_rms_history_chronological_for_the_next_miss(audio_file):
    """The issue's Test Plan #1: chunks 0-2 processed, chunk 3 a cache HIT,
    chunk 4 a MISS smoothed against chunk 3's REAL RMS."""
    # A previous stream of the same track renders chunk 3 to disk.
    warm = _make_processor(audio_file)
    cached_path, _ = warm.process_chunk(3)

    # A new stream (fresh LevelManager) plays through it.
    proc = _make_processor(audio_file)
    for idx in (0, 1, 2):
        proc.process_chunk(idx)
    hit_path, _ = proc.process_chunk(3)
    assert hit_path == cached_path, "chunk 3 must be served from the disk cache"

    recorded_hit_rms = proc._level_manager.history[3]
    assert recorded_hit_rms == pytest.approx(_rms_of_cached_wav(cached_path), abs=0.05)

    previous_rms_seen_by_chunk4 = proc._level_manager.current_rms
    proc.process_chunk(4)

    assert len(proc._level_manager.history) == 5, (
        "every chunk 0..4 must contribute exactly one entry, in order"
    )
    assert previous_rms_seen_by_chunk4 == pytest.approx(recorded_hit_rms), (
        "chunk 4 must smooth against chunk 3's real RMS, not a stale "
        "non-adjacent chunk's"
    )


def test_max_level_change_still_clamps_across_a_hit_miss_boundary(audio_file):
    """The issue's Test Plan #3: no step larger than MAX_LEVEL_CHANGE_DB."""
    warm = _make_processor(audio_file)
    warm.process_chunk(3)

    proc = _make_processor(audio_file)
    for idx in (0, 1, 2):
        proc.process_chunk(idx)
    proc.process_chunk(3)  # HIT — quiet chunk
    proc.process_chunk(4)  # MISS — much louder

    step_db = abs(proc._level_manager.history[4] - proc._level_manager.history[3])
    assert step_db <= MAX_LEVEL_CHANGE_DB + 0.5, (
        f"chunk 4 stepped {step_db:.2f} dB from the cache-hit chunk 3; the "
        f"{MAX_LEVEL_CHANGE_DB} dB clamp must survive a hit/miss boundary"
    )


# ---------------------------------------------------------------------------
# get_wav_chunk_path — the path-only cache-hit branch
# ---------------------------------------------------------------------------

def test_get_wav_chunk_path_cache_hit_records_level_exactly_once(audio_file):
    """The issue's Test Plan #2."""
    proc = _make_processor(audio_file)
    proc.get_wav_chunk_path(0)
    proc.get_wav_chunk_path(1)
    before = len(proc._level_manager.history)

    proc.get_wav_chunk_path(1)  # cache HIT

    assert len(proc._level_manager.history) == before + 1


def test_get_wav_chunk_path_cache_hit_does_not_decode_the_wav(audio_file):
    """The recording must come from the level registry written when the WAV
    was encoded — decoding a cached chunk purely to compute an RMS is the cost
    this design avoids on a per-chunk path."""
    warm = _make_processor(audio_file)
    warm.get_wav_chunk_path(1)

    proc = _make_processor(audio_file)
    proc.get_wav_chunk_path(0)

    sentinel_rms, sentinel_gain = -33.25, -2.75
    with patch.object(
        chunk_render, "recall_chunk_level", return_value=(sentinel_rms, sentinel_gain)
    ):
        proc.get_wav_chunk_path(1)  # cache HIT

    assert proc._level_manager.history[-1] == pytest.approx(sentinel_rms)
    assert proc._level_manager.gain_history[-1] == pytest.approx(sentinel_gain)


def test_get_wav_chunk_path_hit_without_a_remembered_level_is_a_no_op(audio_file):
    """A WAV left on disk by an earlier run of the process has no registry
    entry. Rather than decode it on this path, the recording is skipped — the
    documented, deliberate limit of the fix."""
    warm = _make_processor(audio_file)
    warm.get_wav_chunk_path(1)
    chunk_render.reset_chunk_levels()  # simulate a fresh process

    proc = _make_processor(audio_file)
    proc.get_wav_chunk_path(0)
    before = len(proc._level_manager.history)

    proc.get_wav_chunk_path(1)  # cache HIT, nothing remembered

    assert len(proc._level_manager.history) == before


# ---------------------------------------------------------------------------
# No double counting
# ---------------------------------------------------------------------------

def test_recording_fires_once_per_cache_hit_call(audio_file):
    proc = _make_processor(audio_file)
    proc.process_chunk(0)
    proc.process_chunk(1)

    with patch.object(proc, "note_cached_chunk_level") as spy:
        proc.process_chunk(1)
        assert spy.call_count == 1
        spy.reset_mock()
        proc.get_wav_chunk_path(1)
        assert spy.call_count == 1


def test_a_cache_miss_never_records_a_cached_level(audio_file):
    """The recording belongs to the hit branches only — a MISS already goes
    through smooth_transition, and recording again would double-count it."""
    proc = _make_processor(audio_file)
    with patch.object(proc, "note_cached_chunk_level") as spy:
        proc.process_chunk(0)
        proc.get_wav_chunk_path(1)
    spy.assert_not_called()
