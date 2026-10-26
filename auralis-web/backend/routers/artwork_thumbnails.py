"""
Album-artwork thumbnail cache: size buckets, per-file render locks, rendering, eviction (split from artwork.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from auralis.utils.artwork_security import ArtworkRejectedError, open_bounded_image
from core.thumbnail_cache import THUMB_TMP_PREFIX, artwork_cache_dirs, prune_thumbnail_cache, purge_thumbnails, reap_orphan_temp_files, thumb_path_hash
from pathlib import Path
from .errors import NotFoundError
import os
import tempfile
import threading

logger = logging.getLogger(__name__)


# Downscaled-thumbnail support (#4447). Requested sizes snap UP to one of these
# buckets so the on-disk cache holds at most len(_THUMB_BUCKETS) variants per
# source image instead of an unbounded set of arbitrary sizes.
_THUMB_BUCKETS: tuple[int, ...] = (64, 128, 256, 512, 1024)


def _bucket_size(size: int) -> int:
    """Snap a requested max-dimension up to the nearest cache bucket."""
    for bucket in _THUMB_BUCKETS:
        if size <= bucket:
            return bucket
    return _THUMB_BUCKETS[-1]


# Prefix for in-progress thumbnail renders (#4527). Owned by core.thumbnail_cache
# (which reaps orphans by it, #4532) and re-exported here for the existing
# callers and tests that read it from this module.
_THUMB_TMP_PREFIX = THUMB_TMP_PREFIX


# Per-cache-key render locks (#4527). Two requests for the same album at the
# same bucket used to render concurrently; now the second waits and takes the
# first's result, which also caps the peak memory of a grid scroll. Keyed on the
# full cache key, NOT the album id — a per-album lock would serialise unrelated
# buckets against each other.
_THUMB_LOCKS: dict[str, threading.Lock] = {}


_THUMB_WAITERS: dict[str, int] = {}


_THUMB_GUARD = threading.Lock()


@contextmanager
def _thumb_render_lock(key: str) -> Iterator[None]:
    """Hold the render lock for one cache key, and retire it when idle.

    The waiter count is what makes retiring safe: dropping a lock another
    thread is still blocked on would let a third thread create a second lock
    for the same key and render concurrently again. Without retiring, the dict
    would instead grow one entry per (album, bucket, artwork generation) for the
    life of the process.
    """
    with _THUMB_GUARD:
        lock = _THUMB_LOCKS.setdefault(key, threading.Lock())
        _THUMB_WAITERS[key] = _THUMB_WAITERS.get(key, 0) + 1
    try:
        with lock:
            yield
    finally:
        with _THUMB_GUARD:
            remaining = _THUMB_WAITERS[key] - 1
            if remaining:
                _THUMB_WAITERS[key] = remaining
            else:
                del _THUMB_WAITERS[key]
                _THUMB_LOCKS.pop(key, None)


def _render_thumbnail(
    src: Path, dst: Path, bucket: int, pil_fmt: str, ext: str, thumb_dir: Path
) -> None:
    """Render ``src`` into ``dst`` via a temp file unique to this writer (#4527).

    The previous temp name was derived only from the cache key
    (``dst.suffix + ".tmp"``), so N threads rendering the same album at the same
    bucket interleaved their bytes into one file and each then promoted whatever
    it happened to contain. ``Path.replace()`` is atomic within a filesystem, so
    a per-writer temp is all that is needed for correctness — the lock above is
    an efficiency measure, not the fix.

    Raises on failure, having removed its own temp file; the caller converts
    that to ``None``.
    """
    fd, tmp_name = tempfile.mkstemp(
        dir=thumb_dir, prefix=_THUMB_TMP_PREFIX, suffix=ext
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            # Refuses a decompression bomb before decoding it (#6153); PIL itself
            # stays lazily imported inside open_bounded_image.
            with open_bounded_image(src) as image:
                # thumbnail() preserves aspect ratio and only ever downsizes, so
                # a small source is served as-is rather than upscaled.
                image.thumbnail((bucket, bucket))
                # Rebound to a new name: convert() returns a plain Image while
                # `image` is typed as the ImageFile the context manager yielded,
                # so reassigning it is an incompatible-assignment for mypy.
                out_image = (
                    image.convert("RGB")
                    if pil_fmt == "JPEG" and image.mode not in ("RGB", "L")
                    else image
                )
                out_image.save(handle, format=pil_fmt)
        tmp.replace(dst)
    except BaseException:
        # Leave no orphan behind — a generation-based cache purge keys on the
        # source path hash and would never match a stray temp file.
        tmp.unlink(missing_ok=True)
        raise


def _artwork_dirs() -> tuple[Path, Path]:
    """``(artwork_dir, thumb_dir)`` — one definition for every caller.

    The render path and the purge path MUST agree on where the cache lives, so
    both read it from here rather than each rebuilding the path.
    """
    return artwork_cache_dirs()


def _purge_album_thumbnails(*sources: Path | str | None) -> int:
    """Purge cached thumbnails derived from ``sources``, and reap stale temps.

    Blocking (filesystem) — call via ``asyncio.to_thread``.

    Resolves each source before hashing, because that is what the render path
    hashes: ``get_album_artwork`` passes
    ``Path(album.artwork_path).resolve(strict=False)`` into the cache. Hashing
    the unresolved ``album.artwork_path`` instead would produce a different
    prefix and silently purge nothing whenever the stored path is relative or
    crosses a symlink (#4532).
    """
    _artwork_dir, thumb_dir = _artwork_dirs()

    resolved: list[Path] = []
    for source in sources:
        if not source:
            continue
        try:
            resolved.append(Path(source).resolve(strict=False))
        except (OSError, RuntimeError, ValueError):
            logger.warning("Could not resolve artwork path for purge: %s", source)

    return purge_thumbnails(thumb_dir, *resolved) + reap_orphan_temp_files(thumb_dir)


def _thumb_target(media_type: str) -> tuple[str, str, str]:
    """Map a source media type to (PIL format, file extension, response type).

    JPEG stays JPEG; WEBP stays WEBP; everything else (PNG/GIF/unknown) is
    rendered as PNG so transparency is preserved.
    """
    if media_type == "image/jpeg":
        return "JPEG", ".jpg", "image/jpeg"
    if media_type == "image/webp":
        return "WEBP", ".webp", "image/webp"
    return "PNG", ".png", "image/png"


def _get_or_create_thumbnail(
    src: Path, requested_size: int, media_type: str, thumb_dir: Path
) -> tuple[Path, str] | None:
    """Return (thumbnail_path, media_type) for a downscaled copy of ``src``.

    Blocking (PIL + disk IO) — call via ``asyncio.to_thread``. The cache key
    includes the source path hash, bucketed size, and source mtime/size so an
    artwork edit produces a new file and stale thumbnails are never served.
    Returns ``None`` on any failure so the caller can fall back to the original,
    except a decompression bomb, which raises a 404: the original is exactly the
    image that must not be served (#6153).
    """
    try:
        bucket = _bucket_size(requested_size)
        pil_fmt, ext, resp_type = _thumb_target(media_type)

        stat = src.stat()
        # thumb_path_hash is shared with the purge in core.thumbnail_cache, which
        # globs on this exact prefix — computing it here independently would let
        # the two drift and silently strand every entry (#4532).
        path_hash = thumb_path_hash(src)
        key = f"{path_hash}_{bucket}_{stat.st_mtime_ns:x}_{stat.st_size:x}{ext}"
        dst = thumb_dir / key

        if not dst.exists():
            thumb_dir.mkdir(parents=True, exist_ok=True)
            with _thumb_render_lock(key):
                # Re-check under the lock: whoever held it before us may have
                # rendered this exact key already.
                if not dst.exists():
                    # Sweep dead writers' temp files before adding our own, so
                    # orphans cannot accumulate indefinitely on an install that
                    # never deletes artwork (#4532). Cheap: one glob over a
                    # directory whose size is bounded by live thumbnails, and
                    # only on an actual cache miss.
                    reap_orphan_temp_files(thumb_dir)
                    _render_thumbnail(src, dst, bucket, pil_fmt, ext, thumb_dir)
                    # Never evict the file this request is about to serve. If
                    # one thumbnail somehow exceeds the whole cap, keep that
                    # response valid and reclaim it on a later miss instead.
                    prune_thumbnail_cache(thumb_dir, keep=dst)

        return dst, resp_type
    except ArtworkRejectedError:
        logger.warning("Refused to thumbnail an artwork image over the pixel budget: %s", src.name)
        raise NotFoundError("Artwork") from None
    except Exception:
        logger.exception("Thumbnail generation failed for %s", src)
        return None
