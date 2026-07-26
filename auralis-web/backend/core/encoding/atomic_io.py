"""Crash-safe writes and validity checks for cached audio files (#4576).

Every producer of a cached WAV used to write straight to the final,
content-addressed cache filename, and the cache-hit path gated on
``Path.exists()`` alone. An unclean exit mid-write — Electron quit, ``kill -9``,
OOM, power loss — left a truncated file at exactly the key the cache looks up,
and served it as a hit forever. Cache keys embed CACHE_VERSION, track id, file
signature, preset and intensity, so the poisoned entry was stable across
restarts and recovery needed a manual cache clear. Nothing logged, because the
file *was* there.

Two halves, both needed:

  * :func:`atomic_write_bytes` / :func:`atomic_save_audio` stage into a
    sibling temp file and ``os.replace()`` onto the final name. ``os.replace``
    is atomic within a filesystem, so a reader sees either the complete file or
    no file — never a prefix.
  * :func:`is_wav_complete` gates the hit path, so entries poisoned *before*
    this fix are evicted and regenerated rather than served.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
import os
import struct
import tempfile
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# Marker embedded in the name of an in-progress write.
#
# The staged file keeps the destination's real extension (".part.wav", not
# ".part"): auralis.io.saver.save delegates to soundfile, which infers the
# container format from the extension and raises on an unknown one. It is also
# written as a dotfile, so the `track_*.wav` cleanup patterns in
# WAVEncoder.cleanup_track_chunks cannot match it. `is_partial_path` is the
# single predicate for "this is staging, not a cache entry".
PARTIAL_SUFFIX = ".part"

# A canonical RIFF/WAVE header is 44 bytes; anything at or below that carries no
# audio frames and is treated as truncated.
_MIN_WAV_BYTES = 44


def _stage_and_replace(final_path: Path, write: Callable[[Path], None]) -> None:
    """Run *write* against a temp sibling, then atomically move it into place.

    The temp file lives in the destination directory so ``os.replace`` stays on
    one filesystem (a cross-device rename is not atomic and raises). On any
    failure the partial file is removed and the exception propagates, leaving
    nothing at the canonical path.
    """
    final_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(final_path.parent),
        prefix=f".{final_path.name}.",
        suffix=f"{PARTIAL_SUFFIX}{final_path.suffix}",
    )
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        write(tmp_path)
        # Flush the staged bytes to disk before publishing the name, so a power
        # loss right after the rename cannot expose an empty file.
        with open(tmp_path, "rb") as handle:
            os.fsync(handle.fileno())
        os.replace(tmp_path, final_path)
    except BaseException:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as cleanup_error:  # pragma: no cover - best effort
            logger.debug(f"Could not remove staged file {tmp_path}: {cleanup_error}")
        raise


def atomic_write_bytes(final_path: Path, data: bytes) -> None:
    """Write *data* to *final_path* atomically."""
    def _write(tmp: Path) -> None:
        tmp.write_bytes(data)

    _stage_and_replace(final_path, _write)


def atomic_save_audio(
    final_path: Path,
    save: Callable[[str], None],
) -> None:
    """Run a ``save_audio``-style callable against a staged path, then publish.

    *save* receives the temp path as a string and must write the whole file.
    Kept callable-based so this module does not need to know the encoder's
    signature (subtype, sample rate, backend), which differs per call site.
    """
    _stage_and_replace(final_path, lambda tmp: save(str(tmp)))


def is_partial_path(path: Path) -> bool:
    """True if *path* is a staging file rather than a published cache entry."""
    return PARTIAL_SUFFIX in path.name


def is_wav_complete(path: Path) -> bool:
    """Return True if *path* looks like a complete RIFF/WAVE file.

    Compares the size declared in the RIFF header against the actual file size.
    This is the cheap check that catches the failure this module exists to
    prevent — a truncated write — without decoding the audio. It is deliberately
    tolerant: a file whose declared size is *smaller* than the real size (extra
    trailing chunks) is accepted, since only truncation is the poison case.

    Any unreadable/short/non-RIFF file returns False so the caller treats it as
    a miss and regenerates.
    """
    try:
        size = path.stat().st_size
        if size < _MIN_WAV_BYTES:
            return False

        with open(path, "rb") as handle:
            header = handle.read(12)

        if len(header) < 12 or header[0:4] != b"RIFF" or header[8:12] != b"WAVE":
            return False

        # RIFF size counts everything after the 8-byte 'RIFF<size>' prefix.
        (riff_size,) = struct.unpack("<I", header[4:8])
        declared_total = int(riff_size) + 8

        return bool(size >= declared_total)
    except (OSError, struct.error) as e:
        logger.debug(f"WAV completeness check failed for {path}: {e}")
        return False


def cleanup_partial_files(directory: Path) -> int:
    """Delete leftover ``*.part`` staging files from interrupted writes.

    Returns the number removed. Best-effort: per-file errors are logged, never
    raised.
    """
    removed = 0
    try:
        for candidate in directory.glob(f"*{PARTIAL_SUFFIX}*"):
            try:
                candidate.unlink()
                removed += 1
            except OSError as e:  # pragma: no cover - best effort
                logger.debug(f"Could not remove stale partial {candidate}: {e}")
    except OSError as e:  # pragma: no cover - directory may not exist yet
        logger.debug(f"Partial-file sweep skipped for {directory}: {e}")

    if removed:
        logger.info(f"Removed {removed} stale partial write(s) from {directory}")
    return removed
