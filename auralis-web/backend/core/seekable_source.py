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

Once per file, not once per stream (#5402)
------------------------------------------
Memoising on the `SeekableSource` instance made the decode once per
*processor* — but every play, seek and resume builds a fresh processor, and
#5253 closes the old one (deleting its WAV) before the next is built. Each seek
of an m4a therefore paid a full decode again. Conversions now live in
`converted_wavs`, shared by every holder of the same file and keyed on its
signature so an edited file is never served stale. The most recently released
conversion is kept for the next holder — that is what a seek is — and dropped
when a different file converts or the app shuts down.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import shutil
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from config.limits import SEEKABLE_TEMP_PREFIX
from core.file_signature import FileSignatureService

logger = logging.getLogger(__name__)

ConversionKey = tuple[str, str]

# Released conversions kept on disk for the next holder of the same file. One
# covers the seek case (the old stream releases just before the new one
# acquires) while bounding the disk a decoded track holds — which is RAM where
# the temp root is a tmpfs.
IDLE_CONVERSIONS_RETAINED = 1


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


@dataclass
class _Conversion:
    refs: int = 0
    temp_dir: str | None = None
    wav_path: str | None = None
    # Held while decoding, so a concurrent holder of the same file waits for
    # this conversion instead of starting its own.
    build_lock: threading.Lock = field(default_factory=threading.Lock)


def _remove_temp_dirs(temp_dirs: list[str]) -> None:
    # Log instead of swallowing (#3877): an EBUSY/EACCES holdout is swept and
    # counted at next startup (config/startup.py).
    for temp_dir in temp_dirs:
        shutil.rmtree(
            temp_dir,
            onexc=lambda _func, path, exc: logger.warning(
                "Failed to remove seekable temp file %s: %s", path, exc
            ),
        )


class ConvertedWavRegistry:
    """Refcounted temp-WAV conversions shared across processors and streams (#5402).

    `acquire` returns a seekable WAV for a file, decoding only if no conversion
    of that exact file content exists; `release` gives it back. A conversion
    with no holders is kept idle (at most `max_idle` of them, oldest dropped
    first) so the next stream of the same track reuses it. Blocking — call from
    a worker thread, never the event loop.
    """

    def __init__(self, max_idle: int = IDLE_CONVERSIONS_RETAINED) -> None:
        self._lock = threading.Lock()
        self._conversions: dict[ConversionKey, _Conversion] = {}
        self._idle: OrderedDict[ConversionKey, None] = OrderedDict()
        self._max_idle = max_idle

    def acquire(self, filepath: str, *, prefix: str = SEEKABLE_TEMP_PREFIX) -> tuple[ConversionKey, str]:
        """Return ``(key, wav_path)``; the caller must `release(key)` exactly once.

        `prefix` only names the directory when this call is the one that
        converts — a holder reusing an existing conversion gets it as is.
        """
        key = (filepath, FileSignatureService.generate(filepath))
        stale: list[str] = []
        with self._lock:
            conversion = self._conversions.get(key)
            if conversion is None:
                conversion = self._conversions[key] = _Conversion()
                # Make room before decoding another file, so a new track does
                # not sit on disk alongside the previous track's idle WAV.
                stale = self._evict_locked(self._max_idle - 1)
            conversion.refs += 1
            self._idle.pop(key, None)
        _remove_temp_dirs(stale)

        try:
            with conversion.build_lock:
                if conversion.wav_path is None:
                    logger.info(
                        "libsndfile cannot open %s — converting to a temp WAV "
                        "shared by every stream of this file (#4737/#5402)",
                        Path(filepath).name,
                    )
                    conversion.temp_dir, conversion.wav_path = convert_to_temp_wav(
                        filepath, prefix=prefix
                    )
                else:
                    logger.debug("Reusing the converted temp WAV for %s", Path(filepath).name)
                return key, conversion.wav_path
        except BaseException:
            self.release(key)
            raise

    def release(self, key: ConversionKey) -> None:
        """Drop one hold; an unheld conversion goes idle, or away if over the cap."""
        stale: list[str] = []
        with self._lock:
            conversion = self._conversions.get(key)
            if conversion is None or conversion.refs <= 0:
                return
            conversion.refs -= 1
            if conversion.refs > 0:
                return
            if conversion.wav_path is None:
                # Its conversion failed; nothing on disk to keep.
                del self._conversions[key]
                return
            self._idle[key] = None
            stale = self._evict_locked(self._max_idle)
        _remove_temp_dirs(stale)

    def release_idle(self) -> None:
        """Delete every conversion no one holds; held ones are untouched."""
        with self._lock:
            stale = self._evict_locked(0)
        _remove_temp_dirs(stale)

    def shutdown(self) -> None:
        """Delete idle conversions and stop retaining any released later."""
        with self._lock:
            self._max_idle = 0
            stale = self._evict_locked(0)
        _remove_temp_dirs(stale)

    def _evict_locked(self, keep: int) -> list[str]:
        stale: list[str] = []
        while len(self._idle) > max(keep, 0):
            key, _ = self._idle.popitem(last=False)
            conversion = self._conversions.pop(key)
            if conversion.temp_dir is not None:
                stale.append(conversion.temp_dir)
        return stale


converted_wavs = ConvertedWavRegistry()


class SeekableSource:
    """Resolves a track path to something seekable, holding any conversion it uses.

    The holder must call `close()` — see `ChunkedAudioProcessor.close()`, which
    is invoked when the worker evicts a processor from its LRU and when a
    stream ends (#5253).
    """

    def __init__(self, filepath: str, registry: ConvertedWavRegistry | None = None) -> None:
        self._filepath = filepath
        self._registry = registry if registry is not None else converted_wavs
        self._resolved: str | None = None
        self._key: ConversionKey | None = None

    @property
    def converted(self) -> bool:
        """True once this source holds a temp WAV (tests assert on this)."""
        return self._key is not None

    def resolve(self) -> str:
        """Return a path libsndfile can seek, converting only if no one has yet.

        Memoised: the probe and any registry lookup happen on the first call
        only, so N chunk reads cost at most one decode rather than N.
        """
        if self._resolved is not None:
            return self._resolved

        if can_seek_natively(self._filepath):
            self._resolved = self._filepath
            return self._resolved

        self._key, self._resolved = self._registry.acquire(self._filepath)
        return self._resolved

    def close(self) -> None:
        """Release the conversion this source holds, if any. Safe to call twice."""
        if self._key is None:
            return
        key, self._key = self._key, None
        self._resolved = None
        self._registry.release(key)

    def __enter__(self) -> SeekableSource:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
