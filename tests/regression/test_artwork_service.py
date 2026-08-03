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
from auralis.utils.artwork_security import (
    MAX_ARTWORK_PAYLOAD_BYTES,
    validate_artwork_url,
)


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


class TestArtworkURLSafety:
    """Regression coverage for trusted external artwork sources (#4936)."""

    @staticmethod
    def _response(payload=None, *, resolved_url=None):
        response = MagicMock()
        if payload is not None:
            response.read.return_value = json.dumps(payload).encode()
        if resolved_url is not None:
            response.geturl.return_value = resolved_url

        cm = MagicMock()
        cm.__enter__.return_value = response
        cm.__exit__.return_value = False
        return response, cm

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1:8765/api/library",
            "http://192.168.1.10/art.jpg",
            "file:///etc/passwd",
            "https://upload.wikimedia.org.evil.example/art.jpg",
        ],
    )
    def test_validator_rejects_local_and_untrusted_urls(self, url):
        assert not validate_artwork_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://upload.wikimedia.org/example/art.jpg",
            "https://i.discogs.com/example/art.jpg",
            "https://lastfm.freetls.fastly.net/example/art.jpg",
            "https://coverartarchive.org/release/example/front.jpg",
            "https://ia801.us.archive.org/example/art.jpg",
            "https://is1-ssl.mzstatic.com/example/art.jpg",
        ],
    )
    def test_validator_accepts_supported_artwork_hosts(self, url):
        assert validate_artwork_url(url)

    def test_musicbrainz_rejects_poisoned_relation_url(self):
        svc = ArtworkService()
        _, search_cm = self._response({"artists": [{"id": "artist-id"}]})
        _, relations_cm = self._response(
            {
                "relations": [
                    {
                        "type": "image",
                        "url": {"resource": "http://127.0.0.1:8765/api/library"},
                    }
                ]
            }
        )

        with patch(
            "auralis.services.artwork_service.urllib.request.urlopen",
            side_effect=[search_cm, relations_cm],
        ):
            assert svc._fetch_from_musicbrainz("Poisoned Artist") is None

    def test_musicbrainz_accepts_wikimedia_relation_url(self):
        svc = ArtworkService()
        image_url = "https://upload.wikimedia.org/example/artist.jpg"
        _, search_cm = self._response({"artists": [{"id": "artist-id"}]})
        _, relations_cm = self._response(
            {
                "relations": [
                    {"type": "image", "url": {"resource": image_url}}
                ]
            }
        )

        with patch(
            "auralis.services.artwork_service.urllib.request.urlopen",
            side_effect=[search_cm, relations_cm],
        ):
            assert svc._fetch_from_musicbrainz("Trusted Artist") == {
                "artwork_url": image_url,
                "source": "musicbrainz",
            }

    def test_discogs_rejects_untrusted_result_url(self):
        svc = ArtworkService(discogs_token="token")
        _, response_cm = self._response(
            {"results": [{"cover_image": "http://192.168.1.10/cover.jpg"}]}
        )

        with patch(
            "auralis.services.artwork_service.urllib.request.urlopen",
            return_value=response_cm,
        ):
            assert svc._fetch_from_discogs("Artist") is None

    def test_lastfm_rejects_untrusted_result_url(self):
        svc = ArtworkService(lastfm_api_key="key")
        _, response_cm = self._response(
            {"artist": {"image": [{"#text": "http://localhost/cover.jpg"}]}}
        )

        with patch(
            "auralis.services.artwork_service.urllib.request.urlopen",
            return_value=response_cm,
        ):
            assert svc._fetch_from_lastfm("Artist") is None

    def test_cover_art_archive_rejects_untrusted_redirect(self):
        svc = ArtworkService()
        _, search_cm = self._response({"release-groups": [{"id": "mbid-1"}]})
        _, cover_cm = self._response(
            resolved_url="http://127.0.0.1:8765/api/library"
        )

        with patch(
            "auralis.services.artwork_service.urllib.request.urlopen",
            side_effect=[search_cm, cover_cm],
        ):
            assert svc._fetch_album_from_musicbrainz("Album") is None

    def test_metadata_response_read_is_size_limited(self):
        svc = ArtworkService(discogs_token="token")
        response = MagicMock()
        response.read.return_value = b"x" * (MAX_ARTWORK_PAYLOAD_BYTES + 1)
        cm = MagicMock()
        cm.__enter__.return_value = response
        cm.__exit__.return_value = False

        with patch(
            "auralis.services.artwork_service.urllib.request.urlopen",
            return_value=cm,
        ):
            assert svc._fetch_from_discogs("Artist") is None

        response.read.assert_called_once_with(MAX_ARTWORK_PAYLOAD_BYTES + 1)


class TestFetchAlbumArtwork:
    """#4037: fetch_album_artwork now resolves via MusicBrainz release-group +
    Cover Art Archive instead of logging 'not implemented' and returning None."""

    @staticmethod
    def _cm(obj):
        """Wrap a mock response as a context manager (urlopen is used in `with`)."""
        cm = MagicMock()
        cm.__enter__.return_value = obj
        cm.__exit__.return_value = False
        return cm

    def test_delegates_to_musicbrainz_helper(self):
        svc = ArtworkService()
        expected = {"artwork_url": "https://x/front.jpg", "source": "coverartarchive"}
        with patch.object(svc, "_fetch_album_from_musicbrainz", return_value=expected) as m:
            result = svc.fetch_album_artwork("Album", "Artist")
        m.assert_called_once_with("Album", "Artist")
        assert result == expected

    def test_resolves_cover_art_archive_front_url(self):
        svc = ArtworkService()
        search = MagicMock()
        search.read.return_value = json.dumps({"release-groups": [{"id": "mbid-1"}]}).encode()
        caa = MagicMock()
        caa.geturl.return_value = "https://coverartarchive.org/release/abc/front-500.jpg"
        with patch(
            "auralis.services.artwork_service.urllib.request.urlopen",
            side_effect=[self._cm(search), self._cm(caa)],
        ):
            result = svc.fetch_album_artwork("Some Album", "Some Artist")
        assert result == {
            "artwork_url": "https://coverartarchive.org/release/abc/front-500.jpg",
            "source": "coverartarchive",
        }

    def test_no_release_group_returns_none(self):
        svc = ArtworkService()
        search = MagicMock()
        search.read.return_value = json.dumps({"release-groups": []}).encode()
        with patch(
            "auralis.services.artwork_service.urllib.request.urlopen",
            side_effect=[self._cm(search)],
        ):
            assert svc.fetch_album_artwork("Unknown Album") is None

    def test_no_front_cover_returns_none(self):
        import urllib.error

        svc = ArtworkService()
        search = MagicMock()
        search.read.return_value = json.dumps({"release-groups": [{"id": "mbid-1"}]}).encode()
        http_404 = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
        with patch(
            "auralis.services.artwork_service.urllib.request.urlopen",
            side_effect=[self._cm(search), http_404],
        ):
            assert svc.fetch_album_artwork("Album With No Cover") is None
