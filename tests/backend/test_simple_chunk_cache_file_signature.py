"""Regression tests for SimpleChunkCache file_signature keying (#4358).

The in-memory SimpleChunkCache keyed on (version, track_id, chunk_idx, preset,
intensity) with NO file_signature, while the on-disk ChunkCacheManager includes
it. If a track's file changed mid-session (re-scan/re-tag) with the same
track_id, the on-disk layer correctly missed and reprocessed, but the in-memory
layer kept serving the previously-processed samples and their stored sample_rate
for the process lifetime — stale, and wrong-speed/pitch if the new file had a
different sample rate. The key now includes file_signature.
"""

import sys
from pathlib import Path

import numpy as np

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.chunk_cache import SimpleChunkCache  # noqa: E402


def _audio(sr: int) -> tuple[np.ndarray, int]:
    return np.zeros(1024, dtype=np.float32), sr


def test_signature_change_misses_the_cache():
    cache = SimpleChunkCache()
    audio, sr = _audio(44100)
    cache.put(track_id=1, chunk_idx=0, preset="warm", intensity=0.5,
              audio=audio, sample_rate=sr, file_signature="sigA")

    # Same signature → hit.
    hit = cache.get(track_id=1, chunk_idx=0, preset="warm", intensity=0.5,
                    file_signature="sigA")
    assert hit is not None
    assert hit[1] == 44100

    # File changed (new signature) but same track_id → MISS, not stale audio.
    miss = cache.get(track_id=1, chunk_idx=0, preset="warm", intensity=0.5,
                     file_signature="sigB")
    assert miss is None


def test_new_signature_serves_new_sample_rate_not_stale():
    cache = SimpleChunkCache()
    old_audio, _ = _audio(44100)
    cache.put(track_id=7, chunk_idx=2, preset="adaptive", intensity=1.0,
              audio=old_audio, sample_rate=44100, file_signature="old")

    # Replacement file with a different sample rate, same track_id.
    new_audio, _ = _audio(48000)
    cache.put(track_id=7, chunk_idx=2, preset="adaptive", intensity=1.0,
              audio=new_audio, sample_rate=48000, file_signature="new")

    # The new-signature read returns the 48 kHz entry, never the stale 44.1 kHz one.
    got = cache.get(track_id=7, chunk_idx=2, preset="adaptive", intensity=1.0,
                    file_signature="new")
    assert got is not None
    assert got[1] == 48000
    # And the old signature still maps to the old rate (distinct key).
    old = cache.get(track_id=7, chunk_idx=2, preset="adaptive", intensity=1.0,
                    file_signature="old")
    assert old is not None and old[1] == 44100


def test_invalidate_targets_the_signed_entry():
    cache = SimpleChunkCache()
    audio, sr = _audio(44100)
    cache.put(track_id=3, chunk_idx=1, preset="warm", intensity=0.5,
              audio=audio, sample_rate=sr, file_signature="sig")

    # Invalidating with a different signature must NOT drop the real entry.
    cache.invalidate_chunk(track_id=3, chunk_idx=1, preset="warm", intensity=0.5,
                           file_signature="other")
    assert cache.get(track_id=3, chunk_idx=1, preset="warm", intensity=0.5,
                     file_signature="sig") is not None

    # Invalidating with the matching signature drops it.
    cache.invalidate_chunk(track_id=3, chunk_idx=1, preset="warm", intensity=0.5,
                           file_signature="sig")
    assert cache.get(track_id=3, chunk_idx=1, preset="warm", intensity=0.5,
                     file_signature="sig") is None


def test_default_signature_backward_compatible():
    # Callers that omit file_signature (non-streaming/tests) still round-trip.
    cache = SimpleChunkCache()
    audio, sr = _audio(44100)
    cache.put(track_id=9, chunk_idx=0, preset="warm", intensity=0.5,
              audio=audio, sample_rate=sr)
    assert cache.get(track_id=9, chunk_idx=0, preset="warm", intensity=0.5) is not None
