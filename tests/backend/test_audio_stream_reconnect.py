"""
Regression tests for WS reconnect-mid-stream behaviour (#3861 / BE-TC-6)

The WS handler in system.py maintains per-ws-id state dicts
(_active_streaming_tasks, _active_streaming_track_ids, _stream_pause_events,
_stream_flow_events).  The `finally` block on disconnect cleans them up so a
reconnecting client starts with fresh state.  Without this cleanup the second
connection would be deduplicated as an already-streaming duplicate and silently
dropped, or would observe stale flow-control / pause events.

These tests verify that a disconnect + reconnect cycle:
  1. completes without hanging or crashing;
  2. produces a clean response on the second connection (not a stale-state error).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


class TestWebSocketReconnect:
    """WS reconnect-after-disconnect verifies per-ws-id state cleanup."""

    @staticmethod
    def _recv_until(websocket, target_types: set, max_reads: int = 15) -> dict:
        """Drain frames and return the first whose type is in ``target_types``."""
        for _ in range(max_reads):
            try:
                msg = json.loads(websocket.receive_text())
                if msg.get("type") in target_types:
                    return msg
            except Exception:
                break
        raise AssertionError(
            f"None of {target_types} received within {max_reads} reads"
        )

    def test_reconnect_after_play_enhanced_produces_clean_stream(self, client):
        """
        First connection: send play_enhanced for a nonexistent track → get
        audio_stream_error (fast path — track not in DB).
        Disconnect.
        Second connection: same play_enhanced → must also produce a clean
        audio_stream_error (not a 'duplicate stream' skip or a hang).
        """
        TRACK_ID = 99999  # guaranteed not in the test DB

        payload = json.dumps({
            "type": "play_enhanced",
            "data": {"track_id": TRACK_ID, "preset": "adaptive", "intensity": 1.0},
        })

        # --- First connection ---
        with client.websocket_connect("/ws") as ws1:
            ws1.send_text(payload)
            msg1 = self._recv_until(ws1, {"audio_stream_error"})
            assert msg1["data"]["stream_type"] == "enhanced"

        # ws1 is now closed; the finally block in the WS handler should have
        # cleaned up _active_streaming_tasks[ws1_id] and _active_streaming_track_ids.

        # --- Second connection (fresh ws_id) ---
        with client.websocket_connect("/ws") as ws2:
            ws2.send_text(payload)
            msg2 = self._recv_until(ws2, {"audio_stream_error"})
            # Must receive the same error shape, not a "duplicate stream" silence
            assert msg2["data"]["stream_type"] == "enhanced"

    def test_reconnect_after_play_normal_produces_clean_stream(self, client):
        """
        play_normal with a nonexistent track also exercises the disconnect /
        reconnect cleanup path for the normal-stream task dict.
        """
        TRACK_ID = 88888

        payload = json.dumps({
            "type": "play_normal",
            "data": {"track_id": TRACK_ID},
        })

        error_types = {"audio_stream_error", "error"}

        with client.websocket_connect("/ws") as ws1:
            ws1.send_text(payload)
            msg1 = self._recv_until(ws1, error_types)
            assert isinstance(msg1, dict)

        # Second connection must receive its own error (no stale task block)
        with client.websocket_connect("/ws") as ws2:
            ws2.send_text(payload)
            msg2 = self._recv_until(ws2, error_types)
            assert isinstance(msg2, dict)

    def test_resume_after_reconnect_does_not_raise(self, client):
        """
        Sending `resume` on a fresh connection (no active stream) must not
        crash the handler — it already tests the case where the pause-event
        map has no entry for the ws_id (reconnect scenario).
        """
        with client.websocket_connect("/ws") as ws1:
            ws1.send_text(json.dumps({"type": "ping"}))
            for _ in range(10):
                msg = json.loads(ws1.receive_text())
                if msg["type"] == "pong":
                    break

        with client.websocket_connect("/ws") as ws2:
            ws2.send_text(json.dumps({"type": "resume"}))
            msg = None
            for _ in range(10):
                msg = json.loads(ws2.receive_text())
                if msg.get("type") == "playback_resumed":
                    break
            assert msg is not None and msg.get("type") == "playback_resumed"
