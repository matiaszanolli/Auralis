"""
Only the containers Auralis uses reach the bundled libsndfile (#6512)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The soundfile wheel bundles its own libsndfile (1.2.2 in soundfile 0.14.0, the latest release),
which has memory-safety CVEs in readers Auralis never needs (the IRCAM header, IMA-ADPCM WAV block
arithmetic). libsndfile chooses its reader from the file's *content*, and the ``format=`` hint is
ignored when reading anything but RAW, so the extension allowlist in ``formats.py`` did not stop a
hostile ``.wav`` with another header from reaching those readers, in the backend process.

``install()`` wraps ``soundfile.SoundFile``'s read-mode open, which ``sf.info``, ``sf.read`` and
``sf.blocks`` all go through, so every call site in ``auralis`` and the backend is covered without
naming each one. The file's header is read first; only WAV/RF64/BW64/RIFX, AIFF/AIFC, FLAC, AU, Ogg
and MPEG are handed on, and a WAV whose ``fmt`` chunk says IMA-ADPCM is refused (FFmpeg can still
decode it). A refusal raises ``UnsupportedAudioContainer``, a ``LibsndfileError``, so the callers'
existing libsndfile error handling covers it. Write mode is untouched.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import functools
import os
import struct
from typing import Any

import soundfile

_HEAD_BYTES = 64 * 1024  # enough to reach the fmt chunk of any real WAV
_IMA_ADPCM = 0x0011
_WAVE_FORMAT_EXTENSIBLE = 0xFFFE


class UnsupportedAudioContainer(soundfile.LibsndfileError):  # type: ignore[misc]  # soundfile is untyped
    """libsndfile was not allowed to open this file: its container is not one Auralis reads."""

    def __init__(self, reason: str) -> None:
        super().__init__(0, "")
        self.reason = reason

    @property
    def error_string(self) -> str:
        return self.reason


def _wav_format_tag(head: bytes) -> int | None:
    """The ``fmt `` chunk's format tag (the sub-format for WAVE_FORMAT_EXTENSIBLE), if in ``head``."""
    offset = 12
    while offset + 8 <= len(head):
        chunk_id, size = head[offset:offset + 4], struct.unpack_from("<I", head, offset + 4)[0]
        if chunk_id == b"fmt " and offset + 10 <= len(head):
            tag = struct.unpack_from("<H", head, offset + 8)[0]
            if tag == _WAVE_FORMAT_EXTENSIBLE and offset + 34 <= len(head):
                tag = struct.unpack_from("<H", head, offset + 32)[0]  # first 2 bytes of the sub-format GUID
            return int(tag)
        offset += 8 + size + (size & 1)
    return None


def refusal_reason(head: bytes) -> str | None:
    """Why libsndfile must not open a file starting with ``head``; None when it may."""
    if head[:4] in (b"RIFF", b"RF64", b"BW64", b"RIFX") and head[8:12] == b"WAVE":
        if head[:4] != b"RIFX" and _wav_format_tag(head) == _IMA_ADPCM:
            return "IMA-ADPCM WAV is not decoded in-process"
        return None
    if head[:4] == b"FORM" and head[8:12] in (b"AIFF", b"AIFC"):
        return None
    if head[:4] in (b"fLaC", b".snd", b"dns.", b"OggS") or head[:3] == b"ID3":
        return None
    if len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0:  # MPEG frame sync
        return None
    return "not an audio container Auralis reads"


def _read_head(file: Any) -> bytes | None:
    """The first bytes of a path or a seekable file object; None when the source cannot be peeked."""
    if isinstance(file, (str, bytes, os.PathLike)):
        try:
            with open(file, "rb") as handle:
                return handle.read(_HEAD_BYTES)
        except OSError:
            return None  # let libsndfile report the missing/unreadable file as before
    if all(hasattr(file, name) for name in ("read", "seek", "tell")):
        try:
            position = file.tell()
            head = file.read(_HEAD_BYTES)
            file.seek(position)
            return bytes(head)
        except (OSError, ValueError):
            return None
    return None  # an int descriptor or a non-seekable stream: nothing to peek without consuming it


def check_readable(file: Any) -> None:
    """Raise UnsupportedAudioContainer when ``file`` must not reach libsndfile's readers."""
    head = _read_head(file)
    if head is None:
        return
    reason = refusal_reason(head)
    if reason is not None:
        raise UnsupportedAudioContainer(reason)


def install() -> None:
    """Wrap soundfile.SoundFile's read-mode open with ``check_readable``. Idempotent."""
    original = soundfile.SoundFile.__init__
    if getattr(original, "_auralis_sndfile_guard", False):
        return

    @functools.wraps(original)
    def guarded_init(self: soundfile.SoundFile, file: Any, mode: str | None = "r", *args: Any, **kwargs: Any) -> None:
        reading = mode is None or not any(flag in mode for flag in "wx")
        if reading and str(kwargs.get("format") or "").upper() != "RAW":
            try:
                check_readable(file)
            except UnsupportedAudioContainer:
                self._file = None  # so SoundFile.__del__ -> close() finds nothing to close
                raise
        original(self, file, mode, *args, **kwargs)

    guarded_init._auralis_sndfile_guard = True  # type: ignore[attr-defined]
    soundfile.SoundFile.__init__ = guarded_init
