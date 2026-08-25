"""
Seekable Audio Source
~~~~~~~~~~~~~~~~~~~~~

Gives chunk readers a path that libsndfile can *seek*, converting the source
exactly once when it cannot.

Why this exists (#4737): `ChunkOperations.load_chunk_from_file` opened the raw
track path with `sf.SoundFile(...)` and, on failure, fell back to decoding the
WHOLE file via `load_audio()` and slicing out the 25 s it wanted. libsndfile
cannot open `.m4a`/`.aac`/`.wma` at all, so for those formats that fallback ran
on *every chunk* with no memoisation — roughly 60 full-track FFmpeg decodes for
a 10-minute track, each spawning a subprocess, writing and re-reading a temp
WAV, and allocating a large float transient. #4497 fixed the same amplification
in the metadata probe; the chunk-loading path kept it.

Trigger on capability, not on extension
---------------------------------------
The obvious guard — "convert if the suffix is in `FFMPEG_FORMATS`" — is wrong
here. That set is `{.aac, .m4a, .mp3, .ogg, .opus, .wma}`, but libsndfile 1.2.x
opens MP3, OGG and FLAC natively. Converting on suffix would therefore ADD a
full decode for `.mp3` — the dominant library format — where today there is
none. So the decision is made by actually trying to open the file: formats
libsndfile handles are used in place, and only a genuine open failure triggers
the one-time conversion.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from config.limits import SEEKABLE_TEMP_PREFIX

logger = logging.getLogger(__name__)


def can_seek_natively(filepath: str) -> bool:
    """True if libsndfile can open `filepath` (and therefore seek within it).

    Opens and immediately closes — it reads the header only, not the audio, so
    this is cheap enough to do once per track.
    """
    try:
        import soundfile as sf

        with sf.SoundFile(filepath):
            return True
    except Exception:
        return False


def convert_to_temp_wav(filepath: str, *, prefix: str = SEEKABLE_TEMP_PREFIX) -> tuple[str, str]:
    """Decode `filepath` once and write it to a temp WAV that libsndfile can seek.

    Returns ``(temp_dir, wav_path)``. The caller owns ``temp_dir`` and must
    remove it — return the directory, not just the file, because the directory
    exists from `mkdtemp` onward while the WAV only appears after a successful
    write, so a failure partway leaves the dir behind (the #4365 lesson from
    `stream_normal.py`).
    """
    import soundfile as sf

    from auralis.io.unified_loader import load_audio

    temp_dir = tempfile.mkdtemp(prefix=prefix)
    try:
        audio, sample_rate = load_audio(filepath, "audio", temp_dir)
        wav_path = str(Path(temp_dir) / "seekable.wav")
        sf.write(wav_path, audio, sample_rate, format="WAV", subtype="FLOAT")
        return temp_dir, wav_path
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


class SeekableSource:
    """Resolves a track path to something seekable, at most once per instance.

    Owns any temp directory it creates, so the holder must call `close()` — see
    `ChunkedAudioProcessor.close()`, which is invoked when the worker evicts a
    processor from its LRU.
    """

    def __init__(self, filepath: str) -> None:
        self._filepath = filepath
        self._resolved: str | None = None
        self._temp_dir: str | None = None

    @property
    def converted(self) -> bool:
        """True once a temp WAV has actually been produced (tests assert on this)."""
        return self._temp_dir is not None

    def resolve(self) -> str:
        """Return a path libsndfile can seek, converting once if it must.

        Memoised: the probe and any conversion happen on the first call only, so
        N chunk reads cost at most one decode rather than N.
        """
        if self._resolved is not None:
            return self._resolved

        if can_seek_natively(self._filepath):
            self._resolved = self._filepath
            return self._resolved

        logger.info(
            "libsndfile cannot open %s — converting once to a temp WAV for "
            "chunk seeking (#4737)",
            self._filepath,
        )
        self._temp_dir, wav_path = convert_to_temp_wav(self._filepath)
        self._resolved = wav_path
        return self._resolved

    def close(self) -> None:
        """Remove the temp directory, if one was created. Safe to call twice."""
        if self._temp_dir is None:
            return
        temp_dir, self._temp_dir = self._temp_dir, None
        self._resolved = None
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as exc:  # pragma: no cover - rmtree already swallows
            logger.warning("Seekable-source cleanup failed for %s: %s", temp_dir, exc)

    def __enter__(self) -> SeekableSource:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
