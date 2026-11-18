"""An integration test that boots main.app must not touch the developer's real ~/.auralis (#6441).

``test_api_integration.py`` ran the real lifespan against ``DEFAULT_DB_PATH`` and sent
state-changing requests; the isolation fixtures only existed in ``tests/backend/conftest.py``.
"""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

import auralis.library.constants as constants
import auralis.library.database_engine as database_engine
from auralis.analysis.fingerprint import fingerprint_storage


def _real_library_db() -> Path:
    return Path.home() / ".auralis" / "library.db"


def test_default_db_path_is_a_throwaway_without_the_test_asking_for_it():
    """Autouse wiring (tests/integration/conftest.py): no fixture is requested here."""
    real = _real_library_db()
    assert constants.DEFAULT_DB_PATH != real
    assert database_engine.DEFAULT_DB_PATH == constants.DEFAULT_DB_PATH
    assert real.parent not in constants.DEFAULT_DB_PATH.parents


def test_fingerprint_store_is_a_throwaway():
    assert not str(fingerprint_storage.fingerprints_dir()).startswith(str(Path.home() / ".auralis"))


def test_booting_the_lifespan_opens_the_throwaway_and_leaves_the_real_db_alone(_isolated_library_db):
    from main import app

    real = _real_library_db()
    before = real.stat().st_mtime_ns if real.exists() else None

    with TestClient(app, headers={"origin": "http://localhost:8765"}) as client:
        assert client.get("/api/health").status_code == 200

    assert _isolated_library_db.exists(), "the lifespan did not open the isolated database"
    after = real.stat().st_mtime_ns if real.exists() else None
    assert after == before, "booting the app modified the developer's real library.db"
