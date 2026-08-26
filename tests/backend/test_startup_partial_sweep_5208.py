# -*- coding: utf-8 -*-

"""
The startup temp sweep reaps orphaned `.part` staging files (#5208)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`atomic_io.cleanup_partial_files()` shipped with the #4576 staged-write fix but
was never called from anywhere except its own test, so the crash-recovery half
of that design was inert.

The gap it left was narrow but real. `_cleanup_temp_directories()` has two
branches, and only one of them cleaned anything:

- Lone instance (every packaged Electron run): `claim_chunk_cache()` returns
  True and the whole chunk dir is `rmtree`d, partials included — unless the
  wipe raises, which it only warns about.
- A *live* second backend owns the cache (#4713): the directory is left
  untouched, so staging files orphaned by a crashed sibling accumulated there
  across every restart with nothing to reap them.

The second branch is also why the sweep is age-gated rather than
unconditional: a staging file is indistinguishable by name from one the live
instance is still filling, and deleting that would make its `os.replace()` fail.
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.limits import (  # noqa: E402
    CHUNK_TEMP_DIRNAME,
    CHUNK_TEMP_OWNER_FILENAME,
)
from config import startup as startup_mod  # noqa: E402
from core.encoding.atomic_io import (  # noqa: E402
    PARTIAL_MAX_AGE_SECONDS,
    PARTIAL_SUFFIX,
)

DEAD_PID = 4_000_000


def _partial(directory: Path, tag: str, age_seconds: float = 0.0) -> Path:
    p = directory / f".track_1_chunk_0.wav.{tag}{PARTIAL_SUFFIX}.wav"
    p.write_bytes(b"staged bytes")
    if age_seconds:
        stamp = time.time() - age_seconds
        os.utime(p, (stamp, stamp))
    return p


def _run_sweep(temp_root: Path) -> None:
    with mock.patch.object(startup_mod.tempfile, "gettempdir", return_value=str(temp_root)):
        asyncio.run(startup_mod._cleanup_temp_directories())


def test_sweep_targets_the_directory_atomic_save_audio_stages_into(tmp_path):
    """The sweep and the writers must agree on the directory.

    Both production writers (core/chunk_batch.py and
    core/encoding/wav_encoder.py) stage into `ChunkedAudioProcessor.chunk_dir`,
    which is `gettempdir() / CHUNK_TEMP_DIRNAME`. A mismatch would make the
    sweep a silent no-op.
    """
    chunk_dir = tmp_path / CHUNK_TEMP_DIRNAME
    chunk_dir.mkdir()
    orphan = _partial(chunk_dir, "dead")

    _run_sweep(tmp_path)

    assert not orphan.exists()


def test_partials_are_swept_when_the_wipe_is_skipped(tmp_path):
    """A live foreign owner blocks the wipe; stale partials must still go.

    This is the branch that previously neither wiped nor swept.
    """
    chunk_dir = tmp_path / CHUNK_TEMP_DIRNAME
    chunk_dir.mkdir()
    keep = chunk_dir / "track_1_chunk_0.wav"
    keep.write_bytes(b"a published cache entry")
    stale = _partial(chunk_dir, "orphan", age_seconds=PARTIAL_MAX_AGE_SECONDS * 2)

    with mock.patch.object(startup_mod, "claim_chunk_cache", return_value=False):
        _run_sweep(tmp_path)

    assert not stale.exists(), "orphaned partial survived the sweep"
    assert keep.exists(), "the sweep must not touch published cache entries"


def test_an_in_flight_partial_is_spared_while_another_backend_is_live(tmp_path):
    """Deleting a partial the live owner is still writing breaks its rename."""
    chunk_dir = tmp_path / CHUNK_TEMP_DIRNAME
    chunk_dir.mkdir()
    in_flight = _partial(chunk_dir, "live")

    with mock.patch.object(startup_mod, "claim_chunk_cache", return_value=False):
        _run_sweep(tmp_path)

    assert in_flight.exists(), "reaped a staging file another instance may be writing"


def test_partials_swept_when_the_wipe_raises(tmp_path):
    """rmtree failure only warns, so the sweep is the remaining safety net."""
    chunk_dir = tmp_path / CHUNK_TEMP_DIRNAME
    chunk_dir.mkdir()
    orphan = _partial(chunk_dir, "dead")

    def _boom(*_args, **_kwargs):
        raise OSError("permission denied")

    with mock.patch.object(startup_mod.shutil, "rmtree", _boom):
        _run_sweep(tmp_path)

    assert not orphan.exists()


def test_owner_marker_from_a_dead_pid_still_wipes(tmp_path):
    """The lone-instance path: a dead previous owner must not block the wipe."""
    chunk_dir = tmp_path / CHUNK_TEMP_DIRNAME
    chunk_dir.mkdir()
    _partial(chunk_dir, "dead")
    (tmp_path / CHUNK_TEMP_OWNER_FILENAME).write_text(str(DEAD_PID))

    _run_sweep(tmp_path)

    assert list(chunk_dir.glob(f"*{PARTIAL_SUFFIX}*")) == []


def test_missing_chunk_dir_is_not_an_error(tmp_path):
    _run_sweep(tmp_path)  # must not raise
