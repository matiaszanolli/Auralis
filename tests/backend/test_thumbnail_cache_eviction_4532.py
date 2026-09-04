# -*- coding: utf-8 -*-

"""Thumbnail cache lifecycle: superseded generations are evicted (#4532).

The cache added in #4447 is content-addressed on the SOURCE image — the key is
``{path_hash}_{bucket}_{mtime_ns}_{size}{ext}`` — so editing artwork produces a
new key and a stale thumbnail can never be served. Nothing removed the old key,
though, so with five buckets every re-extract, re-download and delete stranded
up to five files permanently, and a crashed render left a ``.tmp-*`` orphan that
no key would ever match.

Covers the issue's three acceptance criteria:
  * after DELETE, nothing remains for that album's source hash;
  * after re-extract/re-download, only the new generation's buckets remain;
  * ``*.tmp`` files do not accumulate across repeated failed renders.
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from core.thumbnail_cache import (  # noqa: E402
    THUMB_TMP_PREFIX,
    clear_artwork_cache,
    prune_thumbnail_cache,
    purge_thumbnails,
    reap_orphan_temp_files,
    thumb_path_hash,
)
from routers.artwork import (  # noqa: E402
    _THUMB_BUCKETS,
    _get_or_create_thumbnail,
    _purge_album_thumbnails,
)


@pytest.fixture
def thumb_dir(tmp_path) -> Path:
    d = tmp_path / "thumbnails"
    d.mkdir()
    return d


def _seed_generation(thumb_dir: Path, source: Path, mtime: str = "aaa") -> list[Path]:
    """Write one file per bucket for `source`, as the real cache would."""
    path_hash = thumb_path_hash(source)
    files = [thumb_dir / f"{path_hash}_{b}_{mtime}_100{'.png'}" for b in _THUMB_BUCKETS]
    for f in files:
        f.write_bytes(b"fake-thumb")
    return files


def _png(path: Path, size: int = 64) -> Path:
    """A real PNG on disk, so PIL can actually render from it."""
    from PIL import Image

    Image.new("RGB", (size, size), (10, 120, 200)).save(path, format="PNG")
    return path


class TestPathHashIsShared:
    """The purge globs on the same hash the render path embeds."""

    def test_hash_matches_the_key_built_by_the_render_path(self, thumb_dir, tmp_path):
        source = _png(tmp_path / "cover.png")

        result = _get_or_create_thumbnail(source, 256, "image/png", thumb_dir)

        assert result is not None
        cached, _media_type = result
        assert cached.name.startswith(thumb_path_hash(source) + "_"), (
            "render path and purge path disagree on the hash; every purge would "
            "silently match nothing"
        )


class TestPurgeThumbnails:
    """Unit behaviour of the purge helper."""

    def test_removes_every_bucket_for_the_source(self, thumb_dir, tmp_path):
        source = tmp_path / "cover.png"
        _seed_generation(thumb_dir, source)

        removed = purge_thumbnails(thumb_dir, source)

        assert removed == len(_THUMB_BUCKETS)
        assert list(thumb_dir.glob(f"{thumb_path_hash(source)}_*")) == []

    def test_leaves_other_albums_untouched(self, thumb_dir, tmp_path):
        mine = tmp_path / "mine.png"
        theirs = tmp_path / "theirs.png"
        _seed_generation(thumb_dir, mine)
        other_files = _seed_generation(thumb_dir, theirs)

        purge_thumbnails(thumb_dir, mine)

        assert all(f.exists() for f in other_files)

    def test_removes_all_generations_for_the_source(self, thumb_dir, tmp_path):
        """Old and new generations differ only by mtime; both go."""
        source = tmp_path / "cover.png"
        _seed_generation(thumb_dir, source, mtime="aaa")
        _seed_generation(thumb_dir, source, mtime="bbb")

        removed = purge_thumbnails(thumb_dir, source)

        assert removed == 2 * len(_THUMB_BUCKETS)

    def test_none_sources_are_skipped(self, thumb_dir):
        assert purge_thumbnails(thumb_dir, None) == 0

    def test_duplicate_sources_are_not_double_counted(self, thumb_dir, tmp_path):
        """extract/download pass old and new paths, often identical."""
        source = tmp_path / "cover.png"
        _seed_generation(thumb_dir, source)

        assert purge_thumbnails(thumb_dir, source, source) == len(_THUMB_BUCKETS)

    def test_missing_directory_is_not_an_error(self, tmp_path):
        assert purge_thumbnails(tmp_path / "nope", tmp_path / "cover.png") == 0

    def test_unlink_failure_is_swallowed(self, thumb_dir, tmp_path):
        """A cache failure must never fail the artwork request that triggered it."""
        source = tmp_path / "cover.png"
        _seed_generation(thumb_dir, source)

        with patch.object(Path, "unlink", side_effect=OSError("read-only fs")):
            assert purge_thumbnails(thumb_dir, source) == 0  # no raise


class TestReapOrphanTempFiles:
    """Stale render temps are reaped; in-flight ones are not."""

    def test_old_temp_files_are_removed(self, thumb_dir):
        orphan = thumb_dir / f"{THUMB_TMP_PREFIX}dead.png"
        orphan.write_bytes(b"partial")
        old = time.time() - 10_000
        os.utime(orphan, (old, old))

        assert reap_orphan_temp_files(thumb_dir) == 1
        assert not orphan.exists()

    def test_fresh_temp_files_are_left_alone(self, thumb_dir):
        """A young temp file may belong to a render happening right now."""
        live = thumb_dir / f"{THUMB_TMP_PREFIX}live.png"
        live.write_bytes(b"in progress")

        assert reap_orphan_temp_files(thumb_dir) == 0
        assert live.exists()

    def test_cache_entries_are_never_reaped(self, thumb_dir, tmp_path):
        """Real keys are hex digests and never start with a dot."""
        files = _seed_generation(thumb_dir, tmp_path / "cover.png")

        reap_orphan_temp_files(thumb_dir, max_age_seconds=0.0)

        assert all(f.exists() for f in files)

    def test_repeated_failed_renders_do_not_accumulate(self, thumb_dir, tmp_path):
        """Acceptance: no *.tmp build-up across repeated failed renders."""
        source = _png(tmp_path / "cover.png")

        # PIL is imported lazily inside _render_thumbnail, so patch it at source.
        with patch("PIL.Image.open", side_effect=OSError("boom")):
            for _ in range(5):
                assert _get_or_create_thumbnail(source, 256, "image/png", thumb_dir) is None

        leftovers = [p for p in thumb_dir.iterdir() if p.name.startswith(THUMB_TMP_PREFIX)]
        assert leftovers == [], f"failed renders leaked temp files: {leftovers}"


class TestThumbnailCacheBackstop:
    """#5255: completed thumbnails have a byte-capped oldest-file sweep."""

    def test_prune_deletes_oldest_files_until_under_cap(self, thumb_dir):
        files = [thumb_dir / f"{idx}.png" for idx in range(3)]
        now = time.time()
        for idx, path in enumerate(files):
            path.write_bytes(b"1234")
            os.utime(path, (now + idx, now + idx))

        deleted, reclaimed = prune_thumbnail_cache(thumb_dir, max_bytes=8)

        assert (deleted, reclaimed) == (1, 4)
        assert not files[0].exists()
        assert files[1].exists() and files[2].exists()

    def test_prune_preserves_the_thumbnail_being_served(self, thumb_dir):
        files = [thumb_dir / f"{idx}.png" for idx in range(3)]
        now = time.time()
        for idx, path in enumerate(files):
            path.write_bytes(b"1234")
            os.utime(path, (now + idx, now + idx))

        deleted, reclaimed = prune_thumbnail_cache(
            thumb_dir,
            max_bytes=4,
            keep=files[0],
        )

        assert (deleted, reclaimed) == (2, 8)
        assert files[0].read_bytes() == b"1234"
        assert not files[1].exists() and not files[2].exists()

    def test_render_miss_invokes_the_size_backstop(self, thumb_dir, tmp_path):
        source = _png(tmp_path / "cover.png")

        with patch("routers.artwork.prune_thumbnail_cache") as prune:
            result = _get_or_create_thumbnail(source, 256, "image/png", thumb_dir)

        assert result is not None
        cached, _media_type = result
        assert prune.call_args_list == [((thumb_dir,), {"keep": cached})]

    def test_clear_artwork_cache_removes_sources_and_derived_files(self, tmp_path):
        artwork_dir = tmp_path / "artwork"
        thumb_dir = artwork_dir / "thumbnails"
        thumb_dir.mkdir(parents=True)
        source = artwork_dir / "album-1.jpg"
        thumbnail = thumb_dir / "derived.png"
        source.write_bytes(b"source")
        thumbnail.write_bytes(b"thumb")

        deleted, reclaimed = clear_artwork_cache(artwork_dir)

        assert (deleted, reclaimed) == (2, 11)
        assert artwork_dir.exists()
        assert list(artwork_dir.rglob("*")) == []


class TestPurgeResolvesLikeTheRenderPath:
    """The router purge must hash the resolved path, as the cache does."""

    def test_relative_source_still_purges(self, thumb_dir, tmp_path, monkeypatch):
        """A stored relative path resolves to the same key the cache used.

        Hashing the raw `album.artwork_path` here would produce a different
        prefix and purge nothing at all.
        """
        real = _png(tmp_path / "cover.png")
        monkeypatch.chdir(tmp_path)
        _seed_generation(thumb_dir, real.resolve())

        with patch("routers.artwork._artwork_dirs", return_value=(thumb_dir.parent, thumb_dir)):
            removed = _purge_album_thumbnails("cover.png")

        assert removed == len(_THUMB_BUCKETS)
        assert list(thumb_dir.glob(f"{thumb_path_hash(real.resolve())}_*")) == []

    def test_unresolvable_source_does_not_raise(self, thumb_dir):
        with patch("routers.artwork._artwork_dirs", return_value=(thumb_dir.parent, thumb_dir)):
            with patch.object(Path, "resolve", side_effect=OSError("bad path")):
                assert _purge_album_thumbnails("whatever.png") == 0


class TestGenerationReplacement:
    """Acceptance: after the source changes, only the new generation remains."""

    def test_editing_the_source_leaves_one_generation_after_purge(self, thumb_dir, tmp_path):
        source = _png(tmp_path / "cover.png")

        # Populate every bucket for generation 1.
        for bucket in _THUMB_BUCKETS:
            assert _get_or_create_thumbnail(source, bucket, "image/png", thumb_dir) is not None
        assert len(list(thumb_dir.iterdir())) == len(_THUMB_BUCKETS)

        # Replace the source image (new mtime AND new size) — as extract or
        # download would — and purge, as the routers now do.
        time.sleep(0.01)
        _png(source, size=128)
        with patch("routers.artwork._artwork_dirs", return_value=(thumb_dir.parent, thumb_dir)):
            _purge_album_thumbnails(source, source)

        # Re-request every bucket for generation 2.
        for bucket in _THUMB_BUCKETS:
            assert _get_or_create_thumbnail(source, bucket, "image/png", thumb_dir) is not None

        # Five, not ten: the superseded generation is gone.
        assert len(list(thumb_dir.iterdir())) == len(_THUMB_BUCKETS)

    def test_without_the_purge_both_generations_would_persist(self, thumb_dir, tmp_path):
        """Pins that the test above is actually measuring the purge.

        Without it the count doubles — which is precisely the leak in #4532.
        """
        source = _png(tmp_path / "cover.png")
        for bucket in _THUMB_BUCKETS:
            _get_or_create_thumbnail(source, bucket, "image/png", thumb_dir)

        time.sleep(0.01)
        _png(source, size=128)
        for bucket in _THUMB_BUCKETS:
            _get_or_create_thumbnail(source, bucket, "image/png", thumb_dir)

        assert len(list(thumb_dir.iterdir())) == 2 * len(_THUMB_BUCKETS)


class TestDeleteRoutePurges:
    """Acceptance: DELETE /api/albums/{id}/artwork clears the derived cache."""

    @pytest.mark.asyncio
    async def test_delete_reads_the_path_before_clearing_and_purges(self, thumb_dir, tmp_path):
        """The path must be captured BEFORE delete_artwork discards it."""
        # Since #4670 the handler is a module-level `async def`, so it is
        # called directly with explicit repos/connection_manager instead of
        # being dug out of a router the factory had to build first.
        from routers.artwork import delete_album_artwork

        source = tmp_path / "cover.png"
        seeded = _seed_generation(thumb_dir, source.resolve())

        album = MagicMock()
        album.artwork_path = str(source)
        repos = MagicMock()
        repos.albums.get_by_id.return_value = album
        repos.albums.delete_artwork.return_value = True

        manager = MagicMock()

        async def _broadcast(_msg):
            return None

        manager.broadcast = _broadcast

        with patch(
            "routers.artwork._artwork_dirs", return_value=(thumb_dir.parent, thumb_dir)
        ):
            await delete_album_artwork(
                album_id=1, repos=repos, connection_manager=manager
            )

        assert all(not f.exists() for f in seeded)
        assert list(thumb_dir.glob(f"{thumb_path_hash(source.resolve())}_*")) == []
