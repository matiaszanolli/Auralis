"""A stream reports the fingerprint status its processor actually masters with (#6507).

ChunkedAudioProcessor's construction extracts the fingerprint when it is missing (a .25d sidecar,
no DB row), but the readiness check that ran afterwards tested only the DB, so the client was told
"queued, using standard mastering" for a stream mastered against the whole-track plan; the seek path
reported nothing at all. The check now takes in_use from the processor, and play and seek pass it.
"""

import ast
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(BACKEND))

from core import stream_fingerprint  # noqa: E402


def _controller(in_db: bool):
    repo = MagicMock()
    repo.fingerprints.exists.return_value = in_db
    return SimpleNamespace(_get_repository_factory=lambda: repo, _send_fingerprint_progress=AsyncMock())


def _status(controller):
    return controller._send_fingerprint_progress.await_args.kwargs


@pytest.mark.asyncio
async def test_an_extracted_fingerprint_is_reported_cached_and_still_persisted():
    controller = _controller(in_db=False)
    queue = MagicMock()
    queue.enqueue.return_value = True
    with patch("analysis.fingerprint_queue.get_fingerprint_queue", return_value=queue):
        ready = await stream_fingerprint.check_or_queue_fingerprint(controller, 7, MagicMock(), in_use=True)

    assert ready is True
    assert _status(controller)["status"] == "cached"
    assert "standard mastering" not in _status(controller)["message"]
    queue.enqueue.assert_called_once_with(7)  # only to persist the DB row


@pytest.mark.asyncio
async def test_without_a_fingerprint_the_stream_is_reported_as_standard_mastering():
    controller = _controller(in_db=False)
    queue = MagicMock()
    queue.enqueue.return_value = True
    with patch("analysis.fingerprint_queue.get_fingerprint_queue", return_value=queue):
        ready = await stream_fingerprint.check_or_queue_fingerprint(controller, 7, MagicMock(), in_use=False)

    assert ready is False
    assert _status(controller)["status"] == "queued"


@pytest.mark.parametrize("module", ["stream_enhanced.py", "stream_seek.py"])
def test_play_and_seek_pass_what_their_processor_masters_with(module):
    tree = ast.parse((BACKEND / "core" / module).read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "_check_or_queue_fingerprint"]
    assert calls, f"{module} never reports the fingerprint status"
    assert all(any(k.arg == "in_use" for k in call.keywords) for call in calls)
