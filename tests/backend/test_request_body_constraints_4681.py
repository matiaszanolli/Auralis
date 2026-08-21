"""Player/queue/playlist request bodies enforce numeric and length bounds (#4681).

The query-parameter surface has always been constrained (`Query(50, ge=1,
le=200)`, `PaginationParams`), while the body models accepted any `int`. A
negative index or a `track_id` of -1 therefore reached QueueService and the
engine queue, where the failure mode is a 500 or a silently wrong queue
position rather than a 422 naming the offending field.

Two things are deliberately NOT enforced here, both recorded so a later reader
does not "fix" them:

* `SetVolumeRequest` still clamps rather than rejects.
  `tests/integration/test_phase4_player_workflow.py::test_volume_out_of_range`
  asserts a *successful* clamped response for 150 and -50, so clamping is the
  intended contract (#3896 considered and declined).
* `SeekRequest.position` still has no upper bound. The only meaningful ceiling
  is the loaded track's duration, which a body model cannot see;
  `test_player_api_comprehensive.py::test_seek_overflow_protection` pins the
  no-track-loaded case to a pass-through 200.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.metadata import (  # noqa: E402
    MAX_BATCH_UPDATES,
    BatchMetadataRequest,
)
from routers.player import (  # noqa: E402
    AddTrackToQueueRequest,
    LoadTrackRequest,
    MoveQueueTrackRequest,
    QueueHistoryStateSnapshot,
    ReorderQueueRequest,
    SeekRequest,
    SetQueueRequest,
    SetVolumeRequest,
)
from routers.playlists import (  # noqa: E402
    MAX_PLAYLIST_NAME,
    AddTracksRequest,
    CreatePlaylistRequest,
    ReorderTrackRequest,
    UpdatePlaylistRequest,
)
from schemas import MAX_TRACK_ID_LIST  # noqa: E402


# ---------------------------------------------------------------------------
# Acceptance criterion: the listed out-of-range values are rejected
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "model,payload,field",
    [
        (SetQueueRequest, {"tracks": [1], "start_index": -1}, "start_index"),
        (SetQueueRequest, {"tracks": [0]}, "tracks"),
        (SetQueueRequest, {"tracks": [-1]}, "tracks"),
        (ReorderQueueRequest, {"new_order": [-1]}, "new_order"),
        (MoveQueueTrackRequest, {"from_index": -1, "to_index": 0}, "from_index"),
        (MoveQueueTrackRequest, {"from_index": 0, "to_index": -1}, "to_index"),
        (AddTrackToQueueRequest, {"track_id": -1}, "track_id"),
        (AddTrackToQueueRequest, {"track_id": 0}, "track_id"),
        (AddTrackToQueueRequest, {"track_id": 1, "position": -1}, "position"),
        (LoadTrackRequest, {"track_id": -1}, "track_id"),
        (LoadTrackRequest, {"track_id": 0}, "track_id"),
        (QueueHistoryStateSnapshot, {"track_ids": [1], "current_index": -1}, "current_index"),
        (QueueHistoryStateSnapshot, {"track_ids": [0]}, "track_ids"),
        (CreatePlaylistRequest, {"name": ""}, "name"),
        (CreatePlaylistRequest, {"name": "x", "track_ids": [0]}, "track_ids"),
        (UpdatePlaylistRequest, {"name": ""}, "name"),
        (AddTracksRequest, {"track_ids": [-5]}, "track_ids"),
        (ReorderTrackRequest, {"from_index": -1, "to_index": 0}, "from_index"),
    ],
)
def test_out_of_range_values_are_rejected(model, payload, field):
    with pytest.raises(ValidationError) as excinfo:
        model(**payload)
    # The 422 must name the offending field — the whole point is that the
    # error is legible instead of surfacing as a downstream 500.
    assert any(field in str(error["loc"]) for error in excinfo.value.errors())


# ---------------------------------------------------------------------------
# Length bounds
# ---------------------------------------------------------------------------

class TestLengthBounds:
    def test_a_pathological_queue_payload_is_refused(self):
        with pytest.raises(ValidationError):
            SetQueueRequest(tracks=list(range(1, MAX_TRACK_ID_LIST + 2)))

    def test_a_realistic_play_all_still_fits(self):
        """The bound must not break the frontend's real setQueue payload."""
        request = SetQueueRequest(tracks=list(range(1, 5001)))
        assert len(request.tracks) == 5000

    def test_playlist_name_length_is_bounded(self):
        with pytest.raises(ValidationError):
            CreatePlaylistRequest(name="x" * (MAX_PLAYLIST_NAME + 1))

    def test_batch_metadata_updates_are_bounded(self):
        one = {"track_id": 1, "metadata": {"title": "t"}}
        with pytest.raises(ValidationError):
            BatchMetadataRequest(updates=[one] * (MAX_BATCH_UPDATES + 1))

    def test_an_empty_batch_is_not_a_422(self):
        """The route answers the empty case with its own 400, not a 422.

        Adding `min_length=1` here would preempt that and change a contract
        two tests already pin (test_metadata_batch_atomicity.py::
        test_empty_updates_returns_400 and test_metadata_api.py::
        test_batch_update_empty_list). Only the upper bound is new.
        """
        assert BatchMetadataRequest(updates=[]).updates == []


# ---------------------------------------------------------------------------
# Valid requests are unaffected
# ---------------------------------------------------------------------------

class TestValidRequestsStillPass:
    def test_queue_boundaries(self):
        assert SetQueueRequest(tracks=[1, 2], start_index=0).start_index == 0
        assert MoveQueueTrackRequest(from_index=0, to_index=0).to_index == 0
        assert AddTrackToQueueRequest(track_id=1, position=0).position == 0
        assert AddTrackToQueueRequest(track_id=1).position is None
        assert LoadTrackRequest(track_id=1).track_id == 1

    def test_an_empty_queue_is_a_legitimate_clear(self):
        assert SetQueueRequest(tracks=[]).tracks == []

    def test_playlist_creation_defaults(self):
        request = CreatePlaylistRequest(name="Mix")
        assert request.description == ""
        assert request.track_ids == []

    def test_update_with_no_fields_is_still_valid(self):
        assert UpdatePlaylistRequest().name is None


# ---------------------------------------------------------------------------
# Deliberate non-changes
# ---------------------------------------------------------------------------

class TestDeliberateNonChanges:
    def test_volume_still_clamps_rather_than_rejecting(self):
        """#3896 declined: test_phase4_player_workflow pins the clamp."""
        assert SetVolumeRequest(volume=150).volume == 100.0
        assert SetVolumeRequest(volume=-50).volume == 0.0

    def test_seek_has_no_upper_bound(self):
        """The only real ceiling is track duration, checked at the route."""
        assert SeekRequest(position=999999999.0).position == 999999999.0

    def test_seek_still_rejects_nan_inf_and_negative(self):
        for bad in (float("nan"), float("inf"), -1.0):
            with pytest.raises(ValidationError):
                SeekRequest(position=bad)
