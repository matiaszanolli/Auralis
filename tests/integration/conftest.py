"""Integration-test configuration: nothing here may touch the developer's real ~/.auralis (#6441)."""
import pytest


@pytest.fixture(autouse=True)
def _use_isolated_app_state(_isolated_library_db, _isolated_fingerprint_store):
    """test_api_integration boots the real lifespan (a library DB, background workers, the
    fingerprint store) and POSTs settings changes and Clear Cache. Any future test here that does the
    same gets a throwaway DB and .25d store without having to remember to ask (definitions in
    tests/app_isolation.py)."""
