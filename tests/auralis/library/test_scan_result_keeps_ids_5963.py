"""A scan result keeps track ids, not full Track objects (#5963).

process_file_batch appended the detached Track returned by add() (~10 KB each, relationships
included) to the scan-wide result, so a large scan held every added track until it returned.
The only consumers read ``.id``.
"""

from unittest.mock import Mock

from auralis.library.scan_models import ScannedTrackRef
from auralis.library.scanner.batch_processor import BatchProcessor


def test_added_and_updated_tracks_are_reduced_to_their_ids():
    processor = BatchProcessor.__new__(BatchProcessor)
    processor.should_stop = Mock(is_set=Mock(return_value=False))
    big_added, big_updated = Mock(id=11), Mock(id=22)
    outcomes = iter([("added", big_added, None), ("updated", big_updated, None)])
    processor.process_single_file = Mock(side_effect=lambda *a, **k: next(outcomes))

    result = processor.process_file_batch(["/a.flac", "/b.flac"], skip_existing=True, check_modifications=True)

    assert result.added_tracks == [ScannedTrackRef(11)]
    assert result.updated_tracks == [ScannedTrackRef(22)]
    assert not any(t is big_added or t is big_updated for t in result.added_tracks + result.updated_tracks)


def test_the_ref_is_what_the_fingerprint_enqueue_reads():
    assert ScannedTrackRef(5).id == 5
    assert not hasattr(ScannedTrackRef(5), "__dict__")  # slots: nothing else is retained
