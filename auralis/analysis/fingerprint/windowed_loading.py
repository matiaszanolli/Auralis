"""
Window loading for the windowed fingerprint (split from windowed_compute.py,
#5838): the three ways to get the body window and the two 30 s probes -- an
FFmpeg bounded decode, a libsndfile/librosa seek, and a crop of a pre-loaded
buffer. All three produce the same windows at ``FINGERPRINT_SAMPLE_RATE``.

Lazy imports of librosa, soundfile and the FFmpeg loaders are deliberate: they
are heavy, and tests patch them at their home modules.
"""

import logging
import tempfile
from pathlib import Path

import numpy as np

from .windows import (
    FINGERPRINT_BODY_POSITION,
    FINGERPRINT_BODY_WINDOW_S,
    FINGERPRINT_PROBE_POSITIONS,
    FINGERPRINT_PROBE_WINDOW_S,
    FINGERPRINT_SAMPLE_RATE,
    window_offset_s,
)

logger = logging.getLogger(__name__)

# Seconds decoded ahead of a bounded FFmpeg window and then trimmed off, so the
# samples handed to the analyzer are identical to the same span of a full decode
# (#5110). 0.5 s was measured as sufficient for bit-exact agreement on MP3;
# 1.0 s carries margin for other codecs at negligible cost against a 90 s window.
_SEEK_PREROLL_S = 1.0

WindowSet = tuple[np.ndarray, int, list[np.ndarray]]  # (body audio, its rate, probe windows)


def _resample_channels(win: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample a (samples,) or (channels, samples) float buffer to ``target_sr``."""
    import librosa

    if win.ndim == 2:
        return np.stack([
            librosa.resample(win[ch].astype(np.float32), orig_sr=orig_sr, target_sr=target_sr)
            for ch in range(win.shape[0])
        ])
    return librosa.resample(win.astype(np.float32), orig_sr=orig_sr, target_sr=target_sr)


def _decode_window(
    audio_path: Path, tmp_dir: str, offset_s: float | None, dur_s: float | None
) -> np.ndarray:
    """Decode one bounded span and return it as (channels, samples).

    Decodes _SEEK_PREROLL_S ahead of the window and trims it off by exact
    sample count. A bounded MP3/AAC decode starting cold at the seek point
    differs from the same span of a full decode -- the codec needs a few
    frames to converge (bit reservoir, filterbank state). Measured on a real
    MP3, a zero-pre-roll window drifted up to 1.1% on crest_db and ~1% on
    transient_density; with 0.5 s of pre-roll the samples are bit-identical to
    the full-decode span.

    That is what keeps this a pure performance change: stored fingerprints
    stay comparable with newly computed ones, so no FINGERPRINT_ALGORITHM_VERSION
    bump (and no library-wide re-fingerprint) is required.
    """
    from auralis.io.loaders import load_with_ffmpeg

    preroll = 0.0
    if offset_s is not None and offset_s > 0:
        preroll = min(_SEEK_PREROLL_S, offset_s)
        offset_s = offset_s - preroll
        if dur_s is not None:
            dur_s = dur_s + preroll

    win, win_sr = load_with_ffmpeg(audio_path, tmp_dir, offset=offset_s, duration=dur_s)
    # Trim at the NATIVE rate, before resampling -- resampling would make the
    # sample count no longer map to preroll.
    if preroll > 0:
        win = win[int(round(preroll * win_sr)):]
    if win.ndim == 2:
        win = win.T
    if win_sr != FINGERPRINT_SAMPLE_RATE:
        win = _resample_channels(win, win_sr, FINGERPRINT_SAMPLE_RATE)
    return win


def load_ffmpeg_windows(audio_path: Path) -> WindowSet:
    """Windows for formats libsndfile can't decode (AAC/MP3/...), via FFmpeg.

    #5110: decode only the windows actually analysed. This branch used to
    decode the ENTIRE file, resample the ENTIRE buffer, and only then crop to
    150 s -- the opposite of the two sibling branches. For a 2-hour podcast
    that was up to ~50x the necessary CPU with a peak footprint in the GB
    range, multiplied by the extraction queue's concurrency.
    """
    from auralis.io.loaders.ffmpeg_probe import _probe_audio

    body_s, probe_s = FINGERPRINT_BODY_WINDOW_S, FINGERPRINT_PROBE_WINDOW_S
    # Duration from ffprobe rather than from a decoded buffer -- the window
    # offsets need it *before* anything is decoded, and the soundfile probe
    # cannot open these containers.
    total_s = _probe_audio(audio_path).get('duration')

    with tempfile.TemporaryDirectory() as tmp:
        if not total_s or total_s <= 0:
            # ffprobe gave no duration (rare: true-VBR without a header). Fall
            # back to decoding from the start and bounding by length -- still
            # avoids the full file.
            logger.debug(
                f"No probed duration for {audio_path.name}; "
                f"decoding a bounded head window instead"
            )
            audio = _decode_window(audio_path, tmp, None, body_s)
            probes: list[np.ndarray] = []
        else:
            body_offset = window_offset_s(FINGERPRINT_BODY_POSITION, total_s, body_s)
            audio = _decode_window(audio_path, tmp, body_offset, body_s)
            # Lightweight LUFS/crest probes at 25 % and 75 %
            probes = [
                _decode_window(audio_path, tmp, window_offset_s(frac, total_s, probe_s), probe_s)
                for frac in FINGERPRINT_PROBE_POSITIONS
            ]

    # Rounding safety at the target rate (works for 1-D and 2-D).
    audio = audio[..., :int(FINGERPRINT_SAMPLE_RATE * body_s)]
    return audio, FINGERPRINT_SAMPLE_RATE, probes


def load_librosa_windows(audio_path: Path) -> WindowSet:
    """Windows via librosa's seek (offset/duration), after a header-only duration read."""
    import librosa

    body_s, probe_s = FINGERPRINT_BODY_WINDOW_S, FINGERPRINT_PROBE_WINDOW_S
    # Get total duration without loading audio
    try:
        import soundfile as _sf
        with _sf.SoundFile(str(audio_path)) as _f:
            total_s: float | None = _f.frames / _f.samplerate
    except Exception:
        total_s = None

    # Body window: centred on 50 % of track duration
    if total_s is not None:
        body_offset = window_offset_s(FINGERPRINT_BODY_POSITION, total_s, body_s)
    else:
        body_offset = 0.0

    audio, loaded_sr = librosa.load(
        str(audio_path), sr=FINGERPRINT_SAMPLE_RATE, mono=False,
        offset=body_offset, duration=body_s,
    )
    # Lightweight probes: mono is sufficient for LUFS/crest estimation
    probes: list[np.ndarray] = []
    if total_s is not None:
        for frac in FINGERPRINT_PROBE_POSITIONS:
            poff = window_offset_s(frac, total_s, probe_s)
            try:
                pa, _ = librosa.load(
                    str(audio_path), sr=FINGERPRINT_SAMPLE_RATE, mono=True,
                    offset=poff, duration=probe_s,
                )
                probes.append(pa)
            except Exception:
                pass
    return audio, int(loaded_sr), probes


def crop_preloaded_windows(raw_audio: np.ndarray, orig_sr: int) -> WindowSet:
    """Body + probe windows cropped from an already-decoded buffer.

    #4994: share the exact body+probe windowing strategy the fresh-load
    branches use, instead of the less-accurate start-crop + no correction this
    branch used to do -- the branches disagreeing defeated #4595's "cannot
    drift again" guarantee for any caller that passes pre-loaded audio.
    """
    body_s, probe_s = FINGERPRINT_BODY_WINDOW_S, FINGERPRINT_PROBE_WINDOW_S
    total_s = raw_audio.shape[-1] / orig_sr

    def _crop_and_resample(offset_s: float, dur_s: float) -> np.ndarray:
        """Crop [offset_s, offset_s + dur_s) at the ORIGINAL sample rate, then
        resample to the target rate. Crop-before-resample avoids an
        O(duration) resample + full-duration float32 allocation on a
        multi-hour buffer -- the same #4116/#4499 OOM/latency class the old
        start-crop-only code avoided."""
        start = int(orig_sr * offset_s)
        end = start + int(orig_sr * dur_s)
        cropped = raw_audio[..., start:end]
        if orig_sr == FINGERPRINT_SAMPLE_RATE:
            return cropped
        return _resample_channels(cropped, orig_sr, FINGERPRINT_SAMPLE_RATE)

    # Body window: centred on 50 % of duration, same as fresh-load.
    audio = _crop_and_resample(window_offset_s(FINGERPRINT_BODY_POSITION, total_s, body_s), body_s)
    # Rounding safety at the target rate (works for 1-D and 2-D).
    audio = audio[..., :int(FINGERPRINT_SAMPLE_RATE * body_s)]
    # Lightweight LUFS/crest probes at 25 % / 75 %, cropped from the same
    # pre-loaded buffer.
    probes = [
        _crop_and_resample(window_offset_s(frac, total_s, probe_s), probe_s)
        for frac in FINGERPRINT_PROBE_POSITIONS
    ]
    return audio, FINGERPRINT_SAMPLE_RATE, probes
