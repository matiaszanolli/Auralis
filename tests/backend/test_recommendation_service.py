"""
Unit tests for RecommendationService (#3860 / BE-TC-5)

RecommendationService is wired into routers/player.py and called on track
load to broadcast mastering recommendations, but had no dedicated tests.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.recommendation_service import RecommendationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service():
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()
    return RecommendationService(connection_manager=connection_manager), connection_manager


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRecommendationServiceInit:
    def test_stores_connection_manager(self):
        service, conn_mgr = _make_service()
        assert service.connection_manager is conn_mgr


class TestGenerateAndBroadcastRecommendation:
    @pytest.mark.asyncio
    async def test_broadcasts_recommendation_when_analysis_succeeds(self):
        service, conn_mgr = _make_service()

        rec = {"preset": "adaptive", "confidence": 0.85, "track_id": 1}

        with patch.object(service, "generate_and_broadcast_recommendation") as mock_method:
            mock_method.return_value = rec
            result = await service.generate_and_broadcast_recommendation(1, "/music/track.mp3")

        assert result == rec

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_analysis_returns_none(self):
        """When _analyze() returns None (low confidence), service returns {} without broadcasting."""
        service, conn_mgr = _make_service()

        # Patch asyncio.to_thread to return None (simulate low confidence)
        with patch("services.recommendation_service.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = None
            result = await service.generate_and_broadcast_recommendation(1, "/music/track.mp3")

        assert result == {}
        conn_mgr.broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_analysis_raises(self):
        """Exceptions during analysis are swallowed — recommendations are optional."""
        service, conn_mgr = _make_service()

        with patch("services.recommendation_service.asyncio.to_thread", side_effect=RuntimeError("analysis failed")):
            result = await service.generate_and_broadcast_recommendation(1, "/music/track.mp3")

        assert result == {}
        conn_mgr.broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_broadcasts_mastering_recommendation_message(self):
        """When analysis returns a dict, it must be broadcast with type mastering_recommendation."""
        service, conn_mgr = _make_service()

        rec_dict = {"preset": "warm", "confidence": 0.9, "track_id": 42}

        with patch("services.recommendation_service.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = rec_dict
            await service.generate_and_broadcast_recommendation(42, "/music/track.mp3")

        conn_mgr.broadcast.assert_awaited_once()
        payload = conn_mgr.broadcast.call_args[0][0]
        assert payload["type"] == "mastering_recommendation"
        assert payload["data"] is rec_dict


class TestGetRecommendationForTrack:
    @pytest.mark.asyncio
    async def test_returns_recommendation_dict_on_success(self):
        service, conn_mgr = _make_service()
        rec_dict = {"preset": "adaptive", "confidence": 0.75, "track_id": 7}

        with patch("services.recommendation_service.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = rec_dict
            result = await service.get_recommendation_for_track(7, "/music/track.mp3")

        assert result == rec_dict
        conn_mgr.broadcast.assert_not_awaited()  # no broadcast in this path

    @pytest.mark.asyncio
    async def test_returns_none_when_analysis_returns_none(self):
        service, _ = _make_service()

        with patch("services.recommendation_service.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = None
            result = await service.get_recommendation_for_track(7, "/music/track.mp3")

        assert result is None

    @pytest.mark.asyncio
    async def test_raises_on_exception(self):
        """get_recommendation_for_track propagates exceptions (not swallowed)."""
        service, _ = _make_service()

        with patch("services.recommendation_service.asyncio.to_thread", side_effect=ValueError("bad")):
            with pytest.raises(ValueError, match="bad"):
                await service.get_recommendation_for_track(7, "/music/track.mp3")
