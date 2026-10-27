"""A rescan that finds a modified file discards its stale fingerprint (#5719)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``.25d`` sidecars and the chunk cache key on size+mtime and invalidate
themselves, but the database fingerprint row is keyed on ``track_id`` alone.
``update_by_filepath`` refreshed the track row and left the fingerprint, the
scan enqueued only ``added_tracks``, and the extractor skips any track that
already has a row — so a remaster / re-rip / re-encode at the same path kept
the previous recording's analysis (mastering targets, similarity, the reference
cloud) until the database was reset.
"""

import os

import numpy as np
import pytest
import soundfile as sf

from auralis.analysis.fingerprint.schema import DIMENSION_SCHEMA
from auralis.library.scanner import LibraryScanner


def _fingerprint() -> dict[str, float]:
    return {name: 0.5 for name in DIMENSION_SCHEMA}


def _track_info(**overrides):
    info = {
        "title": "t", "artists": ["A"], "album": "B", "filepath": "/t/rescan_5719.flac",
        "duration": 10.0, "filesize": 1000, "sample_rate": 44100, "channels": 2,
        "format": "FLAC", "file_mtime": 1_000_000.0,
    }
    info.update(overrides)
    return info


@pytest.fixture
def fingerprinted_track(library_database):
    track = library_database.tracks.add(_track_info())
    assert track is not None
    assert library_database.fingerprints.upsert(track.id, _fingerprint()) is not None
    assert library_database.fingerprints.exists(track.id)
    return track


class TestUpdateByFilepathInvalidation:
    @pytest.mark.parametrize("changed", [
        {"filesize": 2000},
        {"duration": 10.5},
        {"sample_rate": 48000},
        {"channels": 1},
        {"format": "WAV"},
        {"file_mtime": 1_000_500.0},
    ], ids=lambda c: next(iter(c)))
    def test_a_changed_audio_field_discards_the_fingerprint(
        self, library_database, fingerprinted_track, changed
    ):
        library_database.tracks.update_by_filepath(
            "/t/rescan_5719.flac", _track_info(**changed)
        )

        assert not library_database.fingerprints.exists(fingerprinted_track.id)
        assert library_database.fingerprints.get_by_track_id(fingerprinted_track.id) is None

    def test_an_unchanged_file_keeps_its_fingerprint(
        self, library_database, fingerprinted_track
    ):
        library_database.tracks.update_by_filepath(
            "/t/rescan_5719.flac", _track_info(title="retitled")
        )

        assert library_database.fingerprints.exists(fingerprinted_track.id)

    def test_a_sub_tolerance_duration_wobble_keeps_the_fingerprint(
        self, library_database, fingerprinted_track
    ):
        library_database.tracks.update_by_filepath(
            "/t/rescan_5719.flac", _track_info(duration=10.004)
        )

        assert library_database.fingerprints.exists(fingerprinted_track.id)

    def test_a_pre_watermark_row_with_the_same_size_is_not_reanalysed(
        self, library_database
    ):
        """A NULL watermark means 'unknown' (pre-v22 rows); the one-time
        refresh it triggers must not throw away every legacy fingerprint."""
        track = library_database.tracks.add(_track_info(file_mtime=None))
        library_database.fingerprints.upsert(track.id, _fingerprint())

        library_database.tracks.update_by_filepath(
            "/t/rescan_5719.flac", _track_info(file_mtime=1_234_567.0)
        )

        assert library_database.fingerprints.exists(track.id)

    def test_other_tracks_keep_their_fingerprints(
        self, library_database, fingerprinted_track
    ):
        other = library_database.tracks.add(_track_info(filepath="/t/other_5719.flac"))
        library_database.fingerprints.upsert(other.id, _fingerprint())

        library_database.tracks.update_by_filepath(
            "/t/rescan_5719.flac", _track_info(filesize=2000)
        )

        assert library_database.fingerprints.exists(other.id)

    def test_a_track_without_a_fingerprint_updates_normally(self, library_database):
        track = library_database.tracks.add(_track_info())

        updated = library_database.tracks.update_by_filepath(
            "/t/rescan_5719.flac", _track_info(filesize=2000)
        )

        assert updated is not None and updated.id == track.id


def _write_wav(path, seconds: float, freq: float) -> None:
    t = np.arange(int(44100 * seconds)) / 44100
    tone = (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(str(path), np.stack([tone, tone], axis=1), 44100, subtype="PCM_16")


class TestRescanEndToEnd:
    def test_replaced_file_loses_its_fingerprint_and_is_reported_updated(
        self, library_database, tmp_path
    ):
        wav = tmp_path / "song.wav"
        _write_wav(wav, 1.0, 440.0)
        scanner = LibraryScanner(library_database)
        first = scanner.scan_directories(
            directories=[str(tmp_path)], recursive=False,
            skip_existing=True, check_modifications=True,
        )
        assert first.files_added == 1
        track_id = first.added_tracks[0].id
        library_database.fingerprints.upsert(track_id, _fingerprint())

        # Replace the recording at the same path, with a later mtime.
        _write_wav(wav, 2.0, 880.0)
        later = os.stat(wav).st_mtime + 60
        os.utime(wav, (later, later))
        second = scanner.scan_directories(
            directories=[str(tmp_path)], recursive=False,
            skip_existing=True, check_modifications=True,
        )

        assert second.files_updated == 1
        assert [t.id for t in second.updated_tracks] == [track_id]
        assert second.added_tracks == []
        assert not library_database.fingerprints.exists(track_id)

    def test_untouched_file_is_skipped_and_keeps_its_fingerprint(
        self, library_database, tmp_path
    ):
        wav = tmp_path / "song.wav"
        _write_wav(wav, 1.0, 440.0)
        scanner = LibraryScanner(library_database)
        first = scanner.scan_directories(
            directories=[str(tmp_path)], recursive=False,
            skip_existing=True, check_modifications=True,
        )
        track_id = first.added_tracks[0].id
        library_database.fingerprints.upsert(track_id, _fingerprint())

        second = scanner.scan_directories(
            directories=[str(tmp_path)], recursive=False,
            skip_existing=True, check_modifications=True,
        )

        assert second.files_skipped == 1
        assert second.updated_tracks == []
        assert library_database.fingerprints.exists(track_id)
