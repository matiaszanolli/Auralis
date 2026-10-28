"""QueueInfoResponse ships only its declared fields (#5983).

The model was extra="allow" and get_queue_info() returns the engine's dict
verbatim, so the engine-internal `repeat_enabled` bool - deliberately replaced by
the three-valued `repeat_mode` in #3896 - was shipped next to it, as would be any
key the engine adds later. It is extra="ignore" now.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.player_models import QueueInfoResponse  # noqa: E402

ENGINE_DICT = {
    "tracks": [],
    "current_index": 0,
    "current_track": None,
    "track_count": 0,
    "has_next": False,
    "has_previous": False,
    "shuffle_enabled": False,
    "repeat_enabled": True,  # engine-internal; the response says repeat_mode
}


def test_engine_only_keys_are_not_shipped():
    payload = QueueInfoResponse.model_validate({**ENGINE_DICT, "repeat_mode": "all"}).model_dump()

    assert "repeat_enabled" not in payload
    assert payload["repeat_mode"] == "all"


def test_a_future_engine_key_is_not_shipped_either():
    payload = QueueInfoResponse.model_validate({**ENGINE_DICT, "internal_cursor": 7}).model_dump()

    assert "internal_cursor" not in payload


def test_every_declared_field_still_round_trips():
    payload = QueueInfoResponse.model_validate({**ENGINE_DICT, "repeat_mode": "one"}).model_dump()

    assert {"tracks", "current_index", "current_track", "track_count", "has_next", "has_previous",
            "shuffle_enabled", "repeat_mode"} <= set(payload)
