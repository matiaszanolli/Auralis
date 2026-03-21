# -*- coding: utf-8 -*-

"""
Concurrency test for FingerprintExtractor._is_rust_server_available() TOCTOU fix

Verifies that the socket probe runs exactly once when 16 threads call
_is_rust_server_available() concurrently (issue #2914).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import socket
import threading
from unittest.mock import Mock, patch

import pytest

from auralis.services.fingerprint_extractor import FingerprintExtractor


@pytest.fixture
def extractor():
    """Create a FingerprintExtractor with mocked dependencies"""
    repo = Mock()
    return FingerprintExtractor(
        fingerprint_repository=repo,
        use_sidecar_files=False,
        use_rust_server=True,
    )


def _make_mock_socket(connect_result: int = 0) -> Mock:
    """Create a mock socket constructor that returns a mock with given connect_ex result."""
    mock_sock = Mock()
    mock_sock.connect_ex.return_value = connect_result
    mock_constructor = Mock(return_value=mock_sock)
    return mock_constructor


def test_concurrent_availability_check_probes_once(extractor):
    """16 threads call _is_rust_server_available(); socket probe runs exactly once."""
    num_threads = 16
    barrier = threading.Barrier(num_threads)
    results: list[bool] = [False] * num_threads

    mock_constructor = _make_mock_socket(connect_result=0)

    with patch.object(socket, "socket", mock_constructor):
        def worker(idx: int) -> None:
            barrier.wait()  # All threads start at the same time
            results[idx] = extractor._is_rust_server_available()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    # All threads should see True
    assert all(results), f"Expected all True, got {results}"

    # Socket probe should have been called exactly once
    assert mock_constructor.call_count == 1, (
        f"Socket probe called {mock_constructor.call_count} times, expected 1"
    )


def test_single_thread_availability_check(extractor):
    """Single-threaded check still works correctly (no regression)."""
    mock_constructor = _make_mock_socket(connect_result=0)

    with patch.object(socket, "socket", mock_constructor):
        result = extractor._is_rust_server_available()
        assert result is True

        # Second call should use cached value
        result2 = extractor._is_rust_server_available()
        assert result2 is True

    assert mock_constructor.call_count == 1


def test_server_unavailable_cached(extractor):
    """Unavailable result is also cached (probe runs once)."""
    mock_constructor = _make_mock_socket(connect_result=1)

    with patch.object(socket, "socket", mock_constructor):
        assert extractor._is_rust_server_available() is False
        assert extractor._is_rust_server_available() is False

    assert mock_constructor.call_count == 1
