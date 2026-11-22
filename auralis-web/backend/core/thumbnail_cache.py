# -*- coding: utf-8 -*-

"""
Thumbnail Cache Lifecycle
~~~~~~~~~~~~~~~~~~~~~~~~~

The on-disk thumbnail cache added in #4447 is content-addressed on the SOURCE
image: its key is ``{path_hash}_{bucket}_{mtime_ns}_{size}{ext}``. Embedding
mtime/size means an edited artwork file yields a fresh key, so a stale
thumbnail can never be served — but it also means the superseded key is simply
orphaned, and nothing removed it (#4532). With five buckets, every re-extract,
re-download or delete stranded up to five files forever.

This module owns the *removal* half of that cache. It deliberately holds no
rendering logic and no knowledge of albums or repositories: it maps source
image paths to cache entries and unlinks them, so the routers can invalidate
without the repository layer having to touch the filesystem.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import hashlib
import logging
from pathlib import Path

from auralis.library.data_dir import artwork_dir
from core.dir_sweep import prune_directory_lru, reap_older_than

logger = logging.getLogger(__name__)

__all__ = [
    "THUMB_TMP_PREFIX",
    "THUMBNAIL_CACHE_MAX_BYTES",
    "TEMP_FILE_MAX_AGE_SECONDS",
    "artwork_cache_dirs",
    "artwork_cache_root",
    "clear_artwork_cache",
    "prune_thumbnail_cache",
    "thumb_path_hash",
    "purge_thumbnails",
    "reap_orphan_temp_files",
]

# A full reset removes both the source-artwork cache and its derived thumbnail
# tree. Outside a reset, the thumbnail tier is capped independently so stale
# generations and albums that disappear without an explicit purge cannot grow
# forever (#5255). 128 MiB comfortably holds thousands of UI-sized images.
THUMBNAIL_CACHE_MAX_BYTES = 128 * 1024 * 1024

# Prefix for in-progress thumbnail renders (#4527). Stable and distinctive so a
# sweeper can recognise an orphan left by a crashed render — the cache keys
# themselves are hex digests and never start with a dot.
THUMB_TMP_PREFIX = ".tmp-"

# Only temp files older than this are reaped. A render in flight owns its temp
# file, and unlinking it would make that render fail; thumbnailing an image
# takes milliseconds, so anything this old belongs to a dead writer (#4532).
TEMP_FILE_MAX_AGE_SECONDS = 300.0


def artwork_cache_root() -> Path:
    """Return the canonical source-artwork cache root."""
    return artwork_dir()


def artwork_cache_dirs() -> tuple[Path, Path]:
    """Return the canonical ``(artwork_dir, thumbnail_dir)`` pair."""
    artwork_dir = artwork_cache_root()
    return artwork_dir, artwork_dir / "thumbnails"


def thumb_path_hash(src: Path | str) -> str:
    """The leading cache-key component for a source image path.

    Must stay identical to the hash used when building cache keys — it is the
    only thing tying an entry back to its source, and the purge below globs on
    it. Shared from here rather than duplicated so the two cannot drift.
    """
    return hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:12]


def purge_thumbnails(thumb_dir: Path, *sources: Path | str | None) -> int:
    """Unlink every cached thumbnail derived from any of ``sources``.

    Removes ALL generations for each source, not just superseded ones. That is
    safe because thumbnails are rendered lazily on request: after an artwork
    write the new generation does not exist yet, so purging the whole hash
    clears the old files and the next GET re-renders. It is also what makes the
    same call correct whether the new artwork reused the old path (overwrite —
    same hash, new mtime) or landed on a new one.

    ``None`` sources are skipped, so callers can pass an optional
    ``album.artwork_path`` without pre-checking it.

    Never raises: a cache purge failure must not turn a successful artwork
    delete into a 500 (the caller's DB work has already committed). Failures
    are logged and counted as not-removed.

    Args:
        thumb_dir: The thumbnail cache directory.
        *sources: Source image paths whose derived thumbnails should go.

    Returns:
        How many files were unlinked.
    """
    if not thumb_dir.is_dir():
        return 0

    removed = 0
    # Deduplicate: extract/download commonly pass the same path as both the old
    # and the new source, and globbing twice would log phantom failures.
    hashes = {thumb_path_hash(src) for src in sources if src}
    for path_hash in hashes:
        for entry in thumb_dir.glob(f"{path_hash}_*"):
            try:
                entry.unlink()
                removed += 1
            except OSError:
                logger.warning("Could not purge cached thumbnail %s", entry, exc_info=True)

    if removed:
        logger.debug("Purged %d cached thumbnail(s) from %s", removed, thumb_dir)
    return removed


def prune_thumbnail_cache(
    thumb_dir: Path,
    max_bytes: int = THUMBNAIL_CACHE_MAX_BYTES,
    *,
    keep: Path | None = None,
) -> tuple[int, int]:
    """Evict oldest completed thumbnails until ``thumb_dir`` is within its cap.

    Temporary render files are excluded because they may belong to live
    writers; :func:`reap_orphan_temp_files` owns their age-based lifecycle.
    Best-effort filesystem errors never fail the artwork request that triggered
    the sweep. Returns ``(files_deleted, bytes_reclaimed)``.
    """
    return prune_directory_lru(
        thumb_dir,
        max_bytes,
        label="thumbnail",
        skip=lambda entry: entry.name.startswith(THUMB_TMP_PREFIX),
        keep=keep,
        log=logger,
    )


def clear_artwork_cache(artwork_dir: Path) -> tuple[int, int]:
    """Remove every cached source artwork and derived thumbnail below a root.

    The root directory itself is retained. Symlinked roots are refused so a
    malformed cache path cannot make a reset traverse outside the cache tree.
    Individual failures are logged and skipped. Returns
    ``(files_deleted, bytes_reclaimed)``.
    """
    if artwork_dir.is_symlink():
        logger.warning("Refusing to clear symlinked artwork cache %s", artwork_dir)
        return (0, 0)
    if not artwork_dir.is_dir():
        return (0, 0)

    try:
        entries = list(artwork_dir.rglob("*"))
    except OSError:
        logger.warning("Could not enumerate artwork cache %s", artwork_dir, exc_info=True)
        return (0, 0)

    deleted = 0
    reclaimed = 0
    for entry in entries:
        try:
            if not (entry.is_file() or entry.is_symlink()):
                continue
            size = entry.lstat().st_size
            entry.unlink()
            deleted += 1
            reclaimed += size
        except OSError:
            logger.warning("Could not clear cached artwork %s", entry, exc_info=True)

    for directory in sorted(
        (entry for entry in entries if entry.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass

    if deleted:
        logger.info(
            "Cleared %d artwork-cache file(s) from %s, reclaimed %.1f MiB",
            deleted,
            artwork_dir,
            reclaimed / 1024 / 1024,
        )
    return (deleted, reclaimed)


def reap_orphan_temp_files(
    thumb_dir: Path, max_age_seconds: float = TEMP_FILE_MAX_AGE_SECONDS
) -> int:
    """Unlink stale in-progress render files left behind by dead writers.

    A crashed or killed render leaves a ``.tmp-*`` file that no cache key ever
    matches, so :func:`purge_thumbnails` can never reach it (#4532). Age is the
    only safe discriminator — a young temp file may be owned by a render
    happening right now.

    Never raises, for the same reason as :func:`purge_thumbnails`.

    Returns:
        How many files were unlinked.
    """
    if not thumb_dir.is_dir():
        return 0

    # A failure includes the benign race where a live writer promoted or removed the file.
    removed = reap_older_than(
        thumb_dir.glob(f"{THUMB_TMP_PREFIX}*"),
        max_age_seconds,
        label="temp thumbnail",
        log=logger,
        failure_level=logging.DEBUG,
    )

    if removed:
        logger.info("Reaped %d orphaned thumbnail temp file(s) from %s", removed, thumb_dir)
    return removed
