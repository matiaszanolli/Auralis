"""GET /api/library/scan/status reports the server's scan bound (#6576).

The frontend hard-coded its scan request bound to the backend's DEFAULT AURALIS_SCAN_TIMEOUT, so a
raised setting was cut at 61 minutes as a client disconnect. The status payload now carries
scan_timeout_s, from which the client derives a bound that always exceeds the server's.
"""
import asyncio
from types import SimpleNamespace

import routers.library_scan as library_scan
from config.limits import SCAN_TIMEOUT_S
from routers.library_scan import ScanStatusResponse, get_scan_status


def _status(**overrides):
    db = SimpleNamespace(is_scanning=lambda: False)
    return asyncio.run(get_scan_status(library_database=db))


def test_status_reports_the_configured_scan_bound():
    payload = _status()

    assert payload == {"is_scanning": False, "scan_timeout_s": SCAN_TIMEOUT_S}
    assert ScanStatusResponse(**payload).scan_timeout_s == SCAN_TIMEOUT_S


def test_a_raised_bound_is_what_the_client_is_told(monkeypatch):
    monkeypatch.setattr(library_scan, "SCAN_TIMEOUT_S", 7200)

    assert _status()["scan_timeout_s"] == 7200


def test_the_bound_is_part_of_the_documented_response_model():
    assert ScanStatusResponse.model_fields["scan_timeout_s"].is_required()
