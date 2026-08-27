"""Schema models declare their real value sets (#3896).

Two related looseness defects:

1. `ProcessResponse.status` and `JobStatusResponse.status` were bare `str`,
   and `list_jobs`'s `status` query param was `str | None` guarded by a
   hand-rolled membership check -- even though `ProcessingStatus` already
   existed and the handler already used it to build that check. OpenAPI
   therefore published "string" instead of the five valid values.

2. `QueueInfoResponse.repeat_enabled: bool` diverged from the canonical
   three-valued `PlayerState.repeat_mode`. The engine queue genuinely only
   tracks a boolean, so the response silently collapsed "all" and "one" and
   could not populate the frontend's `Queue.repeatMode` -- callers had to hit
   GET /api/player/status instead, defeating the queue endpoint.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from core.job_models import ProcessingStatus  # noqa: E402
from player_state import create_track_info  # noqa: E402
from routers.player import QueueInfoResponse, SetVolumeRequest  # noqa: E402
from routers.processing_api import JobStatusResponse, ProcessResponse  # noqa: E402
from services.queue_service import QueueService  # noqa: E402


# ---------------------------------------------------------------------------
# Job status enums
# ---------------------------------------------------------------------------


class TestJobStatusIsAnEnum:
    def test_job_status_response_rejects_an_unknown_status(self):
        with pytest.raises(Exception):
            JobStatusResponse(job_id="j1", status="not-a-real-status", progress=0.0)

    def test_process_response_rejects_an_unknown_status(self):
        with pytest.raises(Exception):
            ProcessResponse(job_id="j1", status="bogus", message="hi")

    @pytest.mark.parametrize("value", [s.value for s in ProcessingStatus])
    def test_every_enum_member_is_accepted(self, value):
        model = JobStatusResponse(job_id="j1", status=value, progress=0.5)
        assert model.status == ProcessingStatus(value)

    def test_serialises_to_the_same_plain_string_as_before(self):
        """ProcessingStatus is a str Enum, so the wire format is unchanged --
        this is a schema tightening, not a payload change."""
        model = JobStatusResponse(job_id="j1", status="completed", progress=1.0)
        assert model.model_dump(mode="json")["status"] == "completed"

    def test_openapi_publishes_the_value_set(self):
        """The point of the change: the schema names the values."""
        schema = JobStatusResponse.model_json_schema()
        # The enum is emitted either inline or via $defs depending on Pydantic's
        # ref strategy; assert on the whole rendered schema.
        rendered = str(schema)
        for value in (s.value for s in ProcessingStatus):
            assert value in rendered


# ---------------------------------------------------------------------------
# Volume bounds (deliberately NOT converted to Field(ge/le) -- see below)
# ---------------------------------------------------------------------------


class TestVolumeStaysClamped:
    """#3896 proposed Field(ge=0, le=100) so OpenAPI shows the bounds. That
    would turn a forgiving clamp into a 422, and clamping is the intended
    contract -- tests/integration/test_phase4_player_workflow.py::
    test_volume_out_of_range sends 150 and -50 and asserts success. Pinned here
    so the tempting "tighten it" change fails loudly instead of silently
    breaking that contract."""

    @pytest.mark.parametrize("sent,expected", [(150.0, 100.0), (-50.0, 0.0), (75.0, 75.0)])
    def test_out_of_range_volume_is_clamped_not_rejected(self, sent, expected):
        assert SetVolumeRequest(volume=sent).volume == expected

    def test_the_range_is_documented_for_openapi(self):
        schema = SetVolumeRequest.model_json_schema()
        assert "0-100" in schema["properties"]["volume"]["description"]


# ---------------------------------------------------------------------------
# Queue repeat mode
# ---------------------------------------------------------------------------


def _build_service(*, engine_info: dict, repeat_mode: object = "off",
                   with_state_manager: bool = True) -> QueueService:
    audio_player = MagicMock()
    audio_player.queue.get_queue_info = MagicMock(return_value=engine_info)

    state_manager = None
    if with_state_manager:
        state_manager = MagicMock()
        state_manager.get_state = MagicMock(
            return_value=SimpleNamespace(queue=[], repeat_mode=repeat_mode)
        )

    return QueueService(
        audio_player=audio_player,
        player_state_manager=state_manager,
        library_database=MagicMock(),
        connection_manager=MagicMock(),
        create_track_info_fn=create_track_info,
    )


def _engine_info(*, repeat_enabled: bool) -> dict:
    return {
        "tracks": [],
        "current_index": 0,
        "track_count": 0,
        "shuffle_enabled": False,
        "repeat_enabled": repeat_enabled,
    }


class TestQueueRepeatMode:
    def test_response_model_declares_repeat_mode_not_a_bool(self):
        fields = QueueInfoResponse.model_fields
        assert "repeat_mode" in fields
        assert "repeat_enabled" not in fields

    def test_response_model_rejects_an_invalid_mode(self):
        with pytest.raises(Exception):
            QueueInfoResponse(tracks=[], current_index=0, repeat_mode="sometimes")

    @pytest.mark.parametrize("mode", ["off", "all", "one"])
    @pytest.mark.asyncio
    async def test_takes_the_three_valued_mode_from_the_state_manager(self, mode):
        service = _build_service(
            engine_info=_engine_info(repeat_enabled=True), repeat_mode=mode
        )

        info = await service.get_queue_info()

        assert info["repeat_mode"] == mode

    @pytest.mark.asyncio
    async def test_one_is_no_longer_collapsed_into_all(self):
        """The defect itself: a bool cannot carry this distinction."""
        one = await _build_service(
            engine_info=_engine_info(repeat_enabled=True), repeat_mode="one"
        ).get_queue_info()
        every = await _build_service(
            engine_info=_engine_info(repeat_enabled=True), repeat_mode="all"
        ).get_queue_info()

        assert one["repeat_mode"] != every["repeat_mode"]

    @pytest.mark.asyncio
    async def test_stale_repeat_enabled_is_not_emitted_alongside(self):
        """QueueInfoResponse sets extra='allow', so an un-popped engine key
        would still reach the client and the rename would not have landed."""
        service = _build_service(engine_info=_engine_info(repeat_enabled=True))

        info = await service.get_queue_info()

        assert "repeat_enabled" not in info
        assert "repeat_enabled" not in QueueInfoResponse(**info).model_dump()

    @pytest.mark.parametrize("engine_repeat,expected", [(True, "all"), (False, "off")])
    @pytest.mark.asyncio
    async def test_falls_back_to_widening_the_engine_bool(self, engine_repeat, expected):
        """With no state manager attached, the engine bool is all there is:
        "repeat the queue" widens to "all"."""
        service = _build_service(
            engine_info=_engine_info(repeat_enabled=engine_repeat),
            with_state_manager=False,
        )

        info = await service.get_queue_info()

        assert info["repeat_mode"] == expected

    @pytest.mark.asyncio
    async def test_falls_back_when_the_state_manager_reports_a_bogus_mode(self):
        service = _build_service(
            engine_info=_engine_info(repeat_enabled=True), repeat_mode="garbage"
        )

        info = await service.get_queue_info()

        assert info["repeat_mode"] == "all"

    @pytest.mark.asyncio
    async def test_result_validates_against_the_response_model(self):
        """get_queue_info feeds QueueInfoResponse directly, so the dict it
        returns must satisfy the schema."""
        service = _build_service(
            engine_info=_engine_info(repeat_enabled=False), repeat_mode="one"
        )

        info = await service.get_queue_info()

        assert QueueInfoResponse(**info).repeat_mode == "one"
