"""
MetadataExtractor M4A & WMA Tag Extraction Regression Test (#5568)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Scanner tag extraction dropped track/disc numbers for every M4A file
because MP4 atoms store `trkn` and `disk` as tuples `[(track, total)]`,
which were not handled in `_normalize_field_value`. Additionally,
`TAG_MAPPINGS` lacked ASF/WMA keys (`Title`, `Author`, `WM/AlbumTitle`,
`WM/Genre`, `WM/TrackNumber`, `WM/PartOfSet`, `WM/Year`), resulting in
WMA files extracting zero metadata during library scans.

This regression test verifies that:
1. M4A tuple track/disc values are correctly unwrapped to integer numbers.
2. Unset M4A track/disc values (zeros) are omitted.
3. WMA/ASF tags are extracted and `ASFUnicodeAttribute` objects are unwrapped.
4. FLAC, MP3, and OGG formats remain unaffected.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import pytest
from mutagen.asf import ASFUnicodeAttribute

from auralis.library.scanner.metadata_extractor import MetadataExtractor


class MockAudioFile(dict):
    """Mock mutagen audio file dictionary supporting key access and containment."""


class TestScannerMetadataM4AWMA5568:
    @pytest.fixture
    def extractor(self):
        return MetadataExtractor()

    def test_m4a_tuple_track_and_disc_extracted(self, extractor):
        """M4A trkn and disk tuples are unwrapped to integer track/disc numbers."""
        audio_file = MockAudioFile({
            'trkn': [(3, 12)],
            'disk': [(1, 2)],
            '\xa9nam': ['Track Title'],
            '\xa9ART': ['Artist Name'],
            '\xa9alb': ['Album Name'],
        })
        metadata = extractor.extract_metadata(audio_file)

        assert metadata['title'] == 'Track Title'
        assert metadata['artist'] == 'Artist Name'
        assert metadata['album'] == 'Album Name'
        assert metadata['track'] == 3
        assert metadata['disc'] == 1

    def test_m4a_zero_track_and_disc_omitted(self, extractor):
        """M4A unset track/disc numbers represented as (0, 0) are omitted."""
        audio_file = MockAudioFile({
            'trkn': [(0, 0)],
            'disk': [(0, 0)],
            '\xa9nam': ['Track Title'],
        })
        metadata = extractor.extract_metadata(audio_file)

        assert metadata['title'] == 'Track Title'
        assert 'track' not in metadata
        assert 'disc' not in metadata

    def test_m4a_single_element_tuple_track(self, extractor):
        """M4A tuple with a single element is correctly converted."""
        audio_file = MockAudioFile({
            'trkn': [(7,)],
            'disk': [(2,)],
        })
        metadata = extractor.extract_metadata(audio_file)

        assert metadata['track'] == 7
        assert metadata['disc'] == 2

    def test_wma_asf_tags_extracted(self, extractor):
        """WMA/ASF metadata fields are mapped and ASFUnicodeAttribute values are unwrapped."""
        audio_file = MockAudioFile({
            'Title': [ASFUnicodeAttribute('Song Title')],
            'Author': [ASFUnicodeAttribute('Artist Name')],
            'WM/AlbumTitle': [ASFUnicodeAttribute('Album Name')],
            'WM/AlbumArtist': [ASFUnicodeAttribute('Album Artist Name')],
            'WM/Genre': [ASFUnicodeAttribute('Progressive Rock')],
            'WM/TrackNumber': [ASFUnicodeAttribute('4')],
            'WM/PartOfSet': [ASFUnicodeAttribute('2')],
            'WM/Year': [ASFUnicodeAttribute('2024')],
        })
        metadata = extractor.extract_metadata(audio_file)

        assert metadata['title'] == 'Song Title'
        assert metadata['artist'] == 'Artist Name'
        assert metadata['album'] == 'Album Name'
        assert metadata['albumartist'] == 'Album Artist Name'
        assert metadata['genre'] == 'Progressive Rock'
        assert metadata['track'] == 4
        assert metadata['disc'] == 2
        assert metadata['year'] == 2024

    def test_wma_slash_formatted_track_number(self, extractor):
        """WMA track number containing total tracks ('3/10') extracts the track number."""
        audio_file = MockAudioFile({
            'Title': [ASFUnicodeAttribute('Title')],
            'WM/TrackNumber': [ASFUnicodeAttribute('3/10')],
            'WM/PartOfSet': [ASFUnicodeAttribute('1/2')],
        })
        metadata = extractor.extract_metadata(audio_file)

        assert metadata['track'] == 3
        assert metadata['disc'] == 1

    def test_existing_formats_unchanged(self, extractor):
        """FLAC and MP3 standard tags remain fully intact."""
        flac_file = MockAudioFile({
            'TITLE': ['Flac Title'],
            'ARTIST': ['Flac Artist'],
            'ALBUM': ['Flac Album'],
            'TRACKNUMBER': ['5/12'],
            'DISCNUMBER': ['1/1'],
            'DATE': ['2023-05-01'],
        })
        flac_meta = extractor.extract_metadata(flac_file)
        assert flac_meta['title'] == 'Flac Title'
        assert flac_meta['artist'] == 'Flac Artist'
        assert flac_meta['album'] == 'Flac Album'
        assert flac_meta['track'] == 5
        assert flac_meta['disc'] == 1
        assert flac_meta['year'] == 2023

        mp3_file = MockAudioFile({
            'TIT2': ['MP3 Title'],
            'TPE1': ['MP3 Artist'],
            'TALB': ['MP3 Album'],
            'TRCK': ['8'],
            'TPOS': ['1'],
            'TDRC': ['2021'],
        })
        mp3_meta = extractor.extract_metadata(mp3_file)
        assert mp3_meta['title'] == 'MP3 Title'
        assert mp3_meta['artist'] == 'MP3 Artist'
        assert mp3_meta['album'] == 'MP3 Album'
        assert mp3_meta['track'] == 8
        assert mp3_meta['disc'] == 1
        assert mp3_meta['year'] == 2021

    def test_normalize_field_value_invalid_types_return_none(self, extractor):
        """Genuinely invalid or empty values return None and are skipped."""
        assert extractor._normalize_field_value('track', 'invalid') is None
        assert extractor._normalize_field_value('track', None) is None
        assert extractor._normalize_field_value('track', ()) is None
        assert extractor._normalize_field_value('track', 0) is None
        assert extractor._normalize_field_value('disc', 0) is None
        assert extractor._normalize_field_value('year', '') is None
