"""
Regression tests: each live stream renders on its own HybridProcessor (#6091).

``ProcessorFactory.get_or_create`` returned the identical cached instance to every
stream of one (track, preset, config, targets) key, so a reconnect whose old
WebSocket was still half-open, or a second window, fed chunks into one processor
in interleaved order and baked the resulting seams into the durable chunk cache.
A ``ChunkedAudioProcessor`` now leases its processor: concurrent streams get
distinct instances, one stream keeps one instance for all its chunks, and
``close()`` hands it back for the next stream.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

import core.chunked_processor as cp
from core.processor_factory import ProcessorFactory

SR = 44100


@pytest.fixture
def wav(tmp_path):
    path = tmp_path / "tiny.wav"
    sf.write(str(path), np.zeros((SR // 10, 2), dtype=np.float32), SR, subtype="FLOAT")
    return str(path)


@pytest.fixture
def factory():
    """A real factory whose HybridProcessor construction is stubbed (200-500 ms each)."""
    built: list[MagicMock] = []

    def _build(*_a, **_k):
        processor = MagicMock(name=f"hybrid-{len(built)}")
        built.append(processor)
        return processor

    with patch("auralis.core.hybrid_processor.HybridProcessor", side_effect=_build):
        factory = ProcessorFactory()
        factory.built = built  # type: ignore[attr-defined]
        yield factory


def _stream(wav: str, factory: ProcessorFactory) -> "cp.ChunkedAudioProcessor":
    return cp.ChunkedAudioProcessor(
        track_id=1, filepath=wav, preset="adaptive", processor_factory=factory
    )


def test_two_concurrent_streams_of_one_track_get_distinct_processors(wav, factory):
    old_socket, new_socket = _stream(wav, factory), _stream(wav, factory)
    try:
        assert old_socket.hybrid_processor() is not new_socket.hybrid_processor()
        assert len(factory.built) == 2
    finally:
        old_socket.close()
        new_socket.close()


def test_one_stream_uses_the_same_processor_for_every_chunk(wav, factory):
    stream = _stream(wav, factory)
    try:
        first = stream.hybrid_processor()
        assert all(stream.hybrid_processor() is first for _ in range(5))
        assert len(factory.built) == 1
    finally:
        stream.close()


def test_close_returns_the_processor_for_the_next_stream_of_the_track(wav, factory):
    first = _stream(wav, factory)
    leased = first.hybrid_processor()
    first.close()

    second = _stream(wav, factory)
    try:
        assert second.hybrid_processor() is leased
        assert len(factory.built) == 1
    finally:
        second.close()


def test_close_is_idempotent_and_does_not_close_the_cached_processor(wav, factory):
    stream = _stream(wav, factory)
    leased = stream.hybrid_processor()

    stream.close()
    stream.close()

    leased.close.assert_not_called()
    assert list(factory._processor_cache.values()) == [leased]


def test_a_discarded_processor_is_replaced_by_a_fresh_lease_on_the_next_chunk(wav, factory):
    from core.chunk_stream_state import invalidate_pooled_processor

    stream = _stream(wav, factory)
    try:
        advanced = stream.hybrid_processor()

        invalidate_pooled_processor(stream, 0, "DSP timed out")

        assert stream.processor is None
        advanced.close.assert_called_once()
        fresh = stream.hybrid_processor()
        assert fresh is not advanced
        assert stream.hybrid_processor() is fresh
    finally:
        stream.close()

    # Only the healthy one went back to the cache.
    assert list(factory._processor_cache.values()) == [fresh]


def test_original_audio_streams_lease_nothing(wav, factory):
    stream = cp.ChunkedAudioProcessor(
        track_id=1, filepath=wav, preset=None, processor_factory=factory
    )

    assert stream.hybrid_processor() is None
    stream.close()
    assert factory.built == []
