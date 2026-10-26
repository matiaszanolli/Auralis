"""A batch progress frame names the last file of the batch it just finished (#5913).

`BatchFeeder` reports after a whole batch is processed, so `current_file` of
`batch[0]` named a file batch_size-1 files behind the one the scanner had reached.
"""

from unittest.mock import MagicMock

from auralis.library.scan_models import ScanResult
from auralis.library.scanner.scan_stages import BatchFeeder


def _feeder(batch_size: int):
    frames: list[dict] = []
    processor = MagicMock()
    processor.process_file_batch.return_value = MagicMock(
        files_processed=batch_size, files_added=batch_size, files_updated=0,
        files_skipped=0, files_failed=0, failures=[], added_tracks=[],
    )
    feeder = BatchFeeder(
        processor, ScanResult(), frames.append,
        total_expected=100, batch_size=batch_size,
        skip_existing=True, check_modifications=False,
    )
    return feeder, frames


def test_full_batch_frame_names_the_last_file_of_the_batch():
    feeder, frames = _feeder(batch_size=3)

    for name in ("/m/a.mp3", "/m/b.mp3", "/m/c.mp3"):
        feeder.feed(name)

    assert [f["current_file"] for f in frames] == ["/m/c.mp3"]


def test_flushed_partial_batch_names_its_last_file():
    feeder, frames = _feeder(batch_size=10)

    feeder.feed("/m/a.mp3")
    feeder.feed("/m/b.mp3")
    feeder.flush()

    assert [f["current_file"] for f in frames] == ["/m/b.mp3"]
