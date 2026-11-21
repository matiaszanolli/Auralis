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
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from dataclasses import dataclass

import soundfile as sf

from core.chunk_boundaries import content_chunk_count
from core.seekable_probe import can_seek_natively
from core.seekable_source import SeekableSource
from auralis.io import loader as _io_loader
from auralis.io.audio_probe import get_audio_info
from auralis.io.processing import decoded_channel_count
from auralis.io.unified_loader import load_audio

logger = logging.getLogger("core.chunked_processor")


def _bounded_chunk_count(total_duration: float, filepath: str) -> int:
    """Chunk count for ``total_duration``, clamped to the decode budget (#5312).

    Defense in depth behind the probe-time cap in ``auralis.io.unified_loader``:
    a duration is only ever as trustworthy as the container header it came
    from, and every chunk past real EOF costs a DSP render, a cache write and
    two ERROR/WARNING log lines. No track may be loaded that is longer than
    ``MAX_DURATION_SECONDS``, so no stream can legitimately need more chunks
    than that duration implies. The clamp never binds on a file the loaders
    would actually accept.
    """
    # Read through the module so an AURALIS_MAX_DURATION_SECONDS override (or
    # a test monkeypatch) of the single source of truth is honoured here too.
    max_duration = _io_loader.MAX_DURATION_SECONDS
    total_chunks = content_chunk_count(total_duration)
    ceiling = content_chunk_count(float(max_duration))
    if total_chunks > ceiling:
        logger.warning(
            f"Duration {total_duration:.0f}s implies {total_chunks} chunks, above the "
            f"{max_duration}s decode budget ({ceiling} chunks) — clamping. "
            f"The container's reported duration is likely forged or corrupt: {filepath}"
        )
        return ceiling
    return total_chunks


@dataclass(frozen=True)
class AudioMetadata:
    """Track metadata needed to drive chunked processing."""

    sample_rate: int
    channels: int
    total_duration: float
    total_chunks: int


def _container_duration_is_unreliable(filepath: str) -> bool:
    """libsndfile opens `filepath` yet `can_seek_natively` rejects it: their lengths disagree (#6448).

    That is the signature of a header-less VBR or joined MP3: one of the two sizes is wrong, and
    ffprobe's is only an estimate there (off by single-digit percent), so a chunk count derived
    from it can run past the real end or stop short of it. A file libsndfile cannot open at all
    (m4a, aac, wma) is not flagged: nothing contradicts ffprobe, and its estimate is sound.
    """
    if can_seek_natively(filepath):
        return False
    try:
        sf.info(filepath)
    except Exception:
        return False
    return True


def _decoded_duration(source: SeekableSource, probed: float) -> float:
    """The length of the audio the chunk reader will actually read (#6448).

    `source` resolves to the converted WAV the chunks are read from, so its frame count is the
    only length that agrees with what gets streamed (and with `stream_normal`, which also sizes
    itself from the converted WAV). A conversion that fails keeps the probed length: the first
    chunk read then fails exactly as it did before, with the real error.
    """
    try:
        info = sf.info(source.resolve())
        return float(info.frames / info.samplerate)
    except Exception as e:
        logger.warning(f"Could not measure the decoded length ({e}); keeping the probed {probed:.2f}s")
        return probed


def load_audio_metadata(filepath: str, source: SeekableSource | None = None) -> AudioMetadata:
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

    ``source`` is the caller's own :class:`SeekableSource` (it owns the conversion and must close
    it). Given one, a file whose container duration cannot be trusted - libsndfile opens it but
    its length disagrees with ffprobe's, a header-less VBR or joined MP3 - is converted now and
    its length measured from the WAV, so the chunk count, the stream-start duration and the seek
    clamp all describe the audio that is streamed (#6448). Every other file keeps the
    decode-free probe: a recommendation-only construction must not decode a healthy m4a.
    """
    try:
        meta = get_audio_info(filepath)
        if meta.get('error') or 'sample_rate' not in meta:
            raise RuntimeError(meta.get('error', 'incomplete audio metadata'))
        sample_rate = int(meta['sample_rate'])
        channels = int(meta['channels'])
        # A file libsndfile cannot open is decoded through FFmpeg, which folds
        # >2 channels to stereo: advertise what the chunks actually carry, not
        # the container's native count (#5709). Native files stream as-is.
        if not can_seek_natively(filepath):
            channels = decoded_channel_count(channels)
        total_duration = float(meta['duration_seconds'])
        if source is not None and _container_duration_is_unreliable(filepath):
            total_duration = _decoded_duration(source, total_duration)
        # Count only content-carrying chunks under the overlap model
        # (#4124) — see core.chunk_boundaries.content_chunk_count.
        total_chunks = _bounded_chunk_count(total_duration, filepath)
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
        total_chunks = _bounded_chunk_count(total_duration, filepath)
        return AudioMetadata(
            sample_rate=sr,
            channels=channels,
            total_duration=total_duration,
            total_chunks=total_chunks,
        )
