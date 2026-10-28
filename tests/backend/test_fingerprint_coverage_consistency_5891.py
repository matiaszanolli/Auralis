"""The coverage payload counts one thing: usable (current-version) fingerprints (#5891).

get_fingerprint_stats defines fingerprinted = current + outdated, but progress_percent uses
only current, and similarity treats outdated rows as missing. The status route derived
"All tracks fingerprinted" and "N/N" from the larger number next to a bar that was not full.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.fingerprint_status import get_fingerprinting_status

pytestmark = pytest.mark.asyncio

# 10 tracks: 6 current, 3 outdated (an older algorithm version), 1 never fingerprinted.
STATS = {"total": 10, "fingerprinted": 9, "current": 6, "outdated": 3, "pending": 1, "progress_percent": 60}


def _repos(stats=STATS):
    repos = Mock()
    repos.fingerprint_stats.get_fingerprint_stats = Mock(return_value=stats)
    return repos


async def test_outdated_rows_are_pending_not_fingerprinted():
    result = await get_fingerprinting_status(repos=_repos())

    assert result["fingerprinted_tracks"] == 6
    assert result["pending_tracks"] == 4
    assert result["progress_percent"] == 60
    assert "All tracks" not in result["status"]
    assert "6/10" in result["status"]


async def test_all_tracks_fingerprinted_only_when_every_row_is_current():
    stats = {"total": 5, "fingerprinted": 5, "current": 5, "outdated": 0, "pending": 0, "progress_percent": 100}

    result = await get_fingerprinting_status(repos=_repos(stats))

    assert "All tracks fingerprinted" in result["status"]
    assert result["pending_tracks"] == 0
