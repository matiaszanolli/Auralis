"""
Where the body window starts, for callers that decode it themselves (#6143)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``windowed_loading`` places the 25D fingerprint's body window from a header-only duration
probe. ``MasteringFingerprint`` decodes its own window, and must use the same placement:
a window from t=0 biases loudness by up to 9 dB on ambient intros (#4595).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path

from .windows import FINGERPRINT_BODY_POSITION, FINGERPRINT_BODY_WINDOW_S, window_offset_s


def _probe_duration_s(audio_path: Path) -> float | None:
    """Total duration from the container header, without decoding; ``None`` if unreadable."""
    from auralis.io.formats import FFMPEG_FORMATS

    try:
        if audio_path.suffix.lower() in FFMPEG_FORMATS:
            from auralis.io.loaders.ffmpeg_probe import _probe_audio
            return _probe_audio(audio_path).get('duration')
        import soundfile as sf
        with sf.SoundFile(str(audio_path)) as f:
            return float(f.frames / f.samplerate)
    except Exception:
        return None


def body_window_offset_s(audio_path: Path, window_s: float = FINGERPRINT_BODY_WINDOW_S) -> float:
    """Start of the body window for *audio_path*.

    Falls back to 0.0 (the head of the file) when the duration cannot be probed, as
    ``load_*_windows`` do.
    """
    total_s = _probe_duration_s(audio_path)
    if not total_s or total_s <= 0:
        return 0.0
    return window_offset_s(FINGERPRINT_BODY_POSITION, total_s, window_s)
