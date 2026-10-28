"""Scanner title default and get_by_paths keying (#6148, #6149)."""

from datetime import datetime

import pytest

import auralis.library.repositories.track_repository_lifecycle as lifecycle_module
import auralis.library.repositories.track_repository_lookup as lookup_module
from auralis.library.scan_models import AudioFileInfo
from auralis.library.scanner.metadata_extractor import MetadataExtractor


def _info(filepath: str, metadata=None) -> AudioFileInfo:
    return AudioFileInfo(
        filepath=filepath, filename=filepath.rsplit("/", 1)[-1], filesize=1,
        modified_time=datetime(2026, 1, 1), duration=1.0, sample_rate=44100, channels=2,
        format="FLAC", metadata=metadata,
    )


class TestTitleDefault:
    """#6148: an untagged file got 'a.wav' while a tagged-but-untitled one got 'a'."""

    @pytest.fixture
    def extractor(self):
        return MetadataExtractor()

    def test_untagged_file_title_is_the_stem(self, extractor):
        assert extractor.audio_info_to_track_info(_info("/m/Song One.wav", metadata={}))["title"] == "Song One"

    def test_metadata_without_a_title_gets_the_same_stem(self, extractor):
        info = _info("/m/Song One.wav", metadata={"artist": "X"})
        assert extractor.audio_info_to_track_info(info)["title"] == "Song One"

    def test_no_metadata_at_all_gets_the_stem_too(self, extractor):
        assert extractor.audio_info_to_track_info(_info("/m/a.b.flac"))["title"] == "a.b"

    def test_a_tagged_title_still_wins(self, extractor):
        info = _info("/m/x.wav", metadata={"title": "Real Title"})
        assert extractor.audio_info_to_track_info(info)["title"] == "Real Title"


class TestGetByPathsKeyedByRequestedPath:
    """#6149: the query matches the normalised filepath_key but the result was keyed by
    the stored spelling, so a differently-cased request found its row and then missed it."""

    @pytest.fixture(autouse=True)
    def _case_folding_keys(self, monkeypatch):
        # Linux preserves case in make_filepath_key; emulate the Windows/macOS folding.
        fold = lambda p: p.lower()  # noqa: E731
        monkeypatch.setattr(lookup_module, "make_filepath_key", fold)
        monkeypatch.setattr(lifecycle_module, "make_filepath_key", fold)

    @staticmethod
    def _add(repo, path):
        track = repo.add({"title": "t", "filepath": path, "sample_rate": 44100, "channels": 2, "format": "FLAC"})
        assert track is not None
        return track

    def test_result_is_keyed_by_the_requested_spelling(self, track_repository):
        stored = self._add(track_repository, "/Music/Song.flac")

        result = track_repository.get_by_paths(["/MUSIC/SONG.FLAC"])

        assert list(result) == ["/MUSIC/SONG.FLAC"]
        assert result["/MUSIC/SONG.FLAC"].id == stored.id

    def test_two_spellings_of_one_file_both_map_to_it(self, track_repository):
        stored = self._add(track_repository, "/Music/Song.flac")

        result = track_repository.get_by_paths(["/music/song.flac", "/MUSIC/SONG.FLAC"])

        assert {k: v.id for k, v in result.items()} == {
            "/music/song.flac": stored.id, "/MUSIC/SONG.FLAC": stored.id,
        }

    def test_exact_spelling_and_misses_behave_as_before(self, track_repository):
        stored = self._add(track_repository, "/Music/Song.flac")

        result = track_repository.get_by_paths(["/Music/Song.flac", "/Music/Missing.flac"])

        assert set(result) == {"/Music/Song.flac"}
        assert result["/Music/Song.flac"].id == stored.id
        assert track_repository.get_by_paths([]) == {}
