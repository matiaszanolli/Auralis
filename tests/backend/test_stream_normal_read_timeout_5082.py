"""
Regression tests for unbounded normal-stream disk reads (#5082)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every other chunk-producing streaming path bounds its worker-thread call with
`asyncio.wait_for(..., timeout=CHUNK_PROCESS_TIMEOUT)` — stream_chunk_ops
(#3852), stream_enhanced, stream_seek. `stream_normal.py`'s two
`asyncio.to_thread(_read_audio_chunk, ...)` calls (the inline read and the
look-ahead read) were the exception: only the semaphore *acquire* was bounded,
at 5.0s.

`_read_audio_chunk` does `sf.SoundFile(path)` -> seek -> read. On a stalled
network mount or a yanked external drive that call neither returns nor raises,
so the stream hung forever holding one of `MAX_CONCURRENT_STREAMS` permits and
one default-executor thread, with the client receiving neither further chunks
nor an `audio_stream_error`. Repeat attempts against the same stalled storage
exhausted the semaphore, after which every play request across the whole app
got "Server busy" regardless of track.

These tests drive the real `stream_normal_audio` with a fake `sf.SoundFile`
whose reads block, and assert it now terminates, reports, releases its permit,
and stops re-arming reads once the storage is clearly gone.
"""

import asyncio
import inspect
import json
import re
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import stream_normal, stream_normal_chunks
from core.audio_stream_controller import AudioStreamController

SAMPLE_RATE = 8000
CHANNELS = 2
TRACK_ID = 77
# 6 chunks at the real 15s CHUNK_DURATION. Small sample rate keeps the fake
# frame count cheap; nothing here allocates a real buffer for a blocked read.
TOTAL_CHUNKS = 6
CHUNK_SAMPLES = 15 * SAMPLE_RATE
TOTAL_FRAMES = TOTAL_CHUNKS * CHUNK_SAMPLES

# Short enough to keep the test fast, long enough that a healthy (instant)
# read never trips it. The code reads _asc.CHUNK_PROCESS_TIMEOUT at call time,
# so patching the module attribute is enough.
FAST_TIMEOUT = 0.1


class _BlockingSoundFile:
    """Stands in for `sf.SoundFile`.

    Metadata opens (`_get_audio_info`) always succeed — the hang in the real
    failure mode happens once streaming starts pulling chunks, not at open.
    `read()` blocks on an Event that the test never sets until teardown,
    which is what a stalled mount looks like to `_read_audio_chunk`: no
    return, no exception.
    """

    def __init__(self, filepath, *args, **kwargs):
        self.samplerate = SAMPLE_RATE
        self.channels = CHANNELS
        self._filepath = filepath

    # Instances double as their own context manager, like soundfile's.
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __len__(self):
        return TOTAL_FRAMES

    def seek(self, frames):
        return frames


def _make_soundfile_class(release: threading.Event, reads: list, block_reads: bool):
    class _Fake(_BlockingSoundFile):
        def read(self, frames=None, dtype='float32', always_2d=True):
            reads.append(frames)
            if block_reads:
                # Bounded so the strand-ed worker threads cannot outlive the
                # test session even if an assertion fails early. The real
                # stall is unbounded; wait_for fires long before this does.
                release.wait(timeout=30)
            n = int(frames or 0)
            return np.zeros((n, CHANNELS), dtype=np.float32)

    return _Fake


def _make_websocket(sent: list) -> MagicMock:
    ws = MagicMock()
    ws.client_state = MagicMock()
    ws.client_state.name = "CONNECTED"

    async def fake_send_text(text: str) -> None:
        sent.append(json.loads(text))

    ws.send_text = AsyncMock(side_effect=fake_send_text)
    ws.send_bytes = AsyncMock()
    return ws


def _make_controller() -> AudioStreamController:
    controller = AudioStreamController()
    controller._send_stream_start = AsyncMock(return_value=True)

    track = MagicMock()
    track.filepath = "/tmp/fake_normal_5082.wav"
    factory = MagicMock()
    factory.tracks.get_by_id.return_value = track
    controller._get_repository_factory = MagicMock(return_value=factory)
    return controller


async def _run_stream(controller, ws, release, reads, block_reads=True):
    fake_sf = MagicMock()
    fake_sf.SoundFile = _make_soundfile_class(release, reads, block_reads)

    # #5032 split the per-chunk read out into stream_normal_chunks; the
    # metadata read stayed behind. Both need the fake, and both modules'
    # CHUNK_PROCESS_TIMEOUT view is the same _asc attribute.
    with patch.object(stream_normal, "sf", fake_sf), \
         patch.object(stream_normal_chunks, "sf", fake_sf), \
         patch.object(stream_normal._asc, "CHUNK_PROCESS_TIMEOUT", FAST_TIMEOUT), \
         patch.object(stream_normal, "validate_file_path",
                      side_effect=lambda p: p), \
         patch.dict(sys.modules, {"routers.system": MagicMock(
             _stream_pause_events={}, _stream_flow_events={})}):
        await stream_normal.stream_normal_audio(
            controller=controller, track_id=TRACK_ID, websocket=ws,
        )


def _terminal(sent: list) -> dict | None:
    """The terminal message's `data` payload — `reason` lives inside it, not
    at the envelope's top level."""
    for msg in reversed(sent):
        if msg.get("type") in ("audio_stream_end", "stream_end"):
            return msg.get("data", {})
    return None


@pytest.mark.regression
class TestNormalStreamReadTimeout:

    @pytest.mark.asyncio
    async def test_stalled_read_terminates_instead_of_hanging(self):
        """The whole point of #5082: a read that never returns must not wedge
        the stream. Without the wait_for wrappers this call never completes."""
        release = threading.Event()
        reads: list = []
        sent: list = []
        controller = _make_controller()
        ws = _make_websocket(sent)

        try:
            # Generous relative to FAST_TIMEOUT; the pre-fix code hangs
            # forever, so any finite bound distinguishes fixed from broken.
            await asyncio.wait_for(
                _run_stream(controller, ws, release, reads), timeout=20.0
            )
        finally:
            release.set()

        assert reads, "the stream never attempted a disk read"

    @pytest.mark.asyncio
    async def test_stalled_read_reports_an_error_to_the_client(self):
        """Previously the client got neither chunks nor an error and could
        only recover by disconnecting."""
        release = threading.Event()
        sent: list = []
        controller = _make_controller()
        ws = _make_websocket(sent)

        try:
            await asyncio.wait_for(
                _run_stream(controller, ws, release, []), timeout=20.0
            )
        finally:
            release.set()

        errors = [m for m in sent if "error" in str(m.get("type", ""))]
        assert errors, f"no error message sent to client; got types {[m.get('type') for m in sent]}"

    @pytest.mark.asyncio
    async def test_stalled_read_does_not_report_the_track_as_completed(self):
        """#4790's rule: a stream with gaps must not claim reason='completed'.
        A storage abort is a server-side failure, so it reports 'errored'
        rather than 'stopped' (which is reserved for a clean client-driven
        exit)."""
        release = threading.Event()
        sent: list = []
        controller = _make_controller()
        ws = _make_websocket(sent)

        try:
            await asyncio.wait_for(
                _run_stream(controller, ws, release, []), timeout=20.0
            )
        finally:
            release.set()

        end = _terminal(sent)
        assert end is not None, "no terminal stream_end message was sent"
        assert end.get("reason") == "errored", (
            f"expected reason='errored' for a storage abort, got {end.get('reason')!r}"
        )

    @pytest.mark.asyncio
    async def test_stalled_read_releases_the_stream_semaphore(self):
        """The blast radius in #5082: a permit held forever eventually starves
        every track in the app with 'Server busy'."""
        release = threading.Event()
        sent: list = []
        controller = _make_controller()
        ws = _make_websocket(sent)
        before = controller._stream_semaphore._value

        try:
            await asyncio.wait_for(
                _run_stream(controller, ws, release, []), timeout=20.0
            )
        finally:
            release.set()

        assert controller._stream_semaphore._value == before, (
            "stream permit was not released after the read timed out"
        )

    @pytest.mark.asyncio
    async def test_consecutive_timeouts_stop_re_arming_reads(self):
        """wait_for bounds the coroutine, not the blocking read underneath it
        (#4815/#4727) — the abandoned worker thread keeps running. So the loop
        must stop retrying once the storage is clearly gone, rather than
        stranding one executor thread per chunk and holding the permit for
        TOTAL_CHUNKS x CHUNK_PROCESS_TIMEOUT."""
        release = threading.Event()
        reads: list = []
        sent: list = []
        controller = _make_controller()
        ws = _make_websocket(sent)

        try:
            await asyncio.wait_for(
                _run_stream(controller, ws, release, reads), timeout=20.0
            )
        finally:
            release.set()

        # Each failed iteration may arm at most one look-ahead read alongside
        # its inline read, so allow 2 per tolerated timeout.
        limit = 2 * stream_normal.MAX_CONSECUTIVE_READ_TIMEOUTS
        assert len(reads) <= limit, (
            f"kept re-arming reads on unreachable storage: {len(reads)} reads "
            f"for {TOTAL_CHUNKS} chunks (limit {limit})"
        )

    @pytest.mark.asyncio
    async def test_healthy_reads_are_unaffected(self):
        """The bound must not change the happy path: instant reads still
        stream every chunk and report completion."""
        release = threading.Event()
        release.set()
        reads: list = []
        sent: list = []
        controller = _make_controller()
        ws = _make_websocket(sent)

        await asyncio.wait_for(
            _run_stream(controller, ws, release, reads, block_reads=False),
            timeout=20.0,
        )

        end = _terminal(sent)
        assert end is not None, "no terminal stream_end message was sent"
        assert end.get("reason") == "completed", (
            f"healthy stream reported reason={end.get('reason')!r}"
        )
        # Every chunk read exactly once — the first inline, the rest served by
        # the look-ahead task. (send_bytes fires several times per chunk; the
        # PCM framing is stream_protocol's business, not this test's.)
        assert len(reads) == TOTAL_CHUNKS, (
            f"expected {TOTAL_CHUNKS} disk reads, got {len(reads)}"
        )
        assert ws.send_bytes.await_count > 0, "no PCM was sent on the healthy path"


@pytest.mark.regression
class TestBothReadSitesAreBounded:
    """#5082's acceptance criterion, checked structurally so a future edit
    that re-introduces a bare `to_thread(_read_audio_chunk, ...)` fails here
    even if the behavioural tests above happen not to cover that path."""

    def test_no_unbounded_read_audio_chunk_call_remains(self):
        # #5032 moved the read loop into pump_normal_chunks. The guard follows
        # the code: what it protects is that neither chunk producer calls the
        # blocking reader without a wait_for around it, and both producers now
        # live in that function.
        src = inspect.getsource(stream_normal_chunks.pump_normal_chunks)
        code = "\n".join(
            line for line in src.splitlines() if not line.strip().startswith("#")
        )

        # Both producers must sit inside a wait_for: the inline read wraps the
        # offload call directly, the look-ahead one bounds the await of the
        # task it armed earlier. The offload is `run_in_stream_executor`
        # rather than bare `asyncio.to_thread` since #5086 moved the per-chunk
        # hot path onto its own pool; either spelling satisfies #5082.
        assert re.search(
            r"wait_for\(\s*\n?\s*(asyncio\.to_thread|run_in_stream_executor)"
            r"\(\s*\n?\s*_read_audio_chunk", code
        ), "the inline _read_audio_chunk read is not wrapped in asyncio.wait_for"

        assert re.search(
            r"wait_for\(\s*\n?\s*lookahead_read", code
        ), "the look-ahead read is not bounded by asyncio.wait_for"

        assert "_asc.CHUNK_PROCESS_TIMEOUT" in code, (
            "reads should use the same CHUNK_PROCESS_TIMEOUT constant as every "
            "sibling streaming path, not a local literal"
        )
