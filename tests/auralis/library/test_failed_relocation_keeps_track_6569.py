"""A failed moved-file check neither adds a twin nor lets the prune delete the old row (#6569).

relocate_missing_track ran under _guarded, so a DB error (a lock wait past the busy
timeout, an IntegrityError) came back as None, the same as 'not a moved file'. The
scanner then added a twin at the new path, and the post-scan prune deleted the old
row whose file was gone, taking its playlist membership, favourite and play count:
the data loss #5880's relocation exists to prevent. The error now propagates, the
file is reported failed, and the scan is not prune-safe, so a later scan can still
relocate the row.

Real scanner, real FLAC files, real temp-file LibraryDatabase.
"""

import numpy as np
import soundfile as sf
from sqlalchemy.exc import OperationalError

from auralis.library.repositories import track_repository_relocation
from auralis.library.scanner import LibraryScanner


def _write_flac(path, duration=0.4):
    sample_rate = 44100
    t = np.linspace(0, duration, int(duration * sample_rate), endpoint=False)
    tone = (np.sin(2 * np.pi * 440 * t) * 0.2).astype(np.float32)
    sf.write(str(path), np.column_stack([tone, tone]), sample_rate, format='FLAC')


def _scan(library_database, folder):
    return LibraryScanner(library_database).scan_directories([str(folder)], skip_existing=True)


def test_db_error_during_relocation_keeps_the_original_row(library_database, tmp_path, monkeypatch):
    music = tmp_path / "music"
    music.mkdir()
    _write_flac(music / "old.flac")
    _scan(library_database, music)
    track = library_database.tracks.get_by_path(str(music / "old.flac"))
    playlist = library_database.playlists.create("Keepers", track_ids=[track.id])
    library_database.tracks.set_favorite(track.id, True)

    (music / "old.flac").rename(music / "new.flac")

    def locked(*_args, **_kwargs):
        raise OperationalError("UPDATE tracks", {}, Exception("database is locked"))

    monkeypatch.setattr(track_repository_relocation, "make_filepath_key", locked)
    result = _scan(library_database, music)

    assert (result.files_added, result.files_failed) == (0, 1)
    assert "moved file" in result.failures[0].reason
    assert result.prune_safe is False
    # No twin at the new path, and the old row (playlist, favourite) is untouched.
    assert library_database.tracks.get_by_path(str(music / "new.flac")) is None
    kept = library_database.tracks.get_by_id(track.id)
    assert kept is not None and kept.favorite is True
    assert [t.id for t in library_database.playlists.get_by_id(playlist.id).tracks] == [track.id]

    # Once the database is healthy again, the next scan relocates the same row.
    monkeypatch.undo()
    retry = _scan(library_database, music)
    assert (retry.files_added, retry.files_updated, retry.prune_safe) == (0, 1, True)
    assert library_database.tracks.get_by_path(str(music / "new.flac")).id == track.id
