"""
A moved or renamed file keeps its track row (#5880)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rescan identity was the path alone, so after a reorganisation the scanner
inserted each moved file as a fresh track and the post-scan prune deleted the
old row, taking its playlist membership, favorite flag and play count along.
The scanner now re-points the old row when a new path carries the same bytes
(size + duration) as exactly one track whose file is gone.

Real scanner, real FLAC files, real temp-file LibraryDatabase.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import shutil

import numpy as np
import soundfile as sf

from auralis.library.scanner import LibraryScanner


def _write_flac(path, *, duration: float, freq: float = 440.0) -> None:
    sample_rate = 44100
    t = np.linspace(0, duration, int(duration * sample_rate), endpoint=False)
    tone = (np.sin(2 * np.pi * freq * t) * 0.2).astype(np.float32)
    sf.write(str(path), np.column_stack([tone, tone]), sample_rate, format='FLAC')


def _scan(library_database, folder):
    result = LibraryScanner(library_database).scan_directories([str(folder)], skip_existing=True)
    removed = library_database.tracks.cleanup_missing_files()  # the post-scan prune
    return result, removed


def test_renamed_file_keeps_id_playlist_favorite_and_play_count(library_database, tmp_path):
    music = tmp_path / "music"
    music.mkdir()
    _write_flac(music / "01 - old name.flac", duration=0.4)
    _scan(library_database, music)
    track = library_database.tracks.get_by_path(str(music / "01 - old name.flac"))
    playlist = library_database.playlists.create("Keepers", track_ids=[track.id])
    library_database.tracks.set_favorite(track.id, True)
    library_database.tracks.record_play(track.id)

    (music / "01 - old name.flac").rename(music / "01 - new name.flac")
    result, removed = _scan(library_database, music)

    moved = library_database.tracks.get_by_path(str(music / "01 - new name.flac"))
    assert moved is not None and moved.id == track.id
    assert library_database.tracks.get_by_path(str(music / "01 - old name.flac")) is None
    assert (result.files_added, result.files_updated, removed) == (0, 1, 0)
    assert moved.favorite is True
    assert moved.play_count == 1
    assert [t.id for t in library_database.playlists.get_by_id(playlist.id).tracks] == [track.id]
    _, total = library_database.tracks.get_all(limit=10)
    assert total == 1


def test_moved_album_folder_keeps_its_tracks(library_database, tmp_path):
    """A renamed album folder is the commonest reorganisation; the old parent is gone."""
    music = tmp_path / "music"
    (music / "Old Album").mkdir(parents=True)
    _write_flac(music / "Old Album" / "a.flac", duration=0.3)
    _write_flac(music / "Old Album" / "b.flac", duration=0.5)
    _scan(library_database, music)
    ids = {library_database.tracks.get_by_path(str(music / "Old Album" / n)).id for n in ("a.flac", "b.flac")}

    (music / "Old Album").rename(music / "New Album")
    result, _ = _scan(library_database, music)

    assert result.files_added == 0
    new_ids = {library_database.tracks.get_by_path(str(music / "New Album" / n)).id for n in ("a.flac", "b.flac")}
    assert new_ids == ids
    _, total = library_database.tracks.get_all(limit=10)
    assert total == 2


def test_deleted_file_is_still_pruned_and_a_new_file_still_added(library_database, tmp_path):
    music = tmp_path / "music"
    music.mkdir()
    _write_flac(music / "gone.flac", duration=0.3)
    _scan(library_database, music)
    gone_id = library_database.tracks.get_by_path(str(music / "gone.flac")).id

    (music / "gone.flac").unlink()
    _write_flac(music / "different.flac", duration=0.6)  # other bytes: not a move
    result, removed = _scan(library_database, music)

    assert (result.files_added, removed) == (1, 1)
    assert library_database.tracks.get_by_id(gone_id) is None


def test_ambiguous_match_is_not_relocated(library_database, tmp_path):
    """Two vanished identical copies: neither is guessed; the new file is added."""
    music = tmp_path / "music"
    music.mkdir()
    _write_flac(music / "copy1.flac", duration=0.3)
    shutil.copy(music / "copy1.flac", music / "copy2.flac")
    _scan(library_database, music)
    old_ids = {library_database.tracks.get_by_path(str(music / n)).id for n in ("copy1.flac", "copy2.flac")}

    (music / "copy1.flac").rename(music / "only.flac")
    (music / "copy2.flac").unlink()
    result, removed = _scan(library_database, music)

    assert (result.files_added, removed) == (1, 2)
    assert library_database.tracks.get_by_path(str(music / "only.flac")).id not in old_ids
