"""
Regression tests for the player router's closure-to-module-level extraction
(#4670).

create_player_router() used to be a 515-line closure -- every handler was a
nested `async def` reachable only by constructing the whole router with its
full dependency graph. Handlers are now module-level `async def` functions
with FastAPI Depends() defaults; a caller that wants to unit-test one
directly just passes the dependency/service explicitly as a keyword
argument, bypassing Depends() (and _PlayerDeps, and the router) entirely.
These tests exist to prove that seam is real, not just that it types.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.player import (  # noqa: E402
    get_player_status,
    next_track,
    previous_track,
    set_volume,
    SetVolumeRequest,
)

pytestmark = pytest.mark.asyncio


async def test_get_player_status_callable_with_a_bare_stub_service():
    """No router, no _PlayerDeps, no app -- just the handler and a stub."""
    stub_service = MagicMock()
    stub_service.get_status = AsyncMock(return_value={"status": "playing"})

    result = await get_player_status(service=stub_service)

    assert result == {"status": "playing"}
    stub_service.get_status.assert_awaited_once()


async def test_set_volume_callable_with_a_bare_stub_service():
    stub_service = MagicMock()
    stub_service.set_volume = AsyncMock(return_value={"message": "Volume set"})

    result = await set_volume(SetVolumeRequest(volume=42), service=stub_service)

    # 42/100 normalized before the service call, then the response volume is
    # converted back to the original 0-100 scale (#3204) -- preserved by the
    # extraction, not just the direct-call plumbing.
    stub_service.set_volume.assert_awaited_once_with(0.42)
    assert result["volume"] == 42


async def test_next_track_callable_with_a_bare_stub_service():
    stub_service = MagicMock()
    stub_service.next_track = AsyncMock(return_value={"message": "Skipped"})

    result = await next_track(service=stub_service)

    assert result == {"message": "Skipped"}


async def test_previous_track_callable_with_a_bare_stub_service():
    stub_service = MagicMock()
    stub_service.previous_track = AsyncMock(return_value={"message": "Skipped back"})

    result = await previous_track(service=stub_service)

    assert result == {"message": "Skipped back"}
