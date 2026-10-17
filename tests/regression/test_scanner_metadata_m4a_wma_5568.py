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

    def test_wma_disc_part_of_set_single_and_compound_values(self, extractor):
        """WM/PartOfSet correctly handles single, compound, and numeric word attributes."""
        from mutagen.asf import ASFDWordAttribute, ASFWordAttribute

        # Compound string e.g. '2/3'
        compound_file = MockAudioFile({'WM/PartOfSet': [ASFUnicodeAttribute('2/3')]})
        assert extractor.extract_metadata(compound_file)['disc'] == 2

        # Single string e.g. '2'
        single_file = MockAudioFile({'WM/PartOfSet': [ASFUnicodeAttribute('2')]})
        assert extractor.extract_metadata(single_file)['disc'] == 2

        # Padded compound string e.g. ' 03 / 05 '
        padded_file = MockAudioFile({'WM/PartOfSet': [ASFUnicodeAttribute(' 03 / 05 ')]})
        assert extractor.extract_metadata(padded_file)['disc'] == 3

        # Word int attribute e.g. ASFWordAttribute(4)
        word_file = MockAudioFile({'WM/PartOfSet': [ASFWordAttribute(4)]})
        assert extractor.extract_metadata(word_file)['disc'] == 4

        # DWord int attribute e.g. ASFDWordAttribute(5)
        dword_file = MockAudioFile({'WM/PartOfSet': [ASFDWordAttribute(5)]})
        assert extractor.extract_metadata(dword_file)['disc'] == 5

        # Unset zero values are omitted
        zero_word = MockAudioFile({'WM/PartOfSet': [ASFWordAttribute(0)]})
        assert 'disc' not in extractor.extract_metadata(zero_word)

        zero_str = MockAudioFile({'WM/PartOfSet': [ASFUnicodeAttribute('0/0')]})
        assert 'disc' not in extractor.extract_metadata(zero_str)

    def test_wma_boolean_and_binary_attributes_rejected(self, extractor):
        """Boolean and binary ASF attributes are not treated as valid metadata."""
        from mutagen.asf import ASFBoolAttribute, ASFByteArrayAttribute

        # Boolean attributes on text and numeric fields
        bool_file = MockAudioFile({
            'Title': [ASFBoolAttribute(True)],
            'WM/TrackNumber': [ASFBoolAttribute(True)],
            'WM/PartOfSet': [ASFBoolAttribute(False)],
            'WM/Year': [ASFBoolAttribute(True)],
        })
        assert extractor.extract_metadata(bool_file) == {}

        # Binary byte array attributes
        binary_file = MockAudioFile({
            'Title': [ASFByteArrayAttribute(b'\x01\x02\x03\x04')],
            'WM/TrackNumber': [ASFByteArrayAttribute(b'\x00\x01')],
        })
        assert extractor.extract_metadata(binary_file) == {}

        # Empty and whitespace-only attributes are omitted
        empty_file = MockAudioFile({
            'Title': [ASFUnicodeAttribute('')],
            'Author': [ASFUnicodeAttribute('   ')],
        })
        assert extractor.extract_metadata(empty_file) == {}
