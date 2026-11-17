"""GET /api/cache/stats counts a Tier-2-served request as a Tier-1 miss, on the loop (#6003).

`get_chunk` recorded a Tier-1 miss only when BOTH tiers missed, so `tier1.hit_rate` ignored
every request Tier 2 served (1 Tier-1 hit + 9 Tier-2 hits reported 100%, true 10%). The
router also ran `get_stats` in a worker thread, iterating dicts the loop mutates.
"""

import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from cache.manager import StreamlinedCacheManager  # noqa: E402
from routers import cache_streamlined  # noqa: E402


def _wav(path: Path) -> Path:
    sf.write(str(path), np.zeros((441, 2), dtype=np.float32), 44100, subtype="PCM_16")
    return path


@pytest.mark.asyncio
async def test_tier2_hits_count_as_tier1_misses(tmp_path):
    manager = StreamlinedCacheManager()
    await manager.add_chunk(1, 0, _wav(tmp_path / "t1.wav"), tier="tier1")
    for i in range(1, 10):
        await manager.add_chunk(1, i, _wav(tmp_path / f"t2_{i}.wav"), tier="tier2")

    assert (await manager.get_chunk(1, 0))[1] == "tier1"
    for i in range(1, 10):
        assert (await manager.get_chunk(1, i))[1] == "tier2"

    stats = manager.get_stats()
    assert stats["tier1"]["hit_rate"] == pytest.approx(0.1)  # was 1.0
    assert stats["tier1"]["misses"] == 9
    assert stats["overall"]["total_misses"] == 0
    assert stats["overall"]["overall_hit_rate"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_full_miss_is_one_overall_miss(tmp_path):
    manager = StreamlinedCacheManager()
    await manager.add_chunk(1, 0, _wav(tmp_path / "t1.wav"), tier="tier1")
    await manager.get_chunk(1, 0)
    assert (await manager.get_chunk(1, 99))[1] == "miss"

    stats = manager.get_stats()
    assert stats["overall"]["total_misses"] == 1
    assert stats["overall"]["overall_hit_rate"] == pytest.approx(0.5)


def test_stats_endpoint_reads_the_manager_on_the_event_loop_thread():
    seen: list[int] = []

    def get_stats():
        seen.append(threading.get_ident())
        return {
            "overall": {"total_size_mb": 0.0, "overall_hit_rate": 0.0},
            "tier1": {"size_mb": 0.0, "hit_rate": 0.0},
            "tier2": {"size_mb": 0.0, "hit_rate": 0.0},
        }

    manager = MagicMock()
    manager.get_stats.side_effect = get_stats

    async def run() -> int:
        await cache_streamlined.cache_health(manager)
        return threading.get_ident()

    loop_thread = asyncio.run(run())
    assert seen == [loop_thread]
