#!/usr/bin/env python3

"""
Normal (Unprocessed) Audio Streaming
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The stream_normal_audio entry point: streams original, unprocessed audio
chunks to a client via WebSocket for A/B comparison against the enhanced
path. No DSP or crossfade is applied — chunks are read straight from disk
(or a temp WAV for compressed formats) with look-ahead I/O.

Extracted from audio_stream_controller.py (#4071).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any
from collections.abc import Callable

import numpy as np
import soundfile as sf
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from . import audio_stream_controller as _asc

logger = logging.getLogger(__name__)


async def stream_normal_audio(
    controller: '_asc.AudioStreamController',
    track_id: int,
    websocket: WebSocket,
    start_position: float = 0.0,
    on_progress: Callable[[int, float, str], Any] | None = None
) -> None:
    """
    Stream original (unprocessed) audio chunks to client via WebSocket.

    Used for comparing original vs enhanced audio. Same chunking format as enhanced,
    but with no DSP processing applied.

    Args:
        controller: AudioStreamController instance
        track_id: Track ID to stream
        websocket: WebSocket connection to client
        on_progress: Optional callback for progress updates

    Raises:
        ValueError: If track not found or file unavailable
        Exception: If loading or streaming fails
    """
    _asc._stream_type_var.set("normal")  # per-task; safe for concurrent coroutines (fixes #2493)

    if not controller._get_repository_factory:
        raise ValueError("RepositoryFactory not available")

    # Limit concurrent streams to prevent unbounded memory growth (#2185)
    try:
        await asyncio.wait_for(controller._stream_semaphore.acquire(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning(
            f"Stream limit ({_asc.MAX_CONCURRENT_STREAMS}) reached, rejecting track {track_id}"
        )
        await controller._send_error(websocket, track_id, "Server busy - too many active streams")
        return

    # Declare look-ahead task early so the outer `finally:` can drain it
    # even on early-exit paths (fixes #3493 unbound-var hazard).
    lookahead_read: asyncio.Task[np.ndarray] | None = None

    # Get track from library
    try:
        factory = controller._get_repository_factory()
        track = await asyncio.to_thread(factory.tracks.get_by_id, track_id)
        if not track:
            await controller._send_error(websocket, track_id, "Track not found")
            controller._stream_semaphore.release()
            return

        if not Path(track.filepath).exists():
            await controller._send_error(
                websocket, track_id, "Audio file not found"
            )
            controller._stream_semaphore.release()
            return
    except Exception as e:
        logger.error(f"Failed to load track {track_id}: {e}", exc_info=True)
        await controller._send_error(websocket, track_id, "Failed to load track")
        controller._stream_semaphore.release()
        return

    # For compressed formats (MP3, M4A, etc.), convert to temp WAV first
    # since sf.SoundFile only supports PCM formats (#3225).
    temp_wav_path: str | None = None
    streaming_filepath = str(track.filepath)

    try:
        from auralis.io.unified_loader import FFMPEG_FORMATS
        file_ext = Path(track.filepath).suffix.lower()
        if file_ext in FFMPEG_FORMATS:
            import tempfile
            from auralis.io.unified_loader import load_audio
            temp_dir = tempfile.mkdtemp(prefix='auralis_stream_')
            audio_data, sr = await asyncio.to_thread(
                load_audio, str(track.filepath), "audio", temp_dir
            )
            # Write to temp WAV for chunked streaming
            temp_wav_path = str(Path(temp_dir) / 'stream.wav')
            import soundfile as _sf
            await asyncio.to_thread(
                _sf.write, temp_wav_path, audio_data, sr, format='WAV', subtype='FLOAT'
            )
            streaming_filepath = temp_wav_path
            logger.info(f"Converted {file_ext} to temp WAV for normal streaming")

        # Read file metadata only — do NOT load audio data yet (#2121).
        # sf.read() would allocate ~200 MB for a 10-min stereo track; instead
        # we open the SoundFile, record its shape, and close it immediately.
        def _get_audio_info(filepath: str) -> tuple[int, int, int]:
            with sf.SoundFile(filepath) as audio_file:
                return audio_file.samplerate, audio_file.channels, len(audio_file)

        sample_rate, channels, total_frames = await asyncio.to_thread(
            _get_audio_info, streaming_filepath
        )

        duration = total_frames / sample_rate

        # Calculate chunks (NO overlap for normal streaming - no crossfade applied)
        # #3775: pull the constant from chunk_boundaries instead of
        # re-declaring it (third declaration removed; chunked_processor
        # CHUNK_DURATION already mirrors chunk_boundaries.CHUNK_DURATION).
        from .chunk_boundaries import CHUNK_DURATION
        chunk_duration = float(CHUNK_DURATION)
        chunk_samples = int(chunk_duration * sample_rate)

        # For normal path: chunk_interval = chunk_duration (no overlap)
        # Unlike enhanced path which uses ChunkedProcessor with server-side crossfade,
        # normal path sends chunks without processing, so overlap would cause duplication
        interval_samples = chunk_samples  # No overlap

        total_chunks = max(1, int(np.ceil(total_frames / interval_samples)))

        # Calculate start chunk for seek (#3187)
        start_chunk = 0
        if start_position > 0:
            start_sample = int(start_position * sample_rate)
            start_chunk = min(start_sample // interval_samples, total_chunks - 1)
        # #3768: kept only for the logging line below — audio_stream_start
        # reports full total_chunks (see seek_kwargs), not this value.
        remaining_chunks = total_chunks - start_chunk

        # Register active stream so cleanup can always find it (fixes #2076, #3182)
        async with controller._active_streams_lock:
            controller.active_streams[_asc.ws_id(websocket)] = asyncio.current_task()

        logger.info(
            f"Starting normal audio stream: track={track_id}, "
            f"duration={duration:.1f}s, chunks={total_chunks}, sr={sample_rate}Hz"
            + (f", seek={start_position:.1f}s (chunk {start_chunk})" if start_chunk > 0 else "")
        )

        # When resuming mid-track (start_position > 0), emit is_seek=true so
        # the client preserves its AudioContext + PCMStreamBuffer instead of
        # tearing them down (click-free WS reconnect resume, fixes #3755;
        # mirrors the enhanced path since #3185). chunk_interval ==
        # chunk_duration here (no overlap), so seek_offset is the
        # within-chunk offset of start_position.
        seek_kwargs: dict[str, Any] = {}
        if start_position > 0:
            seek_kwargs = {
                "start_chunk": start_chunk,
                "seek_position": start_position,
                "seek_offset": start_position - (start_chunk * chunk_duration),
            }
        if not await controller._send_stream_start(
            websocket,
            track_id=track_id,
            preset="none",  # No processing
            intensity=1.0,   # Full intensity (original)
            sample_rate=sample_rate,
            channels=channels,
            # #3768: emit the FULL track's chunk count as a stable
            # denominator across seeks; start_chunk (via seek_kwargs)
            # lets the client offset the numerator (matches enhanced
            # path convention since #3185).
            total_chunks=total_chunks,
            chunk_duration=chunk_duration,
            total_duration=duration - (start_chunk * chunk_duration),
            **seek_kwargs,
        ):
            logger.info(f"WebSocket disconnected, cannot start stream")
            return

        # Helper: open → seek → read → close for a single chunk (#2121).
        # Uses streaming_filepath (temp WAV for compressed formats, original for PCM).
        def _read_audio_chunk(filepath: str, start: int, frames: int) -> np.ndarray:
            with sf.SoundFile(filepath) as audio_file:
                audio_file.seek(start)
                # always_2d=True: mono returned as (N, 1) matching stereo shape
                # Do NOT use fill_value: send the last chunk at its actual
                # length to avoid appending silence (#2124).
                return audio_file.read(
                    frames=frames, dtype='float32', always_2d=True
                )

        # Look-ahead variant: short-circuits the disk read if the client
        # vanished during the previous chunk's send (#3874). Runs in a
        # worker thread concurrently with send_pcm_chunk; mirrors the
        # enhanced-path ConnectionError guard in process_chunk_only.
        def _read_audio_chunk_lookahead(filepath: str, start: int, frames: int) -> np.ndarray:
            if not controller._is_websocket_connected(websocket):
                raise ConnectionError("WebSocket disconnected before look-ahead read")
            return _read_audio_chunk(filepath, start, frames)

        # Stream chunks with look-ahead: read chunk N+1 from disk while
        # streaming chunk N to eliminate I/O gaps.
        for chunk_idx in range(start_chunk, total_chunks):
            # Honour pause/resume events from the WebSocket handler (#2106).
            from routers.system import _stream_pause_events, _stream_flow_events
            pause_evt = _stream_pause_events.get(_asc.ws_id(websocket))
            if pause_evt is not None:
                await pause_evt.wait()
            # Honour flow control: wait if frontend buffer is full.
            flow_evt = _stream_flow_events.get(_asc.ws_id(websocket))
            if flow_evt is not None:
                await flow_evt.wait()

            if not controller._is_websocket_connected(websocket):
                logger.info(f"WebSocket disconnected, stopping stream")
                await controller._drain_cancelled_task(lookahead_read)
                lookahead_read = None
                break

            try:
                # Get chunk audio: from look-ahead task or read now
                if lookahead_read is not None:
                    try:
                        chunk_audio = await lookahead_read
                    except ConnectionError:
                        # Client disconnected during the look-ahead read (#3874).
                        # Clean exit — not a chunk failure, so don't log it as one.
                        break
                    lookahead_read = None
                else:
                    start_sample = chunk_idx * interval_samples
                    chunk_audio = await asyncio.to_thread(
                        _read_audio_chunk, streaming_filepath, start_sample, chunk_samples
                    )

                # Start look-ahead: read next chunk while we stream current one
                if chunk_idx + 1 < total_chunks:
                    next_start = (chunk_idx + 1) * interval_samples
                    lookahead_read = asyncio.create_task(
                        asyncio.to_thread(
                            _read_audio_chunk_lookahead, streaming_filepath, next_start, chunk_samples
                        )
                    )

                # Stream the chunk
                await controller._send_pcm_chunk(
                    websocket,
                    pcm_samples=chunk_audio,
                    chunk_index=chunk_idx,
                    total_chunks=total_chunks,
                    crossfade_samples=0,  # No overlap in normal path (no crossfade applied)
                )

                # Progress update
                if on_progress:
                    progress = ((chunk_idx + 1) / total_chunks) * 100
                    await on_progress(track_id, progress, f"Streamed chunk {chunk_idx + 1}")

            except Exception as chunk_error:
                # Drain the cancelled look-ahead so the next iteration
                # doesn't trip on its CancelledError (#3493).
                await controller._drain_cancelled_task(lookahead_read)
                lookahead_read = None
                logger.error(f"Failed to stream chunk {chunk_idx}: {chunk_error}", exc_info=True)
                # Recovery position: start of the failed chunk (issue #2085)
                normal_recovery_position: float = chunk_idx * chunk_duration
                await controller._send_error(
                    websocket,
                    track_id,
                    f"Failed to stream audio chunk {chunk_idx}",
                    recovery_position=normal_recovery_position,
                )
                # Skip failed chunk and continue with remaining chunks (#3190)
                continue

        # Stream complete
        logger.info(f"Normal audio stream complete: track={track_id}")
        await controller._send_stream_end(
            websocket,
            track_id=track_id,
            total_samples=total_frames,
            duration=duration,
        )

    except WebSocketDisconnect:
        # Client closed the WebSocket — normal exit (#3511 / BE-NEW-53).
        logger.info(f"Normal audio streaming stopped: client disconnected")
    except Exception as e:
        logger.error(f"Normal audio streaming failed: {e}", exc_info=True)
        # Only try to send error if WebSocket is still connected
        if controller._is_websocket_connected(websocket):
            await controller._send_error(websocket, track_id, "Audio streaming failed")
    finally:
        # Drain any in-flight look-ahead read task (fixes #3493).
        await controller._drain_cancelled_task(lookahead_read)
        async with controller._active_streams_lock:  # fixes #2076, #3182
            controller.active_streams.pop(_asc.ws_id(websocket), None)
        controller._stream_semaphore.release()
        # Clean up temp WAV created for compressed format streaming (#3225).
        # Log on failure instead of swallowing it (#3877): an EBUSY/EACCES
        # holdout is swept and counted at next startup (config/startup.py).
        if temp_wav_path:
            import shutil
            try:
                shutil.rmtree(
                    Path(temp_wav_path).parent,
                    onexc=lambda _func, path, exc: logger.warning(
                        f"Failed to remove temp stream file {path}: {exc}"
                    ),
                )
            except Exception as cleanup_error:
                logger.warning(
                    f"Temp stream cleanup failed for {temp_wav_path}: {cleanup_error}"
                )
