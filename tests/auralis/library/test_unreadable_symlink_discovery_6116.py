"""One bad directory entry no longer aborts discovery of its whole directory (#6116).

``DirEntry.is_dir()/is_file()`` swallow only FileNotFoundError. For a symlink
they stat() the target, so a looping link (ELOOP) or one into an unsearchable
directory raised inside the single try that wrapped the whole scandir loop, and
every later sibling and subdirectory was silently lost.
"""

import os
from unittest.mock import patch

import pytest

from auralis.library.scanner.file_discovery import FileDiscovery


def _discover(root):
    discovery = FileDiscovery()
    errors: list[tuple[str, str]] = []
    discovery.on_directory_error = lambda path, reason: errors.append((path, reason))
    return sorted(os.path.basename(f) for f in discovery.discover_audio_files(str(root))), errors


@pytest.mark.skipif(os.name != "posix", reason="symlinks")
def test_a_looping_symlink_does_not_hide_its_siblings_or_later_subdirectories(tmp_path):
    for name in ("a.flac", "b.flac", "c.flac"):
        (tmp_path / name).write_bytes(b"")
    os.symlink("loop", tmp_path / "loop")  # ln -s loop loop
    (tmp_path / "zz_sub").mkdir()  # scanned after the bad entry, on most filesystems
    (tmp_path / "zz_sub" / "deep.flac").write_bytes(b"")
    (tmp_path / "aa_sub").mkdir()
    (tmp_path / "aa_sub" / "early.flac").write_bytes(b"")

    files, errors = _discover(tmp_path)

    assert files == ["a.flac", "b.flac", "c.flac", "deep.flac", "early.flac"]
    # A loop holds no files, so it must not mark the walk incomplete (that would
    # disable pruning for good, #5877).
    assert errors == []


@pytest.mark.skipif(os.name != "posix", reason="symlinks")
def test_a_loop_is_logged_by_name(tmp_path):
    (tmp_path / "a.flac").write_bytes(b"")
    os.symlink("loop", tmp_path / "loop")

    with patch("auralis.library.scanner.file_discovery.warning") as warn:
        _discover(tmp_path)

    assert any("loop" in str(c.args[0]) for c in warn.call_args_list)


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions as non-root")
def test_a_symlink_into_an_unsearchable_directory_skips_only_that_entry(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "inner").mkdir()
    os.symlink(locked / "inner", tmp_path / "link")
    (tmp_path / "a.flac").write_bytes(b"")
    (tmp_path / "later").mkdir()
    (tmp_path / "later" / "b.flac").write_bytes(b"")
    locked.chmod(0)
    try:
        files, errors = _discover(tmp_path)
    finally:
        locked.chmod(0o755)

    assert "a.flac" in files and "b.flac" in files
    # `locked` itself and the link into it are unreadable: both are reported,
    # because files may be hiding behind them.
    assert any("link" in path for path, _ in errors)
