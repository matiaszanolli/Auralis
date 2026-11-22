"""
Converted WAV Registry
~~~~~~~~~~~~~~~~~~~~~~

One-shot conversion of a track libsndfile cannot seek into a temp WAV, shared
by every holder of the same file.

Why this exists (#4737): the chunk loader used to decode the WHOLE file on every
chunk it read from an `.m4a`/`.aac`/`.wma` (libsndfile cannot open them at all) -
roughly 60 full-track FFmpeg decodes for a 10-minute track, each spawning a
subprocess and writing and re-reading a temp WAV.

Once per file, not once per stream (#5402)
------------------------------------------
Memoising on the `SeekableSource` instance made the decode once per
*processor* - but every play, seek and resume builds a fresh processor, and
#5253 closes the old one (deleting its WAV) before the next is built. Each seek
of an m4a therefore paid a full decode again. Conversions now live in
`converted_wavs`, shared by every holder of the same file and keyed on its
signature so an edited file is never served stale. The most recently released
conversion is kept for the next holder - that is what a seek is - and dropped
when a different file converts or the app shuts down.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import shutil
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from auralis.io.audio_probe import get_audio_info
from auralis.io.formats import FFMPEG_FORMATS
from auralis.io.loaders.ffmpeg_space import require_decode_space
from config.limits import SEEKABLE_TEMP_PREFIX
from core.file_signature import FileSignatureService

logger = logging.getLogger(__name__)

ConversionKey = tuple[str, str]

# Released conversions kept on disk for the next holder of the same file. One
# covers the seek case (the old stream releases just before the new one
# acquires) while bounding the disk a decoded track holds - which is RAM where
# the temp root is a tmpfs.
IDLE_CONVERSIONS_RETAINED = 1


def _require_free_space(filepath: str, temp_dir: str) -> None:
    """Refuse a conversion whose float32 WAV cannot fit in the temp root, before decoding it (#6166).

    Several long tracks started in quick succession are refused instead of exhausting a tmpfs (and
    the RAM behind it). The FFmpeg path gets the same check inside decode_to_wav; this covers the
    libsndfile one. See auralis.io.loaders.ffmpeg_space.
    """
    meta = get_audio_info(filepath)
    duration, rate, channels = meta.get("duration_seconds"), meta.get("sample_rate"), meta.get("channels")
    if duration and rate and channels:  # an unreadable header is reported by the decode itself
        require_decode_space(temp_dir, duration, rate, channels)


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
        wav_path = str(Path(temp_dir) / "seekable.wav")
        if Path(filepath).suffix.lower() in FFMPEG_FORMATS:
            # FFmpeg writes the float32 WAV itself and it is never read into memory: a 6 GiB decode
            # used to be held as an array AND written out, and the temp root is often a tmpfs (#6166).
            from auralis.io.loaders import decode_to_wav
            from auralis.io.wav_sanitize import sanitize_wav_in_place

            decoded = decode_to_wav(Path(filepath), temp_dir)
            sanitize_wav_in_place(decoded)
            decoded.replace(wav_path)
        else:
            _require_free_space(filepath, temp_dir)
            audio, sample_rate = load_audio(filepath, "audio", temp_dir)
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
    # counted at next startup (config/startup/tempfiles.py).
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
                        "libsndfile cannot read all of %s — converting to a temp WAV "
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


def _release_late_acquire(registry: ConvertedWavRegistry, task: "asyncio.Future[tuple[ConversionKey, str]]") -> None:
    """Give back a hold whose awaiting coroutine was cancelled before it arrived."""
    if task.cancelled() or task.exception() is not None:
        return  # acquire releases its own hold when it fails
    key, _path = task.result()
    # release() can delete a full decoded WAV, so it stays off the event loop.
    asyncio.get_running_loop().run_in_executor(None, registry.release, key)


async def acquire_conversion(
    registry: ConvertedWavRegistry, filepath: str, *, prefix: str = SEEKABLE_TEMP_PREFIX
) -> tuple[ConversionKey, str]:
    """`registry.acquire` off the event loop, without leaking the hold on cancel (#5946).

    A bare ``await asyncio.to_thread(registry.acquire, ...)`` cancelled mid-decode
    leaves the worker thread running: it finishes the acquire, takes the hold and
    returns the key to nobody, so the conversion's refs never reach zero and the
    full-track WAV is never evicted. Here the thread is shielded from the
    cancellation and a done-callback releases whatever it eventually returns.
    The caller still owns exactly one ``release(key)`` when this returns normally.
    """
    task = asyncio.ensure_future(asyncio.to_thread(registry.acquire, filepath, prefix=prefix))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        task.add_done_callback(lambda t: _release_late_acquire(registry, t))
        raise
