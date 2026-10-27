"""Post-scan fingerprint enqueue covers updated tracks too (#5719)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A rescan that finds a modified file discards its stale fingerprint row, and
the extractor never revisits a track that has none unless it is enqueued — but
only ``added_tracks`` used to be. Both scan sites (the manual route and the
auto-scanner) go through ``enqueue_scanned_for_fingerprinting``.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.scan_events import enqueue_scanned_for_fingerprinting  # noqa: E402


def _tracks(*ids: int) -> list[SimpleNamespace]:
    return [SimpleNamespace(id=i) for i in ids]


async def _enqueue(result, fp_queue) -> list[int]:
    with patch("analysis.fingerprint_queue.get_fingerprint_queue", return_value=fp_queue):
        await enqueue_scanned_for_fingerprinting(result)
    return sorted(c.args[0] for c in fp_queue.enqueue.call_args_list) if fp_queue else []


async def test_added_and_updated_tracks_are_both_enqueued():
    fp_queue = MagicMock()
    fp_queue.enqueue.return_value = True
    result = SimpleNamespace(added_tracks=_tracks(1, 2), updated_tracks=_tracks(7))

    assert await _enqueue(result, fp_queue) == [1, 2, 7]


async def test_updated_only_scan_still_enqueues():
    fp_queue = MagicMock()
    fp_queue.enqueue.return_value = True
    result = SimpleNamespace(added_tracks=[], updated_tracks=_tracks(9))

    assert await _enqueue(result, fp_queue) == [9]


async def test_a_result_without_updated_tracks_is_tolerated():
    fp_queue = MagicMock()
    fp_queue.enqueue.return_value = True
    result = SimpleNamespace(added_tracks=_tracks(3))

    assert await _enqueue(result, fp_queue) == [3]


async def test_nothing_to_enqueue_leaves_the_queue_untouched():
    fp_queue = MagicMock()
    result = SimpleNamespace(added_tracks=[], updated_tracks=[])

    assert await _enqueue(result, fp_queue) == []
    fp_queue.enqueue.assert_not_called()


async def test_a_missing_queue_is_not_an_error():
    result = SimpleNamespace(added_tracks=_tracks(4), updated_tracks=_tracks(5))

    await _enqueue(result, None)
