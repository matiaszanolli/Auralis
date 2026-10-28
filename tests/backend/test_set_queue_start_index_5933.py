"""set_queue's start_index addresses the requested ids, not the filtered list (#5933).

Ids missing from the library are dropped, then the same numeric start_index was applied to the
shorter list: it pointed at a different track, or past the end, and was never range-checked
against the request.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.queue_set_mixin import _start_index_after_filtering  # noqa: E402


def _tracks(*ids):
    return [SimpleNamespace(id=i) for i in ids]


@pytest.mark.parametrize(
    "requested, kept, start, expected",
    [
        ([10, 20, 30], [10, 20, 30], 2, 2),          # nothing dropped: unchanged
        ([10, 99, 30, 40], [10, 30, 40], 2, 1),       # 99 was before the start: 30 is now index 1
        ([10, 20, 99, 40], [10, 20, 40], 2, 2),       # the requested track itself was dropped: next survivor
        ([10, 20, 30, 98, 99], [10, 20, 30], 4, 2),   # everything from the start on was dropped: last survivor
        ([98, 10, 20], [10, 20], 0, 0),               # the first request was dropped: first survivor
    ],
)
def test_start_index_follows_the_requested_track(requested, kept, start, expected):
    assert _start_index_after_filtering(requested, _tracks(*kept), start) == expected


def test_duplicate_ids_keep_their_own_positions():
    assert _start_index_after_filtering([7, 7, 99, 7], _tracks(7, 7, 7), 3) == 2


@pytest.mark.asyncio
async def test_a_start_index_outside_the_request_is_rejected():
    from unittest.mock import AsyncMock, MagicMock

    from services.errors import InvalidRequest
    from services.queue_service import QueueService

    repo = SimpleNamespace(get_by_ids=lambda ids: {i: SimpleNamespace(id=i, filepath=f"/m/{i}") for i in ids})
    service = QueueService(
        audio_player=SimpleNamespace(queue=MagicMock()),
        player_state_manager=SimpleNamespace(set_queue=AsyncMock(), broadcast_state=AsyncMock()),
        library_database=SimpleNamespace(tracks=repo),
        connection_manager=MagicMock(broadcast=AsyncMock()),
        create_track_info_fn=lambda t: t,
    )

    with pytest.raises(InvalidRequest):
        await service.set_queue([1, 2, 3], start_index=3)
