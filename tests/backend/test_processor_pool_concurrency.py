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


def _config(profile: str) -> SimpleNamespace:
    adaptive = SimpleNamespace(
        mode="adaptive",
        eq_gains=None,
        compressor=None,
        target_lufs=None,
        gain=None,
        genre_override=None,
    )
    return SimpleNamespace(
        internal_sample_rate=44_100,
        mastering_profile=profile,
        adaptive=adaptive,
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
