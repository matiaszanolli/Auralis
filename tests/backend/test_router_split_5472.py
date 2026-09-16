"""
Regression: splitting routers/player.py and routers/processing_api.py into
sub-resource siblings (#5472) must not drop, add or reorder a route.

A dropped registration is silent -- the app still starts -- so this pins the
exact (path, method, handler) table each factory builds, in order. The order
matters for /api/player: the queue-history routes must be registered before
DELETE /api/player/queue/{index}, or a DELETE to .../history is captured by
{index} and 422s.
"""

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from routers import player, processing_api  # noqa: E402

PLAYER_ROUTES = [
    ("/api/player/status", "GET", "get_player_status"),
    ("/api/player/load", "POST", "load_track"),
    ("/api/player/seek", "POST", "seek_position"),
    ("/api/player/volume", "POST", "set_volume"),
    ("/api/player/queue", "GET", "get_queue"),
    ("/api/player/queue", "POST", "set_queue"),
    ("/api/player/queue/history", "GET", "get_queue_history"),
    ("/api/player/queue/history", "POST", "record_queue_history"),
    ("/api/player/queue/undo", "POST", "undo_queue_operation"),
    ("/api/player/queue/history", "DELETE", "clear_queue_history"),
    ("/api/player/queue/{index}", "DELETE", "remove_from_queue"),
    ("/api/player/queue/reorder", "PUT", "reorder_queue"),
    ("/api/player/queue/clear", "POST", "clear_queue"),
    ("/api/player/queue/add-track", "POST", "add_track_to_queue"),
    ("/api/player/queue/move", "PUT", "move_queue_track"),
    ("/api/player/queue/shuffle", "POST", "shuffle_queue"),
    ("/api/player/queue/repeat", "POST", "set_repeat_mode"),
    ("/api/player/next", "POST", "next_track"),
    ("/api/player/previous", "POST", "previous_track"),
]

PROCESSING_ROUTES = [
    ("/api/processing/process", "POST", "process_audio"),
    ("/api/processing/upload-and-process", "POST", "upload_and_process"),
    ("/api/processing/job/{job_id}", "GET", "get_job_status"),
    ("/api/processing/job/{job_id}/download", "GET", "download_result"),
    ("/api/processing/job/{job_id}/cancel", "POST", "cancel_job"),
    ("/api/processing/jobs", "GET", "list_jobs"),
    ("/api/processing/queue/status", "GET", "get_queue_status"),
    ("/api/processing/presets", "GET", "get_processing_presets"),
    ("/api/processing/parameters", "GET", "get_processing_parameters"),
    ("/api/processing/jobs/cleanup", "DELETE", "cleanup_old_jobs"),
]


def _table(router):
    return [
        (r.path, method, r.endpoint.__name__)
        for r in router.routes
        for method in sorted(r.methods)
    ]


@pytest.fixture
def player_router():
    saved = dict(vars(player._deps))
    router = player.create_player_router(
        lambda: None, lambda: None, lambda: None, None, None, lambda t: t
    )
    yield router
    # create_player_router() writes the process-wide _deps holder; put back
    # whatever main.app's own factory call stored there.
    for name in list(vars(player._deps)):
        delattr(player._deps, name)
    for name, value in saved.items():
        setattr(player._deps, name, value)


def test_player_route_table_is_unchanged(player_router):
    assert _table(player_router) == PLAYER_ROUTES


def test_processing_route_table_is_unchanged():
    router = processing_api.create_processing_router(lambda: None)
    assert _table(router) == PROCESSING_ROUTES


@pytest.mark.parametrize(
    ("module", "routes"),
    [(player, PLAYER_ROUTES), (processing_api, PROCESSING_ROUTES)],
)
def test_every_handler_is_still_importable_from_the_router_module(module, routes):
    """`from routers.player import X` and dependency_overrides keyed on
    routers.player providers keep working after the move."""
    for _path, _method, name in routes:
        assert callable(getattr(module, name)), f"{module.__name__}.{name} missing"
