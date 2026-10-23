"""Concurrency contracts for ProcessorPool construction and returns (#4689)."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from core.processor_pool import ProcessorPool
from core.processor_cache_key import hash_config


def test_cache_key_follows_the_config_content_hash():
    """#6193: the pool key is `mode|hash_config(config)` — any field of
    UnifiedConfig.to_dict() changing must derive a new key, and identical
    configs must share one."""
    pool = ProcessorPool(create_processor=MagicMock())

    base = {"internal_sample_rate": 44100, "fft_size": 4096, "processing_mode": "adaptive"}
    first = SimpleNamespace(to_dict=lambda: dict(base))
    faster_decay = dict(base, adaptation_strength=0.9)
    second = SimpleNamespace(to_dict=lambda: faster_decay)

    assert pool.cache_key("adaptive", first) == pool.cache_key("adaptive", first)
    assert pool.cache_key("adaptive", first) != pool.cache_key("adaptive", second)
    assert pool.cache_key("adaptive", first) != pool.cache_key("hybrid", first)


def test_cache_key_matches_the_processor_factory_scheme():
    """#6193: one key scheme — the pool must embed the same content hash
    ProcessorFactory's hash_config derives, not a second hand-picked list."""
    pool = ProcessorPool(create_processor=MagicMock())
    config = SimpleNamespace(to_dict=lambda: {"internal_sample_rate": 44100})

    assert pool.cache_key("adaptive", config) == f"adaptive|{hash_config(config)}"


def _config(profile: str) -> SimpleNamespace:
    adaptive = SimpleNamespace(mode="adaptive")
    return SimpleNamespace(
        internal_sample_rate=44_100,
        mastering_profile=profile,
        adaptive=adaptive,
        # ProcessorPool.cache_key hashes UnifiedConfig.to_dict() (#6193); the
        # stub carries the distinguishing field there so two profiles still
        # derive different keys.
        to_dict=lambda: {"processing_mode": "adaptive", "profile": profile},
    )


@pytest.mark.asyncio
async def test_different_cold_keys_construct_concurrently():
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async def create(config):
        if config.mastering_profile == "first":
            first_started.set()
            await release_first.wait()
        return MagicMock(name=f"processor-{config.mastering_profile}")

    pool = ProcessorPool(create)
    first_task = asyncio.create_task(pool.get_or_create("adaptive", _config("first")))
    await asyncio.wait_for(first_started.wait(), timeout=1.0)

    second = await asyncio.wait_for(
        pool.get_or_create("adaptive", _config("second")), timeout=0.1
    )
    release_first.set()
    first = await asyncio.wait_for(first_task, timeout=1.0)

    assert first is not second


@pytest.mark.asyncio
async def test_cache_return_during_construction_wins_and_closes_redundant_build():
    construction_started = asyncio.Event()
    release_construction = asyncio.Event()
    constructed = MagicMock(name="constructed")

    async def create(_config_value):
        construction_started.set()
        await release_construction.wait()
        return constructed

    pool = ProcessorPool(create)
    config = _config("same")
    acquisition = asyncio.create_task(pool.get_or_create("adaptive", config))
    await asyncio.wait_for(construction_started.wait(), timeout=1.0)

    cached = MagicMock(name="cached")
    await pool.return_to_cache("adaptive", config, cached)
    release_construction.set()

    assert await acquisition is cached
    constructed.close.assert_called_once()


@pytest.mark.asyncio
async def test_same_key_concurrent_leases_remain_exclusive_and_reclaim_replacement():
    created: list[MagicMock] = []

    async def create(_config_value):
        processor = MagicMock(name=f"processor-{len(created)}")
        created.append(processor)
        await asyncio.sleep(0)
        return processor

    pool = ProcessorPool(create)
    config = _config("same")
    first, second = await asyncio.gather(
        pool.get_or_create("adaptive", config),
        pool.get_or_create("adaptive", config),
    )

    assert first is not second
    await pool.return_to_cache("adaptive", config, first)
    await pool.return_to_cache("adaptive", config, second)

    assert list(pool.processors.values()) == [second]
    first.close.assert_called_once()
    second.close.assert_not_called()


@pytest.mark.asyncio
async def test_close_all_closes_every_cached_processor_and_empties_the_pool():
    """#5061: shutdown must drain this pool the same way ProcessorFactory's
    cache is drained (#3746) — nothing did before close_all() existed."""
    async def create(_config_value):
        raise AssertionError("create_processor should not be called by this test")

    pool = ProcessorPool(create)
    for name in ("a", "b", "c"):
        pool.processors[name] = MagicMock(name=f"processor-{name}")
    processors = list(pool.processors.values())

    await pool.close_all()

    for processor in processors:
        processor.close.assert_called_once()
    assert pool.processors == {}


@pytest.mark.asyncio
async def test_close_all_tolerates_individual_close_failures():
    async def create(_config_value):
        raise AssertionError("create_processor should not be called by this test")

    pool = ProcessorPool(create)
    exploding = MagicMock(name="exploding")
    exploding.close.side_effect = OSError("already gone")
    fine = MagicMock(name="fine")
    pool.processors["bad"] = exploding
    pool.processors["good"] = fine

    await pool.close_all()

    exploding.close.assert_called_once()
    fine.close.assert_called_once()
    assert pool.processors == {}
