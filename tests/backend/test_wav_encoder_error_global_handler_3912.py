"""
Regression: WAVEncoderError has a registered global exception handler (#3912)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both encoder modules used to define their own `*Error(Exception)` subclasses
but config/app.py only had handlers for HTTPException, RequestValidationError,
and the generic Exception. Every current WAVEncoderError call site already
catches and translates it explicitly, so this is a safety net for a future
REST caller that forgets to — it must get a category message ("Audio encoding
failed"), not the generic catch-all's "Internal server error" with no class
context.

WebMEncoderError (the issue's other named type) no longer exists in this
codebase (its module was removed by #5147) — only WAVEncoderError is mapped.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.app import create_app
from core.encoding import WAVEncoderError


def _app_with_wav_encoder_error_route():
    with patch("config.app.is_dev_mode", return_value=False):
        app = create_app()

    @app.get("/api/test/wav-encoder-boom")
    async def boom():
        raise WAVEncoderError("disk full while writing chunk")

    return app


def test_unmapped_wav_encoder_error_gets_a_category_message_not_generic_500():
    app = _app_with_wav_encoder_error_route()
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.get("/api/test/wav-encoder-boom")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Audio encoding failed"}


def test_wav_encoder_error_message_never_leaks_into_the_response():
    """The raw exception message (which could carry filesystem detail) must
    not appear in the client-visible body — only the category message."""
    app = _app_with_wav_encoder_error_route()
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.get("/api/test/wav-encoder-boom")

    assert "disk full" not in resp.text


def test_web_m_encoder_error_class_no_longer_exists():
    """Sibling documentation check: the issue's other named type
    (WebMEncoderError) was removed from the codebase entirely (#5147) — this
    guards against silently reintroducing an unmapped one under the same
    name."""
    with pytest.raises(ImportError):
        from core.encoding import WebMEncoderError  # noqa: F401
