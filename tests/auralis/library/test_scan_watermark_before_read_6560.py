"""The scan watermark is the file's state BEFORE its content was read (#6560).

process_single_file read the audio info and tags and only then stat()ed the file
for file_mtime / filesize. A tag edit (or any writer) landing between the read and
the stat got its NEW mtime recorded next to the OLD tags, so the next scan skipped
the file as current and the row stayed stale. The stat now comes first; a change
during the read leaves a stored mtime older than the file, and the next scan
re-reads it.

Real scanner, real FLAC file, real temp-file LibraryDatabase.
"""

import os

import numpy as np
import soundfile as sf

from auralis.library.scanner import LibraryScanner
from auralis.library.scanner.metadata_extractor import MetadataExtractor


def _write_flac(path):
    t = np.linspace(0, 0.4, int(0.4 * 44100), endpoint=False)
    tone = (np.sin(2 * np.pi * 440 * t) * 0.2).astype(np.float32)
    sf.write(str(path), np.column_stack([tone, tone]), 44100, format='FLAC')


def _scan(library_database, folder):
    return LibraryScanner(library_database).scan_directories([str(folder)], skip_existing=True)


def test_an_edit_during_the_read_is_re_read_by_the_next_scan(library_database, tmp_path, monkeypatch):
    music = tmp_path / "music"
    music.mkdir()
    song = music / "song.flac"
    _write_flac(song)
    os.utime(song, (1_700_000_000, 1_700_000_000))
    before_read = song.stat().st_mtime

    real_extract = MetadataExtractor.extract_metadata_from_file

    def edit_during_read(self, file_path):
        result = real_extract(self, file_path)
        os.utime(file_path, (1_700_000_500, 1_700_000_500))  # a tag save lands mid-read
        return result

    monkeypatch.setattr(MetadataExtractor, "extract_metadata_from_file", edit_during_read)
    first = _scan(library_database, music)
    monkeypatch.undo()

    assert first.files_added == 1
    stored = library_database.tracks.get_by_path(str(song))
    assert stored.file_mtime == before_read, "the watermark recorded the post-edit mtime"

    second = _scan(library_database, music)
    assert (second.files_skipped, second.files_updated) == (0, 1), "the edited file was skipped as current"
