#!/usr/bin/env python3

"""
Chunked-Processor Metadata Loading
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Loads a track's sample rate / channel count / duration / content-chunk-count
without decoding the full audio file. Extracted from
``ChunkedAudioProcessor._load_metadata()`` (#4245) — pure I/O-probing logic,
not a chunk-streaming concern.

The module logger is deliberately named ``core.chunked_processor`` rather than
``__name__`` (see :mod:`core.chunked_processor` for the shared rationale) so
existing log-capture assertions continue to see these records under the
processor's historical logger name.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.chunk_boundaries import content_chunk_count
from auralis.io.unified_loader import get_audio_info, load_audio

logger = logging.getLogger("core.chunked_processor")


@dataclass(frozen=True)
class AudioMetadata:
    """Track metadata needed to drive chunked processing."""

    sample_rate: int
    channels: int
    total_duration: float
    total_chunks: int


def load_audio_metadata(filepath: str) -> AudioMetadata:
    """Load audio file metadata without loading full audio.

    Routes by extension via ``unified_loader.get_audio_info()``: a
    millisecond ``ffprobe`` for FFmpeg-only formats (mp3/m4a/aac/ogg/wma/
    opus) and ``sf.info()`` for natively-decodable ones. The previous
    implementation opened ``sf.SoundFile()`` directly, which libsndfile
    cannot do for FFmpeg-only formats — the open raised and the ``except``
    fell back to a full-file decode (temp-WAV + full float32 read) just to
    read duration/sample-rate/channels, defeating the bounded-decode
    architecture for the dominant library format (#4497).

    Falls back to a full decode only on a genuine probe failure.
    """
    try:
        meta = get_audio_info(filepath)
        if meta.get('error') or 'sample_rate' not in meta:
            raise RuntimeError(meta.get('error', 'incomplete audio metadata'))
        sample_rate = int(meta['sample_rate'])
        channels = int(meta['channels'])
        total_duration = float(meta['duration_seconds'])
        # Count only content-carrying chunks under the overlap model
        # (#4124) — see core.chunk_boundaries.content_chunk_count.
        total_chunks = content_chunk_count(total_duration)
        return AudioMetadata(
            sample_rate=sample_rate,
            channels=channels,
            total_duration=total_duration,
            total_chunks=total_chunks,
        )
    except Exception as e:
        # Last-resort fallback for a genuine probe failure: full decode.
        logger.error(f"Metadata probe failed, falling back to full decode: {e}")
        audio, sr = load_audio(filepath)
        # load_audio() returns mono as a 1-D (frames,) array and
        # multi-channel as (frames, channels) — samples-first — so channels
        # is shape[1] and frame count is always shape[0]. The old chained
        # ternary keyed on `shape[0] <= 2`, mislabelling very short stereo
        # clips as mono (#3881).
        channels = 1 if audio.ndim == 1 else audio.shape[1]
        total_duration = audio.shape[0] / sr
        total_chunks = content_chunk_count(total_duration)
        return AudioMetadata(
            sample_rate=sr,
            channels=channels,
            total_duration=total_duration,
            total_chunks=total_chunks,
        )
