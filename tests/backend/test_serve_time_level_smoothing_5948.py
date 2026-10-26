"""Level smoothing is applied per stream at serve time, never baked into the cache (#5948).

``LevelManager.smooth_transition`` bakes a gain into a chunk relative to whatever
chunk its processor served *previously*. The durable chunk file used to be written
AFTER that, under a key that carries no render context, so its bytes depended on
scheduling: the cache worker's tier-1 (current+1) and tier-2 (sequential) writers,
pre-warm and seek all render on processors whose previous chunk is not the
predecessor, and a later play served those bytes as a hit that is never re-smoothed.
Measured on an alternating loud/quiet track: chunk 4 differed by 15.5 dB between
rendering it first and rendering it in order, under the same cache key.

The file now holds the raw emitted segment and ``process_chunk`` smooths a copy for
the stream that asked for it, hit or miss, in that stream's own order.

These tests run real ChunkedAudioProcessors over a real file, with only the DSP
pipeline replaced by a passthrough.
"""

import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_processing_pipeline import AudioProcessingPipeline
from core.chunk_boundaries import CHUNK_INTERVAL
from core.chunked_processor import ChunkedAudioProcessor
from core.encoding import WAVEncoder, read_chunk_wav

SR = 8000
# Emitted segments are [0,15], [15,25], [25,35], ... (chunk 0 carries the head).
# One alternating loud/quiet level per chunk, so every seam is a step big enough
# for the smoother to fire.
SEGMENT_SECONDS = [15.0] + [CHUNK_INTERVAL] * 8
LEVELS = [0.4, 0.05] * 5
CHUNKS = range(6)


@pytest.fixture(autouse=True)
def _passthrough_dsp():
    def passthrough(audio: np.ndarray, **_kwargs: Any) -> np.ndarray:
        return audio.copy()

    with patch.object(AudioProcessingPipeline, "process_audio", side_effect=passthrough):
        yield


@pytest.fixture
def track(tmp_path: Path) -> str:
    rng = np.random.default_rng(5948)
    audio = np.concatenate([
        rng.uniform(-1.0, 1.0, (int(seconds * SR), 2)) * level
        for seconds, level in zip(SEGMENT_SECONDS, LEVELS, strict=False)
    ])
    path = tmp_path / "track.wav"
    sf.write(str(path), audio.astype(np.float32), SR, subtype="FLOAT")
    return str(path)


class _Cache:
    """One on-disk chunk cache; processors made on it share files, as streams do."""

    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
        self.root = root / name
        self.root.mkdir()
        self._monkeypatch = monkeypatch

    def processor(self, filepath: str) -> ChunkedAudioProcessor:
        self._monkeypatch.setattr(tempfile, "tempdir", str(self.root))
        return ChunkedAudioProcessor(
            track_id=5948, filepath=filepath, preset="adaptive", intensity=1.0, chunk_cache={}
        )

    def files(self) -> dict[str, Path]:
        return {p.name: p for p in self.root.rglob("*.wav")}


@pytest.fixture
def caches(tmp_path, monkeypatch):
    return lambda name: _Cache(tmp_path, monkeypatch, name)


def _play(proc: ChunkedAudioProcessor, order) -> dict[int, np.ndarray]:
    return {index: proc.process_chunk(index)[1].copy() for index in order}


def _durable(cache: _Cache) -> dict[int, np.ndarray]:
    by_index = {}
    for name, path in cache.files().items():
        index = int(name.rsplit("_chunk_", 1)[1].split("_")[0].split(".")[0]) if "_chunk_" in name else None
        if index is not None:
            by_index[index] = read_chunk_wav(path)
    return by_index


def test_cache_version_invalidates_files_with_baked_in_gain():
    assert WAVEncoder.CACHE_VERSION >= 5


def test_durable_chunks_do_not_depend_on_render_order(track, caches):
    in_order, scrambled = caches("in_order"), caches("scrambled")

    straight = in_order.processor(track)
    _play(straight, CHUNKS)
    # The cache worker's tier-1/tier-2 interleave, or a seek: 4 first, then 0..3, 5.
    jumpy = scrambled.processor(track)
    _play(jumpy, [4, 0, 1, 2, 3, 5])

    a, b = _durable(in_order), _durable(scrambled)
    assert sorted(a) == sorted(b) == list(CHUNKS)
    for index in CHUNKS:
        np.testing.assert_array_equal(a[index], b[index], err_msg=f"chunk {index} differs by render order")


def test_a_hit_is_smoothed_exactly_like_the_miss_it_replaces(track, caches):
    cache = caches("shared")
    missed = _play(cache.processor(track), CHUNKS)
    hit = _play(cache.processor(track), CHUNKS)  # fresh stream: every chunk is a cache hit

    for index in CHUNKS:
        assert hit[index].shape == missed[index].shape
        # Only the 16-bit quantisation of the stored file separates them.
        np.testing.assert_allclose(hit[index], missed[index], atol=2e-3, err_msg=f"chunk {index}")
    # The smoother really fired, so this is not comparing two untouched copies.
    raw = _durable(cache)
    assert any(not np.allclose(raw[i], missed[i], atol=2e-3) for i in CHUNKS)


def test_priming_the_cache_out_of_order_does_not_change_what_a_stream_hears(track, caches):
    reference = _play(caches("reference").processor(track), CHUNKS)

    primed = caches("primed")
    _play(primed.processor(track), [4, 0, 1, 2, 3, 5])  # e.g. seek/prewarm/worker writers
    heard = _play(primed.processor(track), CHUNKS)  # a later, sequential play of the track

    for index in CHUNKS:
        np.testing.assert_allclose(heard[index], reference[index], atol=2e-3, err_msg=f"chunk {index}")


def test_a_seek_starts_a_fresh_baseline_without_marking_the_cache(track, caches):
    cache = caches("seeked")
    seek = cache.processor(track)
    heard_at_seek = seek.process_chunk(4)[1].copy()  # first chunk a stream hears: unsmoothed baseline
    raw = _durable(cache)[4]

    np.testing.assert_allclose(heard_at_seek, raw, atol=2e-3)
    # ...and a straight-through play afterwards still smooths chunk 4 against chunk 3.
    reference = _play(caches("ref2").processor(track), CHUNKS)
    heard = _play(cache.processor(track), CHUNKS)
    np.testing.assert_allclose(heard[4], reference[4], atol=2e-3)
    assert not np.allclose(heard[4], raw, atol=2e-3), "chunk 4 should have been smoothed against chunk 3"
