"""
TrackRepository.remove_tracks_under_folder Regression Test (#5467)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Removing a scan folder revoked filesystem path trust for its files
(`unregister_allowed_directory`) but never pruned or flagged the `Track`
rows pointing into it — they stayed visible in the library while every
path-validated endpoint (metadata, tracks, enhancement) started rejecting
them with an unexplained 400.

`remove_tracks_under_folder()` removes exactly the tracks whose file lives
under a given folder, using the same `Path.is_relative_to()` on resolved
paths convention `security/path_security.py` already uses for the trust
check itself — regardless of whether the file still exists on disk (the
folder may still be perfectly valid, just no longer a trusted scan root).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


def _add_track(track_repository, filepath: str, title: str) -> object:
    return track_repository.add({
        "title": title,
        "filepath": filepath,
        "duration": 30.0,
        "sample_rate": 44100,
        "channels": 2,
        "format": "WAV",
    })


def _count(track_repository) -> int:
    _, total = track_repository.get_all(limit=1, offset=0)
    return total


class TestRemoveTracksUnderFolder:
    def test_removes_only_tracks_under_the_folder(self, track_repository, tmp_path):
        removed_folder = tmp_path / "removed"
        kept_folder = tmp_path / "kept"
        removed_folder.mkdir()
        kept_folder.mkdir()

        # Files under `removed_folder` still exist on disk -- this is not a
        # "missing file" cleanup, it's a "no longer trusted" cleanup.
        removed_file = removed_folder / "a.wav"
        removed_file.touch()
        nested_file = removed_folder / "sub" / "b.wav"
        nested_file.parent.mkdir()
        nested_file.touch()
        kept_file = kept_folder / "c.wav"
        kept_file.touch()

        _add_track(track_repository, str(removed_file), "A")
        _add_track(track_repository, str(nested_file), "B (nested)")
        _add_track(track_repository, str(kept_file), "C")

        assert _count(track_repository) == 3

        removed_count = track_repository.remove_tracks_under_folder(str(removed_folder))

        assert removed_count == 2
        assert _count(track_repository) == 1
        remaining, _ = track_repository.get_all(limit=10, offset=0)
        assert [t.title for t in remaining] == ["C"]

    def test_does_not_check_whether_the_file_still_exists(self, track_repository, tmp_path):
        """Unlike cleanup_missing_files, this prunes by folder membership
        alone -- the file may still be perfectly readable."""
        removed_folder = tmp_path / "removed"
        removed_folder.mkdir()
        still_present_file = removed_folder / "a.wav"
        still_present_file.touch()

        _add_track(track_repository, str(still_present_file), "A")

        removed_count = track_repository.remove_tracks_under_folder(str(removed_folder))

        assert removed_count == 1
        assert still_present_file.exists(), "the file itself must be untouched"

    def test_no_matching_tracks_removes_nothing(self, track_repository, tmp_path):
        other_folder = tmp_path / "other"
        removed_folder = tmp_path / "removed"
        other_folder.mkdir()
        removed_folder.mkdir()
        other_file = other_folder / "a.wav"
        other_file.touch()

        _add_track(track_repository, str(other_file), "A")

        removed_count = track_repository.remove_tracks_under_folder(str(removed_folder))

        assert removed_count == 0
        assert _count(track_repository) == 1

    def test_removes_across_multiple_batches(self, track_repository, tmp_path):
        """Same cursor-pagination shape as cleanup_missing_files (#2242) --
        deletes inside a batch must not skip rows in the next one."""
        removed_folder = tmp_path / "removed"
        removed_folder.mkdir()

        for i in range(25):
            p = removed_folder / f"track_{i:03d}.wav"
            p.touch()
            _add_track(track_repository, str(p), f"Track {i}")

        assert _count(track_repository) == 25

        removed_count = track_repository.remove_tracks_under_folder(
            str(removed_folder), batch_size=5
        )

        assert removed_count == 25
        assert _count(track_repository) == 0
