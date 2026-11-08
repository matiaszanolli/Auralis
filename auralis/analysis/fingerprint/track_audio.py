"""
Which audio the fingerprint analyses: the whole track, or a window of a long one.

Analysis is a property of the entire track; only mastering is chunked. A track up
to ``FINGERPRINT_FULL_TRACK_MAX_S`` is therefore decoded in full (algorithm v13).
Longer files, and files whose duration cannot be read, keep the body + probe
windows from ``windowed_loading``.

A whole track is decoded in ``FINGERPRINT_SEGMENT_S`` segments so the buffer at
the file's NATIVE rate (a 24/192 file is 25x the 22.05 kHz size) never exceeds one
segment. Each segment carries ``FINGERPRINT_SEGMENT_MARGIN_S`` of extra audio on
both sides, trimmed off by exact sample count AFTER resampling: the resampler's
edge response falls in the margin, so segments join with no seam (verified against
a one-shot resample to ~1e-7, float32 noise).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np

from .windowed_loading import (
    WindowSet,
    _decode_window,
    _resample_channels,
    crop_preloaded_windows,
    load_ffmpeg_windows,
    load_librosa_windows,
)
from .windows import (
    FINGERPRINT_SAMPLE_RATE,
    FINGERPRINT_SEGMENT_MARGIN_S,
    FINGERPRINT_SEGMENT_S,
    analyses_whole_track,
    stereo_window,
)


def join_segments(
    total_s: float, load_segment: Callable[[float, float], np.ndarray]
) -> np.ndarray:
    """Decode ``total_s`` seconds via ``load_segment(offset_s, duration_s)`` and join them.

    ``load_segment`` returns one span as ``(channels, samples)`` (or ``(samples,)``
    for mono) already at ``FINGERPRINT_SAMPLE_RATE``.
    """
    rate = FINGERPRINT_SAMPLE_RATE
    segment_samples = int(round(FINGERPRINT_SEGMENT_S * rate))
    out: np.ndarray | None = None
    filled = 0
    start = 0.0
    while start < total_s:
        end = min(start + FINGERPRINT_SEGMENT_S, total_s)
        offset = max(0.0, start - FINGERPRINT_SEGMENT_MARGIN_S)
        span = load_segment(offset, min(total_s, end + FINGERPRINT_SEGMENT_MARGIN_S) - offset)
        lead = int(round((start - offset) * rate))
        body = span[..., lead:] if end >= total_s else span[..., lead:lead + segment_samples]
        if out is None:
            # One second of slack: the probed duration can round either way.
            out = np.empty((*body.shape[:-1], int(total_s * rate) + rate), dtype=np.float32)
        count = min(body.shape[-1], out.shape[-1] - filled)
        out[..., filled:filled + count] = body[..., :count]
        filled += count
        start = end
    if out is None:
        raise ValueError("whole-track load produced no audio")
    return out[..., :filled]


def probe_duration_s(audio_path: Path) -> float | None:
    """Track length from the container header, without decoding; None if unreadable."""
    from auralis.io.formats import FFMPEG_FORMATS

    try:
        if audio_path.suffix.lower() in FFMPEG_FORMATS:
            from auralis.io.loaders.ffmpeg_probe import _probe_audio

            duration = _probe_audio(audio_path).get('duration')
            return float(duration) if duration else None
        import soundfile as sf

        with sf.SoundFile(str(audio_path)) as handle:
            return float(handle.frames) / float(handle.samplerate)
    except Exception:
        return None


def _load_whole_file(audio_path: Path, total_s: float) -> np.ndarray:
    """Segmented whole-track decode through the format's own loader."""
    from auralis.io.formats import FFMPEG_FORMATS

    if audio_path.suffix.lower() in FFMPEG_FORMATS:
        with tempfile.TemporaryDirectory() as tmp:
            return join_segments(total_s, lambda off, dur: _decode_window(audio_path, tmp, off, dur))

    import librosa

    def _segment(offset_s: float, duration_s: float) -> np.ndarray:
        span, _ = librosa.load(
            str(audio_path), sr=FINGERPRINT_SAMPLE_RATE, mono=False,
            offset=offset_s, duration=duration_s,
        )
        return stereo_window(span)

    return join_segments(total_s, _segment)


def load_track_audio(
    audio_path: Path, audio: np.ndarray | None = None, sr: int | None = None
) -> WindowSet:
    """``(audio, rate, probes)`` to analyse, from the file or from a pre-loaded buffer.

    A track within ``FINGERPRINT_FULL_TRACK_MAX_S`` comes back whole with no probes
    (the analyzer's own loudness and crest stand). Anything else gets the body
    window plus two 30 s probes, whose median corrects a single window's bias (#4595).
    """
    if audio is not None and sr is not None:
        if not analyses_whole_track(audio.shape[-1] / sr):
            return crop_preloaded_windows(audio, sr)
        whole = stereo_window(audio)
        if sr != FINGERPRINT_SAMPLE_RATE:
            whole = _resample_channels(whole, sr, FINGERPRINT_SAMPLE_RATE)
        return whole, FINGERPRINT_SAMPLE_RATE, []

    total_s = probe_duration_s(audio_path)
    if total_s is not None and analyses_whole_track(total_s):
        return _load_whole_file(audio_path, total_s), FINGERPRINT_SAMPLE_RATE, []

    from auralis.io.formats import FFMPEG_FORMATS

    if audio_path.suffix.lower() in FFMPEG_FORMATS:
        # libsndfile can't decode AAC/MP3/etc -- load via ffmpeg.
        return load_ffmpeg_windows(audio_path)
    return load_librosa_windows(audio_path)
