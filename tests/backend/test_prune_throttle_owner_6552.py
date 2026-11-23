"""The chunk-prune throttle counter lives on the class that owns its locks (#6552).

_maybe_prune did `cls = type(self)` and `cls._write_counter += 1`: on a plain
subclass that read the inherited counter but assigned a new subclass-level one,
so the subclass and the base each counted to the threshold separately over one
directory and one lock pair. The owner is now the nearest class in the MRO that
defines _prune_lock. ThumbnailSweeper declares its own state on purpose (a
separate directory) and must keep it.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from core.chunk_disk_prune import ChunkDiskPruneMixin  # noqa: E402
from core.thumbnail_sweep import ThumbnailSweeper  # noqa: E402


class _Base(ChunkDiskPruneMixin):
    """Stands in for ChunkCacheManager: inherits the mixin's throttle state."""

    def __init__(self, sweeps: list):
        self._prune_every = 4
        self._max_disk_bytes = 0
        self._sweeps = sweeps

    def _sweep(self, directory):
        self._sweeps.append(type(self).__name__)


class _Subclass(_Base):
    """A plain subclass, as a future ChunkCacheManager variant would be."""


@pytest.fixture(autouse=True)
def _fresh_counters():
    saved = (ChunkDiskPruneMixin._write_counter, ThumbnailSweeper._write_counter)
    ChunkDiskPruneMixin._write_counter = 0
    ThumbnailSweeper._write_counter = 0
    yield
    ChunkDiskPruneMixin._write_counter, ThumbnailSweeper._write_counter = saved
    for cls in (_Base, _Subclass):
        if "_write_counter" in vars(cls):
            delattr(cls, "_write_counter")


def test_subclass_and_base_writes_advance_one_counter(tmp_path):
    sweeps: list = []
    base, sub = _Base(sweeps), _Subclass(sweeps)

    for writer in (base, sub, base, sub, base, sub, base, sub):  # 8 writes, every 4th prunes
        writer._maybe_prune(tmp_path)

    assert len(sweeps) == 2
    assert "_write_counter" not in vars(_Subclass), "the subclass grew its own counter"


def test_thumbnail_sweeper_keeps_its_own_cadence(tmp_path, monkeypatch):
    thumbs: list = []
    monkeypatch.setattr(ThumbnailSweeper, "_sweep", lambda self, d: thumbs.append(d))
    sweeper = ThumbnailSweeper(every=3)
    chunk_writer = _Base([])

    for _ in range(3):
        chunk_writer._maybe_prune(tmp_path)  # chunk-cache writes must not count toward thumbnails
    assert thumbs == []

    for _ in range(3):
        sweeper.note_render(tmp_path)
    assert len(thumbs) == 1
    assert ChunkDiskPruneMixin._write_counter == 3
