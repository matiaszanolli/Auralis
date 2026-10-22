"""
Shared service guards and queue-mutation scaffold (#5790)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Twenty-eight hand-written "X not available" guards and eight copies of
"invalidate the set_queue generation, then take the engine lock" collapsed into
``errors.require_collaborators`` and ``QueueServiceBase._queue_mutation``. The
first fixes the message and precedence; the second is what makes a ninth
mutator inherit the #5320 protocol by using it.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from services.errors import ServiceUnavailable, require_collaborators  # noqa: E402
from services.queue_service_base import QueueServiceBase  # noqa: E402


def _base(audio_player=None) -> QueueServiceBase:
    return QueueServiceBase(
        audio_player=audio_player,
        player_state_manager=MagicMock(),
        library_database=MagicMock(),
        connection_manager=MagicMock(),
        create_track_info_fn=MagicMock(),
    )


class TestRequireCollaborators:
    @pytest.mark.parametrize(
        "name, message",
        [
            ("audio_player", "Audio player not available"),
            ("player_state_manager", "Player state manager not available"),
            ("library", "Library not available"),
            ("queue_manager", "Queue manager not available"),
        ],
    )
    def test_names_the_missing_collaborator(self, name, message):
        with pytest.raises(ServiceUnavailable, match=message):
            require_collaborators(**{name: None})

    def test_reports_the_first_missing_in_keyword_order(self):
        with pytest.raises(ServiceUnavailable, match="Player state manager"):
            require_collaborators(audio_player=object(), player_state_manager=None, library=None)

    def test_passes_when_everything_is_present(self):
        assert require_collaborators(audio_player=object(), player_state_manager=object()) is None


class TestQueueGuard:
    def test_player_without_a_queue_is_unavailable(self):
        with pytest.raises(ServiceUnavailable, match="Queue manager"):
            _base(audio_player=object())._require_queue()

    def test_missing_player_is_unavailable(self):
        with pytest.raises(ServiceUnavailable, match="Queue manager"):
            _base(audio_player=None)._require_queue()

    def test_player_with_a_queue_passes(self):
        assert _base(audio_player=MagicMock())._require_queue() is None


@pytest.mark.asyncio
class TestQueueMutationScope:
    async def test_supersedes_in_flight_set_queue_and_holds_the_engine_lock(self):
        service = _base(audio_player=MagicMock())
        before = service._set_queue_generation

        async with service._queue_mutation():
            assert service._set_queue_engine_lock.locked()
            assert service._set_queue_generation > before

        assert not service._set_queue_engine_lock.locked()

    async def test_releases_the_lock_when_the_body_raises(self):
        service = _base(audio_player=MagicMock())

        with pytest.raises(RuntimeError):
            async with service._queue_mutation():
                raise RuntimeError("boom")

        assert not service._set_queue_engine_lock.locked()

    async def test_early_return_inside_the_scope_releases_the_lock(self):
        service = _base(audio_player=MagicMock())

        async def mutate() -> str:
            async with service._queue_mutation():
                return "nothing to do"

        assert await mutate() == "nothing to do"
        assert not service._set_queue_engine_lock.locked()
