"""
Regression tests: player_state snapshots identify the backend process (#5487)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The playback session lives only in PlayerStateManager's memory, so a backend
restart hands a reconnecting client an empty snapshot identical to a fresh
launch. Every snapshot now carries a per-process ``server_instance_id``; the
frontend (useServerRestartNotice) warns when it changes.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import subprocess
import sys
from pathlib import Path
from typing import get_type_hints
from unittest.mock import MagicMock

BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(BACKEND))

from core.state_manager import PlayerStateManager
from player_state import SERVER_INSTANCE_ID, PlayerState
from websocket.outbound_messages import PlayerStatePayload


def test_snapshot_carries_the_process_instance_id():
    payload = PlayerStateManager(MagicMock()).get_state().model_dump()
    assert payload["server_instance_id"] == SERVER_INSTANCE_ID
    assert len(SERVER_INSTANCE_ID) == 32


def test_id_is_stable_within_one_process():
    assert PlayerState().server_instance_id == PlayerState().server_instance_id


def test_a_new_process_gets_a_new_id():
    code = "import player_state; print(player_state.SERVER_INSTANCE_ID)"
    other = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert other and other != SERVER_INSTANCE_ID


def test_typed_broadcast_payload_declares_the_field():
    assert get_type_hints(PlayerStatePayload)["server_instance_id"] is str
    assert set(get_type_hints(PlayerStatePayload)) == set(PlayerState.model_fields)
