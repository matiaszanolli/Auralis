"""Outbound artwork searches are spaced per host (#5069)."""

import asyncio
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.utils.host_throttle import HostThrottle  # noqa: E402

pytestmark = pytest.mark.asyncio


async def test_requests_to_one_host_start_at_least_the_interval_apart():
    throttle = HostThrottle({"musicbrainz.org": 0.15})
    starts: list[float] = []

    async def request():
        await throttle.wait("musicbrainz.org")
        starts.append(time.monotonic())

    await asyncio.gather(*(request() for _ in range(4)))

    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert len(gaps) == 3
    assert all(gap >= 0.14 for gap in gaps)


async def test_other_hosts_and_unlisted_hosts_do_not_wait():
    throttle = HostThrottle({"musicbrainz.org": 5.0})

    await throttle.wait("musicbrainz.org")  # takes the first slot
    started = time.monotonic()
    await throttle.wait("itunes.apple.com")  # not configured here
    await throttle.wait("example.org")

    assert time.monotonic() - started < 0.5


async def test_the_downloader_paces_its_provider_searches():
    from services.artwork_downloader import ArtworkDownloader

    downloader = ArtworkDownloader(cache_dir="/tmp/auralis_throttle_test")
    assert downloader.throttle._intervals["musicbrainz.org"] >= 1.0
    assert downloader.throttle._intervals["itunes.apple.com"] > 0
