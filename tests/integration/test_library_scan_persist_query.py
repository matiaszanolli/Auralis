#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Library Scan -> Persist -> Query Integration Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Re-establishes the coverage removed in #4041: tests/integration/test_library_integration.py
carried 16 tests that had been permanently skipped (>6 months) as DEPRECATED
against a pre-#4619 API — the old ``scan_folder()`` tuple return
``(added, skipped, errors)`` is now ``list[dict]``, and ``TrackRepository.get_all()``
replaced the deleted ``LibraryManager`` facade's ``add_track()``/``get_all_tracks()``
(#4915) — plus one ``test_summary_stats()`` that only printed a stale count.
Zero running coverage resulted (#4234).

Exercises the real production pipeline against the CURRENT API:

- Scan-add / dedup / metadata persistence: the actual production path —
  ``LibraryScanner.scan_directories()`` -> ``BatchProcessor.process_single_file()``
  -> ``TrackRepository.get_by_path()`` (dedup check) / ``.add()`` — using real,
  decodable FLAC files with embedded Vorbis comments so extraction is exercised
  end to end, not just the DB write.
- Query/pagination, search, album grouping, metadata edit, favorites, deletion,
  and read-after-write consistency: directly against ``TrackRepository`` /
  ``AlbumRepository`` via the ``library_database`` fixture (a real
  ``LibraryDatabase`` backed by a temp SQLite file — see tests/conftest.py),
  adding synthetic tracks with ``TrackRepository.add()`` where a real audio
  file isn't the point of the test.

Basic scan mechanics (file discovery, re-scan skip counting) already have
dedicated coverage in tests/auralis/library/test_folder_scanner.py and
tests/auralis/library/test_scanner_concurrency.py; this file focuses on the
persist -> query half of the pipeline the deleted file used to cover.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import numpy as np
import pytest
import soundfile as sf
from mutagen.flac import FLAC

from auralis.library.scanner import LibraryScanner

pytestmark = pytest.mark.integration


def _write_flac(path, *, title=None, artist=None, album=None, genre=None,
                 duration=0.3, sample_rate=44100, freq=440.0):
    """Write a real, decodable FLAC file with optional embedded tags.

    A short sine wave is enough for AudioAnalyzer to extract real duration/
    sample_rate/channels — the point is exercising extraction, not audio
    content.
    """
    samples = int(duration * sample_rate)
    t = np.linspace(0, duration, samples, endpoint=False)
    tone = (np.sin(2 * np.pi * freq * t) * 0.2).astype(np.float32)
    audio = np.column_stack([tone, tone])
    sf.write(str(path), audio, sample_rate, format='FLAC')

    if title or artist or album or genre:
        tags = FLAC(str(path))
        if title:
            tags['title'] = title
        if artist:
            tags['artist'] = artist
        if album:
            tags['album'] = album
        if genre:
            tags['genre'] = genre
        tags.save()


def _add_track(tracks_repo, *, filepath, title, artists=None, album=None,
                genres=None, duration=180.0, sample_rate=44100, channels=2,
                format='FLAC', **extra):
    """Add a synthetic track directly via TrackRepository.add() — no file
    needs to exist on disk since format/sample_rate/channels are supplied
    explicitly, short-circuiting add()'s soundfile.info() fallback."""
    track_info = {
        'filepath': filepath,
        'title': title,
        'artists': artists or [],
        'duration': duration,
        'sample_rate': sample_rate,
        'channels': channels,
        'format': format,
        **extra,
    }
    if album:
        track_info['album'] = album
    if genres:
        track_info['genres'] = genres
    track = tracks_repo.add(track_info)
    assert track is not None, f"failed to add track {title!r}"
    return track


class TestScanAddAndDedup:
    """LibraryScanner.scan_directories() -> BatchProcessor -> TrackRepository."""

    def test_scan_persists_tracks_queryable_afterward(self, library_database, tmp_path):
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        _write_flac(music_dir / "01.flac", title="Song One", artist="Band A", album="Album A")
        _write_flac(music_dir / "02.flac", title="Song Two", artist="Band A", album="Album A")

        scanner = LibraryScanner(library_database)
        result = scanner.scan_directories([str(music_dir)])

        assert result.files_added == 2
        tracks, total = library_database.tracks.get_all(limit=50)
        assert total == 2
        assert {t.title for t in tracks} == {"Song One", "Song Two"}

    def test_rescan_dedups_via_get_by_path(self, library_database, tmp_path):
        """A second scan of the same directory must not create duplicate rows.

        Exercises the real dedup check (BatchProcessor -> TrackRepository.get_by_path())
        rather than asserting on ScanResult counters alone.
        """
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        _write_flac(music_dir / "01.flac", title="Song", artist="Band", album="Album")

        scanner = LibraryScanner(library_database)
        first = scanner.scan_directories([str(music_dir)])
        assert first.files_added == 1

        second = scanner.scan_directories([str(music_dir)], skip_existing=True)
        assert second.files_added == 0
        assert second.files_skipped == 1

        tracks, total = library_database.tracks.get_all(limit=50)
        assert total == 1, "rescan must not create a duplicate row for the same file"
        assert library_database.tracks.get_by_path(str(music_dir / "01.flac")) is not None


class TestMetadataPersistence:
    """Embedded tags survive extraction, DB persistence, and re-query."""

    def test_embedded_tags_round_trip_through_scan(self, library_database, tmp_path):
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        _write_flac(
            music_dir / "track.flac",
            title="Persisted Title", artist="Persisted Artist",
            album="Persisted Album", genre="Ambient",
            duration=1.5, sample_rate=48000,
        )

        scanner = LibraryScanner(library_database)
        result = scanner.scan_directories([str(music_dir)])
        assert result.files_added == 1

        tracks, _ = library_database.tracks.get_all(limit=10)
        assert len(tracks) == 1
        track = tracks[0]

        assert track.title == "Persisted Title"
        assert track.duration == pytest.approx(1.5, abs=0.1)
        assert track.sample_rate == 48000
        assert track.channels == 2
        assert [a.name for a in track.artists] == ["Persisted Artist"]
        assert track.album is not None and track.album.title == "Persisted Album"
        assert [g.name for g in track.genres] == ["Ambient"]


class TestQueryAndPagination:
    def test_get_all_paginates_without_overlap_or_gaps(self, library_database):
        tracks_repo = library_database.tracks
        for i in range(5):
            _add_track(
                tracks_repo, filepath=f"/music/page_{i}.flac",
                title=f"Track {i:02d}", artists=["Pager"],
            )

        page1, total1 = tracks_repo.get_all(limit=2, offset=0)
        page2, total2 = tracks_repo.get_all(limit=2, offset=2)
        page3, total3 = tracks_repo.get_all(limit=2, offset=4)

        assert total1 == total2 == total3 == 5
        assert [t.title for t in page1] == ["Track 00", "Track 01"]
        assert [t.title for t in page2] == ["Track 02", "Track 03"]
        assert [t.title for t in page3] == ["Track 04"]

        # No page overlaps another and every track is covered exactly once.
        seen_ids = [t.id for t in (*page1, *page2, *page3)]
        assert len(seen_ids) == len(set(seen_ids)) == 5


class TestSearch:
    def test_search_matches_title_artist_and_album(self, library_database):
        tracks_repo = library_database.tracks
        _add_track(
            tracks_repo, filepath="/music/searchable_title.flac",
            title="Searchable Nightfall", artists=["Someone Else"],
        )
        _add_track(
            tracks_repo, filepath="/music/searchable_artist.flac",
            title="Unrelated", artists=["Nightfall Collective"],
        )
        _add_track(
            tracks_repo, filepath="/music/searchable_album.flac",
            title="Also Unrelated", artists=["Nobody"], album="Nightfall Sessions",
        )
        _add_track(
            tracks_repo, filepath="/music/no_match.flac",
            title="Completely Different", artists=["Irrelevant"],
        )

        results, total = tracks_repo.search("nightfall")

        assert total == 3
        titles = {t.title for t in results}
        assert titles == {"Searchable Nightfall", "Unrelated", "Also Unrelated"}

    def test_search_escapes_like_metacharacters(self, library_database):
        """A literal '%' in the query must not match every row (fixes #2405)."""
        tracks_repo = library_database.tracks
        _add_track(tracks_repo, filepath="/music/percent.flac", title="100% Done", artists=["A"])
        _add_track(tracks_repo, filepath="/music/other.flac", title="Something Else", artists=["B"])

        results, total = tracks_repo.search("100%")

        assert total == 1
        assert results[0].title == "100% Done"


class TestAlbumGrouping:
    def test_tracks_sharing_an_album_are_grouped_under_one_album_row(self, library_database):
        tracks_repo = library_database.tracks
        albums_repo = library_database.albums

        t1 = _add_track(
            tracks_repo, filepath="/music/grouped_1.flac",
            title="Grouped One", artists=["Grouping Artist"], album="Grouped Album",
        )
        t2 = _add_track(
            tracks_repo, filepath="/music/grouped_2.flac",
            title="Grouped Two", artists=["Grouping Artist"], album="Grouped Album",
        )
        # Same title, different artist -> a distinct album row (#3365 dedup is
        # scoped to (title, artist_id), not title alone).
        t3 = _add_track(
            tracks_repo, filepath="/music/other_artist.flac",
            title="Other Artist's Track", artists=["Different Artist"], album="Grouped Album",
        )

        assert t1.album_id == t2.album_id
        assert t3.album_id != t1.album_id

        album = albums_repo.get_by_id(t1.album_id)
        assert album is not None
        assert {t.title for t in album.tracks} == {"Grouped One", "Grouped Two"}

        albums, total = albums_repo.get_all(limit=50)
        assert total == 2  # "Grouped Album" (Grouping Artist) + "Grouped Album" (Different Artist)


class TestMetadataEdit:
    def test_update_metadata_changes_only_provided_fields(self, library_database):
        tracks_repo = library_database.tracks
        track = _add_track(
            tracks_repo, filepath="/music/editable.flac",
            title="Original Title", artists=["Original Artist"], track_number=3,
        )

        updated = tracks_repo.update_metadata(track.id, title="Edited Title")

        assert updated is not None
        assert updated.title == "Edited Title"
        assert updated.track_number == 3, "fields not passed to update_metadata must survive untouched"

        # Re-query independently of the return value to prove the edit
        # actually persisted rather than only mutating the in-memory object.
        reloaded = tracks_repo.get_by_id(track.id)
        assert reloaded.title == "Edited Title"
        assert reloaded.track_number == 3


class TestFavorites:
    def test_set_favorite_and_get_favorites_round_trip(self, library_database):
        tracks_repo = library_database.tracks
        fav = _add_track(tracks_repo, filepath="/music/fav.flac", title="Favorite Track", artists=["A"])
        not_fav = _add_track(tracks_repo, filepath="/music/not_fav.flac", title="Ordinary Track", artists=["B"])

        assert tracks_repo.set_favorite(fav.id, True) is True

        favorites, total = tracks_repo.get_favorites()
        assert total == 1
        assert {t.id for t in favorites} == {fav.id}
        assert not_fav.id not in {t.id for t in favorites}

        # Un-favoriting removes it from the favorites view again.
        assert tracks_repo.set_favorite(fav.id, False) is True
        favorites_after, total_after = tracks_repo.get_favorites()
        assert total_after == 0
        assert favorites_after == []


class TestDeletion:
    def test_delete_removes_track_and_it_no_longer_queries(self, library_database):
        tracks_repo = library_database.tracks
        track = _add_track(tracks_repo, filepath="/music/to_delete.flac", title="Doomed Track", artists=["A"])

        assert tracks_repo.get_by_id(track.id) is not None

        assert tracks_repo.delete(track.id) is True

        assert tracks_repo.get_by_id(track.id) is None
        _, total = tracks_repo.get_all(limit=50)
        assert total == 0

        # Idempotent-ish: deleting an already-gone track reports False, not an error.
        assert tracks_repo.delete(track.id) is False


class TestReadAfterWriteConsistency:
    """No caching layer sits between a repository write and the next read —
    every mutation must be immediately visible to query methods, matching the
    project's live-computed-stats invariant (no cached table, see #4243)."""

    def test_add_is_immediately_visible_to_get_all_and_search(self, library_database):
        tracks_repo = library_database.tracks

        _, total_before = tracks_repo.get_all(limit=50)
        assert total_before == 0

        _add_track(tracks_repo, filepath="/music/fresh.flac", title="Freshly Added", artists=["A"])

        _, total_after = tracks_repo.get_all(limit=50)
        assert total_after == 1
        results, search_total = tracks_repo.search("Freshly")
        assert search_total == 1
        assert results[0].title == "Freshly Added"

    def test_update_and_delete_are_immediately_visible(self, library_database):
        tracks_repo = library_database.tracks
        track = _add_track(tracks_repo, filepath="/music/mutable.flac", title="Before Edit", artists=["A"])

        tracks_repo.update_metadata(track.id, title="After Edit")
        assert tracks_repo.get_by_id(track.id).title == "After Edit"
        assert tracks_repo.search("Before Edit")[1] == 0
        assert tracks_repo.search("After Edit")[1] == 1

        tracks_repo.delete(track.id)
        assert tracks_repo.search("After Edit")[1] == 0
