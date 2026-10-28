"""The 'frontend assets not found' page links nowhere that 404s (#5070).

It is registered only when the backend is not in dev mode, which is exactly when
create_app() disables /api/docs, so its "View API Documentation" link was a
guaranteed 404 for everyone who saw the page.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.fallback_routes import FRONTEND_MISSING_HTML  # noqa: E402


def test_the_page_does_not_link_to_the_disabled_api_docs():
    assert "/api/docs" not in FRONTEND_MISSING_HTML
    assert "/api/redoc" not in FRONTEND_MISSING_HTML


def test_the_page_still_tells_the_user_what_to_do():
    assert "Frontend assets not found" in FRONTEND_MISSING_HTML
    assert "--dev" in FRONTEND_MISSING_HTML
