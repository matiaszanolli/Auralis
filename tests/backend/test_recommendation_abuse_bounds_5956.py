"""
GET /api/player/mastering/recommendation/{id} is rate-limited and its cache key
is quantised (#5956)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each uncached call runs a 1-5 s analysis on the shared IO_EXECUTOR. The route
sat outside ``_RATE_LIMITS`` and ``confidence_threshold`` keyed the result
cache as a free float, so varying it by 0.001 missed the cache every time.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from cache.manager import StreamlinedCacheManager  # noqa: E402
from config.limits import RATE_LIMIT_RECOMMENDATION_MAX  # noqa: E402
from config.middleware import RateLimitMiddleware  # noqa: E402
from routers import enhancement_recommendation as rec_router  # noqa: E402


@pytest.mark.asyncio
async def test_requests_beyond_the_budget_get_429():
    app = FastAPI()

    @app.get("/api/player/mastering/recommendation/{track_id}")
    async def rec(track_id: int):
        return {"track_id": track_id}

    app.add_middleware(RateLimitMiddleware)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:8765"
    ) as client:
        statuses = [
            (await client.get(f"/api/player/mastering/recommendation/{i}")).status_code
            for i in range(1, RATE_LIMIT_RECOMMENDATION_MAX + 2)
        ]

    assert statuses[:-1] == [200] * RATE_LIMIT_RECOMMENDATION_MAX
    assert statuses[-1] == 429


@pytest.mark.asyncio
async def test_thresholds_within_one_step_run_the_analysis_once(tmp_path):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"x")
    repos = SimpleNamespace(
        tracks=SimpleNamespace(get_by_id=lambda _id: SimpleNamespace(filepath=str(audio)))
    )
    cache = StreamlinedCacheManager()
    rec = MagicMock()
    rec.to_response.return_value = {"track_id": 1, "primary_profile_name": "adaptive"}
    processor = MagicMock()
    processor.get_mastering_recommendation.return_value = rec

    with (
        patch.object(rec_router, "streamlined_cache_manager", cache),
        patch.object(rec_router, "validate_file_path", lambda p: Path(p)),
        patch("core.chunked_processor.ChunkedAudioProcessor", return_value=processor) as ctor,
    ):
        for threshold in (0.401, 0.402, 0.39):
            await rec_router.get_mastering_recommendation(
                track_id=1, confidence_threshold=threshold, repos=repos
            )

    assert ctor.call_count == 1
    assert list(cache.mastering_recommendations) == [(1, 0.4)]
