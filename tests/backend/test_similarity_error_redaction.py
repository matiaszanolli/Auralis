"""
Regression test for #3331 — similarity.py must not leak internal exception
messages through HTTP 500 detail or response-body error fields.

Before: ten endpoints did `raise HTTPException(status_code=500,
detail=f"Error ...: {str(e)}")` and one returned `{"error": str(e)}`. The
exception text could include file paths, SQL fragments, dependency
versions, or other server internals.

After: a single `_internal_error_response(message, exc)` helper redacts the
exception, logs the full traceback server-side with a correlation id, and
returns a generic message + correlation id to the caller.
"""

from __future__ import annotations

import logging
import sys
import re
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


# tests/backend/conftest.py adds auralis-web/backend to sys.path at runtime;
# do the same locally so we can import the router module by file path.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'))

from routers.similarity import _internal_error_response  # noqa: E402


# A "sensitive" message that would leak through `str(e)` pre-fix.
SECRET_PATH = "/home/user/secret_library/library.db"
SECRET_QUERY = "SELECT * FROM tracks WHERE filepath='/etc/passwd'"


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------

def test_helper_returns_http_500():
    exc = RuntimeError(SECRET_PATH)
    http_err = _internal_error_response("Public message", exc)
    assert isinstance(http_err, HTTPException)
    assert http_err.status_code == 500


def test_helper_does_not_leak_exception_text():
    """The user-facing detail must not contain any part of the exception text."""
    exc = RuntimeError(SECRET_PATH)
    http_err = _internal_error_response("Operation failed", exc)
    assert SECRET_PATH not in str(http_err.detail), (
        f"Sensitive path leaked into detail: {http_err.detail!r}"
    )


def test_helper_includes_user_message():
    exc = RuntimeError("internal")
    http_err = _internal_error_response("Operation failed", exc)
    assert "Operation failed" in str(http_err.detail)


def test_helper_appends_correlation_id():
    """Detail must include a `(ref XXXXXXXX)` correlation id for log matching."""
    http_err = _internal_error_response("Op failed", RuntimeError("boom"))
    assert re.search(r"\(ref [0-9a-f]{8}\)", str(http_err.detail)), (
        f"Missing correlation id in detail: {http_err.detail!r}"
    )


def test_helper_correlation_ids_differ_per_call():
    """Each invocation generates a fresh id so log entries are uniquely traceable."""
    err1 = _internal_error_response("Op", RuntimeError("x"))
    err2 = _internal_error_response("Op", RuntimeError("x"))
    id1 = re.search(r"ref ([0-9a-f]{8})", str(err1.detail)).group(1)  # type: ignore[union-attr]
    id2 = re.search(r"ref ([0-9a-f]{8})", str(err2.detail)).group(1)  # type: ignore[union-attr]
    assert id1 != id2


def test_helper_logs_full_exception_server_side(caplog):
    """The full exception (with type + message) must reach the log so
    operators can debug while the API caller only sees a generic ref."""
    with caplog.at_level(logging.ERROR, logger='routers.similarity'):
        _internal_error_response("Op failed", RuntimeError(SECRET_QUERY))
    full_log = "\n".join(r.message + (r.exc_text or "") for r in caplog.records)
    # The secret text appears in the SERVER LOG (where operators can debug)
    assert SECRET_QUERY in full_log


# ---------------------------------------------------------------------------
# End-to-end HTTP test
# ---------------------------------------------------------------------------

def _build_app_with_leaking_endpoint() -> FastAPI:
    """Minimal app that simulates an endpoint catching an unhandled exception
    and routing it through the helper. Mirrors what similarity.py does."""
    app = FastAPI()

    @app.get("/boom")
    async def boom():
        try:
            raise RuntimeError(f"Database error at {SECRET_PATH}: {SECRET_QUERY}")
        except Exception as e:
            raise _internal_error_response("Error reading library", e) from e

    return app


def test_http_response_body_excludes_sensitive_exception_text():
    """End-to-end: an unhandled exception in an endpoint must not surface
    in the HTTP response body."""
    client = TestClient(_build_app_with_leaking_endpoint(), raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 500
    body_text = response.text
    assert SECRET_PATH not in body_text, f"Path leaked into HTTP body: {body_text!r}"
    assert SECRET_QUERY not in body_text, f"Query leaked into HTTP body: {body_text!r}"
    # And the generic message + ref should be present
    assert "Error reading library" in body_text
    assert re.search(r"\(ref [0-9a-f]{8}\)", body_text)


# ---------------------------------------------------------------------------
# Static check that the original leak pattern isn't reintroduced
# ---------------------------------------------------------------------------

def test_no_str_e_leak_in_similarity_router():
    """Source-code check: the file must not regress to the old pattern."""
    path = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend' / 'routers' / 'similarity.py'
    src = path.read_text(encoding='utf-8')
    # Forbid: any `str(e)` in HTTPException detail OR response body
    assert 'str(e)' not in src, (
        f"similarity.py contains `str(e)` — possible exception-text leak (#3331)"
    )
