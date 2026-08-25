# -*- coding: utf-8 -*-

"""
The startup temp sweeps respect a concurrently-running instance (#4713)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`reclaim_leftover_stream_temps` globbed `auralis_stream_*` across the whole
system temp root and `rmtree`d every match with no age, PID or ownership check.
The `auralis_chunks` wipe immediately above it did the same. Both assumed
exactly one backend process ever exists — so a developer running
`main.py --dev` on an alternate port while the packaged Electron app was open
deleted the *live* temp WAVs and cached chunks of the running instance,
producing mid-playback file-not-found errors in the other process.

Two different guards, deliberately:

- Stream temp dirs are PID-tagged by the producer, with an mtime fallback for
  untagged (pre-#4713) directories whose ownership is unknowable.
- The chunk cache uses an ownership marker rather than age, because making that
  wipe age-conditional would change #4666's blast radius (the on-disk chunk
  cache is not keyed on mastering targets) from intra-session to cross-session.
  A lone instance must still wipe on every start.
"""

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.limits import (  # noqa: E402
    CHUNK_TEMP_DIRNAME,
    CHUNK_TEMP_OWNER_FILENAME,
    SEEKABLE_TEMP_PREFIX,
    STREAM_TEMP_PREFIX,
    owning_pid_from_stream_temp_name,
    stream_temp_prefix,
)
from config.startup import (  # noqa: E402
    claim_chunk_cache,
    pid_is_alive,
    reclaim_leftover_stream_temps,
)

# A PID that cannot be live: max_pid+1 on Linux, and never a real process id.
DEAD_PID = 4_000_000


def _make_stream_dir(root: Path, name: str, age_hours: float = 0.0) -> Path:
    d = root / name
    d.mkdir()
    (d / "stream.wav").write_bytes(b"\x00\x01\x02")
    if age_hours:
        stale = time.time() - (age_hours * 3600)
        os.utime(d, (stale, stale))
    return d


class TestStreamTempNaming:
    """CONSISTENCY: the producer and the sweeper must agree on the name."""

    def test_prefix_is_pid_tagged(self):
        assert stream_temp_prefix().startswith(STREAM_TEMP_PREFIX)
        assert stream_temp_prefix() == f"{STREAM_TEMP_PREFIX}{os.getpid()}_"

    def test_round_trips_through_the_parser(self):
        # mkdtemp appends its own random suffix after our prefix.
        name = stream_temp_prefix(pid=1234) + "ab3f9x"
        assert owning_pid_from_stream_temp_name(name) == 1234

    def test_untagged_legacy_name_parses_as_unknown(self):
        # Pre-#4713 names were `auralis_stream_<mkdtemp suffix>`.
        assert owning_pid_from_stream_temp_name("auralis_stream_aaa") is None
        assert owning_pid_from_stream_temp_name("auralis_stream_8f2c1d") is None

    def test_numeric_mkdtemp_suffix_is_not_mistaken_for_a_pid(self):
        """`auralis_stream_827361` is an untagged dir whose random suffix is all
        digits — treating it as a PID would resurrect the bug for that name."""
        assert owning_pid_from_stream_temp_name("auralis_stream_827361") is None

    def test_unrelated_name_returns_none(self):
        assert owning_pid_from_stream_temp_name(CHUNK_TEMP_DIRNAME) is None

    def test_producer_uses_the_shared_prefix(self):
        """WIRING: if stream_normal.py stops using stream_temp_prefix(), the
        sweep can never recognise a directory as owned."""
        backend = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
        source = (backend / "core" / "stream_normal.py").read_text()

        assert "stream_temp_prefix()" in source
        assert "prefix='auralis_stream_'" not in source


class TestSeekableTempPrefixWiring:
    """WIRING (#5253): if seekable_source.py stops using the shared
    SEEKABLE_TEMP_PREFIX constant, the sweep can never recognise its temp
    dirs as belonging to it — the producer and the sweeper must agree,
    exactly like TestStreamTempNaming.test_producer_uses_the_shared_prefix
    above does for the stream-temp prefix."""

    def test_producer_uses_the_shared_prefix(self):
        backend = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
        source = (backend / "core" / "seekable_source.py").read_text()

        assert "SEEKABLE_TEMP_PREFIX" in source
        assert 'prefix: str = "auralis_seekable_"' not in source


class TestSeekableTempSweep:
    """#5253: auralis_seekable_* directories (SeekableSource.convert_to_temp_wav,
    #4737) leaked unconditionally — not just on a crash — because neither
    stream_seek.py nor stream_enhanced.py ever called processor.close(), and
    the startup sweep never globbed this prefix at all. Both halves of the
    fix (the .close() calls and this sweep) are independent backstops for
    the same leak."""

    def test_fresh_seekable_dir_is_skipped(self, tmp_path):
        fresh = _make_stream_dir(tmp_path, f"{SEEKABLE_TEMP_PREFIX}fresh")

        assert reclaim_leftover_stream_temps(tmp_path) == 0
        assert fresh.exists()

    def test_aged_seekable_dir_is_reclaimed(self, tmp_path):
        aged = _make_stream_dir(tmp_path, f"{SEEKABLE_TEMP_PREFIX}aged", age_hours=2.0)

        assert reclaim_leftover_stream_temps(tmp_path) == 1
        assert not aged.exists()

    def test_mixed_stream_and_seekable_dirs_both_swept(self, tmp_path):
        """One sweep call must cover both prefixes, not just one or the
        other — a regression that narrowed the glob back to a single
        prefix would still pass every other test in this file."""
        aged_stream = _make_stream_dir(tmp_path, "auralis_stream_aged", age_hours=2.0)
        aged_seekable = _make_stream_dir(tmp_path, f"{SEEKABLE_TEMP_PREFIX}aged", age_hours=2.0)
        fresh_seekable = _make_stream_dir(tmp_path, f"{SEEKABLE_TEMP_PREFIX}fresh")

        assert reclaim_leftover_stream_temps(tmp_path) == 2
        assert not aged_stream.exists()
        assert not aged_seekable.exists()
        assert fresh_seekable.exists()

    def test_seekable_prefix_has_no_pid_tag_so_falls_to_age_heuristic(self):
        """SeekableSource never adopted the #4713 PID-tagging scheme, so
        parsing one of its directory names must return None (ownership
        unknowable) rather than misidentifying it as an auralis_stream_*
        name — which is exactly what routes it to the safe age fallback
        instead of the PID-liveness branch."""
        assert owning_pid_from_stream_temp_name(f"{SEEKABLE_TEMP_PREFIX}abc123") is None


class TestStreamTempSweepOwnership:
    """Test-plan item 2: live PID kept, dead PID reclaimed."""

    def test_live_pid_dir_is_not_reclaimed(self, tmp_path):
        mine = _make_stream_dir(tmp_path, stream_temp_prefix() + "abc")

        assert reclaim_leftover_stream_temps(tmp_path) == 0
        assert mine.exists(), "a live instance's temp WAV dir must survive"

    def test_live_pid_dir_survives_even_when_old(self, tmp_path):
        """A long audiobook or DJ set legitimately holds one open for hours, so
        the PID check must win over the age fallback."""
        mine = _make_stream_dir(tmp_path, stream_temp_prefix() + "abc", age_hours=48.0)

        assert reclaim_leftover_stream_temps(tmp_path) == 0
        assert mine.exists()

    def test_dead_pid_dir_is_reclaimed_immediately(self, tmp_path):
        """Exact ownership beats the heuristic: no need to wait out the age."""
        orphan = _make_stream_dir(tmp_path, stream_temp_prefix(pid=DEAD_PID) + "xyz")

        assert reclaim_leftover_stream_temps(tmp_path) == 1
        assert not orphan.exists()

    def test_mixed_set_reclaims_only_the_orphans(self, tmp_path):
        mine = _make_stream_dir(tmp_path, stream_temp_prefix() + "live")
        dead = _make_stream_dir(tmp_path, stream_temp_prefix(pid=DEAD_PID) + "dead")
        fresh_untagged = _make_stream_dir(tmp_path, "auralis_stream_fresh")
        aged_untagged = _make_stream_dir(tmp_path, "auralis_stream_aged", age_hours=2.0)

        assert reclaim_leftover_stream_temps(tmp_path) == 2

        assert mine.exists()
        assert fresh_untagged.exists()
        assert not dead.exists()
        assert not aged_untagged.exists()


class TestUntaggedAgeFallback:
    """Test-plan item 1: one fresh and one aged untagged dir."""

    def test_fresh_untagged_dir_is_skipped(self, tmp_path):
        fresh = _make_stream_dir(tmp_path, "auralis_stream_fresh")

        assert reclaim_leftover_stream_temps(tmp_path) == 0
        assert fresh.exists()

    def test_aged_untagged_dir_is_reclaimed(self, tmp_path):
        aged = _make_stream_dir(tmp_path, "auralis_stream_aged", age_hours=2.0)

        assert reclaim_leftover_stream_temps(tmp_path) == 1
        assert not aged.exists()

    def test_age_threshold_is_configurable(self, tmp_path):
        half_hour_old = _make_stream_dir(tmp_path, "auralis_stream_x", age_hours=0.5)

        assert reclaim_leftover_stream_temps(tmp_path, max_age_hours=1.0) == 0
        assert reclaim_leftover_stream_temps(tmp_path, max_age_hours=0.25) == 1
        assert not half_hour_old.exists()


class TestReclaimCountAndLogging:
    """RETURN VALUE: the count must report reclaimed, never skipped."""

    def test_count_excludes_skipped_dirs(self, tmp_path):
        _make_stream_dir(tmp_path, stream_temp_prefix() + "live")
        _make_stream_dir(tmp_path, "auralis_stream_fresh")
        _make_stream_dir(tmp_path, stream_temp_prefix(pid=DEAD_PID) + "dead")

        assert reclaim_leftover_stream_temps(tmp_path) == 1

    def test_info_line_only_fires_when_something_was_reclaimed(self, tmp_path, caplog):
        _make_stream_dir(tmp_path, stream_temp_prefix() + "live")

        with caplog.at_level(logging.INFO, logger="config.startup"):
            count = reclaim_leftover_stream_temps(tmp_path)

        assert count == 0
        assert not [r for r in caplog.records if "Reclaimed" in r.message]

    def test_info_line_reports_the_reclaimed_count(self, tmp_path, caplog):
        _make_stream_dir(tmp_path, stream_temp_prefix(pid=DEAD_PID) + "dead")

        with caplog.at_level(logging.INFO, logger="config.startup"):
            count = reclaim_leftover_stream_temps(tmp_path)

        assert count == 1
        assert [r for r in caplog.records if "Reclaimed 1" in r.message]


class TestPidLiveness:
    def test_current_process_is_alive(self):
        assert pid_is_alive(os.getpid()) is True

    def test_dead_pid_is_not_alive(self):
        assert pid_is_alive(DEAD_PID) is False

    def test_probe_failure_fails_safe(self, monkeypatch):
        """An unavailable probe must answer 'alive' so the sweep skips rather
        than deletes — never the other way round."""
        # `sys.modules[name] = None` makes `import name` raise ImportError.
        monkeypatch.setitem(sys.modules, "psutil", None)

        assert pid_is_alive(DEAD_PID) is True


class TestChunkCacheOwnership:
    """SIBLING: the auralis_chunks wipe had the identical assumption."""

    def _paths(self, tmp_path):
        return tmp_path / CHUNK_TEMP_DIRNAME, tmp_path / CHUNK_TEMP_OWNER_FILENAME

    def test_lone_instance_still_wipes(self, tmp_path):
        """The single-instance case must be unchanged, or #4666's stale-chunk
        blast radius silently widens from intra-session to cross-session."""
        chunk_dir, marker = self._paths(tmp_path)
        chunk_dir.mkdir()

        assert claim_chunk_cache(chunk_dir, marker) is True

    def test_no_marker_means_wipe(self, tmp_path):
        chunk_dir, marker = self._paths(tmp_path)

        assert claim_chunk_cache(chunk_dir, marker) is True
        assert marker.read_text() == str(os.getpid())

    def test_stale_marker_from_dead_pid_means_wipe(self, tmp_path):
        chunk_dir, marker = self._paths(tmp_path)
        marker.write_text(str(DEAD_PID))

        assert claim_chunk_cache(chunk_dir, marker) is True
        assert marker.read_text() == str(os.getpid())

    def test_live_foreign_owner_blocks_the_wipe(self, tmp_path, monkeypatch):
        chunk_dir, marker = self._paths(tmp_path)
        chunk_dir.mkdir()
        # A live PID that is not us: pretend the parent process owns it.
        foreign = os.getpid() + 1
        monkeypatch.setattr(
            "config.startup.pid_is_alive", lambda pid: pid == foreign
        )
        marker.write_text(str(foreign))

        assert claim_chunk_cache(chunk_dir, marker) is False

    def test_our_own_stale_marker_does_not_block_us(self, tmp_path):
        """A restart of the same PID (or a re-run in-process) must still wipe."""
        chunk_dir, marker = self._paths(tmp_path)
        marker.write_text(str(os.getpid()))

        assert claim_chunk_cache(chunk_dir, marker) is True

    def test_corrupt_marker_is_treated_as_unowned(self, tmp_path):
        chunk_dir, marker = self._paths(tmp_path)
        marker.write_text("not-a-pid")

        assert claim_chunk_cache(chunk_dir, marker) is True
        assert marker.read_text() == str(os.getpid())

    def test_marker_lives_outside_the_chunk_dir(self, tmp_path):
        """ChunkCacheManager.prune_chunk_directory deletes the oldest file in
        the chunk dir by mtime — a marker stored inside would be eaten."""
        chunk_dir, marker = self._paths(tmp_path)
        chunk_dir.mkdir()

        claim_chunk_cache(chunk_dir, marker)

        assert marker.exists()
        assert marker.parent == chunk_dir.parent
        assert list(chunk_dir.iterdir()) == []


class TestNoUnconditionalSweepRemains:
    def test_sweep_is_not_an_unguarded_rmtree_loop(self):
        backend = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
        source = (backend / "config" / "startup.py").read_text()

        assert 'for leftover in temp_root.glob("auralis_stream_*")' not in source, (
            "the hardcoded, unguarded glob is back — see #4713"
        )
        assert "claim_chunk_cache" in source
