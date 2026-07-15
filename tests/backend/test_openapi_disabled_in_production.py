"""
Regression: the OpenAPI schema must be disabled in production (#4375)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

create_app() disabled Swagger/ReDoc in production (#2418) but left openapi_url
at its default /openapi.json, which FastAPI still served — so the complete API
schema was reachable in production despite the stated hardening goal. The fix
also gates openapi_url on dev mode.
"""

import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.app import create_app


class TestOpenApiExposure:
    def test_openapi_json_is_404_in_production(self):
        with patch("config.app.is_dev_mode", return_value=False):
            app = create_app()
        client = TestClient(app)
        # Default location and the dev-only aliased location must both 404.
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/api/openapi.json").status_code == 404
        assert client.get("/api/docs").status_code == 404
        assert client.get("/api/redoc").status_code == 404

    def test_openapi_schema_available_in_dev(self):
        with patch("config.app.is_dev_mode", return_value=True):
            app = create_app()
        client = TestClient(app)
        resp = client.get("/api/openapi.json")
        assert resp.status_code == 200
        assert resp.json().get("openapi")  # a valid OpenAPI document
