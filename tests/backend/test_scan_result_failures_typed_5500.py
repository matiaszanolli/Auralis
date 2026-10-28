"""ScanResultResponse.failures / directory_errors are typed {filename, reason} entries (#5500).

list[dict[str, str]] let OpenAPI describe only an open string-keyed map, so the generated
client could not see the fields the paired scan_complete broadcast declares.
"""

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from schemas.library import ScanResultResponse  # noqa: E402


def _schema_props(name):
    schema = ScanResultResponse.model_json_schema()
    return schema["$defs"][name]["properties"]


def test_failures_have_a_named_item_schema_with_both_fields():
    props = _schema_props("ScanFailure")

    assert set(props) == {"filename", "reason"}
    assert props["filename"]["type"] == "string"


def test_failure_dicts_from_the_scanner_are_coerced():
    response = ScanResultResponse(
        files_found=1, files_added=0, files_updated=0, files_skipped=0, files_failed=1,
        duration=0.1, directories_scanned=1,
        failures=[{"filename": "a.flac", "reason": "undecodable"}],
        directory_errors=[{"filename": "private", "reason": "permission denied"}],
    )

    assert response.model_dump()["failures"] == [{"filename": "a.flac", "reason": "undecodable"}]
    assert response.directory_errors[0].reason == "permission denied"
