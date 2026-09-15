"""
Startup Temp-File Reclamation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sweeps the chunk cache and temp files left behind by a previous run, without
touching anything a concurrently running backend still owns (#4713).

Split out of the former single-file config/startup.py (#5236).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import itertools
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path

from config.limits import (
    CHUNK_TEMP_DIRNAME,
    CHUNK_TEMP_OWNER_FILENAME,
    SEEKABLE_TEMP_PREFIX,
    STREAM_TEMP_PREFIX,
    create_secure_temp_dir,
    owning_pid_from_stream_temp_name,
)
from core.encoding.atomic_io import PARTIAL_MAX_AGE_SECONDS, cleanup_partial_files

logger = logging.getLogger(__name__)


def pid_is_alive(pid: int) -> bool:
    """True if a process with `pid` currently exists.

    Via psutil (already a hard dependency) rather than ``os.kill(pid, 0)``:
    on Windows CPython implements ``os.kill`` for non-CTRL signals by opening
    the process and calling ``TerminateProcess`` — a liveness *probe* written
    that way would kill the process it is asking about.

    A dead PID can be recycled, so a True answer is not proof the process is
    still *ours*. Callers must treat this as "do not touch", never as "this is
    definitely an Auralis instance".
    """
    try:
        import psutil
        return bool(psutil.pid_exists(pid))
    except Exception as e:  # psutil missing or platform refusal — fail safe
        logger.debug(f"PID liveness check unavailable for {pid}: {e}")
        return True


def reclaim_leftover_stream_temps(temp_root: Path, max_age_hours: float = 1.0) -> int:
    """Remove temp WAV dirs orphaned by interrupted compressed-format streams.

    stream_normal_audio writes a temp WAV under ``auralis_stream_<pid>_*`` and
    cleans it in its finally block, but a crash or a locked file (Windows AV /
    cloud-sync) can leave one behind (#3877). SeekableSource.convert_to_temp_wav
    writes an ``auralis_seekable_*`` one for any non-natively-seekable format
    (m4a/aac/wma, #4737) with the same failure mode — plus, until #5253, the
    seek/enhanced streaming entry points never called ``.close()`` at all, so
    every one of those leaked unconditionally, not just on a crash. Sweep both
    prefixes on startup so any leak surfaces in the log and stays bounded.

    #4713: this used to ``rmtree`` **every** ``auralis_stream_*`` match with no
    ownership or age check, so a second backend — a dev running ``main.py
    --dev`` on an alternate port while the packaged app is open, or a test
    pointed at the real temp root — deleted the *live* temp WAVs of the
    running instance, producing file-not-found errors mid-playback in the
    other process.

    Two guards, in order:

    - **PID tag (exact).** Directories written by #4713 or later (the
      ``auralis_stream_*`` producer only) carry the owning PID. A directory
      whose PID is still alive is skipped outright, no matter how old — a
      long audiobook or DJ set can legitimately hold one open for hours.
    - **Age (fallback).** A directory with no PID tag — either it predates the
      tagging, or it's an ``auralis_seekable_*`` directory, which has never
      carried one — has unknowable ownership; anything modified within
      `max_age_hours` is left alone on the assumption it may be live.

    Args:
        temp_root: Directory to sweep (the system temp root in production).
        max_age_hours: Age below which an *untagged* directory is left alone.

    Returns the number of leftover directories successfully reclaimed — skipped
    directories are excluded from the count, which is what the log line reports.
    """
    reclaimed = 0
    skipped = 0
    cutoff = time.time() - (max_age_hours * 3600)

    # #5253: auralis_seekable_* carries no PID tag at all (SeekableSource
    # never adopted the #4713 tagging scheme), so owning_pid_from_stream_temp_name
    # correctly returns None for it below and every match falls straight to
    # the age-based guard — the same safe default an untagged auralis_stream_*
    # directory already gets.
    leftovers = itertools.chain(
        temp_root.glob(f"{STREAM_TEMP_PREFIX}*"),
        temp_root.glob(f"{SEEKABLE_TEMP_PREFIX}*"),
    )
    for leftover in leftovers:
        owner_pid = owning_pid_from_stream_temp_name(leftover.name)

        if owner_pid is not None:
            if pid_is_alive(owner_pid):
                skipped += 1
                continue
        else:
            # Untagged: no ownership information, so fall back to age.
            try:
                if leftover.stat().st_mtime >= cutoff:
                    skipped += 1
                    continue
            except OSError:
                # Vanished between glob and stat — nothing to reclaim.
                continue

        try:
            shutil.rmtree(leftover)
            reclaimed += 1
        except Exception as e:
            logger.warning(
                f"Failed to remove leftover temp stream dir {leftover.name}: "
                f"{type(e).__name__}"
            )

    if reclaimed:
        logger.info(
            f"🧹 Reclaimed {reclaimed} leftover temp stream dir(s) from dead/aged owners"
        )
    if skipped:
        logger.debug(f"Left {skipped} in-use temp stream dir(s) alone (#4713)")
    return reclaimed


def claim_chunk_cache(chunk_dir: Path, owner_marker: Path) -> bool:
    """Decide whether this process may wipe the shared chunk cache, and claim it.

    #4713: the wipe was unconditional, so a second backend starting up deleted
    the cached chunks a running instance was still serving from.

    Deliberately an *ownership* check rather than the age heuristic used for
    stream temps. Making the wipe age-conditional would change the blast radius
    of #4666 (the on-disk chunk cache is not keyed on mastering targets) from
    intra-session to cross-session, because the start-of-run wipe is what
    currently keeps stale un-targeted chunks from outliving a restart. Keying on
    ownership instead preserves that exactly: a lone instance — every packaged
    Electron run — still finds no live foreign owner and still wipes on every
    start. Only the concurrent-instance case, which is the actual defect here,
    takes the new path.

    Returns True when the caller should wipe. Always (re)claims the marker so
    the *next* start sees this process as the owner.
    """
    may_wipe = True
    try:
        if owner_marker.exists():
            recorded = owner_marker.read_text().strip()
            if recorded.isdigit():
                other_pid = int(recorded)
                if other_pid != os.getpid() and pid_is_alive(other_pid):
                    logger.info(
                        f"🔒 Chunk cache is claimed by live PID {other_pid}; "
                        f"leaving {chunk_dir.name} alone (#4713)"
                    )
                    may_wipe = False
    except OSError as e:
        logger.debug(f"Could not read chunk-cache owner marker: {e}")

    try:
        owner_marker.parent.mkdir(parents=True, exist_ok=True)
        owner_marker.write_text(str(os.getpid()))
    except OSError as e:
        logger.debug(f"Could not claim chunk-cache owner marker: {e}")

    return may_wipe


def reclaim_stale_temp_entries(dir_path: Path, max_age_hours: float) -> int:
    """Age-sweep stale files/dirs directly under ``dir_path``.

    ``auralis_processing`` (rendered job outputs) and ``auralis_uploads``
    (uploaded inputs, up to 500MB each) are otherwise only reclaimed by
    ``ProcessingEngine.cleanup_old_jobs()``, which is driven off the
    in-memory ``self.jobs`` registry — empty after any crash or restart, so
    anything left on disk at that point becomes permanently unreferenced
    (#4762). Sweeping by mtime age instead of registry membership catches
    those too.

    Returns the number of entries successfully reclaimed.
    """
    if not dir_path.exists():
        return 0
    reclaimed = 0
    cutoff = time.time() - (max_age_hours * 3600)
    for entry in dir_path.iterdir():
        try:
            if entry.stat().st_mtime >= cutoff:
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            reclaimed += 1
        except Exception as e:
            logger.warning(
                f"Failed to remove stale temp entry {entry.name}: {type(e).__name__}"
            )
    if reclaimed:
        logger.info(f"🧹 Reclaimed {reclaimed} stale entr{'y' if reclaimed == 1 else 'ies'} from {dir_path.name}")
    return reclaimed


async def _cleanup_temp_directories() -> None:
    """Clear stale chunk cache and orphaned stream temp files on startup.

    Offloaded via asyncio.to_thread (#4754) — up to 512 MB of cached WAVs,
    previously removed directly on the event loop during lifespan startup.
    """
    temp_root = Path(tempfile.gettempdir())
    chunk_dir = temp_root / CHUNK_TEMP_DIRNAME
    owner_marker = temp_root / CHUNK_TEMP_OWNER_FILENAME

    # #4713: only wipe when no *live* foreign backend has claimed the shared
    # cache. A lone instance (every packaged run) still wipes on every start,
    # so #4666's stale-chunk blast radius stays intra-session.
    if await asyncio.to_thread(claim_chunk_cache, chunk_dir, owner_marker):
        if chunk_dir.exists():
            try:
                await asyncio.to_thread(shutil.rmtree, chunk_dir)
                await asyncio.to_thread(create_secure_temp_dir, chunk_dir)
                logger.info(f"🧹 Cleared chunk directory: {chunk_dir.name}")
            except Exception as e:
                logger.warning(f"Failed to clear chunk directory: {e}")
        # We own the cache, so every staging file here belongs to a dead
        # writer — no age bar. Normally a no-op, because the wipe above
        # already removed them; this is what runs when the wipe raised
        # partway (it only warns) or when the directory did not exist.
        partial_min_age = 0.0
    else:
        # Another backend is live and may be mid-write. A staging file is
        # indistinguishable by name from an in-flight one, so only reap
        # partials too old to be in flight — deleting a live one would make
        # the other instance's os.replace() fail. This branch is the reason
        # #5208 existed: it is the one path that neither wipes nor sweeps,
        # so orphans from a crashed sibling accumulated here indefinitely.
        partial_min_age = PARTIAL_MAX_AGE_SECONDS

    # #5208: atomic_io wrote this sweep alongside the #4576 staged-write fix
    # but never called it from anywhere but its own test.
    await asyncio.to_thread(cleanup_partial_files, chunk_dir, partial_min_age)

    # Sweep temp WAVs orphaned by interrupted compressed-format streams (#3877),
    # skipping any a live process still owns (#4713).
    await asyncio.to_thread(reclaim_leftover_stream_temps, temp_root)
