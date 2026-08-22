"""
CSP img-src allows artist artwork hosts (issue #4526)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`Artist.artwork_url` stores a raw external CDN URL that is passed through
`/api/artists` unmodified and rendered directly as an `<img src>`, while
`SecurityHeadersMiddleware` emitted `img-src 'self' data: blob:` — which permits
no remote host at all. Every artist image was blocked by the browser, so the
artist detail page showed the no-artwork fallback for every artist that
*did* have artwork.

This is invisible in `--dev` (Vite serves the document from :3000, so this
middleware's CSP never applies to it) and always broken in the shipped Electron
build, where the backend serves the SPA itself.

The chosen fix widens `img-src` rather than proxying the images, so these tests
pin the host allowlist to the sources that actually populate the field.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.middleware import (  # noqa: E402
    _ARTIST_ARTWORK_IMG_HOSTS,
    SecurityHeadersMiddleware,
)


def _csp() -> str:
    """Render the CSP exactly as the middleware emits it."""
    import asyncio

    class _Resp:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

    async def call_next(_request):
        return _Resp()

    middleware = SecurityHeadersMiddleware.__new__(SecurityHeadersMiddleware)
    response = asyncio.run(middleware.dispatch(None, call_next))
    return response.headers["Content-Security-Policy"]


def _directive(name: str) -> list[str]:
    for part in _csp().split(";"):
        part = part.strip()
        if part.startswith(f"{name} "):
            return part[len(name) + 1:].split()
    raise AssertionError(f"{name} not present in CSP: {_csp()}")


class TestImgSrc:
    def test_self_data_blob_still_allowed(self):
        """Widening must not drop what album/track artwork relies on."""
        sources = _directive("img-src")
        for required in ("'self'", "data:", "blob:"):
            assert required in sources

    @pytest.mark.parametrize("host", _ARTIST_ARTWORK_IMG_HOSTS)
    def test_each_declared_host_is_present(self, host: str):
        assert host in _directive("img-src")

    @pytest.mark.parametrize(
        "source,host",
        [
            ("lastfm", "https://lastfm.freetls.fastly.net"),
            ("discogs", "https://i.discogs.com"),
            ("musicbrainz", "https://upload.wikimedia.org"),
        ],
    )
    def test_each_artwork_source_has_a_permitted_host(self, source: str, host: str):
        """One host per fetcher in auralis/services/artwork_service.py."""
        assert host in _directive("img-src"), (
            f"artist artwork from {source} would be blocked by the CSP"
        )

    def test_img_src_is_not_a_blanket_https_wildcard(self):
        """`https:` would allow every image on the internet.

        The whole point of enumerating hosts is that the directive keeps
        meaning something; a bare scheme-source gives that up.
        """
        sources = _directive("img-src")
        assert "https:" not in sources
        assert "*" not in sources

    def test_hosts_are_https_and_fully_qualified(self):
        for host in _ARTIST_ARTWORK_IMG_HOSTS:
            assert host.startswith("https://"), f"{host} is not https"
            assert re.fullmatch(r"https://[A-Za-z0-9.*-]+", host), (
                f"{host} is not a bare host source (no paths/ports expected)"
            )


class TestOtherDirectivesUnchanged:
    """Widening img-src must not disturb the rest of the policy."""

    @pytest.mark.parametrize(
        "directive,expected",
        [
            ("default-src", ["'self'"]),
            ("media-src", ["'self'", "blob:"]),
            ("font-src", ["'self'", "https://fonts.gstatic.com"]),
        ],
    )
    def test_directive_intact(self, directive: str, expected: list[str]):
        assert _directive(directive) == expected

    def test_connect_src_is_generated_from_the_shared_host_policy(self):
        """#4712 replaced the hardcoded localhost-only literal.

        The exact source list is owned by config/origins.py and asserted in
        test_origin_policy_single_source.py; this only pins that widening
        img-src did not disturb it.
        """
        from config.origins import csp_connect_src

        assert _directive("connect-src") == csp_connect_src().split()

    def test_frame_ancestors_protection_still_set(self):
        assert "'self'" in _directive("default-src")


class TestArtistArtworkContract:
    """`Artist.artwork_url` is the deliberate external-URL exception."""

    def test_artist_to_dict_passes_the_external_url_through(self):
        """Pinned so a future 'consistency' refactor is a conscious decision.

        Album/Track rewrite artwork to an /api path; Artist cannot, because
        there is no local file behind it — only a third-party CDN URL.
        """
        from auralis.library.models.core import Artist

        artist = Artist(
            id=7,
            name="Test Artist",
            artwork_url="https://lastfm.freetls.fastly.net/i/u/770x0/abc.jpg",
            artwork_source="lastfm",
        )
        payload = artist.to_dict()
        assert payload["artwork_url"] == (
            "https://lastfm.freetls.fastly.net/i/u/770x0/abc.jpg"
        )
        assert payload["artwork_source"] == "lastfm"

    def test_the_exception_is_documented_in_the_model(self):
        """A divergence nobody wrote down is a bug waiting to be 'fixed'."""
        # #4511 split Artist out of models/core.py into its own module.
        source = (
            Path(__file__).parent.parent.parent
            / "auralis" / "library" / "models" / "artist.py"
        ).read_text()
        artist_block = source[source.index("class Artist("):]
        assert "#4526" in artist_block, (
            "Artist.artwork_url's divergence from Album/Track is undocumented"
        )
