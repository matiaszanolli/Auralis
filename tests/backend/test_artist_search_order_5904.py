"""`ArtistRepository.search()` honours `order_by` like `get_all()` (#5904).

The router validated `order_by` for every request but its search branch never
forwarded it, and the repository hard-coded `ORDER BY name`, so
`?search=x&order_by=track_count` answered 200 in name order.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.artists import get_artists  # noqa: E402


def _seed(track_repository, artist: str, tracks: int) -> None:
    for i in range(tracks):
        track_repository.add({
            'title': f'{artist} {i}',
            'filepath': f'/tmp/{artist}_{i}.wav',
            'duration': 100.0,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'artists': [artist],
            'album': f'{artist} Album',
        })


class TestArtistSearchOrder:
    def test_search_orders_by_track_count(self, artist_repository, track_repository):
        _seed(track_repository, 'Match A', 1)
        _seed(track_repository, 'Match B', 3)
        _seed(track_repository, 'Match C', 2)

        by_name, _ = artist_repository.search('Match')
        by_tracks, total = artist_repository.search('Match', order_by='track_count')

        assert [a.name for a in by_name] == ['Match A', 'Match B', 'Match C']
        assert [a.name for a in by_tracks] == ['Match B', 'Match C', 'Match A']
        assert total == 3

    def test_search_matches_get_all_ordering(self, artist_repository, track_repository):
        _seed(track_repository, 'Same X', 2)
        _seed(track_repository, 'Same Y', 1)

        for order_by in ('name', 'album_count', 'track_count'):
            searched, _ = artist_repository.search('Same', order_by=order_by)
            listed, _ = artist_repository.get_all(order_by=order_by)
            assert [a.id for a in searched] == [a.id for a in listed], order_by


@pytest.mark.parametrize("order_by", ["name", "album_count", "track_count"])
def test_router_forwards_order_by_to_search(order_by):
    repos = MagicMock()
    repos.artists.search.return_value = ([], 0)

    # The handler takes its dependencies as plain arguments, so call it directly.
    asyncio.run(get_artists(limit=10, offset=0, search="x", order_by=order_by, repos=repos))

    repos.artists.search.assert_called_once_with("x", limit=10, offset=0, order_by=order_by, order=None)
