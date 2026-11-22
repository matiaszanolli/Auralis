"""Directory sweeps shared by the on-disk caches and the startup temp reclaim (#6629).

Two shapes, each written once:

- :func:`prune_directory_lru` keeps a directory under a byte budget by deleting its oldest files
  (by mtime). The chunk cache (#3834) and the thumbnail cache (#4532) used to carry their own
  copies, and only the thumbnail one refused a symlinked directory.
- :func:`reap_older_than` deletes entries older than an age. The stale temp entries (#4762), the
  FFmpeg decode WAVs, the ``.part`` staging files (#4576) and the thumbnail render temps each
  repeated it.

Neither follows symlinks: an entry is aged and sized by ``lstat``, a symlinked entry is unlinked
as a link and never descended into, and a symlinked directory is never pruned.
Both are best-effort and never raise; per-entry failures are logged through the caller's logger,
naming the entry rather than its full path.
"""

import logging
import shutil
import stat
import time
from collections.abc import Callable, Iterable
from pathlib import Path

logger = logging.getLogger(__name__)


def prune_directory_lru(
    directory: Path,
    max_bytes: int,
    *,
    label: str,
    skip: Callable[[Path], bool] | None = None,
    keep: Path | None = None,
    log: logging.Logger = logger,
) -> tuple[int, int]:
    """Delete the oldest regular files in *directory* until its total size is within *max_bytes*.

    *skip* excludes entries from both the total and the eviction (files a live writer owns);
    *keep* is counted but never evicted (the file the caller just wrote). Returns
    ``(files_deleted, bytes_reclaimed)``.
    """
    if directory.is_symlink():
        log.warning(f"Refusing to prune symlinked {label} directory {directory}")
        return (0, 0)

    entries: list[tuple[float, int, Path]] = []
    total = 0
    try:
        for entry in directory.iterdir():
            if skip is not None and skip(entry):
                continue
            try:
                st = entry.lstat()
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            entries.append((st.st_mtime, st.st_size, entry))
            total += st.st_size
    except OSError as e:
        log.debug(f"{label} prune skipped ({directory}): {e}")
        return (0, 0)

    if total <= max_bytes:
        return (0, 0)

    entries.sort(key=lambda item: item[0])  # oldest mtime first
    deleted = 0
    reclaimed = 0
    for _mtime, size, entry in entries:
        if total <= max_bytes:
            break
        if keep is not None and entry == keep:
            continue
        try:
            entry.unlink()
        except OSError as e:
            log.warning(f"Could not prune {label} {entry.name}: {e}")
            continue
        deleted += 1
        reclaimed += size
        total -= size

    if deleted:
        log.info(
            f"Pruned {deleted} {label} file(s) from {directory}, reclaimed "
            f"{reclaimed / 1024 / 1024:.1f} MB (cap {max_bytes / 1024 / 1024:.0f} MB)"
        )
    return (deleted, reclaimed)


def reap_older_than(
    candidates: Iterable[Path],
    max_age_seconds: float,
    *,
    label: str,
    remove_dirs: bool = False,
    log: logging.Logger = logger,
    failure_level: int = logging.WARNING,
) -> int:
    """Delete each candidate last modified more than *max_age_seconds* ago; returns how many.

    A *max_age_seconds* of 0 or less removes every candidate regardless of age. Directories are
    removed recursively only with *remove_dirs*, and skipped otherwise. A failure to list the
    candidates (a directory that does not exist yet) ends the sweep quietly.
    """
    cutoff = time.time() - max_age_seconds if max_age_seconds > 0 else None
    removed = 0
    try:
        for entry in candidates:
            try:
                if _remove_if_older(entry, cutoff, remove_dirs):
                    removed += 1
            except OSError as e:
                log.log(failure_level, f"Could not remove {label} {entry.name}: {type(e).__name__}")
    except OSError as e:
        log.debug(f"{label} sweep skipped: {e}")
    return removed


def _remove_if_older(entry: Path, cutoff: float | None, remove_dirs: bool) -> bool:
    """Remove *entry* if it predates *cutoff* (None: any age); True when removed. Raises OSError."""
    st = entry.lstat()
    if cutoff is not None and st.st_mtime >= cutoff:
        return False
    if not stat.S_ISDIR(st.st_mode):
        entry.unlink()
        return True
    if not remove_dirs:
        return False
    shutil.rmtree(entry)
    return True
