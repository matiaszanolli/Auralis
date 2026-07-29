# -*- coding: utf-8 -*-

"""
Regression tests: _calculate_total_chunks delegates to the chunk-model SoT (#4620)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``StreamlinedCacheManager._calculate_total_chunks`` used to re-derive
``content_chunk_count``'s overlap-aware formula inline, with a function-local
``import math`` and a locally recomputed ``overlap = CHUNK_DURATION -
CHUNK_INTERVAL``. Its own docstring asserted the invariant that its result must
equal ``ChunkedAudioProcessor.total_chunks`` — which is set from
``content_chunk_count()`` — but nothing enforced it.

The two expressions were numerically identical, so this was never a live bug.
It became one the moment ``OVERLAP_DURATION`` was decoupled from
``CHUNK_DURATION - CHUNK_INTERVAL``: the copies would diverge silently and the
cache would never report a track complete. These tests pin the delegation.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from cache.manager import StreamlinedCacheManager  # noqa: E402
from core.chunk_boundaries import (  # noqa: E402
    CHUNK_INTERVAL,
    OVERLAP_DURATION,
    content_chunk_count,
)

# Durations spanning the #4124 boundary cases: each n*INTERVAL, plus points
# just inside and just outside the (n*INTERVAL, n*INTERVAL + OVERLAP) window
# where the naive ceil(duration / CHUNK_INTERVAL) over-counted a 0-content
# trailing chunk.
BOUNDARY_DURATIONS = [
    0.0, 0.1, 1.0, 4.9, 5.0, 5.1,
    9.9, 10.0, 10.1, 14.9, 15.0, 15.1,
    19.9, 20.0, 20.1, 24.9, 25.0, 25.1,
    100.0, 180.0, 183.7, 3600.0,
]


@pytest.fixture
def manager():
    return StreamlinedCacheManager()


@pytest.mark.parametrize("duration", BOUNDARY_DURATIONS)
def test_matches_content_chunk_count(manager, duration):
    """The equality the old docstring asserted but nothing enforced."""
    assert manager._calculate_total_chunks(duration) == content_chunk_count(duration)


@pytest.mark.parametrize("duration", BOUNDARY_DURATIONS)
def test_returns_plain_int(manager, duration):
    """content_chunk_count() goes through np.ceil — the result must not leak a
    numpy scalar where the old math.ceil returned a plain int."""
    result = manager._calculate_total_chunks(duration)
    assert type(result) is int


@pytest.mark.parametrize("duration", BOUNDARY_DURATIONS)
def test_never_below_one(manager, duration):
    """Even a zero-length track occupies one chunk slot."""
    assert manager._calculate_total_chunks(duration) >= 1


def test_no_zero_content_trailing_chunk(manager):
    """#4124: durations in (n*INTERVAL, n*INTERVAL + OVERLAP) must not gain a
    chunk that emits no new samples."""
    for n in range(1, 6):
        base = n * CHUNK_INTERVAL
        inside = manager._calculate_total_chunks(base + OVERLAP_DURATION / 2)
        at_base = manager._calculate_total_chunks(base)
        assert inside == at_base, (
            f"duration {base + OVERLAP_DURATION / 2} gained a 0-content chunk "
            f"over {base}"
        )


def test_body_delegates_rather_than_rederiving(manager):
    """Guard the fix itself: no local formula, no function-local import math."""
    source = inspect.getsource(StreamlinedCacheManager._calculate_total_chunks)
    assert "content_chunk_count(duration)" in source
    assert "import math" not in source
    assert "CHUNK_DURATION - CHUNK_INTERVAL" not in source
