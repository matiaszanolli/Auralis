"""
Seekable Audio Probe
~~~~~~~~~~~~~~~~~~~~

Decides whether libsndfile can read a track in place (`can_seek_natively`), so
`SeekableSource` converts only the files that genuinely need it.

Trigger on capability, not on extension (#4737): libsndfile 1.2.x opens MP3, OGG
and FLAC natively although `FFMPEG_FORMATS` lists MP3 and OGG, so converting on
suffix would ADD a full decode for `.mp3`, the dominant library format. The
decision is made by actually trying to open the file.

Opening is not the same as reading all of it (#6314). For an MP3 with no Xing
header libsndfile opens fine but sizes the file wrongly and silently stops
short. For the FFmpeg formats, `can_seek_natively` therefore also requires
libsndfile's length to match ffprobe's; only a disagreement pays the decode.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import functools
from pathlib import Path

from auralis.io.audio_probe import get_audio_info
from auralis.io.formats import FFMPEG_FORMATS
from core.file_signature import FileSignatureService

# libsndfile sizes an MP3 that has no Xing/VBRI header (header-less VBR, files
# joined with `cat`) from its first frame, then reads and seeks only that far
# while FFmpeg decodes the whole file (#6314). An FFmpeg-decoded format is only
# read in place when libsndfile's length agrees with ffprobe's. ffprobe's own
# estimate for such a file is off by single-digit percent, libsndfile's by 20%+,
# and healthy files agree to a few frames — so this tolerance separates them.
LENGTH_AGREEMENT_TOLERANCE_S = 0.5
LENGTH_AGREEMENT_TOLERANCE_FRACTION = 0.01


@functools.lru_cache(maxsize=64)
def _ffprobe_duration(filepath: str, signature: str) -> float:
    """ffprobe's duration for this exact file content; raises when it has none.

    Keyed on the signature so an edited file re-probes, and a failure is raised
    (never cached) so a transient ffprobe error is retried next time.
    """
    meta = get_audio_info(filepath)
    duration = meta.get("duration_seconds")
    if meta.get("error") or not duration or duration <= 0:
        raise LookupError(f"no ffprobe duration for {Path(filepath).name}")
    return float(duration)


def _length_agrees_with_ffmpeg(filepath: str, libsndfile_duration: float) -> bool:
    """False when libsndfile reads materially less (or more) than FFmpeg decodes."""
    if Path(filepath).suffix.lower() not in FFMPEG_FORMATS:
        return True  # libsndfile is the reference decoder for these
    try:
        reference = _ffprobe_duration(filepath, FileSignatureService.generate(filepath))
    except Exception:
        return True  # nothing to compare against: keep the in-place read
    tolerance = max(LENGTH_AGREEMENT_TOLERANCE_S, LENGTH_AGREEMENT_TOLERANCE_FRACTION * reference)
    return abs(libsndfile_duration - reference) <= tolerance


def can_seek_natively(filepath: str) -> bool:
    """True if libsndfile can open `filepath` and reads all of it (so can seek in it).

    Opens and immediately closes — it reads the header only, not the audio, so
    this is cheap enough to do once per track. For a format FFmpeg also decodes
    (MP3/OGG/Opus), libsndfile opening the file is not enough: its length must
    match ffprobe's, or the tail would be silence (#6314).
    """
    try:
        import soundfile as sf

        with sf.SoundFile(filepath) as handle:
            duration = handle.frames / handle.samplerate if handle.samplerate else 0.0
    except Exception:
        return False
    return _length_agrees_with_ffmpeg(filepath, duration)
