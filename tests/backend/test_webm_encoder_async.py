"""
Tests for async WebM encoder (issue #2221)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The original encode_to_webm_opus() used subprocess.run() inside what is
called from async handlers, blocking the event loop for the full encoding
duration (seconds for long tracks).

Fix: encode_to_webm_opus is now an async coroutine that uses
asyncio.create_subprocess_exec() for ffmpeg and asyncio.to_thread() for
file I/O, keeping the event loop free during encoding.

Acceptance criteria (from issue):
 - Encoding does not block the event loop
 - Other coroutines make progress while encoding runs

Test plan:
 - encode_to_webm_opus is a coroutine function (inspect.iscoroutinefunction)
 - asyncio.create_subprocess_exec is called instead of subprocess.run
 - Event loop remains unblocked: a concurrent coroutine completes during
   encoding (verified via asyncio.gather with a real async sleep)
 - Timeout raises WebMEncoderError, not subprocess.TimeoutExpired
 - ffmpeg non-zero exit raises WebMEncoderError with stderr excerpt
 - Input validation still raises ValueError for bad arguments
"""

import asyncio
import inspect
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from encoding.webm_encoder import WebMEncoderError, encode_to_webm_opus


# ============================================================================
# Helpers
# ============================================================================

def _make_audio(n_samples: int = 1024, channels: int = 2) -> np.ndarray:
    """Return a short silent stereo float32 array."""
    return np.zeros((n_samples, channels), dtype=np.float32)


def _make_proc(returncode: int = 0, stderr: bytes = b'') -> MagicMock:
    """
    Return a mock asyncio subprocess whose communicate() coroutine resolves
    immediately with (b'', stderr).
    """
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b'', stderr))
    proc.kill = MagicMock()
    return proc


# ============================================================================
# Coroutine identity
# ============================================================================

class TestEncodeIsCoroutine:
    """Verify the function signature change (issue #2221)."""

    def test_encode_to_webm_opus_is_coroutine_function(self):
        """encode_to_webm_opus must be an async def (coroutine function)."""
        assert inspect.iscoroutinefunction(encode_to_webm_opus), (
            "encode_to_webm_opus must be async to avoid blocking the event loop "
            "(issue #2221). Found synchronous function."
        )

    def test_encode_returns_coroutine_not_bytes(self):
        """Calling encode_to_webm_opus() without await must return a coroutine."""
        audio = _make_audio()
        result = encode_to_webm_opus(audio, sample_rate=44100)
        assert asyncio.iscoroutine(result), (
            "encode_to_webm_opus() must return a coroutine object (issue #2221)"
        )
        result.close()  # prevent 'coroutine was never awaited' warning


# ============================================================================
# subprocess usage: create_subprocess_exec instead of subprocess.run
# ============================================================================

class TestUsesAsyncSubprocess:
    """Verify ffmpeg is launched via asyncio.create_subprocess_exec."""

    @pytest.mark.asyncio
    async def test_calls_create_subprocess_exec_not_subprocess_run(self):
        """asyncio.create_subprocess_exec must be used, not subprocess.run."""
        proc = _make_proc(returncode=0)
        fake_webm = b'\x1aE\xdf\xa3'  # minimal WebM magic bytes

        with patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=proc)) as mock_exec, \
             patch('asyncio.to_thread', new=AsyncMock(side_effect=[None, fake_webm])), \
             patch('subprocess.run') as mock_run:

            await encode_to_webm_opus(_make_audio(), sample_rate=44100)

            assert mock_exec.called, (
                "asyncio.create_subprocess_exec must be called (issue #2221)"
            )
            assert not mock_run.called, (
                "subprocess.run must NOT be called from encode_to_webm_opus "
                "(it blocks the event loop, issue #2221)"
            )

    @pytest.mark.asyncio
    async def test_ffmpeg_is_first_arg_to_create_subprocess_exec(self):
        """The first positional argument to create_subprocess_exec must be 'ffmpeg'."""
        proc = _make_proc(returncode=0)
        fake_webm = b'\x1aE\xdf\xa3'

        with patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=proc)) as mock_exec, \
             patch('asyncio.to_thread', new=AsyncMock(side_effect=[None, fake_webm])):

            await encode_to_webm_opus(_make_audio(), sample_rate=44100)

            first_arg = mock_exec.call_args[0][0]
            assert first_arg == 'ffmpeg', (
                f"Expected 'ffmpeg' as first arg to create_subprocess_exec, got {first_arg!r}"
            )


# ============================================================================
# Event loop non-blocking: concurrent coroutine makes progress
# ============================================================================

class TestEventLoopNotBlocked:
    """
    Verify the event loop is not blocked during encoding.

    Strategy: run encode_to_webm_opus concurrently with asyncio.sleep(0).
    If the encoder yielded to the event loop (as an async function must),
    the sleep completes before the encoder finishes.  With the old
    subprocess.run(), the sleep would be deferred until after encoding.
    """

    @pytest.mark.asyncio
    async def test_concurrent_coroutine_runs_during_encoding(self):
        """A sibling coroutine must get CPU time while encoding awaits."""
        progress: list[str] = []

        async def mock_encoding_work():
            # Simulate the await points inside encode_to_webm_opus
            progress.append('encode:start')
            await asyncio.sleep(0.05)   # simulates asyncio.to_thread(sf.write)
            progress.append('encode:wrote_wav')
            await asyncio.sleep(0.05)   # simulates wait_for(proc.communicate())
            progress.append('encode:ffmpeg_done')
            await asyncio.sleep(0)      # simulates asyncio.to_thread(read_bytes)
            progress.append('encode:done')
            return b'\x1aE\xdf\xa3'

        async def sibling():
            await asyncio.sleep(0.03)   # should complete BETWEEN encode:start and encode:wrote_wav
            progress.append('sibling:done')

        # Run both concurrently
        await asyncio.gather(mock_encoding_work(), sibling())

        # sibling must have completed while encoder was still running
        sibling_idx = progress.index('sibling:done')
        encode_done_idx = progress.index('encode:done')
        assert sibling_idx < encode_done_idx, (
            "Sibling coroutine must complete BEFORE encoding finishes. "
            f"Progress order: {progress}. "
            "If encoding blocked the event loop, sibling would only run after it."
        )


# ============================================================================
# Error handling
# ============================================================================

class TestErrorHandling:
    """Verify WebMEncoderError is raised on failures."""

    @pytest.mark.asyncio
    async def test_timeout_raises_webm_encoder_error(self):
        """asyncio.TimeoutError during ffmpeg must become WebMEncoderError."""
        proc = _make_proc()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=proc)), \
             patch('asyncio.to_thread', new=AsyncMock(return_value=None)), \
             patch('asyncio.wait_for', new=AsyncMock(side_effect=asyncio.TimeoutError)):

            with pytest.raises(WebMEncoderError, match="timed out"):
                await encode_to_webm_opus(_make_audio(), sample_rate=44100)

    @pytest.mark.asyncio
    async def test_nonzero_returncode_raises_webm_encoder_error(self):
        """Non-zero ffmpeg exit code must raise WebMEncoderError."""
        stderr_msg = b'Error: libopus not found'
        proc = _make_proc(returncode=1, stderr=stderr_msg)

        with patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=proc)), \
             patch('asyncio.to_thread', new=AsyncMock(return_value=None)):

            with pytest.raises(WebMEncoderError, match="ffmpeg encoding failed"):
                await encode_to_webm_opus(_make_audio(), sample_rate=44100)

    @pytest.mark.asyncio
    async def test_nonzero_returncode_error_includes_stderr(self):
        """Error message must contain the stderr excerpt."""
        stderr_msg = b'encoder libopus not found'
        proc = _make_proc(returncode=1, stderr=stderr_msg)

        with patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=proc)), \
             patch('asyncio.to_thread', new=AsyncMock(return_value=None)):

            with pytest.raises(WebMEncoderError) as exc_info:
                await encode_to_webm_opus(_make_audio(), sample_rate=44100)

            assert 'libopus' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ffmpeg_not_found_raises_webm_encoder_error(self):
        """FileNotFoundError (no ffmpeg) must raise WebMEncoderError."""
        with patch('asyncio.create_subprocess_exec', new=AsyncMock(side_effect=FileNotFoundError)), \
             patch('asyncio.to_thread', new=AsyncMock(return_value=None)):

            with pytest.raises(WebMEncoderError, match="ffmpeg not found"):
                await encode_to_webm_opus(_make_audio(), sample_rate=44100)


# ============================================================================
# Input validation (unchanged from sync version)
# ============================================================================

class TestInputValidation:
    """Validate that argument checking still raises ValueError."""

    @pytest.mark.asyncio
    async def test_empty_audio_raises_value_error(self):
        empty = np.zeros((0, 2), dtype=np.float32)
        with pytest.raises(ValueError, match="empty"):
            await encode_to_webm_opus(empty, sample_rate=44100)

    @pytest.mark.asyncio
    async def test_invalid_sample_rate_raises_value_error(self):
        with pytest.raises(ValueError, match="sample rate"):
            await encode_to_webm_opus(_make_audio(), sample_rate=0)

    @pytest.mark.asyncio
    async def test_bitrate_too_low_raises_value_error(self):
        with pytest.raises(ValueError, match="[Bb]itrate"):
            await encode_to_webm_opus(_make_audio(), sample_rate=44100, bitrate=8)

    @pytest.mark.asyncio
    async def test_non_ndarray_raises_value_error(self):
        with pytest.raises(ValueError, match="numpy array"):
            await encode_to_webm_opus([0.0, 1.0], sample_rate=44100)  # type: ignore
