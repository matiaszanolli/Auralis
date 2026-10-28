"""A refused Host header or CORS preflight leaves an application log line (#6186).

Stock TrustedHostMiddleware and CORSMiddleware answered with a bare 400 and
logged nothing, so a DNS-rebinding probe was blocked without a trace.
"""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.middleware.logged_rejections import LoggingCORSMiddleware, LoggingTrustedHostMiddleware

LOGGER = "config.middleware.logged_rejections"


@pytest.fixture
def client():
    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    app.add_middleware(LoggingTrustedHostMiddleware, allowed_hosts=["testserver"])
    app.add_middleware(
        LoggingCORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET"],
    )
    return TestClient(app)


def test_untrusted_host_is_refused_and_logged(client, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        resp = client.get("/ping", headers={"host": "attacker.example"})

    assert resp.status_code == 400
    assert any("attacker.example" in r.getMessage() for r in caplog.records)


def test_trusted_host_passes_without_a_log(client, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        resp = client.get("/ping")

    assert resp.status_code == 200
    assert caplog.records == []


def test_foreign_origin_preflight_is_refused_and_logged(client, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        resp = client.options("/ping", headers={
            "origin": "http://evil.example", "access-control-request-method": "GET",
        })

    assert resp.status_code == 400
    assert any("evil.example" in r.getMessage() for r in caplog.records)


def test_allowed_preflight_is_not_logged(client, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        resp = client.options("/ping", headers={
            "origin": "http://localhost:3000", "access-control-request-method": "GET",
        })

    assert resp.status_code == 200
    assert caplog.records == []
