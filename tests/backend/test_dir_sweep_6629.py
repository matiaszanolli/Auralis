"""
The shared directory sweeps (#6629)

The chunk-cache and thumbnail-cache LRU pruners, and four age-based temp
sweepers, were separate copies; only the thumbnail pruner refused a symlinked
directory, and the temp sweepers followed symlinks via stat()/rmtree. Both
shapes now live in core/dir_sweep.py and never follow a symlink.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_disk_prune import ChunkDiskPruneMixin  # noqa: E402
from core.dir_sweep import prune_directory_lru, reap_older_than  # noqa: E402


def _file(path: Path, size: int, age_s: float) -> Path:
    path.write_bytes(b"x" * size)
    then = time.time() - age_s
    os.utime(path, (then, then))
    return path


def test_lru_prune_deletes_oldest_first_until_within_budget(tmp_path):
    oldest = _file(tmp_path / "a", 100, 300)
    middle = _file(tmp_path / "b", 100, 200)
    newest = _file(tmp_path / "c", 100, 100)

    assert prune_directory_lru(tmp_path, 150, label="test") == (2, 200)

    assert not oldest.exists() and not middle.exists()
    assert newest.exists()


def test_lru_prune_never_evicts_keep_and_ignores_skipped_entries(tmp_path):
    kept = _file(tmp_path / "kept", 100, 300)
    live = _file(tmp_path / ".tmp-live", 1000, 400)
    other = _file(tmp_path / "other", 100, 200)

    deleted = prune_directory_lru(
        tmp_path, 150, label="test", keep=kept, skip=lambda p: p.name.startswith(".tmp-")
    )

    assert deleted == (1, 100)
    assert kept.exists() and live.exists()
    assert not other.exists()


def test_chunk_prune_now_refuses_a_symlinked_directory(tmp_path):
    """Only the thumbnail copy had this guard before (#6629)."""
    real = tmp_path / "real"
    real.mkdir()
    target = _file(real / "chunk.wav", 100, 300)
    link = tmp_path / "chunks"
    link.symlink_to(real, target_is_directory=True)

    assert ChunkDiskPruneMixin.prune_chunk_directory(link, 0) == (0, 0)
    assert target.exists()


def test_lru_prune_does_not_count_or_delete_through_symlinked_files(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    big = _file(outside / "big", 10_000, 300)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "link").symlink_to(big)
    own = _file(cache / "own", 100, 100)

    assert prune_directory_lru(cache, 150, label="test") == (0, 0)
    assert big.exists() and own.exists()


def test_reap_removes_only_entries_older_than_the_age(tmp_path):
    old = _file(tmp_path / "old", 1, 7200)
    young = _file(tmp_path / "young", 1, 10)

    assert reap_older_than(tmp_path.iterdir(), 3600, label="test") == 1
    assert not old.exists() and young.exists()


def test_reap_with_no_age_removes_everything(tmp_path):
    _file(tmp_path / "a", 1, 0)
    _file(tmp_path / "b", 1, 0)

    assert reap_older_than(tmp_path.iterdir(), 0, label="test") == 2
    assert list(tmp_path.iterdir()) == []


def test_reap_unlinks_a_symlinked_dir_without_touching_its_target(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    precious = _file(target / "precious", 1, 7200)
    sweep = tmp_path / "sweep"
    sweep.mkdir()
    link = sweep / "link"
    link.symlink_to(target, target_is_directory=True)
    then = time.time() - 7200
    os.utime(link, (then, then), follow_symlinks=False)

    assert reap_older_than(sweep.iterdir(), 3600, label="test", remove_dirs=True) == 1
    assert not link.is_symlink()
    assert precious.exists()


def test_reap_skips_directories_unless_asked(tmp_path):
    stale_dir = tmp_path / "stale"
    stale_dir.mkdir()
    then = time.time() - 7200
    os.utime(stale_dir, (then, then))

    assert reap_older_than(tmp_path.iterdir(), 3600, label="test") == 0
    assert stale_dir.exists()
    assert reap_older_than(tmp_path.iterdir(), 3600, label="test", remove_dirs=True) == 1
    assert not stale_dir.exists()


def test_reap_of_a_missing_directory_is_quiet(tmp_path):
    assert reap_older_than((tmp_path / "missing").glob("*"), 0, label="test") == 0
