"""The recommendation route and RecommendationService share one analysis path (#5970).

Both carried their own copy of "cache lookup -> bounded ChunkedAudioProcessor analysis -> cache
store", so every fix (#5248 timeout, #5956 cache key) had to land twice.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from services import recommendation_analysis  # noqa: E402
from services.recommendation_analysis import cached_or_analyzed_recommendation  # noqa: E402

pytestmark = pytest.mark.asyncio

RESULT = {"track_id": 5, "primary_profile_id": "adaptive", "is_hybrid": False}


def _processor_returning(response):
    rec = MagicMock()
    rec.to_response.return_value = response
    processor = MagicMock()
    processor.get_mastering_recommendation.return_value = rec if response is not None else None
    return MagicMock(return_value=processor)


async def test_a_miss_is_analysed_once_and_cached():
    cache = MagicMock()
    cache.get_mastering_recommendation.return_value = None
    factory = _processor_returning(RESULT)

    with patch("core.chunked_processor.ChunkedAudioProcessor", factory):
        first = await cached_or_analyzed_recommendation(cache, 5, "/m/a.flac", 0.4)

    assert first == RESULT
    cache.set_mastering_recommendation.assert_called_once_with(5, RESULT, 0.4)
    assert factory.call_args.kwargs["filepath"] == "/m/a.flac"


async def test_a_hit_skips_the_analysis():
    cache = MagicMock()
    cache.get_mastering_recommendation.return_value = RESULT
    factory = _processor_returning(RESULT)

    with patch("core.chunked_processor.ChunkedAudioProcessor", factory):
        assert await cached_or_analyzed_recommendation(cache, 5, "/m/a.flac", 0.4) == RESULT

    factory.assert_not_called()


async def test_an_unanalysable_file_is_none_and_not_cached():
    cache = MagicMock()
    cache.get_mastering_recommendation.return_value = None

    with patch("core.chunked_processor.ChunkedAudioProcessor", _processor_returning(None)):
        assert await cached_or_analyzed_recommendation(cache, 5, "/m/a.flac", 0.4) is None

    cache.set_mastering_recommendation.assert_not_called()


async def test_a_slow_analysis_raises_timeout_for_the_caller_to_map():
    cache = MagicMock()
    cache.get_mastering_recommendation.return_value = None

    with patch.object(recommendation_analysis.asyncio, "wait_for", side_effect=TimeoutError):
        with pytest.raises(TimeoutError):
            await cached_or_analyzed_recommendation(cache, 5, "/m/a.flac", 0.4)


def test_neither_caller_builds_its_own_processor():
    for name in ("routers/enhancement_recommendation.py", "services/recommendation_service.py"):
        assert "ChunkedAudioProcessor(" not in (_BACKEND / name).read_text(), name
