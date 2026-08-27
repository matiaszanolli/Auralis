"""Regression tests for the #4656-#4659 backend fix batch.

Four independent defects that share a theme — a contract that was silently
wrong rather than loudly broken:

  #4656 — three similarity routes dereferenced `get_similarity_system()`
          without a None check, so a legitimately uninitialised component
          surfaced as an opaque 500 instead of an actionable 503. Two sibling
          sites (`library_scan.py`, `player.py`) had the same shape.
  #4657 — `_recommendation_cache` detected expiry on read but never deleted,
          had no size cap, and was keyed by an unbounded bare `float`.
  #4658 — `useAppDragDrop` called two playlist paths the backend never
          registered, so both drag operations returned 405.
  #4659 — a stream truncated by a mid-stream enhancement toggle emitted a
          success-shaped `audio_stream_end` reporting the FULL track length.
"""

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi import HTTPException  # noqa: E402


# ---------------------------------------------------------------------------
# #4656 — component-readiness guards report 503, not 500
# ---------------------------------------------------------------------------

class TestRequireSimilaritySystem:
    """`require_similarity_system` converts a None component into a 503."""

    def test_none_raises_503_with_actionable_detail(self):
        from routers.similarity_common import require_similarity_system

        with pytest.raises(HTTPException) as exc_info:
            require_similarity_system(lambda: None)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail
        # Must be actionable, not an opaque correlation id (#4656).
        assert "not available" in str(exc_info.value.detail).lower()

    def test_present_system_is_returned_unchanged(self):
        from routers.similarity_common import require_similarity_system

        sentinel = object()
        assert require_similarity_system(lambda: sentinel) is sentinel

    def test_falsy_but_present_system_is_not_rejected(self):
        """Guard on `is None`, not truthiness.

        A similarity system that defines __len__/__bool__ and is legitimately
        "empty" (nothing fitted yet) must still be returned — rejecting it
        would turn a working component into a spurious 503.
        """
        from routers.similarity_common import require_similarity_system

        class EmptyButValid:
            def __len__(self) -> int:
                return 0

        system = EmptyButValid()
        assert require_similarity_system(lambda: system) is system


class TestSimilarityRoutesUseTheGuard:
    """No unguarded `get_similarity_system()` deref may remain (#4656 WIRING)."""

    def test_no_bare_dereference_left_in_similarity_router(self):
        source = (_BACKEND / "routers" / "similarity.py").read_text()
        assert "= get_similarity_system()" not in source, (
            "an unguarded get_similarity_system() deref reintroduces the "
            "AttributeError -> 500 path fixed in #4656"
        )

    def test_guard_is_actually_called(self):
        source = (_BACKEND / "routers" / "similarity.py").read_text()
        assert source.count("require_similarity_system(get_similarity_system)") >= 3


class TestLibraryScanGuardsResolvedManager:
    """`library_scan.py` guarded the getter, which is always truthy (#4656)."""

    def test_guard_checks_the_resolved_manager_not_the_callable(self):
        source = (_BACKEND / "routers" / "library_scan.py").read_text()
        # The old form `if not get_library_manager:` tested the function object,
        # so it never fired and a None manager reached LibraryScanner.
        assert "if not get_library_manager:" not in source
        assert "if library_manager is None:" in source


class TestPlayerLoadGuardsLibraryManager:
    """`player.py` dereferenced outside its try:, so None escaped (#4656)."""

    def test_none_check_precedes_the_dereference(self):
        source = (_BACKEND / "routers" / "player.py").read_text()
        guard_at = source.find("if library_manager is None:")
        deref_at = source.find("library_manager.tracks.get_by_id")
        assert guard_at != -1, "the None guard added in #4656 is missing"
        assert guard_at < deref_at, "guard must precede the dereference"


# ---------------------------------------------------------------------------
# #4657 — recommendation cache is bounded and self-purging
# ---------------------------------------------------------------------------

class TestRecommendationCacheBounds:
    """The cache must not grow for the life of the process."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        from routers import enhancement

        enhancement._recommendation_cache.clear()
        yield
        enhancement._recommendation_cache.clear()

    def test_cap_is_enforced_across_many_distinct_keys(self):
        from routers import enhancement

        cap = enhancement._RECOMMENDATION_CACHE_MAX
        far_future = 1e18  # never expires within the test

        for i in range(cap * 3):
            enhancement._store_recommendation((i, 0.4), far_future, {"track": i})

        assert len(enhancement._recommendation_cache) <= cap

    def test_expired_entries_are_purged_on_insert(self):
        import time

        from routers import enhancement

        already_expired = time.monotonic() - 1.0
        for i in range(10):
            enhancement._store_recommendation((i, 0.4), already_expired, {"track": i})

        # A fresh insert must evict the stale entries rather than leaving them
        # resident until the process exits (#4657).
        enhancement._store_recommendation((999, 0.4), time.monotonic() + 600, {"track": 999})

        assert len(enhancement._recommendation_cache) == 1
        assert (999, 0.4) in enhancement._recommendation_cache

    def test_hot_entry_survives_eviction_pressure(self):
        from routers import enhancement

        cap = enhancement._RECOMMENDATION_CACHE_MAX
        far_future = 1e18

        enhancement._store_recommendation((0, 0.4), far_future, {"track": 0})

        for i in range(1, cap):
            enhancement._store_recommendation((i, 0.4), far_future, {"track": i})
            # Re-assert the hot key so it stays away from the eviction end.
            enhancement._recommendation_cache.move_to_end((0, 0.4))

        for i in range(cap, cap + 10):
            enhancement._store_recommendation((i, 0.4), far_future, {"track": i})
            enhancement._recommendation_cache.move_to_end((0, 0.4))

        assert (0, 0.4) in enhancement._recommendation_cache

    def test_threshold_query_param_is_range_bounded(self):
        """`confidence_threshold` must reject out-of-range and non-finite input.

        Asserted on the declared constraint rather than through a live request
        so the test does not need the whole app composed.
        """
        import inspect

        from routers import enhancement

        # The handler is a module-level function since #4670 (it used to be
        # nested inside create_enhancement_router), and is wrapped by
        # @with_error_handling -- inspect.getsource unwraps __wrapped__, so
        # this still reads the handler's own source.
        source = inspect.getsource(enhancement.get_mastering_recommendation)
        assert "confidence_threshold: float = Query(" in source
        assert "ge=0.0" in source and "le=1.0" in source


# ---------------------------------------------------------------------------
# #4658 — the two missing playlist routes exist and are registered
# ---------------------------------------------------------------------------

class TestPlaylistDragDropRoutes:
    """Both paths `useAppDragDrop` calls must resolve to a real route."""

    @staticmethod
    def _router():
        from routers.playlists import create_playlists_router

        class _CM:
            async def broadcast(self, *_a, **_k):
                return None

        return create_playlists_router(lambda: None, _CM())

    def _paths(self):
        return {
            (r.path, method)
            for r in self._router().routes
            for method in (getattr(r, "methods", None) or set())
        }

    def test_single_track_add_route_is_registered(self):
        assert ("/api/playlists/{playlist_id}/tracks/add", "POST") in self._paths()

    def test_reorder_route_is_registered(self):
        assert ("/api/playlists/{playlist_id}/tracks/reorder", "PUT") in self._paths()

    def test_existing_batch_add_route_is_preserved(self):
        """The new single-track route must not displace the batch route (#3856)."""
        assert ("/api/playlists/{playlist_id}/tracks", "POST") in self._paths()

    def test_every_frontend_playlist_path_has_a_route(self):
        """Contract check: the hook's paths and the router must agree (#4658)."""
        hook = (
            Path(__file__).resolve().parents[2]
            / "auralis-web" / "frontend" / "src" / "hooks" / "app" / "useAppDragDrop.ts"
        )
        if not hook.exists():  # pragma: no cover - frontend not checked out
            pytest.skip("frontend hook not present")

        source = hook.read_text()
        registered = {path for path, _ in self._paths()}

        # The hook interpolates ${playlistId}; normalise to the FastAPI param.
        for suffix, method in (("tracks/add", "POST"), ("tracks/reorder", "PUT")):
            assert f"/tracks/{suffix.split('/')[-1]}" in source, (
                f"hook no longer calls {suffix}; update this contract test"
            )
            assert f"/api/playlists/{{playlist_id}}/{suffix}" in registered
            assert (f"/api/playlists/{{playlist_id}}/{suffix}", method) in self._paths()

    def test_reorder_request_rejects_negative_indices(self):
        from routers.playlists import ReorderTrackRequest
        from pydantic import ValidationError

        ReorderTrackRequest(from_index=0, to_index=3)  # valid

        with pytest.raises(ValidationError):
            ReorderTrackRequest(from_index=-1, to_index=3)
        with pytest.raises(ValidationError):
            ReorderTrackRequest(from_index=0, to_index=-2)

    def test_add_track_request_allows_absent_position(self):
        from routers.playlists import AddTrackRequest
        from pydantic import ValidationError

        assert AddTrackRequest(track_id=7).position is None
        assert AddTrackRequest(track_id=7, position=2).position == 2

        with pytest.raises(ValidationError):
            AddTrackRequest(track_id=7, position=-1)


# ---------------------------------------------------------------------------
# #4659 — audio_stream_end distinguishes completion from truncation
# ---------------------------------------------------------------------------

class TestStreamEndReason:
    """A truncated stream must be distinguishable from a finished one."""

    @staticmethod
    async def _capture(**kwargs):
        """Invoke send_stream_end and return the emitted message payload."""
        from core import stream_messages

        sent: list[dict] = []

        class _Controller:
            async def _safe_send(self, _ws, message):
                sent.append(message)
                return True

        ok = await stream_messages.send_stream_end(
            _Controller(), object(), **kwargs
        )
        assert ok is True
        assert len(sent) == 1
        return sent[0]["data"]

    @pytest.mark.asyncio
    async def test_completed_stream_reports_reason_completed(self):
        data = await self._capture(
            track_id=1, total_samples=1_323_000, duration=30.0, reason="completed"
        )
        assert data["reason"] == "completed"
        assert data["total_samples"] == 1_323_000
        assert data["duration"] == 30.0

    @pytest.mark.asyncio
    async def test_stopped_stream_reports_reason_and_delivered_length(self):
        """The whole point of #4659: not the full track length."""
        data = await self._capture(
            track_id=1, total_samples=441_000, duration=10.0, reason="stopped"
        )
        assert data["reason"] == "stopped"
        assert data["total_samples"] == 441_000
        assert data["duration"] == 10.0

    @pytest.mark.asyncio
    async def test_reason_defaults_to_completed(self):
        """Callers that predate the field must keep their old semantics."""
        data = await self._capture(track_id=1, total_samples=100, duration=1.0)
        assert data["reason"] == "completed"

    @pytest.mark.asyncio
    async def test_completed_seek_reports_only_delivered_length(self):
        from core import stream_messages

        sent: list[dict] = []

        class _Controller:
            async def _send_stream_end(self, _ws, **kwargs):
                sent.append(kwargs)
                return True

        ok = await stream_messages.send_stream_completion(
            _Controller(),
            object(),
            track_id=1,
            label="Seek stream",
            stopped_early=False,
            failed_chunks=[],
            delivered_samples=220_500,
            sample_rate=44_100,
            full_duration=30.0,
        )

        assert ok is True
        assert sent == [{
            "track_id": 1,
            "total_samples": 220_500,
            "duration": 5.0,
            "reason": "completed",
        }]

    def test_every_send_stream_end_call_site_sets_reason(self):
        """#4659 CONSISTENCY: no call site may silently default."""
        import re

        core = _BACKEND / "core"
        offenders = []
        for path in sorted(core.glob("stream_*.py")):
            source = path.read_text()
            for match in re.finditer(
                r"_send_stream_end\(\s*\n(.*?)\n\s*\)", source, re.S
            ):
                if "reason=" not in match.group(1):
                    offenders.append(f"{path.name}: {match.group(1).strip()[:60]}")

        assert not offenders, "call sites missing an explicit reason=: " + "; ".join(offenders)

    def test_all_stream_paths_track_early_exit(self):
        """Every producer must report a mid-send failure as stopped (#4732).

        #5032 pulled the reason="stopped"/"errored"/"completed" decision out
        of the three handlers into the shared
        stream_messages.send_stream_completion — each handler no longer
        spells `reason="stopped"` itself, it tracks stopped_early and hands
        it to the shared helper. Check both halves: each handler still does
        its own tracking, and the shared helper still reports "stopped".
        """
        # #5032 also moved each handler's per-chunk loop into a companion
        # pump module. The handler still reports completion; the loop still
        # tracks what it delivered and reacts to a failed send. Check each
        # half where it now lives rather than requiring one file to hold both.
        handlers = ("stream_enhanced.py", "stream_seek.py", "stream_normal.py")
        for name in handlers:
            source = (_BACKEND / "core" / name).read_text()
            assert "stopped_early" in source, f"{name} does not track early exit"
            assert "_send_stream_completion(" in source, (
                f"{name} does not report completion via the shared helper"
            )
            assert "delivered_samples" in source, f"{name} does not count delivered audio"

        pumps = ("stream_normal_chunks.py", "stream_enhanced_chunks.py", "stream_seek_chunks.py")
        for name in pumps:
            source = (_BACKEND / "core" / name).read_text()
            assert "stopped_early" in source, f"{name} does not track early exit"
            assert "delivered_samples" in source, f"{name} does not count delivered audio"
            assert "if not delivered:" in source, f"{name} ignores failed chunk sends"

        import re

        shared_source = (_BACKEND / "core" / "stream_messages.py").read_text()
        assert re.search(r'reason\s*=\s*"stopped"', shared_source), (
            "stream_messages.py's send_stream_completion never reports a stopped stream"
        )
