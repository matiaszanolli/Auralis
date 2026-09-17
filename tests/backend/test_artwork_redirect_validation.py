"""Artwork downloads validate every redirect hop before requesting it (#4940, #5330).

#4940 checked ``resp.url`` after aiohttp had followed the whole redirect chain,
so an intermediate hop to a loopback or LAN address had already been sent a real
GET by the time the final URL was rejected. Redirects are now followed by hand,
and each hop is validated before its request.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.artwork_downloader import _MAX_ARTWORK_REDIRECTS, ArtworkDownloader

ITUNES_SEARCH = "https://itunes.apple.com/search"
ITUNES_ART = "https://is1-ssl.mzstatic.com/image/600x600.jpg"
MB_SEARCH = "https://musicbrainz.org/ws/2/release/"
CAA_FRONT = "https://coverartarchive.org/release/rel-1/front"


class _Response:
    def __init__(self, *, status=200, location=None, json_data=None, content=b"image-bytes"):
        self.status = status
        self.headers = {"Location": location} if location else {}
        self.content_length = len(content)
        self._json_data = json_data
        self.content = Mock()
        self.content.read = AsyncMock(return_value=content)

    async def json(self):
        return self._json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _Session:
    """Answers from a {url: response} map and records every URL requested."""

    def __init__(self, responses):
        self._responses = responses
        self.requested = []
        self.redirect_flags = []

    def get(self, url, **kwargs):
        self.requested.append(url)
        self.redirect_flags.append(kwargs.get("allow_redirects", True))
        return self._responses[url]


def _itunes(artwork_url100="https://is1-ssl.mzstatic.com/image/100x100.jpg"):
    return _Response(json_data={"results": [{"artworkUrl100": artwork_url100}]})


def _downloader(tmp_path, session):
    downloader = ArtworkDownloader(cache_dir=str(tmp_path))
    downloader._get_session = lambda: session  # type: ignore[method-assign]
    downloader._save_artwork = AsyncMock(  # type: ignore[method-assign]
        return_value=str(tmp_path / "album.jpg")
    )
    return downloader


@pytest.mark.asyncio
async def test_untrusted_intermediate_hop_is_never_requested(tmp_path):
    lan = "https://192.168.1.10/art.jpg"
    session = _Session({
        MB_SEARCH: _Response(json_data={"releases": [{"id": "rel-1"}]}),
        CAA_FRONT: _Response(status=307, location=lan),
        # Where the chain would have ended had the LAN hop been followed.
        lan: _Response(status=302, location="https://ia801.us.archive.org/art.jpg"),
    })
    downloader = _downloader(tmp_path, session)

    assert await downloader._try_musicbrainz("Artist", "Album", 1) is None

    assert lan not in session.requested
    assert session.redirect_flags[0] is False
    downloader._save_artwork.assert_not_awaited()


@pytest.mark.asyncio
async def test_loopback_redirect_is_never_requested(tmp_path):
    loopback = "http://127.0.0.1:8765/api/library"
    art = _Response(status=302, location=loopback)
    session = _Session({ITUNES_SEARCH: _itunes(), ITUNES_ART: art})
    downloader = _downloader(tmp_path, session)

    assert await downloader._try_itunes("Artist", "Album", 1) is None

    assert session.requested == [ITUNES_SEARCH, ITUNES_ART]
    assert session.redirect_flags == [False, False]
    art.content.read.assert_not_awaited()


@pytest.mark.asyncio
async def test_plaintext_downgrade_hop_is_never_requested(tmp_path):
    """#5337: a trusted host over http is still refused."""
    downgrade = "http://ia801.us.archive.org/art.jpg"
    session = _Session({
        MB_SEARCH: _Response(json_data={"releases": [{"id": "rel-1"}]}),
        CAA_FRONT: _Response(status=302, location=downgrade),
    })
    downloader = _downloader(tmp_path, session)

    assert await downloader._try_musicbrainz("Artist", "Album", 1) is None
    assert downgrade not in session.requested


@pytest.mark.asyncio
async def test_untrusted_response_url_is_never_requested(tmp_path):
    session = _Session({ITUNES_SEARCH: _itunes("https://127.0.0.1/100x100.jpg")})
    downloader = _downloader(tmp_path, session)

    assert await downloader._try_itunes("Artist", "Album", 1) is None
    assert session.requested == [ITUNES_SEARCH]


@pytest.mark.asyncio
async def test_trusted_chain_is_followed_one_hop_at_a_time(tmp_path):
    archive = "https://archive.org/download/mbid-rel-1/front.jpg"
    mirror = "https://ia801.us.archive.org/1/items/mbid-rel-1/front.jpg"
    image = _Response()
    session = _Session({
        MB_SEARCH: _Response(json_data={"releases": [{"id": "rel-1"}]}),
        CAA_FRONT: _Response(status=307, location=archive),
        archive: _Response(status=302, location=mirror),
        mirror: image,
    })
    downloader = _downloader(tmp_path, session)

    assert await downloader._try_musicbrainz("Artist", "Album", 1) == str(tmp_path / "album.jpg")

    assert session.requested == [MB_SEARCH, CAA_FRONT, archive, mirror]
    assert session.redirect_flags[1:] == [False, False, False]
    image.content.read.assert_awaited_once()
    downloader._save_artwork.assert_awaited_once_with(b"image-bytes", 1, "jpg")


@pytest.mark.asyncio
async def test_relative_location_resolves_against_the_current_hop(tmp_path):
    resolved = "https://is1-ssl.mzstatic.com/image/real/600x600.jpg"
    session = _Session({
        ITUNES_SEARCH: _itunes(),
        ITUNES_ART: _Response(status=301, location="/image/real/600x600.jpg"),
        resolved: _Response(),
    })
    downloader = _downloader(tmp_path, session)

    assert await downloader._try_itunes("Artist", "Album", 1) == str(tmp_path / "album.jpg")
    assert session.requested[-1] == resolved


@pytest.mark.asyncio
async def test_redirect_loop_is_bounded(tmp_path):
    loop = "https://archive.org/loop"
    session = _Session({
        MB_SEARCH: _Response(json_data={"releases": [{"id": "rel-1"}]}),
        CAA_FRONT: _Response(status=302, location=loop),
        loop: _Response(status=302, location=CAA_FRONT),
    })
    downloader = _downloader(tmp_path, session)

    assert await downloader._try_musicbrainz("Artist", "Album", 1) is None
    assert len(session.requested) - 1 == _MAX_ARTWORK_REDIRECTS + 1


@pytest.mark.asyncio
async def test_non_200_final_status_yields_nothing(tmp_path):
    missing = _Response(status=404)
    session = _Session({ITUNES_SEARCH: _itunes(), ITUNES_ART: missing})
    downloader = _downloader(tmp_path, session)

    assert await downloader._try_itunes("Artist", "Album", 1) is None
    missing.content.read.assert_not_awaited()
