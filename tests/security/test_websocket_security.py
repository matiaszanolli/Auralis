"""
WebSocket Security Tests
~~~~~~~~~~~~~~~~~~~~~~~~

Security tests for WebSocket message validation and rate limiting.

Fixes #2156: Unvalidated WebSocket message content and size

SECURITY CONTROLS TESTED:
- Message size limits (64KB max)
- JSON parsing safety (malformed/deeply nested)
- Schema validation (unknown message types)
- Rate limiting (10 msg/sec per connection)
- DoS prevention (memory exhaustion, CPU exhaustion)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from websocket.websocket_security import (
    MAX_MESSAGE_SIZE,
    MAX_MESSAGES_PER_SECOND,
    WebSocketRateLimiter,
    send_error_response,
    validate_and_parse_message,
)


@pytest.mark.security
class TestWebSocketMessageSizeValidation:
    """Test message size limits to prevent memory exhaustion."""

    @pytest.mark.asyncio
    async def test_reject_oversized_message(self):
        """
        SECURITY: Messages exceeding 64KB should be rejected.
        Attack vector: Memory exhaustion via large messages.
        """
        # Create oversized message (65KB)
        large_data = "x" * (MAX_MESSAGE_SIZE + 1024)
        message_json = json.dumps({
            "type": "ping",
            "data": large_data
        })

        # Mock WebSocket
        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        # Validate message
        result, error = await validate_and_parse_message(message_json, mock_ws)

        # Should be rejected
        assert result is None
        assert error is not None
        assert "exceeds maximum" in error.lower()

        # Should send error response to client
        mock_ws.send_text.assert_called_once()
        error_response = json.loads(mock_ws.send_text.call_args[0][0])
        assert error_response["error"] == "message_too_large"

    @pytest.mark.asyncio
    async def test_accept_normal_sized_message(self):
        """Valid messages under 64KB should be accepted."""
        message_json = json.dumps({
            "type": "ping",
            "data": None
        })

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        result, error = await validate_and_parse_message(message_json, mock_ws)

        # Should be accepted
        assert result is not None
        assert error is None
        assert result["type"] == "ping"

    @pytest.mark.asyncio
    async def test_boundary_message_size(self):
        """Messages exactly at 64KB limit should be accepted."""
        # Create message at exactly 64KB - overhead for JSON structure
        overhead = len('{"type":"ping","data":""}')
        data_size = MAX_MESSAGE_SIZE - overhead - 100  # Leave buffer for encoding
        large_data = "x" * data_size

        message_json = json.dumps({
            "type": "ping",
            "data": large_data
        })

        mock_ws = AsyncMock()

        result, error = await validate_and_parse_message(message_json, mock_ws)

        # Should be accepted (just under limit)
        assert result is not None
        assert error is None


@pytest.mark.security
class TestWebSocketJSONParsing:
    """Test JSON parsing safety."""

    @pytest.mark.asyncio
    async def test_reject_invalid_json(self):
        """
        SECURITY: Malformed JSON should be rejected.
        Attack vector: Parser exploitation.
        """
        invalid_json = '{"type": "ping", invalid}'

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        result, error = await validate_and_parse_message(invalid_json, mock_ws)

        # Should be rejected
        assert result is None
        assert error is not None
        assert "invalid json" in error.lower()

        # Should send error response
        mock_ws.send_text.assert_called_once()
        error_response = json.loads(mock_ws.send_text.call_args[0][0])
        assert error_response["error"] == "invalid_json"

    @pytest.mark.asyncio
    async def test_reject_deeply_nested_json(self):
        """
        SECURITY: Deeply nested JSON should be size-limited.
        Attack vector: CPU exhaustion via deep recursion.
        """
        # Create deeply nested structure
        nested = {"type": "ping", "data": {}}
        current = nested["data"]
        for _ in range(1000):
            current["nested"] = {}
            current = current["nested"]

        message_json = json.dumps(nested)

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        result, error = await validate_and_parse_message(message_json, mock_ws)

        # If message is under size limit, it will be parsed but schema validation
        # should catch unknown structure
        # If over size limit, it should be rejected for size
        assert result is None or error is not None


@pytest.mark.security
class TestWebSocketSchemaValidation:
    """Test message schema validation."""

    @pytest.mark.asyncio
    async def test_reject_unknown_message_type(self):
        """
        SECURITY: Unknown message types should be rejected.
        Attack vector: Bypass security checks via unknown types.
        """
        message_json = json.dumps({
            "type": "malicious_command",
            "data": {"execute": "rm -rf /"}
        })

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        result, error = await validate_and_parse_message(message_json, mock_ws)

        # Should be rejected
        assert result is None
        assert error is not None
        assert "validation" in error.lower()

        # Should send error response
        mock_ws.send_text.assert_called_once()
        error_response = json.loads(mock_ws.send_text.call_args[0][0])
        assert error_response["error"] == "validation_error"

    @pytest.mark.asyncio
    async def test_accept_valid_message_types(self):
        """Valid message types should be accepted."""
        valid_types = [
            "ping",
            "processing_settings_update",
            "play_enhanced",
            "play_normal",
            "pause",
            "stop",
            "seek"
        ]

        for msg_type in valid_types:
            message_json = json.dumps({
                "type": msg_type,
                "data": {}
            })

            mock_ws = AsyncMock()
            result, error = await validate_and_parse_message(message_json, mock_ws)

            # Should be accepted
            assert result is not None, f"Valid type '{msg_type}' was rejected"
            assert error is None
            assert result["type"] == msg_type

    @pytest.mark.asyncio
    async def test_reject_missing_type_field(self):
        """Messages without 'type' field should be rejected."""
        message_json = json.dumps({
            "data": {"some": "data"}
        })

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        result, error = await validate_and_parse_message(message_json, mock_ws)

        # Should be rejected
        assert result is None
        assert error is not None


@pytest.mark.security
class TestWebSocketRateLimiting:
    """Test rate limiting to prevent DoS attacks."""

    def test_allow_normal_message_rate(self):
        """
        Normal message rates should be allowed.
        Test: 5 messages per second (within limit).
        """
        limiter = WebSocketRateLimiter(max_messages_per_second=10)
        mock_ws = Mock()

        # Send 5 messages (within limit)
        for _ in range(5):
            allowed, error = limiter.check_rate_limit(mock_ws)
            assert allowed is True
            assert error is None

    def test_block_excessive_message_rate(self):
        """
        SECURITY: Excessive message rates should be blocked.
        Attack vector: DoS via message flooding.
        Test: 11 messages in 1 second (exceeds 10 msg/sec limit).
        """
        limiter = WebSocketRateLimiter(max_messages_per_second=10)
        mock_ws = Mock()

        # Send 10 messages (at limit)
        for _ in range(10):
            allowed, error = limiter.check_rate_limit(mock_ws)
            assert allowed is True

        # 11th message should be blocked
        allowed, error = limiter.check_rate_limit(mock_ws)
        assert allowed is False
        assert error is not None
        assert "rate limit exceeded" in error.lower()

    def test_rate_limit_per_connection(self):
        """Rate limits should be per-connection, not global."""
        limiter = WebSocketRateLimiter(max_messages_per_second=10)
        mock_ws1 = Mock()
        mock_ws2 = Mock()

        # Fill limit for connection 1
        for _ in range(10):
            allowed, _ = limiter.check_rate_limit(mock_ws1)
            assert allowed is True

        # Connection 2 should still be allowed
        allowed, error = limiter.check_rate_limit(mock_ws2)
        assert allowed is True
        assert error is None

    def test_rate_limit_cleanup(self):
        """Rate limiter should clean up disconnected connections."""
        limiter = WebSocketRateLimiter(max_messages_per_second=10)
        mock_ws = Mock()

        # Send some messages
        for _ in range(5):
            limiter.check_rate_limit(mock_ws)

        # Connection should be tracked
        assert id(mock_ws) in limiter.message_log

        # Clean up
        limiter.cleanup(mock_ws)

        # Should be removed
        assert id(mock_ws) not in limiter.message_log

    def test_rate_limit_window_sliding(self):
        """Rate limit window should slide over time."""
        import time

        limiter = WebSocketRateLimiter(
            max_messages_per_second=5,
            window_seconds=0.5  # 500ms window
        )
        mock_ws = Mock()

        # Fill the limit
        for _ in range(5):
            allowed, _ = limiter.check_rate_limit(mock_ws)
            assert allowed is True

        # Should be blocked immediately
        allowed, _ = limiter.check_rate_limit(mock_ws)
        assert allowed is False

        # Wait for window to slide
        time.sleep(0.6)

        # Should be allowed again
        allowed, error = limiter.check_rate_limit(mock_ws)
        assert allowed is True
        assert error is None


@pytest.mark.security
class TestWebSocketDoSPrevention:
    """Test DoS prevention mechanisms."""

    @pytest.mark.asyncio
    async def test_prevent_memory_exhaustion_via_large_array(self):
        """
        SECURITY: Large arrays in messages should be size-limited.
        Attack vector: Memory exhaustion via large arrays.
        """
        # Create message with large array
        large_array = [{"item": i} for i in range(10000)]
        message_json = json.dumps({
            "type": "ping",
            "data": large_array
        })

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        result, error = await validate_and_parse_message(message_json, mock_ws)

        # Should be rejected due to size
        if len(message_json.encode('utf-8')) > MAX_MESSAGE_SIZE:
            assert result is None
            assert error is not None

    @pytest.mark.asyncio
    async def test_prevent_cpu_exhaustion_via_complex_structure(self):
        """
        SECURITY: Complex data structures should be size-limited.
        Attack vector: CPU exhaustion via complex parsing.
        """
        # Create complex nested structure
        complex_data = {}
        for i in range(1000):
            complex_data[f"key_{i}"] = {
                "nested": {
                    "data": [1, 2, 3, 4, 5] * 10
                }
            }

        message_json = json.dumps({
            "type": "ping",
            "data": complex_data
        })

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        result, error = await validate_and_parse_message(message_json, mock_ws)

        # Should be rejected if over size limit
        if len(message_json.encode('utf-8')) > MAX_MESSAGE_SIZE:
            assert result is None
            assert error is not None


@pytest.mark.security
class TestWebSocketErrorResponses:
    """Test error response handling."""

    @pytest.mark.asyncio
    async def test_send_error_response_format(self):
        """Error responses should follow standardized format."""
        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await send_error_response(
            mock_ws,
            "test_error",
            "Test error message"
        )

        # Should send error response
        mock_ws.send_text.assert_called_once()
        error_json = mock_ws.send_text.call_args[0][0]
        error_response = json.loads(error_json)

        # Check format
        assert error_response["type"] == "error"
        assert error_response["error"] == "test_error"
        assert error_response["message"] == "Test error message"
        assert "timestamp" in error_response

    @pytest.mark.asyncio
    async def test_error_response_handles_send_failure(self):
        """Error response should handle WebSocket send failures gracefully."""
        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock(side_effect=Exception("Connection closed"))

        # Should not raise exception
        try:
            await send_error_response(mock_ws, "test_error", "Test message")
        except Exception:
            pytest.fail("send_error_response should not raise exceptions")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "security"])
