"""GET /api/cache/health judges the tiers against the cache's own budgets (#5971).

The route hard-coded 15 / 250 / 260 MB while cache.models defines
TIER1_MAX_SIZE_MB (~6.7) and TIER2_MAX_SIZE_MB (240); retuning the cache
budgets left the health thresholds behind.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from cache.models import CHUNK_SIZE_MB, TIER1_MAX_SIZE_MB, TIER2_MAX_SIZE_MB  # noqa: E402
from routers import cache_streamlined  # noqa: E402


def _health(tier1_mb: float, tier2_mb: float):
    manager = MagicMock()
    manager.get_stats.return_value = {
        "overall": {"total_size_mb": tier1_mb + tier2_mb, "overall_hit_rate": 0.0},
        "tier1": {"size_mb": tier1_mb, "hit_rate": 0.0},
        "tier2": {"size_mb": tier2_mb, "hit_rate": 0.0},
    }
    # `with_error_handling` wraps the coroutine; call it directly with the manager.
    return asyncio.run(cache_streamlined.cache_health(manager))


def test_tiers_at_their_budgets_are_healthy():
    health = _health(TIER1_MAX_SIZE_MB, TIER2_MAX_SIZE_MB)
    assert (health.tier1_healthy, health.tier2_healthy, health.memory_healthy, health.healthy) == (True,) * 4


def test_one_chunk_of_slack_is_tolerated():
    assert _health(TIER1_MAX_SIZE_MB + CHUNK_SIZE_MB, TIER2_MAX_SIZE_MB).healthy is True


def test_tier1_over_its_budget_is_unhealthy_even_below_the_old_15mb_literal():
    health = _health(TIER1_MAX_SIZE_MB + CHUNK_SIZE_MB + 1.0, 0.0)
    assert health.tier1_size_mb < 15  # the old literal would have called this healthy
    assert health.tier1_healthy is False and health.healthy is False


def test_tier2_over_its_budget_is_unhealthy():
    health = _health(0.0, TIER2_MAX_SIZE_MB + CHUNK_SIZE_MB + 1.0)
    assert health.tier2_healthy is False and health.healthy is False
