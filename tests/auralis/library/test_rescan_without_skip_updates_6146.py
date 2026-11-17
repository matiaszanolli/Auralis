"""skip_existing=False re-scans existing tracks as updates (#6146).

With skip_existing=False the existing-row lookup was skipped, so a file already in the library fell through to
tracks_repo.add() (a duplicate filepath) and came back as 'failed'/'added' instead of being refreshed.
"""

from unittest.mock import Mock

from auralis.library.scanner.batch_processor import BatchProcessor

PATH = "/music/song.flac"


def _processor(existing):
    processor = BatchProcessor.__new__(BatchProcessor)
    processor.library_database = Mock()
    processor.library_database.tracks.get_by_path.return_value = existing
    processor.library_database.tracks.update_by_filepath.return_value = Mock(id=7)
    processor.audio_analyzer = Mock()
    processor.audio_analyzer.extract_audio_info.return_value = Mock()
    processor.metadata_extractor = Mock()
    processor.metadata_extractor.extract_metadata_from_file.return_value = None
    processor.metadata_extractor.audio_info_to_track_info.return_value = {"filepath": PATH, "title": "Song"}
    return processor


def test_an_existing_track_is_updated_when_skipping_is_off():
    existing = Mock(file_mtime=None)
    processor = _processor(existing)

    status, track, reason = processor.process_single_file(PATH, skip_existing=False, check_modifications=True)

    assert (status, reason) == ("updated", None)
    processor.library_database.tracks.update_by_filepath.assert_called_once()
    processor.library_database.tracks.add.assert_not_called()


def test_an_unchanged_existing_track_is_still_skipped_when_skipping_is_on():
    existing = Mock(file_mtime=1.0, filesize=None)
    processor = _processor(existing)
    processor._skip_existing_track = Mock(return_value=True)

    status, track, reason = processor.process_single_file(PATH, skip_existing=True, check_modifications=True)

    assert status == "skipped"
    processor.library_database.tracks.update_by_filepath.assert_not_called()
