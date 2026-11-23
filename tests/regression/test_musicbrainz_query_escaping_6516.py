"""Tag text cannot inject MusicBrainz query syntax (#6516).

Album and artist names come from file tags and were interpolated straight into
the Lucene query (``artist:"{artist}" AND release:"{album}"``, and unquoted
``artist:{name}`` in the CLI artist-image source). A ``"`` closed the phrase and
the rest was parsed as query syntax, steering the search to another release.
Both call sites now pass the text through ``musicbrainz_phrase``.
"""

import asyncio
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.services import artwork_service  # noqa: E402
from auralis.services.artwork_sources import musicbrainz as cli_musicbrainz  # noqa: E402
from auralis.utils.artwork_security import musicbrainz_phrase  # noqa: E402
from services.artwork_downloader import ArtworkDownloader  # noqa: E402

HOSTILE_ARTIST = 'Band" OR artist:"Other'
HOSTILE_ALBUM = 'Album\\" OR release:*'

# A quoted phrase: opening quote, then escaped pairs or anything but \ and ", then the closing quote.
_PHRASE = r'"(?:\\.|[^"\\])*"'


def _unescape(phrase: str) -> str:
    return re.sub(r"\\(.)", r"\1", phrase[1:-1])


@pytest.mark.parametrize("text", ["AC/DC", 'a"b', "x\\y", HOSTILE_ARTIST, HOSTILE_ALBUM, "", "(*) && ||"])
def test_phrase_is_one_quoted_token_that_round_trips(text):
    phrase = musicbrainz_phrase(text)

    assert re.fullmatch(_PHRASE, phrase), phrase
    assert _unescape(phrase) == text


class _Response:
    status = 404

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _Session:
    def __init__(self):
        self.params = []

    def get(self, url, **kwargs):
        self.params.append(kwargs.get("params"))
        return _Response()


def test_album_artwork_search_quotes_both_fields(tmp_path):
    session = _Session()
    downloader = ArtworkDownloader(cache_dir=str(tmp_path))
    downloader._get_session = lambda: session  # type: ignore[method-assign]

    assert asyncio.run(downloader._try_musicbrainz(HOSTILE_ARTIST, HOSTILE_ALBUM, 1)) is None

    query = session.params[0]["query"]
    match = re.fullmatch(rf"artist:({_PHRASE}) AND release:({_PHRASE})", query)
    assert match, query
    assert (_unescape(match[1]), _unescape(match[2])) == (HOSTILE_ARTIST, HOSTILE_ALBUM)


def test_cli_artist_search_quotes_the_name(monkeypatch):
    sent = []

    def fake_fetch(req, timeout):
        sent.append(req.full_url)
        return {}

    monkeypatch.setattr(cli_musicbrainz, "fetch_metadata_json", fake_fetch)

    assert artwork_service.ArtworkService()._fetch_from_musicbrainz(HOSTILE_ARTIST) is None

    query = urllib.parse.parse_qs(urllib.parse.urlsplit(sent[0]).query)["query"][0]
    match = re.fullmatch(rf"artist:({_PHRASE})", query)
    assert match, query
    assert _unescape(match[1]) == HOSTILE_ARTIST
