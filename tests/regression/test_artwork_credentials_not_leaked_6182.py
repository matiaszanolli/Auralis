"""Artwork API credentials are not exposed via argv or replayed across redirects (#6182).

The CLI took the Discogs token and Last.fm key as arguments (visible in `ps` and shell history), and
the Discogs token travelled as an ordinary header that urllib copies to a redirect target on another
host.
"""

import argparse
import urllib.request
from unittest.mock import MagicMock, patch

from auralis.cli.fetch_artwork import resolve_credentials
from auralis.services.artwork_service import ArtworkService
from auralis.services.artwork_sources.discogs import fetch_from_discogs


def _args(token=None, key=None):
    return argparse.Namespace(discogs_token=token, lastfm_key=key)


def test_environment_variables_supply_the_credentials():
    token, key = resolve_credentials(_args(), {"AURALIS_DISCOGS_TOKEN": "T", "AURALIS_LASTFM_KEY": "K"})

    assert (token, key) == ("T", "K")


def test_arguments_still_work_but_warn(caplog):
    with caplog.at_level("WARNING"):
        token, key = resolve_credentials(_args("argv-token", "argv-key"), {})

    assert (token, key) == ("argv-token", "argv-key")
    assert "visible to other local users" in caplog.text


def test_the_environment_wins_over_an_argument():
    token, _ = resolve_credentials(_args(token="argv"), {"AURALIS_DISCOGS_TOKEN": "env"})

    assert token == "env"


def test_nothing_set_means_no_credentials_and_no_warning(caplog):
    with caplog.at_level("WARNING"):
        assert resolve_credentials(_args(), {}) == (None, None)

    assert caplog.text == ""


def test_the_discogs_token_is_not_carried_to_a_redirect_target():
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"results": []}'
        response.headers = {}
        return response

    service = ArtworkService(discogs_token="SECRET")
    with patch("urllib.request.urlopen", fake_urlopen):
        fetch_from_discogs(service, "Some Band")

    req = captured["req"]
    assert req.get_header("Authorization") == "Discogs token=SECRET"          # sent to the API host
    assert "Authorization" not in req.headers                                   # but not an ordinary header
    redirected = urllib.request.HTTPRedirectHandler().redirect_request(
        req, None, 302, "Found", {}, "https://other.example/x"
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") is None
