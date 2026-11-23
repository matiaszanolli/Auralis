"""A SeekableSource resolved after close() takes no temp-WAV hold (#6545).

close() bumped an epoch that only an in-flight resolve() compared against; a
resolve() that STARTED afterwards (a look-ahead render outliving its stream's
close()) captured the new epoch, re-acquired the full-track conversion and kept
a hold nobody would release. close() is now terminal: a later resolve() raises
SeekableSourceClosed, a ChunkCancelledError, so the render path ends it as a
cancel instead of a failure, and the registry is never touched.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import seekable_source  # noqa: E402
from core.chunk_stream_state import ChunkCancelledError  # noqa: E402
from core.seekable_source import SeekableSource, SeekableSourceClosed  # noqa: E402
from tests.backend.test_conversion_hold_cancel_5946 import _SlowRegistry  # noqa: E402


@pytest.mark.parametrize("native", [False, True], ids=["needs-conversion", "native"])
def test_resolve_after_close_raises_a_cancel_and_takes_no_hold(native):
    registry = _SlowRegistry()
    registry.unblock.set()
    source = SeekableSource("/music/a.m4a", registry)

    with patch.object(seekable_source, "can_seek_natively", return_value=native):
        source.resolve()  # the stream's first chunk
        source.close()  # the stream ends; a look-ahead render is still loading
        with pytest.raises(SeekableSourceClosed) as raised:
            source.resolve()

    assert isinstance(raised.value, ChunkCancelledError)
    assert registry.acquired == ([] if native else ["key-0"])
    assert registry.refs == 0
    assert source.converted is False


def test_a_source_closed_before_its_first_resolve_never_converts():
    registry = _SlowRegistry()
    source = SeekableSource("/music/a.m4a", registry)
    source.close()

    with patch.object(seekable_source, "can_seek_natively", return_value=False):
        with pytest.raises(SeekableSourceClosed):
            source.resolve()

    assert registry.acquired == []
