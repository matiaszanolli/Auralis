"""
create_secure_temp_dir() hardens the fixed-name temp working directories (#4855)

Five separate working directories (auralis_chunks/_processing/_uploads) used
to be created directly under the OS-shared temp root via plain
`Path.mkdir(exist_ok=True)`, with no explicit mode -- yielding world-readable
0o775/0o755 under common umasks -- and `exist_ok=True` silently followed a
pre-existing symlink at the target path rather than rejecting it (a
directory symlink stats as a directory, so the existence check that
`exist_ok=True` relies on never notices).

create_secure_temp_dir() mirrors library/database.py's existing 0o700
hardening for ~/.auralis (#4824/#4347) and adds an explicit is_symlink()
check -- which uses lstat() and so does not follow the link -- before ever
calling mkdir().
"""

import stat
import sys
from pathlib import Path

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from config.limits import create_secure_temp_dir


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_new_directory_is_owner_only(tmp_path):
    target = tmp_path / "auralis_chunks"

    create_secure_temp_dir(target)

    assert target.is_dir()
    assert _mode(target) == 0o700


def test_pre_existing_world_readable_directory_is_re_restricted(tmp_path):
    """mkdir(mode=) is ignored when the directory already exists -- a
    directory left world-readable by the old code, before this fix shipped,
    must be re-restricted on the next call, not just newly-created ones."""
    target = tmp_path / "auralis_uploads"
    target.mkdir(mode=0o755)
    assert _mode(target) == 0o755

    create_secure_temp_dir(target)

    assert _mode(target) == 0o700


def test_second_call_is_idempotent(tmp_path):
    target = tmp_path / "auralis_processing"

    create_secure_temp_dir(target)
    create_secure_temp_dir(target)

    assert target.is_dir()
    assert _mode(target) == 0o700


def test_refuses_a_pre_planted_symlink(tmp_path):
    """A symlink planted at the target path (before first launch, or after
    a /tmp clear) must be rejected, not silently followed -- unlike
    mkdir(exist_ok=True), whose existence check follows symlinks."""
    real_target = tmp_path / "attacker_controlled"
    real_target.mkdir()
    symlink_path = tmp_path / "auralis_chunks"
    symlink_path.symlink_to(real_target)

    with pytest.raises(RuntimeError, match="symlink"):
        create_secure_temp_dir(symlink_path)

    # Must not have chmod'd (or otherwise touched) the symlink's target.
    assert _mode(real_target) != 0o700
