"""
Unmatched /api paths resolve in the API, not the SPA mount (#5090).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Starlette returns 405 for a method mismatch only when NO route fully matches the
request. `main.py` mounts the built frontend with `app.mount("/", StaticFiles(...))`
in production, and a Mount at "/" fully matches *every* path — so it beat the
partial (path-matched, method-mismatched) match on every real API route.
`GET /api/files/upload` reached StaticFiles, found no such file, and returned 404
instead of the 405 the route shape implies.

The sharp edge was that `auralis-web/frontend/dist/` is gitignored and
`backend-tests.yml` never builds it, so the mount exists only on a developer
machine that has run a frontend build. The same test therefore passed in CI
(no mount → 405) and failed locally (mount → 404) — #5090 was filed believing the
gate was red, when it was green in CI and red only locally.

These tests pin the behaviour so it can no longer depend on whether an untracked
build artifact happens to be present.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest


class TestMethodMismatchReturns405:
    """A path that exists under another method is 405, never 404."""

    @pytest.mark.parametrize(
        "path,expected_method",
        [
            ("/api/files/upload", "POST"),
            ("/api/library/scan", "POST"),
        ],
    )
    def test_get_on_post_only_route_is_405(self, client, path, expected_method):
        response = client.get(path)
        assert response.status_code == 405, (
            f"GET {path} returned {response.status_code}; a path registered under "
            f"{expected_method} must report a method mismatch, not fall through to "
            f"the SPA mount"
        )

    @pytest.mark.parametrize(
        "path,expected_method",
        [
            ("/api/files/upload", "POST"),
            ("/api/library/scan", "POST"),
        ],
    )
    def test_405_advertises_the_allowed_method(self, client, path, expected_method):
        """RFC 9110 requires Allow on a 405."""
        response = client.get(path)
        assert "allow" in {k.lower() for k in response.headers}
        assert expected_method in response.headers["allow"]

    def test_405_body_is_json_not_static_file_output(self, client):
        """The response must come from the API, not StaticFiles."""
        response = client.get("/api/files/upload")
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == {"detail": "Method Not Allowed"}


class TestUnknownApiPathReturns404:
    def test_unknown_api_path_is_404_json(self, client):
        response = client.get("/api/definitely/not/a/real/route")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == {"detail": "Not Found"}

    def test_unknown_api_path_has_no_allow_header(self, client):
        """No route matches at all — this is a genuine 404, not a mismatch."""
        response = client.get("/api/definitely/not/a/real/route")
        assert "allow" not in {k.lower() for k in response.headers}


class TestRealRoutesStillResolve:
    """The catch-all must not shadow anything — it is registered last."""

    def test_existing_get_route_is_untouched(self, client):
        response = client.get("/api/audio/formats")
        assert response.status_code == 200, (
            "the /api catch-all shadowed a real GET route — it must be "
            "registered after every router"
        )

    def test_catch_all_does_not_claim_every_method(self, client):
        """A GET-only route must not report POST as allowed."""
        response = client.get("/api/audio/formats")
        assert response.status_code == 200
        assert "allow" not in {k.lower() for k in response.headers}
