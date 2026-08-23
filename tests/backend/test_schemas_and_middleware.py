"""
Tests for Backend Schemas and Middleware
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for Phase B.1 endpoint standardization.

Test Coverage:
- Schemas: Request/response validation and serialization
- Middleware: Validation, error handling, rate limiting, logging
- Helpers: Pagination, batch operations, filtering

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from schemas import (
    LibraryScanRequest,
    WebSocketErrorResponse,
    WebSocketMessageBase,
    WebSocketMessageType,
)

# schemas.PaginationParams (capped limit at 500) was deleted (#4761): it had
# zero production importers and disagreed with the class actually wired into
# routers, routers.pagination.PaginationParams (capped at 200) — see
# tests/backend/test_pagination.py for that one's coverage.

# ============================================================================
# Helper Function Tests
# ============================================================================









# ============================================================================
# Integration Tests
# ============================================================================



# ============================================================================
# LibraryScanRequest path-validation tests (#3920)
# ============================================================================

class TestLibraryScanRequest:
    """Direct construction tests for the `directories` field_validator, which
    wraps `security.path_security.validate_user_chosen_directory`. The
    underlying security function is tested directly in
    tests/security/test_scan_path_validation.py; these tests exercise the
    Pydantic-validator wrapper itself, so a regression that drops the
    `@field_validator` decorator (or returns the unvalidated input) fails
    here even if the security function is untouched.
    """

    def test_valid_existing_directory_is_accepted(self, tmp_path):
        request = LibraryScanRequest(directories=[str(tmp_path)])
        # validate_user_chosen_directory resolves to an absolute path.
        assert request.directories == [str(tmp_path.resolve())]

    def test_path_traversal_is_rejected(self):
        with pytest.raises(ValidationError, match="directory path"):
            LibraryScanRequest(directories=["../../etc"])

    def test_nonexistent_directory_is_rejected(self):
        with pytest.raises(ValidationError, match="directory path"):
            LibraryScanRequest(directories=["/definitely_does_not_exist_xyz_123"])

    def test_empty_directory_list_is_accepted(self):
        """An empty list has nothing to validate and is not itself invalid —
        the caller (routers/library.py) is responsible for deciding whether
        zero directories is a meaningful scan request."""
        request = LibraryScanRequest(directories=[])
        assert request.directories == []

    def test_one_invalid_path_among_valid_ones_rejects_the_whole_request(self, tmp_path):
        """The validator raises on the first bad path — a mixed batch must
        not silently drop the invalid entry and proceed with the rest."""
        with pytest.raises(ValidationError):
            LibraryScanRequest(directories=[str(tmp_path), "../../etc"])

    def test_defaults(self, tmp_path):
        request = LibraryScanRequest(directories=[str(tmp_path)])
        assert request.recursive is True
        assert request.skip_existing is True


# ============================================================================
# WebSocket schema construction tests (#3920 sibling)
# ============================================================================

class TestWebSocketMessageBase:
    """Direct construction tests — no test previously constructed this model."""

    def test_valid_message_type_is_accepted(self):
        message = WebSocketMessageBase(type=WebSocketMessageType.PING, data=None)
        assert message.type == WebSocketMessageType.PING
        assert message.data is None

    def test_unknown_message_type_is_rejected(self):
        with pytest.raises(ValidationError):
            WebSocketMessageBase(type="not_a_real_type", data=None)

    def test_extra_protocol_envelope_fields_are_preserved(self):
        """extra='allow' must keep correlation_id etc. so request-response
        correlation doesn't time out (fixes #2281)."""
        message = WebSocketMessageBase(
            type=WebSocketMessageType.PING,
            data={"foo": "bar"},
            correlation_id="abc-123",
        )
        assert message.model_dump()["correlation_id"] == "abc-123"


class TestWebSocketErrorResponse:
    """Direct construction tests — no test previously constructed this model."""

    def test_required_fields_and_defaults(self):
        response = WebSocketErrorResponse(error="validation_error", message="Invalid message format")
        assert response.type == "error"
        assert response.error == "validation_error"
        assert response.message == "Invalid message format"
        assert response.timestamp is not None

    def test_missing_required_field_is_rejected(self):
        with pytest.raises(ValidationError):
            WebSocketErrorResponse(message="missing the 'error' field")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
