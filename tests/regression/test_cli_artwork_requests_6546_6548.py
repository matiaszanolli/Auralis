"""CLI artwork metadata requests are spaced per host and never redirected (#6546, #6548).

The four provider calls (MusicBrainz search and url-rels, Discogs, Last.fm) used
plain ``urlopen``: it followed a redirect to any host, loopback and LAN included,
and a library-wide run sent them at network speed until MusicBrainz blocked the
User-Agent every install shares, every later artist then logged as "not found"
at DEBUG. They now all go through ``_common.fetch_metadata_json``: the shared
``HostThrottle`` spaces each host's requests, a redirect is refused, and a
429/503 pushes the host's next request out and logs a WARNING.
"""

import io
import json
import logging
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from auralis.services.artwork_service import ArtworkService
from auralis.services.artwork_sources import _common
from auralis.utils import host_throttle
from auralis.utils.host_throttle import MUSICBRAINZ_MIN_INTERVAL_S, HostThrottle


class _Clock:
    """time.monotonic / time.sleep for host_throttle: sleeping advances the clock."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(round(seconds, 3))
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr(host_throttle.time, "monotonic", fake.monotonic)
    monkeypatch.setattr(host_throttle.time, "sleep", fake.sleep)
    monkeypatch.setattr(_common, "_THROTTLE", HostThrottle(_common._THROTTLE._intervals))
    return fake


def _json(payload):
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps(payload).encode()
    return response


def test_musicbrainz_requests_are_spaced_by_its_interval(clock):
    hosts = []

    def open_(req, timeout=None):
        hosts.append(req.host)
        clock.now += 0.05  # the request itself is quick
        return _json({"artists": [{"id": "mbid"}], "relations": []})

    with patch.object(_common._OPENER, "open", open_):
        ArtworkService()._fetch_from_musicbrainz("Artist One")
        ArtworkService()._fetch_from_musicbrainz("Artist Two")

    assert hosts == ["musicbrainz.org"] * 4
    assert len(clock.sleeps) == 3
    assert all(s == pytest.approx(MUSICBRAINZ_MIN_INTERVAL_S - 0.05) for s in clock.sleeps)


@pytest.mark.parametrize("provider", ["musicbrainz", "discogs", "lastfm"])
def test_every_provider_goes_through_the_throttled_unredirected_opener(clock, provider):
    opened = []

    def open_(req, timeout=None):
        opened.append(req.host)
        return _json({})

    service = ArtworkService(discogs_token="t", lastfm_api_key="k")
    with patch.object(_common._OPENER, "open", open_):
        getattr(service, f"_fetch_from_{provider}")("Artist")

    expected = {"musicbrainz": "musicbrainz.org", "discogs": "api.discogs.com", "lastfm": "ws.audioscrobbler.com"}
    assert opened == [expected[provider]]
    assert any(isinstance(h, _common._RefuseRedirects) for h in _common._OPENER.handlers)


def test_a_rate_limit_answer_backs_the_host_off_and_warns(clock, caplog):
    def limited(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {"Retry-After": "30"}, io.BytesIO())

    with caplog.at_level(logging.WARNING, logger=_common.logger.name):
        with patch.object(_common._OPENER, "open", limited):
            assert ArtworkService()._fetch_from_musicbrainz("Artist") is None
        with patch.object(_common._OPENER, "open", lambda req, timeout=None: _json({"artists": []})):
            ArtworkService()._fetch_from_musicbrainz("Next Artist")

    assert clock.sleeps == [30.0]
    assert "musicbrainz.org answered 503; pausing requests to it for 30s" in caplog.text


def test_a_redirect_is_refused_with_a_warning(caplog):
    handler = _common._RefuseRedirects()
    req = _common.urllib.request.Request("https://musicbrainz.org/ws/2/artist/")

    with caplog.at_level(logging.WARNING, logger=_common.logger.name):
        assert handler.redirect_request(req, None, 302, "Found", {}, "http://127.0.0.1:8765/api") is None

    assert "Refusing a 302 redirect from musicbrainz.org" in caplog.text
