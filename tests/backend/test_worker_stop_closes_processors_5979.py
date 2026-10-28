"""Stopping the cache worker releases its cached processors (#5979).

Each cached ChunkedAudioProcessor holds a SeekableSource reference on the converted temp WAV of
an .m4a/.aac/.wma track; ConvertedWavRegistry.shutdown() deletes only unreferenced conversions,
so processors left in the cache kept their temp files until the process died.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.streamlined_worker import StreamlinedCacheWorker  # noqa: E402

pytestmark = pytest.mark.asyncio


def _worker():
    return StreamlinedCacheWorker(Mock(current_track_id=None), Mock())


async def test_stop_closes_and_empties_the_processor_cache():
    worker = _worker()
    processors = [Mock(), Mock(), Mock()]
    for i, processor in enumerate(processors):
        worker._processor_cache[(i, "adaptive", 100)] = processor

    await worker.stop()

    for processor in processors:
        processor.close.assert_called_once()
    assert len(worker._processor_cache) == 0


async def test_one_processor_failing_to_close_does_not_strand_the_rest():
    worker = _worker()
    bad, good = Mock(), Mock()
    bad.close.side_effect = RuntimeError("boom")
    worker._processor_cache[(1, "adaptive", 100)] = bad
    worker._processor_cache[(2, "adaptive", 100)] = good

    await worker.stop()

    good.close.assert_called_once()
    assert len(worker._processor_cache) == 0
