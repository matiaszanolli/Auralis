"""Project-wide typed WebSocket broadcast boundary regression tests (#5293)."""

import ast
import sys
from pathlib import Path
from typing import Any, Literal, get_args, get_origin, get_overloads, is_typeddict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "auralis-web" / "backend"
_BOUNDARY = _BACKEND / "websocket" / "outbound_messages.py"

if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from websocket.outbound_messages import (
    BroadcastMessageType,
    broadcast_typed,
)


class RecordingManager:
    def __init__(self, error: Exception | None = None) -> None:
        self.messages: list[dict[str, Any]] = []
        self.error = error

    async def broadcast(self, message: dict[str, Any]) -> None:
        if self.error is not None:
            raise self.error
        self.messages.append(message)


@pytest.mark.asyncio
async def test_broadcast_typed_preserves_the_wire_envelope() -> None:
    manager = RecordingManager()

    await broadcast_typed(
        manager,
        "cache_cleared",
        {"message": "All caches cleared"},
    )

    assert manager.messages == [
        {"type": "cache_cleared", "data": {"message": "All caches cleared"}}
    ]


@pytest.mark.asyncio
async def test_suppression_is_explicit_and_default_errors_propagate() -> None:
    manager = RecordingManager(RuntimeError("socket closed"))

    with pytest.raises(RuntimeError, match="socket closed"):
        await broadcast_typed(manager, "cache_cleared", {"message": "clear"})

    await broadcast_typed(
        manager,
        "cache_cleared",
        {"message": "clear"},
        suppress_errors=True,
    )


def test_every_message_discriminator_has_a_typed_payload_overload() -> None:
    declared = set(get_args(BroadcastMessageType))
    overloaded: set[str] = set()

    for signature in get_overloads(broadcast_typed):
        message_annotation = signature.__annotations__["message_type"]
        payload_annotation = signature.__annotations__["data"]
        assert get_origin(message_annotation) is Literal
        assert is_typeddict(payload_annotation)
        overloaded.update(get_args(message_annotation))

    assert overloaded == declared
    assert len(declared) > 20


def test_all_backend_manager_broadcasts_are_centralized() -> None:
    direct_calls: list[str] = []
    for path in sorted(_BACKEND.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "broadcast"
            ):
                direct_calls.append(f"{path.relative_to(_REPO_ROOT)}:{node.lineno}")

    assert len(direct_calls) == 1
    assert direct_calls[0].startswith(f"{_BOUNDARY.relative_to(_REPO_ROOT)}:")


def test_production_emitters_use_literal_discriminators() -> None:
    calls: list[str] = []
    invalid: list[str] = []
    declared = set(get_args(BroadcastMessageType))

    for path in sorted(_BACKEND.rglob("*.py")):
        if path == _BOUNDARY:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "broadcast_typed"
            ):
                continue
            site = f"{path.relative_to(_REPO_ROOT)}:{node.lineno}"
            calls.append(site)
            if (
                len(node.args) < 2
                or not isinstance(node.args[1], ast.Constant)
                or node.args[1].value not in declared
            ):
                invalid.append(site)

    assert not invalid
    assert len(calls) >= 45


def test_playlist_reorder_uses_the_frontend_contract_literal() -> None:
    source = (_BACKEND / "routers" / "playlists.py").read_text()
    assert '"action": "reordered"' in source
    assert "tracks_reordered" not in source
