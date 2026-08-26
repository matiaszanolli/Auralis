"""
CSP `'unsafe-inline'` is a documented, investigated decision (#3900)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`script-src 'self' 'unsafe-inline'` and `style-src 'self' 'unsafe-inline'
https://fonts.googleapis.com` weaken CSP's XSS backstop. The audit flagged
this as looking like an unexamined default rather than a deliberate choice.

Both directives were investigated for a hash/nonce replacement:

- script-src: the built frontend's one inline `<script type="module">`
  bootstrap block changes byte-for-byte on every Vite build (embedded chunk
  filenames carry a content hash), so a static CSP hash can't be baked in,
  and computing one from the live index.html at startup can't be verified
  against a real browser's parser in this environment (no Playwright/browser
  test suite) -- a mismatch would silently block the entire app boot.
- style-src: React/MUI render styling via inline `style="..."` element
  ATTRIBUTES (sx props, emotion CSS-in-JS), and CSP nonces/hashes only ever
  allowlist `<script>`/`<style>` ELEMENTS, never the `style=` attribute --
  there is no mechanism that covers this case at all.

This file doesn't re-attempt the removal (see config/middleware.py's CSP
comment for the full reasoning) -- it pins the current, intentional CSP
values and the presence of that reasoning, so any future edit that quietly
drops the explanation (or the directives themselves) without re-examining
this tradeoff is caught.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.middleware import SecurityHeadersMiddleware  # noqa: E402


def _csp() -> str:
    """Render the CSP exactly as the middleware emits it (mirrors
    test_csp_artist_artwork_4526.py's helper)."""
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


class TestUnsafeInlineIsCurrentlyPresentAndDocumented:
    def test_script_src_still_carries_unsafe_inline(self):
        assert "'unsafe-inline'" in _directive("script-src")

    def test_style_src_still_carries_unsafe_inline(self):
        assert "'unsafe-inline'" in _directive("style-src")

    def test_dispatch_source_documents_why_script_src_keeps_unsafe_inline(self):
        source = inspect.getsource(SecurityHeadersMiddleware.dispatch)
        assert "script-src" in source
        assert "sha256" in source or "nonce" in source, (
            "the dispatch source must explain the hash/nonce alternative "
            "that was considered and rejected for script-src"
        )
        assert "Vite build" in source or "index.html" in source, (
            "must reference the concrete reason a script hash can't be "
            "statically baked in"
        )

    def test_dispatch_source_documents_why_style_src_keeps_unsafe_inline(self):
        source = inspect.getsource(SecurityHeadersMiddleware.dispatch)
        assert "style-src" in source
        assert "attribute" in source, (
            "must explain that CSP nonces/hashes cover <style> ELEMENTS, "
            "not the style= ATTRIBUTE React/MUI actually use"
        )
