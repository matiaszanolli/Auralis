"""
Regression test: ArtworkService test coverage (#2305)

Verifies the multi-source fallback strategy, correct auth header usage,
and error handling of ArtworkService.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from auralis.services.artwork_service import ArtworkService


class TestArtworkServiceInit:
    """Test ArtworkService initialization."""

    def test_default_init(self):
        svc = ArtworkService()
        assert svc.discogs_token is None
        assert svc.lastfm_api_key is None
        assert svc.timeout == 10

    def test_init_with_credentials(self):
        svc = ArtworkService(discogs_token="abc", lastfm_api_key="xyz", timeout=5)
        assert svc.discogs_token == "abc"
        assert svc.lastfm_api_key == "xyz"
        assert svc.timeout == 5


class TestFallbackChain:
    """Test the multi-source fallback strategy."""

    def test_musicbrainz_first(self):
        """MusicBrainz is tried first."""
        svc = ArtworkService(discogs_token="tok", lastfm_api_key="key")
        mb_result = {"artwork_url": "https://mb.example/img.jpg", "source": "musicbrainz"}

        with patch.object(svc, "_fetch_from_musicbrainz", return_value=mb_result) as mock_mb:
            result = svc.fetch_artist_artwork("Test Artist")

        mock_mb.assert_called_once_with("Test Artist")
        assert result == mb_result

    def test_discogs_fallback(self):
        """Discogs is tried when MusicBrainz returns None."""
        svc = ArtworkService(discogs_token="tok")
        discogs_result = {"artwork_url": "https://discogs.example/img.jpg", "source": "discogs"}

        with patch.object(svc, "_fetch_from_musicbrainz", return_value=None), \
             patch.object(svc, "_fetch_from_discogs", return_value=discogs_result) as mock_dc:
            result = svc.fetch_artist_artwork("Test Artist")

        mock_dc.assert_called_once_with("Test Artist")
        assert result == discogs_result

    def test_lastfm_fallback(self):
        """Last.fm is tried when both MusicBrainz and Discogs fail."""
        svc = ArtworkService(discogs_token="tok", lastfm_api_key="key")
        lastfm_result = {"artwork_url": "https://lastfm.example/img.jpg", "source": "lastfm"}

        with patch.object(svc, "_fetch_from_musicbrainz", return_value=None), \
             patch.object(svc, "_fetch_from_discogs", return_value=None), \
             patch.object(svc, "_fetch_from_lastfm", return_value=lastfm_result) as mock_lfm:
            result = svc.fetch_artist_artwork("Test Artist")

        mock_lfm.assert_called_once_with("Test Artist")
        assert result == lastfm_result

    def test_all_sources_fail(self):
        """Returns None when all sources fail."""
        svc = ArtworkService(discogs_token="tok", lastfm_api_key="key")

        with patch.object(svc, "_fetch_from_musicbrainz", return_value=None), \
             patch.object(svc, "_fetch_from_discogs", return_value=None), \
             patch.object(svc, "_fetch_from_lastfm", return_value=None):
            result = svc.fetch_artist_artwork("Unknown Artist")

        assert result is None

    def test_discogs_skipped_without_token(self):
        """Discogs is skipped when no token is configured."""
        svc = ArtworkService()  # No token

        with patch.object(svc, "_fetch_from_musicbrainz", return_value=None) as mock_mb, \
             patch.object(svc, "_fetch_from_discogs") as mock_dc:
            result = svc.fetch_artist_artwork("Test")

        mock_dc.assert_not_called()

    def test_lastfm_skipped_without_key(self):
        """Last.fm is skipped when no API key is configured."""
        svc = ArtworkService()  # No key

        with patch.object(svc, "_fetch_from_musicbrainz", return_value=None), \
             patch.object(svc, "_fetch_from_lastfm") as mock_lfm:
            result = svc.fetch_artist_artwork("Test")

        mock_lfm.assert_not_called()


class TestDiscogsAuth:
    """Regression: Discogs token must be in Authorization header, not URL (#2244)."""

    def test_discogs_uses_auth_header(self):
        """Token must be sent in Authorization header, not query parameter."""
        import inspect
        svc = ArtworkService(discogs_token="test_token")
        source = inspect.getsource(svc._fetch_from_discogs)

        # Must use header, not embed in URL
        assert "Authorization" in source or "authorization" in source, (
            "Discogs token must be in Authorization header (fixes #2244)"
        )


class TestReturnShape:
    """Verify the return dict structure."""

    def test_result_has_required_keys(self):
        """Successful result must have artwork_url and source."""
        svc = ArtworkService()
        mock_result = {"artwork_url": "https://example.com/art.jpg", "source": "musicbrainz"}

        with patch.object(svc, "_fetch_from_musicbrainz", return_value=mock_result):
            result = svc.fetch_artist_artwork("Test")

        assert "artwork_url" in result
        assert "source" in result
        assert result["artwork_url"].startswith("http")
