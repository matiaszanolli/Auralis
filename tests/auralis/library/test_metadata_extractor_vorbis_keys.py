#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MetadataExtractor: mixed ID3/Vorbis/MP4 key table on Vorbis-comment files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Found while rewriting the library scan->persist->query integration tests
(#4234): TAG_MAPPINGS mixes ID3 frame IDs, Vorbis-comment names, and MP4 atom
names (e.g. '\\xa9nam') in one table per field so a single mapping covers
every format. Vorbis-comment keys are restricted to printable ASCII excluding
'=' (mutagen's ``vorbis.is_valid_key``) — checking an MP4 atom key like
'\\xa9nam' against a FLAC/OGG file's tags raised ``ValueError`` from
``key in audio_file``, regardless of whether that key was actually present.
Uncaught, this propagated out of ``extract_metadata()`` entirely on the first
field whose earlier (ID3/generic) candidates didn't match, discarding every
already-matched field and silently returning no metadata at all for the file.
In practice this meant embedded tags were never extracted from FLAC/OGG files
unless date/year/genre/comment were also all tagged — title always fell back
to the filename.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import soundfile as sf
from mutagen.flac import FLAC

from auralis.library.scanner.metadata_extractor import MetadataExtractor


def _write_tagged_flac(path, **tags):
    samples = int(0.2 * 44100)
    audio = (np.random.randn(samples, 2) * 0.05).astype(np.float32)
    sf.write(str(path), audio, 44100, format='FLAC')

    flac = FLAC(str(path))
    for key, value in tags.items():
        flac[key] = value
    flac.save()


class TestVorbisCommentKeyMismatch:
    def test_title_only_flac_does_not_raise_and_extracts_title(self, tmp_path):
        """A FLAC with only 'title' set used to raise ValueError as soon as
        the 'artist' field's candidates fell through to '\\xa9ART' — before
        even reaching the fields the file actually had no interest in
        (date/genre/comment), because the walk is unconditional over every
        field in TAG_MAPPINGS regardless of what earlier fields found."""
        path = tmp_path / "title_only.flac"
        _write_tagged_flac(path, title="Only The Title")

        metadata = MetadataExtractor().extract_metadata_from_file(str(path))

        assert metadata is not None, (
            "extraction must not silently discard everything when a later "
            "field's candidate key is MP4-flavored and vorbis-invalid"
        )
        assert metadata.get('title') == "Only The Title"

    def test_fully_tagged_flac_extracts_every_field(self, tmp_path):
        path = tmp_path / "full.flac"
        _write_tagged_flac(
            path,
            title="Full Title", artist="Full Artist", album="Full Album",
            genre="Electronic", date="2024",
        )

        metadata = MetadataExtractor().extract_metadata_from_file(str(path))

        assert metadata is not None
        assert metadata.get('title') == "Full Title"
        assert metadata.get('artist') == "Full Artist"
        assert metadata.get('album') == "Full Album"
        assert metadata.get('genre') == "Electronic"

    def test_untagged_flac_returns_none_without_raising(self, tmp_path):
        """An untagged FLAC's MutagenFile object is falsy (no tag block at
        all), so extract_metadata_from_file's `if audio_file:` guard short-
        circuits to its documented None return — that part is pre-existing,
        correct behavior. The regression this guards is that it must not
        raise getting there."""
        path = tmp_path / "untagged.flac"
        _write_tagged_flac(path)  # No tags at all.

        metadata = MetadataExtractor().extract_metadata_from_file(str(path))

        assert metadata is None

    def test_extract_metadata_never_raises_on_a_vorbis_comment_object(self, tmp_path):
        """Direct call to extract_metadata() (not the outer try/except'd
        extract_metadata_from_file()) — pins that the fix is in the right
        place, not just papered over by the caller's broad except."""
        from mutagen import File as MutagenFile

        path = tmp_path / "direct.flac"
        _write_tagged_flac(path, title="Direct Call")

        audio_file = MutagenFile(str(path))
        metadata = MetadataExtractor().extract_metadata(audio_file)

        assert metadata.get('title') == "Direct Call"
