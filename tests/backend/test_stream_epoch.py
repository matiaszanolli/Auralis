"""Stream epoch discriminates superseded streams (#4563).

On seek the client resets its PCM buffer BEFORE sending the `seek` frame, but
the backend cancels the prior streaming task only when its receive loop
dispatches that frame. Frames already handed to the send queue (up to
`_SEND_QUEUE_MAXSIZE`) plus whatever sits in socket/TCP buffers — roughly
0.9-3.5 s of pre-seek audio — therefore arrive AFTER the reset and are appended
to the fresh buffer. The follow-up `audio_stream_start` carries `is_seek: true`,
which by design tells the client to PRESERVE its buffer, so the stale audio is
never discarded and plays as a stutter/rewind at the head of every seek.

Nothing else on the wire discriminates those frames: `track_id` is the same
track, `chunk_index` is >= the last seen so the client's out-of-sequence guard
(which fires only on `incoming < last - 1`) does not trip, and `seq` restarts at
0 at each `audio_stream_start`.

The epoch is that discriminator: stamped on `audio_stream_start` and on every
`audio_chunk_meta`, monotonic process-wide.
"""

import asyncio
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

from core import audio_stream_controller as asc  # noqa: E402
from core import stream_messages, stream_protocol  # noqa: E402

pytestmark = pytest.mark.asyncio

_BACKEND_CORE = _REPO_ROOT / "auralis-web" / "backend" / "core"


def _controller(sent: list) -> Mock:
    controller = Mock()

    async def _safe_send(websocket, message):
        sent.append(message)
        return True

    async def _safe_send_bytes(websocket, payload):
        return True

    controller._safe_send = _safe_send
    controller._safe_send_bytes = _safe_send_bytes
    controller._is_websocket_connected = Mock(return_value=True)
    return controller


async def _start(controller, track_id=1, **kwargs):
    return await stream_messages.send_stream_start(
        controller,
        Mock(),
        track_id=track_id,
        preset="none",
        intensity=1.0,
        sample_rate=44100,
        channels=2,
        total_chunks=4,
        chunk_duration=15.0,
        total_duration=60.0,
        **kwargs,
    )


def _epochs_of(sent, msg_type):
    return [
        m["data"].get("stream_epoch") for m in sent if m.get("type") == msg_type
    ]


class TestEpochOnStreamStart:
    async def test_stream_start_carries_an_epoch(self):
        sent: list = []
        await _start(_controller(sent))

        assert _epochs_of(sent, "audio_stream_start")[0] is not None

    async def test_epoch_increments_per_stream_start(self):
        sent: list = []
        controller = _controller(sent)

        await _start(controller)
        await _start(controller)
        await _start(controller)

        epochs = _epochs_of(sent, "audio_stream_start")
        assert epochs == sorted(epochs)
        assert len(set(epochs)) == 3, "each stream must get a distinct epoch"

    async def test_seek_start_also_carries_an_epoch(self):
        """The seek path is exactly the case the epoch exists for."""
        sent: list = []
        await _start(
            _controller(sent), start_chunk=1, seek_position=17.0, seek_offset=2.0
        )

        data = sent[0]["data"]
        assert data["is_seek"] is True
        assert data["stream_epoch"] is not None

    async def test_epoch_is_never_reused_across_concurrent_tasks(self):
        """Concurrent streams in different tasks must not collide."""
        sent: list = []
        controller = _controller(sent)

        await asyncio.gather(*(_start(controller, track_id=i) for i in range(8)))

        epochs = _epochs_of(sent, "audio_stream_start")
        assert len(set(epochs)) == 8


class TestEpochOnChunkMeta:
    async def test_chunk_meta_carries_the_current_stream_epoch(self):
        sent: list = []
        controller = _controller(sent)

        await _start(controller)
        start_epoch = _epochs_of(sent, "audio_stream_start")[0]

        await stream_protocol.send_pcm_chunk(
            controller,
            Mock(),
            pcm_samples=np.zeros((1024, 2), dtype=np.float32),
            chunk_index=0,
            total_chunks=4,
        )

        chunk_epochs = _epochs_of(sent, "audio_chunk_meta")
        assert chunk_epochs, "no audio_chunk_meta emitted"
        assert all(e == start_epoch for e in chunk_epochs)

    async def test_a_new_stream_start_rebaselines_the_chunk_epoch(self):
        """Frames emitted after a new start must carry the NEW epoch.

        This is the property the client relies on: a stale frame is one whose
        epoch is lower than the epoch of the most recent stream start.
        """
        sent: list = []
        controller = _controller(sent)

        await _start(controller)
        first_epoch = _epochs_of(sent, "audio_stream_start")[0]
        await _start(controller)
        second_epoch = _epochs_of(sent, "audio_stream_start")[1]

        await stream_protocol.send_pcm_chunk(
            controller,
            Mock(),
            pcm_samples=np.zeros((512, 2), dtype=np.float32),
            chunk_index=0,
            total_chunks=4,
        )

        assert second_epoch > first_epoch
        assert set(_epochs_of(sent, "audio_chunk_meta")) == {second_epoch}

    async def test_chunk_epoch_survives_the_producer_context_copy(self):
        """send_pcm_chunk runs its producer via asyncio.gather.

        That copies the context, so the epoch must be readable there — the same
        constraint that forced `seq` to use a mutable cell (#3841). Reading is
        fine; this pins that it stays readable.
        """
        sent: list = []
        controller = _controller(sent)
        await _start(controller)

        await stream_protocol.send_pcm_chunk(
            controller,
            Mock(),
            # Large enough to span several ~300 KB frames.
            pcm_samples=np.zeros((400_000, 2), dtype=np.float32),
            chunk_index=0,
            total_chunks=4,
        )

        chunk_epochs = _epochs_of(sent, "audio_chunk_meta")
        assert len(chunk_epochs) > 1, "expected multiple frames"
        assert all(e is not None for e in chunk_epochs)
        assert len(set(chunk_epochs)) == 1


class TestWiringCompleteness:
    """#4563 WIRING/CONSISTENCY checks."""

    def test_both_producers_stamp_the_epoch(self):
        start_src = (_BACKEND_CORE / "stream_messages.py").read_text()
        chunk_src = (_BACKEND_CORE / "stream_protocol.py").read_text()

        assert "stream_epoch" in start_src
        assert "stream_epoch" in chunk_src

    def test_every_is_seek_producer_goes_through_send_stream_start(self):
        """Every `is_seek: true` emitter must therefore carry an epoch.

        `is_seek` is derived inside send_stream_start from its seek kwargs, so
        no caller can set it independently — that is what makes epoch coverage
        automatic. Pin it: no other core module may write the key itself.
        """
        offenders = []
        for path in _BACKEND_CORE.glob("*.py"):
            if path.name == "stream_messages.py":
                continue
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if re.search(r"""["']is_seek["']\s*[:=]""", line):
                    offenders.append(f"{path.name}:{lineno}: {line.strip()}")

        assert not offenders, (
            "is_seek set outside send_stream_start would bypass the epoch "
            "stamping (#4563): " + "; ".join(offenders)
        )

    def test_frontend_consumes_the_epoch(self):
        """A stamp with no reader is the defect this issue was about."""
        core = (
            _REPO_ROOT
            / "auralis-web" / "frontend" / "src" / "hooks" / "enhancement"
            / "useAudioStreamingCore.ts"
        )
        if not core.exists():  # pragma: no cover - frontend not checked out
            pytest.skip("frontend not present")
        src = core.read_text()

        assert "stream_epoch" in src, "no frontend consumer of stream_epoch"
        assert "streamEpochRef" in src
