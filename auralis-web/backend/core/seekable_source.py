"""
Seekable Audio Source
~~~~~~~~~~~~~~~~~~~~~

Gives chunk readers a path that libsndfile can *seek*, converting the source
exactly once when it cannot.

Why this exists (#4737): the loader opened the raw track path with
`sf.SoundFile(...)` and, on failure, decoded the WHOLE file per chunk. A source
libsndfile can read in place is used as is (`seekable_probe.can_seek_natively`);
anything else is converted once to a temp WAV held in the shared
`converted_wavs` registry (`converted_wav_registry.py`, #5402) and released by
`close()`.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from pathlib import Path

from core.chunk_stream_state import ChunkCancelledError
from core.converted_wav_registry import ConversionKey, ConvertedWavRegistry, converted_wavs
from core.seekable_probe import can_seek_natively


class SeekableSourceClosed(ChunkCancelledError):
    """`resolve()` after or during `close()`: the stream is gone, so a cancel, not a failure (#6545)."""


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
        # resolve() converts in a worker thread while close() may run from the cancelled
        # stream's finally. close() is terminal: an in-flight resolve releases its late
        # acquire (#5946), and one that starts afterwards acquires nothing (#6545).
        self._state_lock = threading.Lock()
        self._closed = False

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
        if self._closed:
            raise SeekableSourceClosed(f"{Path(self._filepath).name} was closed")

        if can_seek_natively(self._filepath):
            self._resolved = self._filepath
            return self._resolved

        key, path = self._registry.acquire(self._filepath)
        superseded, redundant, path = self._install(key, path)
        if superseded:
            self._registry.release(key)
            raise SeekableSourceClosed(f"closed while converting {Path(self._filepath).name}")
        if redundant:
            self._registry.release(key)
        return path

    def _install(self, key: ConversionKey, path: str) -> tuple[bool, bool, str]:
        """Record a finished acquire as this source's hold.

        Returns ``(superseded, redundant, path)``: *superseded* once `close()`
        ran, *redundant* when a concurrent `resolve()` already
        installed its own hold (then *path* is theirs). Either way the caller
        releases *key*; otherwise it is now held by this source.
        """
        with self._state_lock:
            if self._closed:
                return True, False, path
            if self._key is not None and self._resolved is not None:
                return False, True, self._resolved
            self._key, self._resolved = key, path
            return False, False, path

    def close(self) -> None:
        """Release the conversion this source holds, if any. Safe to call twice.

        Terminal: a `resolve()` still converting releases its late `acquire`, and a
        later one raises `SeekableSourceClosed` instead of taking a hold nobody closes.
        """
        with self._state_lock:
            self._closed = True
            key, self._key = self._key, None
            self._resolved = None
        if key is not None:
            self._registry.release(key)

    def __enter__(self) -> SeekableSource:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
