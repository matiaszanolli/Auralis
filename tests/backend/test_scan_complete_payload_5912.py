"""One scan_complete payload for the manual and auto scan paths (#5912).

The manual route reported ``files_processed or files_found`` while the
auto-scanner reported ``files_processed``, so a scan whose files all failed
said N on one path and 0 on the other.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.scan_models import ScanResult  # noqa: E402
from routers.library_scan_events import broadcast_scan_complete  # noqa: E402
from services.scan_events import scan_complete_payload  # noqa: E402


def _all_failed() -> ScanResult:
    result = ScanResult(files_found=5, files_processed=0, scan_time=1.5, directories_scanned=1)
    for i in range(5):
        result.record_failure(f"/music/{i}.mp3", "boom")
    return result


def test_a_scan_where_nothing_was_processed_reports_zero():
    payload = scan_complete_payload(_all_failed())

    assert payload["files_processed"] == 0
    assert payload["files_failed"] == 5
    assert [f["filename"] for f in payload["failures"]] == [f"{i}.mp3" for i in range(5)]


def test_manual_broadcast_sends_the_same_payload_the_auto_scanner_builds():
    result = _all_failed()
    manager = MagicMock()
    manager.broadcast = AsyncMock()

    asyncio.run(broadcast_scan_complete(manager, result, removed=0))

    frame = manager.broadcast.await_args_list[0].args[0]
    assert frame == {"type": "scan_complete", "data": scan_complete_payload(result)}


def test_no_result_degrades_to_an_empty_payload():
    payload = scan_complete_payload(None)

    assert payload["files_processed"] == 0
    assert payload["failures"] == []
