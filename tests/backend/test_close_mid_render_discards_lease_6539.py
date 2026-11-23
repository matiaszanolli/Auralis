"""Closing a stream while a render is still inside its processor does not hand that processor on (#6539).

A pump exit cannot cancel a look-ahead render already in the stream executor. close() returned
the leased HybridProcessor to the factory's warm cache anyway, so a successor stream of the same
key acquired an instance the orphan render was still advancing. A render holds _processor_lock
for the whole chunk; a lease close() cannot take that lock for is now discarded instead.
"""

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_processor_lease import StreamProcessorLeaseMixin  # noqa: E402


class _Stream(StreamProcessorLeaseMixin):
    def __init__(self):
        self.track_id = 7
        self.preset = "adaptive"
        self.intensity = 1.0
        self.processor_config = None
        self.mastering_targets = None
        self.processor = MagicMock(name="hybrid")
        self._processor_factory = MagicMock(name="factory")
        self._processor_lock = threading.RLock()


def test_close_while_a_render_holds_the_lock_discards_the_lease():
    stream = _Stream()
    leased = stream.processor
    rendering, finish = threading.Event(), threading.Event()

    def orphan_render():
        with stream._processor_lock:
            rendering.set()
            finish.wait(5)

    render = threading.Thread(target=orphan_render)
    render.start()
    rendering.wait(5)
    stream._close_lease()
    finish.set()
    render.join(5)

    stream._processor_factory.release_lease.assert_not_called()
    stream._processor_factory.discard_lease.assert_called_once_with(leased, track_id=7)
    assert stream.processor is None


def test_close_with_no_render_in_flight_returns_the_lease_warm():
    stream = _Stream()
    leased = stream.processor

    stream._close_lease()

    stream._processor_factory.discard_lease.assert_not_called()
    stream._processor_factory.release_lease.assert_called_once()
    assert stream._processor_factory.release_lease.call_args.args == (leased,)
    assert stream._processor_lock.acquire(blocking=False)  # close() let go of it
