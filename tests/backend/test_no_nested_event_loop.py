"""
Test: no nested event loops from get_full_processed_audio_path (fixes #2318)

Verifies that:
- process_chunk_synchronized() no longer exists (deleted)
- get_full_processed_audio_path() is async and calls process_chunk_safe() directly
- No asyncio.run() is invoked from within a running event loop
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunked_processor import ChunkedAudioProcessor


def _make_processor() -> ChunkedAudioProcessor:
    """Build a minimally-configured ChunkedAudioProcessor without touching disk."""
    with patch.object(ChunkedAudioProcessor, "_load_metadata", lambda self: None):
        proc = ChunkedAudioProcessor.__new__(ChunkedAudioProcessor)
        proc.track_id = 1
        proc.filepath = "/fake/track.flac"
        proc.preset = "adaptive"
        proc.intensity = 1.0
        proc.sample_rate = 44100
        proc.total_chunks = 3
        proc.file_signature = "abc123"
        proc.chunk_dir = Path("/tmp/chunks")
        proc._processor_lock = asyncio.Lock()
        proc._cache_manager = MagicMock()
        proc._cache_manager.get_chunk_path.return_value = None
        return proc


def test_process_chunk_synchronized_removed():
    """Acceptance criterion: no more asyncio.run() inside a running loop."""
    assert not hasattr(ChunkedAudioProcessor, "process_chunk_synchronized"), (
        "process_chunk_synchronized() must be removed (fixes #2318)"
    )


def test_get_full_processed_audio_path_is_async():
    """get_full_processed_audio_path() must be a coroutine function."""
    assert asyncio.iscoroutinefunction(ChunkedAudioProcessor.get_full_processed_audio_path), (
        "get_full_processed_audio_path() must be async (fixes #2318)"
    )


@pytest.mark.asyncio
async def test_get_full_processed_audio_path_calls_process_chunk_safe():
    """
    get_full_processed_audio_path() must await process_chunk_safe() per chunk
    without spawning threads or nested event loops.
    """
    proc = _make_processor()

    fake_audio = np.zeros(44100, dtype=np.float32)
    call_log: list[tuple[int, bool]] = []

    async def fake_process_chunk_safe(chunk_index: int, fast_start: bool = False):
        call_log.append((chunk_index, fast_start))
        chunk_path = proc.chunk_dir / f"chunk_{chunk_index}.wav"
        return (str(chunk_path), fake_audio)

    proc.process_chunk_safe = fake_process_chunk_safe  # type: ignore[method-assign]

    # _get_chunk_path must return a fake path that "exists" (patched via load_audio)
    def fake_get_chunk_path(idx: int):
        return proc.chunk_dir / f"chunk_{idx}.wav"

    proc._get_chunk_path = fake_get_chunk_path  # type: ignore[method-assign]

    with (
        patch("core.chunked_processor.load_audio", return_value=(fake_audio, 44100)),
        patch("core.chunked_processor.save_audio"),
        patch("core.chunked_processor.apply_crossfade_between_chunks", side_effect=lambda a, b, _: a),
        patch.object(Path, "exists", return_value=False),
    ):
        result = await proc.get_full_processed_audio_path()

    # Verify all 3 chunks were processed
    assert len(call_log) == 3, f"Expected 3 chunks processed, got {len(call_log)}"
    # Verify chunk indices and fast_start flag
    assert call_log[0] == (0, True), "First chunk must use fast_start=True"
    assert call_log[1] == (1, False)
    assert call_log[2] == (2, False)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_full_processed_audio_path_no_nested_loop():
    """
    process_chunk_safe() must be awaited (not run via asyncio.run/ThreadPoolExecutor)
    when called from within a running event loop.

    This is the core regression test for #2318.
    """
    proc = _make_processor()
    fake_audio = np.zeros(100, dtype=np.float32)

    nested_loop_created = []

    original_run = asyncio.run

    def patched_asyncio_run(coro, **kwargs):
        # If asyncio.run() is ever called here, we're inside a running loop — bug!
        nested_loop_created.append(True)
        return original_run(coro, **kwargs)

    async def fake_process_chunk_safe(chunk_index: int, fast_start: bool = False):
        return (f"/tmp/chunk_{chunk_index}.wav", fake_audio)

    proc.process_chunk_safe = fake_process_chunk_safe  # type: ignore[method-assign]
    proc._get_chunk_path = lambda idx: Path(f"/tmp/chunk_{idx}.wav")  # type: ignore[method-assign]

    with (
        patch("asyncio.run", patched_asyncio_run),
        patch("core.chunked_processor.load_audio", return_value=(fake_audio, 44100)),
        patch("core.chunked_processor.save_audio"),
        patch("core.chunked_processor.apply_crossfade_between_chunks", side_effect=lambda a, b, _: a),
        patch.object(Path, "exists", return_value=False),
    ):
        await proc.get_full_processed_audio_path()

    assert not nested_loop_created, (
        "asyncio.run() was called inside a running event loop — nested loop bug #2318 is still present!"
    )


@pytest.mark.asyncio
async def test_get_full_processed_audio_path_returns_cached():
    """If the full file already exists, return immediately without processing any chunk."""
    proc = _make_processor()

    chunk_calls: list[int] = []

    async def fake_process_chunk_safe(chunk_index: int, fast_start: bool = False):
        chunk_calls.append(chunk_index)
        return (f"/tmp/chunk_{chunk_index}.wav", np.zeros(100, dtype=np.float32))

    proc.process_chunk_safe = fake_process_chunk_safe  # type: ignore[method-assign]

    with patch.object(Path, "exists", return_value=True):
        result = await proc.get_full_processed_audio_path()

    assert chunk_calls == [], "No chunks should be processed when cached file exists"
    assert result.endswith("_full.wav")
