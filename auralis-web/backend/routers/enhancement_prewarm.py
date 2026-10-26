"""
Upcoming-chunk pre-warming for the enhancement router (split from enhancement.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from core.chunk_boundaries import chunk_for_position, content_chunk_count
from core.executors import run_in_stream_executor
from helpers import spawn_background_task
from schemas import DEFAULT_PRESET
from security.path_errors import PathValidationError
from security.path_security import validate_file_path
from typing import Any
import asyncio
import os

logger = logging.getLogger(__name__)


def _track_is_live_streaming(track_id: int) -> bool:
    """True while any WebSocket connection has a live streaming task for this
    track (#5323).

    Pre-warm must not run alongside such a stream. Its independent
    ChunkedAudioProcessor resolves to the SAME shared HybridProcessor through
    ProcessorFactory (intensity is not part of the key, #4707) and writes to
    the same deterministic on-disk chunk path the stream later serves as a
    cache hit — with a fresh LevelManager, so a chunk could be persisted with
    gain smoothed against the wrong history, and alternating calls interleave
    the shared processor's envelope state. The live stream renders those
    chunks itself, and the frontend re-issues it on every mid-playback
    toggle/preset/intensity change, so skipping loses nothing.

    Event-loop only (no await between read and use), so the registries need
    no lock. Imported lazily, as core/stream_enhanced.py does, because
    routers.system_streams pulls in the whole streaming stack.
    """
    from routers.system_streams import _active_streaming_tasks, _active_streaming_track_ids

    for ws_id, streaming_track_id in list(_active_streaming_track_ids.items()):
        if streaming_track_id != track_id:
            continue
        task = _active_streaming_tasks.get(ws_id)
        if task is not None and not task.done():
            return True
    return False


async def _render_upcoming_chunks(
    processor: Any, track_id: int, chunks_to_process: list[int], total_chunks: int
) -> int:
    """Render each of *chunks_to_process* into the cache; return how many landed."""
    processed_count = 0
    for chunk_idx in chunks_to_process:
        if chunk_idx >= total_chunks:
            break  # Don't process chunks beyond the track
        # #5323: a stream for this track can start while pre-warm is
        # probing or rendering (the frontend re-issues it right after
        # the settings POST returns). From then on it owns these chunks.
        if _track_is_live_streaming(track_id):
            logger.info(
                f"🎯 Stopping pre-processing for track {track_id}: "
                "a live stream now covers the upcoming chunks"
            )
            break

        try:
            # Process chunk (this will cache the WAV file).
            # get_wav_chunk_path does CPU-bound audio processing; run it
            # off the event loop (fixes #2330) on the streaming pool, not
            # the default I/O pool, like all other chunk DSP (#5086).
            wav_chunk_path = await run_in_stream_executor(processor.get_wav_chunk_path, chunk_idx)
        except Exception as e:
            logger.error(f"❌ Pre-processing failed for chunk {chunk_idx}: {e}")
            continue

        if os.path.exists(wav_chunk_path):
            processed_count += 1
            logger.info(f"✅ Pre-processed chunk {chunk_idx} ({processed_count}/{len(chunks_to_process)})")
        else:
            logger.warning(f"⚠️ Pre-processing failed for chunk {chunk_idx}: output file not found")
    return processed_count


async def _preprocess_upcoming_chunks(track_id: int, filepath: str, current_time: float, preset: str, intensity: float) -> None:
    """
    Background task to pre-process upcoming chunks when enhancement is enabled mid-playback.
    This prevents audio stopping while waiting for on-demand processing.

    Args:
        track_id: Track database ID
        filepath: Path to audio file
        current_time: Current playback position in seconds
        preset: Enhancement preset name
        intensity: Enhancement intensity (0.0-1.0)
    """
    try:
        # #4818: filepath arrives from player state, i.e. the DB. A folder
        # unregistered after indexing leaves the stored path stale, so re-check
        # containment before any file I/O. This is a background task that
        # nothing awaits, so a rejection skips quietly rather than raising.
        try:
            filepath = str(validate_file_path(str(filepath)))
        except PathValidationError:
            logger.debug(
                f"Skipping chunk pre-processing for track {track_id}: "
                "stored filepath failed validation"
            )
            return

        # Import here to avoid circular dependencies
        from core.chunked_processor import ChunkedAudioProcessor

        from auralis.io.unified_loader import get_audio_info

        # Get audio duration to avoid processing non-existent chunks.
        # #5052: bare sf.info()/soundfile.SoundFile() cannot open
        # .m4a/.aac/.wma — get_audio_info() routes FFmpeg-only formats
        # through ffprobe instead (same fix pattern as #4497's
        # _load_metadata()). It doesn't raise on a probe failure; it
        # sets info_dict['error'] and omits 'duration_seconds', so check
        # explicitly rather than trusting the key is present.
        audio_info = await asyncio.to_thread(get_audio_info, filepath)
        total_duration = audio_info.get('duration_seconds')
        if not total_duration:
            raise ValueError(
                f"Could not determine duration for {filepath}: "
                f"{audio_info.get('error', 'no duration_seconds in probe result')}"
            )
        # Match ChunkedAudioProcessor's content-chunk count so we don't
        # pre-process a spurious trailing chunk (#4124).
        total_chunks = content_chunk_count(total_duration)

        # Calculate current chunk and next 3 chunks to pre-process, via
        # chunk_for_position() (#4557/#4791) — the mapping onto the chunk
        # that actually EMITS current_time, not a naive core-timeline
        # division by CHUNK_INTERVAL, which is off by one for roughly
        # the first half of every emitted chunk window and was skipping
        # the immediately-next chunk (the one whose absence causes the
        # stall this pre-fetch exists to prevent).
        current_chunk_idx = chunk_for_position(
            current_time,
            total_chunks,
            total_duration=total_duration,
        )[0]
        chunks_to_process = [current_chunk_idx + i for i in range(1, 4)]  # Next 3 chunks

        logger.info(f"🎯 Pre-processing chunks {chunks_to_process} for track {track_id} (current chunk: {current_chunk_idx})")

        # Create processor (may perform file I/O — run in thread).
        # #5052: for any format sf.info() can't open, ChunkedAudioProcessor's
        # SeekableSource decodes the whole track to a temp-dir WAV that only
        # processor.close() releases — every other construction site in the
        # backend closes explicitly, this one must too (try/finally below).
        processor = await asyncio.to_thread(
            ChunkedAudioProcessor,
            track_id=track_id,
            filepath=filepath,
            preset=preset,
            intensity=intensity,
            chunk_cache={},
        )
        try:
            processed_count = await _render_upcoming_chunks(
                processor, track_id, chunks_to_process, total_chunks
            )

            logger.info(f"🎯 Pre-processing complete: {processed_count} chunks ready")
        finally:
            await asyncio.to_thread(processor.close)

    except Exception as e:
        logger.error(f"❌ Background chunk pre-processing failed: {e}")


def _maybe_prewarm_upcoming_chunks(
    enhancement_settings: dict[str, Any],
    player_state_manager: Any,
) -> None:
    """Launch background pre-processing of the next few chunks at the
    current preset/intensity, mirroring the toggle-ON pre-warm (#2296).

    Only fires when a track is actively playing — otherwise there is no
    "upcoming" position to pre-process from, same guard toggle_enhancement
    already used. Shared by toggle_enhancement/set_enhancement_preset/
    set_enhancement_intensity (#4425) so a preset or intensity change mid-
    playback gets the same "no audible on-demand gap" treatment the
    enable-toggle path already had.
    """
    if not player_state_manager:
        return
    state = player_state_manager.get_state()
    if not (state.current_track and state.state.value == "playing"):
        return
    if _track_is_live_streaming(state.current_track.id):
        # #5323: the live stream (re-issued by the frontend with these
        # settings) renders the upcoming chunks itself; a parallel pre-warm
        # would race it on the shared processor and the durable chunk cache.
        logger.debug(
            f"Skipping pre-processing for track {state.current_track.id}: "
            "it is already streaming"
        )
        return
    spawn_background_task(
        _preprocess_upcoming_chunks(
            track_id=state.current_track.id,
            filepath=state.current_track.filepath,
            current_time=state.current_time,
            preset=enhancement_settings.get("preset", DEFAULT_PRESET),
            intensity=enhancement_settings.get("intensity", 1.0),
        ),
        name="enhancement._preprocess_upcoming_chunks",
    )
    logger.info(
        f"🎯 Launched background pre-processing for track {state.current_track.id} "
        f"at {state.current_time:.1f}s"
    )
