"""
cleanup_missing_files must not delete on unreadable folders (#5698)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Path.exists()`` swallows every OSError, so a folder the process cannot
read (EACCES: permissions change, macOS TCC revocation, sandbox) or a
dead mount (EIO/ESTALE) read as "file deleted" — and the prune removed
the tracks with their playlist rows, favourites and play counts after
every scan. The decision now goes through ``os.stat`` and only
ENOENT/ENOTDIR count as missing; anything else skips.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
from pathlib import Path

import pytest
from sqlalchemy import func, select

from auralis.library.models import Track, track_playlist
from auralis.library.repositories.track_repository_maintenance import (
    _file_is_definitely_missing,
    _track_file_is_missing,
)


def _info(path: Path, name: str) -> dict:
    return {
        'title': name, 'filepath': str(path), 'sample_rate': 44100, 'channels': 2,
        'format': 'MP3', 'artists': ['Band'], 'genres': ['Rock'], 'album': f'{name} album',
    }


def test_unreadable_folder_is_not_missing(tmp_path):
    """chmod 0 on the folder: stat fails with EACCES, not ENOENT."""
    if os.geteuid() == 0:
        pytest.skip("root bypasses permission bits")

    target = tmp_path / 'music' / 'a.flac'
    target.parent.mkdir()
    target.write_bytes(b'x')
    os.chmod(target.parent, 0)
    try:
        assert not _track_file_is_missing(target)
    finally:
        os.chmod(target.parent, 0o755)


def test_deleted_file_with_readable_parent_is_missing(tmp_path):
    gone = tmp_path / 'a.flac'
    assert _track_file_is_missing(gone)


def test_gone_parent_volume_is_not_missing(tmp_path):
    """#2525 semantics preserved: parent absent -> skip, do not delete."""
    assert not _track_file_is_missing('/nonexistent-volume/x.flac')


def test_existing_file_is_not_missing(tmp_path):
    target = tmp_path / 'a.flac'
    target.write_bytes(b'x')
    assert not _file_is_definitely_missing(target)
    assert not _track_file_is_missing(target)


def test_cleanup_skips_unreadable_folder(library_database, tmp_path):
    """The original data-loss repro: chmod 0 music dir, prune -> everything
    (tracks, playlist rows) survived."""
    if os.geteuid() == 0:
        pytest.skip("root bypasses permission bits")

    tracks = library_database.tracks
    music = tmp_path / 'music'
    music.mkdir()
    track = tracks.add(_info(music / 'a.flac', 'a'))
    track_id = int(track.id)
    playlist = library_database.playlists.create('mix')
    assert library_database.playlists.add_track(playlist.id, track_id)

    (music / 'a.flac').write_bytes(b'x')
    os.chmod(music, 0)
    try:
        removed = tracks.cleanup_missing_files()
    finally:
        os.chmod(music, 0o755)

    assert removed == 0
    assert tracks.get_by_id(track_id) is not None
    with library_database.SessionLocal() as session:
        rows = session.execute(
            select(func.count()).select_from(track_playlist)
        ).scalar_one()
        assert rows == 1


def test_cleanup_still_removes_genuinely_deleted_files(library_database, tmp_path):
    """The prune must keep working for real deletitions (ENOENT)."""
    tracks = library_database.tracks
    gone = tmp_path / 'gone'
    gone.mkdir()
    kept = tmp_path / 'kept'
    kept.mkdir()
    gone_id = int(tracks.add(_info(gone / 'a.mp3', 'a')).id)
    kept_id = int(tracks.add(_info(kept / 'b.mp3', 'b')).id)
    # Neither file exists; both parents do and are readable.

    removed = tracks.cleanup_missing_files()

    assert removed == 2
    assert tracks.get_by_id(gone_id) is None
    assert tracks.get_by_id(kept_id) is None


def test_cleanup_skips_unmounted_volume(library_database, tmp_path):
    """#2525 through the new helper: parent directory absent -> no delete."""
    tracks = library_database.tracks
    track_id = int(tracks.add(_info(tmp_path / 'usb' / 'a.flac', 'a')).id)
    # tmp_path/usb does not exist at all — the volume is away.

    removed = tracks.cleanup_missing_files()

    assert removed == 0
    assert tracks.get_by_id(track_id) is not None
