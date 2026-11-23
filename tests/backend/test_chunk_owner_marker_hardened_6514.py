"""The chunk-cache owner marker is not trusted from, or written through, the shared temp root (#6514).

The marker lives directly in tempfile.gettempdir(). It was read with read_text() and written with
write_text(): another account's pre-created marker naming a live PID suppressed this user's
startup wipe, and a symlink there made the write follow it. Only this user's own regular file now
counts, and it is written 0600 with O_NOFOLLOW.
"""

import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import owner_marker  # noqa: E402
from config.startup.tempfiles import claim_chunk_cache  # noqa: E402


@pytest.fixture
def paths(tmp_path):
    return tmp_path / "auralis_chunks", tmp_path / "auralis_chunks.owner"


def test_a_symlinked_marker_is_neither_trusted_nor_followed(paths, tmp_path):
    chunk_dir, marker = paths
    victim = tmp_path / "victim.conf"
    victim.write_text(str(os.getppid()))  # a live PID, so a followed read would block the wipe
    marker.symlink_to(victim)

    assert claim_chunk_cache(chunk_dir, marker) is True
    assert victim.read_text() == str(os.getppid())  # never truncated or overwritten
    assert marker.is_symlink()


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="POSIX ownership")
def test_another_users_marker_naming_a_live_pid_does_not_suppress_the_wipe(paths, monkeypatch):
    chunk_dir, marker = paths
    marker.write_text(str(os.getppid()))
    real_uid = os.getuid()
    monkeypatch.setattr(owner_marker.os, "getuid", lambda: real_uid + 1)  # the file now reads as foreign

    assert claim_chunk_cache(chunk_dir, marker) is True
    assert marker.read_text() == str(os.getppid())  # and is not written into


def test_the_claim_writes_an_owner_only_marker(paths):
    chunk_dir, marker = paths

    assert claim_chunk_cache(chunk_dir, marker) is True

    assert marker.read_text() == str(os.getpid())
    if hasattr(os, "fchmod"):
        assert stat.S_IMODE(marker.stat().st_mode) == 0o600
    assert owner_marker.read_owned_marker(marker) == str(os.getpid())
