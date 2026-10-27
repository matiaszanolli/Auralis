"""
Regression: artist-name heuristics keep real band names and symbol-only names intact (#5720)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`parse_featured_artists` split any "A & B" / "A and B" whose parts were short
(Iron & Wine -> Iron, Wine) unless the whole name was in a 13-entry list, and
`normalize_artist_name` kept only alphanumerics, so "!!!" and "+/-" both
normalised to '' and the second collapsed onto the first artist row.
"""

import pytest
from sqlalchemy import select

from auralis.library.models import Artist
from auralis.library.utils.artist_normalizer import normalize_artist_name, parse_featured_artists


@pytest.mark.parametrize("tag", [
    "Iron & Wine", "Mumford & Sons", "Belle and Sebastian", "Coheed and Cambria",
    "Tegan and Sara", "Of Monsters and Men", "Simon and Garfunkel", "Simon & Garfunkel",
    "Crosby, Stills & Nash", "Tom Petty and the Heartbreakers", "Florence + the Machine",
])
def test_whole_tag_without_a_marker_is_one_artist(tag):
    assert parse_featured_artists(tag) == [tag]


@pytest.mark.parametrize("tag, expected", [
    ("Artist A feat. Artist B", ["Artist A", "Artist B"]),
    ("Artist A ft. Artist B", ["Artist A", "Artist B"]),
    ("Artist A featuring Artist B", ["Artist A", "Artist B"]),
    ("Artist A vs Artist B", ["Artist A", "Artist B"]),
    ("Artist A feat. Artist B & Artist C", ["Artist A", "Artist B", "Artist C"]),
    ("Artist A feat. Artist B, Artist C", ["Artist A", "Artist B", "Artist C"]),
    # the credit before the marker is the main artist and stays whole
    ("Iron & Wine feat. Sam Beam", ["Iron & Wine", "Sam Beam"]),
    # a preserved duo after the marker is not split
    ("Artist A feat. Hall & Oates", ["Artist A", "Hall & Oates"]),
    ("", ["Unknown Artist"]),
    ("   ", ["Unknown Artist"]),
])
def test_explicit_markers_still_split(tag, expected):
    assert parse_featured_artists(tag) == expected


def test_multi_value_tags_are_parsed_per_value_without_splitting_band_names():
    from auralis.library.scanner.metadata_extractor import MetadataExtractor
    from auralis.library.scan_models import AudioFileInfo
    from datetime import datetime

    info = AudioFileInfo(
        filepath="/tmp/x.flac", filename="x.flac", filesize=1, modified_time=datetime.now(),
        metadata={'artist': ['Iron & Wine', 'Tegan and Sara feat. Someone']},
    )

    track_info = MetadataExtractor().audio_info_to_track_info(info)

    assert track_info['artists'] == ['Iron & Wine', 'Tegan and Sara', 'Someone']


class TestNormalizedKey:
    def test_symbol_only_names_stay_distinct(self):
        assert normalize_artist_name('!!!') == '!!!'
        assert normalize_artist_name('+/-') == '+/-'
        assert normalize_artist_name('!!!') != normalize_artist_name('+/-')

    @pytest.mark.parametrize("a, b", [("AC/DC", "ACDC"), ("AC-DC", "AC/DC"), ("  The   Beatles ", "the beatles")])
    def test_alphanumeric_names_normalise_as_before(self, a, b):
        assert normalize_artist_name(a) == normalize_artist_name(b)

    def test_blank_stays_empty(self):
        assert normalize_artist_name('') == ''
        assert normalize_artist_name('   ') == ''

    def test_compatibility_forms_fold_together(self):
        assert normalize_artist_name('＋／－') == normalize_artist_name('+/-')


class TestThroughTheRepository:
    def test_symbol_only_artists_get_distinct_rows(self, library_database):
        repo = library_database.tracks
        repo.add({'filepath': '/tmp/a.flac', 'title': 'a', 'artists': ['!!!'], 'duration': 1.0,
                  'sample_rate': 44100, 'channels': 2, 'format': 'FLAC'})
        repo.add({'filepath': '/tmp/b.flac', 'title': 'b', 'artists': ['+/-'], 'duration': 1.0,
                  'sample_rate': 44100, 'channels': 2, 'format': 'FLAC'})

        with library_database.SessionLocal() as s:
            rows = {a.name: a.normalized_name for a in s.execute(select(Artist)).scalars()}
        assert rows == {'!!!': '!!!', '+/-': '+/-'}

    def test_legacy_row_keyed_empty_is_adopted_and_rekeyed(self, library_database):
        """A library scanned before the fix holds '!!!' with normalized_name ''.
        The next add must resolve to that row, not fail on the unique name."""
        with library_database.SessionLocal() as s:
            s.add(Artist(name='!!!', normalized_name=''))
            s.commit()

        track = library_database.tracks.add(
            {'filepath': '/tmp/c.flac', 'title': 'c', 'artists': ['!!!'], 'duration': 1.0,
             'sample_rate': 44100, 'channels': 2, 'format': 'FLAC'})

        assert track is not None
        with library_database.SessionLocal() as s:
            rows = list(s.execute(select(Artist)).scalars())
        assert [(a.name, a.normalized_name) for a in rows] == [('!!!', '!!!')]

    def test_band_name_with_ampersand_is_one_artist_row(self, library_database):
        library_database.tracks.add(
            {'filepath': '/tmp/d.flac', 'title': 'd', 'artists': parse_featured_artists('Iron & Wine'),
             'duration': 1.0, 'sample_rate': 44100, 'channels': 2, 'format': 'FLAC'})

        with library_database.SessionLocal() as s:
            names = [a.name for a in s.execute(select(Artist)).scalars()]
        assert names == ['Iron & Wine']
