"""
Thumbnail render concurrency (issue #4527)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_get_or_create_thumbnail` wrote to `dst.with_suffix(dst.suffix + ".tmp")` — a
name derived only from the cache key, not from the writer. N requests for the
same album at the same size bucket each ran on their own thread via
`asyncio.to_thread` and `image.save()`d into that one path concurrently,
interleaving bytes; each then `replace()`d whatever the file happened to
contain into the cache.

Because the key is content-addressed on the SOURCE file's mtime_ns + st_size,
the corrupt thumbnail was then served for every subsequent request at that
bucket and never regenerated — the artwork stayed visibly broken until the
source file was touched or the directory cleared by hand.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.artwork import (  # noqa: E402
    _THUMB_LOCKS,
    _THUMB_TMP_PREFIX,
    _THUMB_WAITERS,
    _get_or_create_thumbnail,
)

Image = pytest.importorskip("PIL.Image")


@pytest.fixture
def source_image(tmp_path: Path) -> Path:
    """A source big enough that rendering is not instantaneous."""
    src = tmp_path / "cover.png"
    img = Image.new("RGB", (2000, 2000))
    # Non-uniform content so a truncated write is detectable, and so the
    # encoder has real work to do.
    for x in range(0, 2000, 10):
        for y in range(0, 2000, 10):
            img.putpixel((x, y), ((x * 7) % 256, (y * 11) % 256, ((x + y) * 3) % 256))
    img.save(src, format="PNG")
    return src


@pytest.fixture
def thumb_dir(tmp_path: Path) -> Path:
    return tmp_path / "thumbnails"


class TestConcurrentRenders:
    def test_eight_threads_produce_one_valid_identical_thumbnail(
        self, source_image: Path, thumb_dir: Path
    ):
        """The reproduction: N writers, same album, same bucket."""
        barrier = threading.Barrier(8)

        def render():
            barrier.wait()  # maximise overlap
            return _get_or_create_thumbnail(source_image, 256, "image/png", thumb_dir)

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = [f.result() for f in [pool.submit(render) for _ in range(8)]]

        assert all(r is not None for r in results)
        paths = {r[0] for r in results}
        assert len(paths) == 1, "threads disagreed on the cache path"

        dst = paths.pop()
        # Every result must be a decodable image, not a truncated one.
        with Image.open(dst) as img:
            img.verify()
        with Image.open(dst) as img:
            assert img.size == (256, 256)

        payloads = {dst.read_bytes()}
        assert len(payloads) == 1

    def test_no_temp_files_survive_a_successful_render(
        self, source_image: Path, thumb_dir: Path
    ):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(
                pool.map(
                    lambda _: _get_or_create_thumbnail(
                        source_image, 256, "image/png", thumb_dir
                    ),
                    range(8),
                )
            )

        # Catch either naming scheme: the new `.tmp-XXXX` prefix and the old
        # `<key>.png.tmp` suffix.
        leftovers = [
            p for p in thumb_dir.iterdir()
            if p.name.startswith(_THUMB_TMP_PREFIX) or ".tmp" in p.name
        ]
        assert leftovers == [], f"orphan temp files: {leftovers}"
        assert len(list(thumb_dir.iterdir())) == 1

    def test_distinct_buckets_are_not_serialized_into_one_file(
        self, source_image: Path, thumb_dir: Path
    ):
        """Different buckets are different keys and must not collide."""
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(
                pool.map(
                    lambda size: _get_or_create_thumbnail(
                        source_image, size, "image/png", thumb_dir
                    ),
                    [64, 128, 256, 512, 1024],
                )
            )

        assert all(r is not None for r in results)
        assert len({r[0] for r in results}) == 5
        for path, _ in results:
            with Image.open(path) as img:
                img.verify()


class TestFailedRenderLeavesNothing:
    def test_partial_write_does_not_create_the_cache_entry(
        self, source_image: Path, thumb_dir: Path, monkeypatch
    ):
        """A mid-write failure must not promote anything, nor leak a temp."""
        real_save = Image.Image.save

        def exploding_save(self, fp, *args, **kwargs):
            # Write some bytes first so the temp file is genuinely partial.
            # Handles both call shapes: the fixed code passes an open handle,
            # the original passed a path.
            partial = b"\x89PNG\r\n\x1a\n" + b"\x00" * 512
            if hasattr(fp, "write"):
                fp.write(partial)
            else:
                Path(fp).write_bytes(partial)
            raise OSError("disk full midway through encode")

        monkeypatch.setattr(Image.Image, "save", exploding_save)
        result = _get_or_create_thumbnail(source_image, 256, "image/png", thumb_dir)

        assert result is None, "a failed render must return None, not raise"
        assert list(thumb_dir.glob("*")) == [], "failed render left files behind"

        # And the next attempt, with save working again, must succeed.
        monkeypatch.setattr(Image.Image, "save", real_save)
        ok = _get_or_create_thumbnail(source_image, 256, "image/png", thumb_dir)
        assert ok is not None
        with Image.open(ok[0]) as img:
            img.verify()

    def test_missing_source_returns_none(self, tmp_path: Path, thumb_dir: Path):
        result = _get_or_create_thumbnail(
            tmp_path / "does-not-exist.png", 256, "image/png", thumb_dir
        )
        assert result is None


class TestLockBookkeeping:
    def test_locks_do_not_accumulate(self, source_image: Path, thumb_dir: Path):
        """The lock dict must not grow one entry per cache key, forever.

        Keys embed the source mtime/size, so an artwork edit mints new ones —
        an unbounded dict would grow for the life of the backend process.
        """
        for size in (64, 128, 256, 512, 1024):
            _get_or_create_thumbnail(source_image, size, "image/png", thumb_dir)

        assert _THUMB_LOCKS == {}
        assert _THUMB_WAITERS == {}

    def test_lock_survives_a_failed_render(
        self, source_image: Path, thumb_dir: Path, monkeypatch
    ):
        """A raising render must still release and retire its lock."""

        def exploding_save(self, fp, *args, **kwargs):
            raise OSError("nope")

        monkeypatch.setattr(Image.Image, "save", exploding_save)
        assert _get_or_create_thumbnail(source_image, 256, "image/png", thumb_dir) is None

        assert _THUMB_LOCKS == {}
        assert _THUMB_WAITERS == {}


class TestRenderIsCollapsed:
    def test_concurrent_requests_render_once(
        self, source_image: Path, thumb_dir: Path, monkeypatch
    ):
        """N concurrent requests for one key should decode once, not N times."""
        calls: list[int] = []
        call_guard = threading.Lock()
        real_open = Image.open

        def counting_open(*args, **kwargs):
            with call_guard:
                calls.append(1)
            return real_open(*args, **kwargs)

        monkeypatch.setattr(Image, "open", counting_open)

        barrier = threading.Barrier(8)

        def render():
            barrier.wait()
            return _get_or_create_thumbnail(source_image, 512, "image/png", thumb_dir)

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = [f.result() for f in [pool.submit(render) for _ in range(8)]]

        assert all(r is not None for r in results)
        assert len(calls) == 1, (
            f"decoded {len(calls)} times for one cache key; concurrent requests "
            "should collapse onto a single render"
        )
