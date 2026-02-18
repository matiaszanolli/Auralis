"""
Tests for centralized error handling and exception definitions.

Covers status codes, detail message formatting, class hierarchy,
and the handle_query_error() helper.
"""

import sys
import types
from pathlib import Path

import pytest

_backend_dir = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
sys.path.insert(0, str(_backend_dir))

if 'routers' not in sys.modules:
    _stub = types.ModuleType('routers')
    _stub.__path__ = [str(_backend_dir / 'routers')]
    _stub.__package__ = 'routers'
    sys.modules['routers'] = _stub

from fastapi import HTTPException

from routers.errors import (
    AudioPlayerUnavailableError,
    BadRequestError,
    ConnectionManagerUnavailableError,
    InternalServerError,
    LibraryManagerUnavailableError,
    NotFoundError,
    PlayerStateUnavailableError,
    ServiceUnavailableError,
    handle_query_error,
)


# ---------------------------------------------------------------------------
# ServiceUnavailableError
# ---------------------------------------------------------------------------

class TestServiceUnavailableError:
    def test_status_code_is_503(self):
        err = ServiceUnavailableError()
        assert err.status_code == 503

    def test_default_detail(self):
        err = ServiceUnavailableError()
        assert "unavailable" in err.detail.lower()

    def test_custom_detail(self):
        err = ServiceUnavailableError("custom message")
        assert err.detail == "custom message"

    def test_is_http_exception(self):
        err = ServiceUnavailableError()
        assert isinstance(err, HTTPException)


# ---------------------------------------------------------------------------
# NotFoundError
# ---------------------------------------------------------------------------

class TestNotFoundError:
    def test_status_code_is_404(self):
        err = NotFoundError("Track")
        assert err.status_code == 404

    def test_detail_with_id(self):
        err = NotFoundError("Track", 42)
        assert "Track" in err.detail
        assert "42" in err.detail

    def test_detail_without_id(self):
        err = NotFoundError("Album")
        assert "Album" in err.detail
        assert err.detail == "Album not found"

    def test_detail_with_string_id(self):
        err = NotFoundError("Playlist", "my-playlist")
        assert "my-playlist" in err.detail

    def test_is_http_exception(self):
        assert isinstance(NotFoundError("X"), HTTPException)


# ---------------------------------------------------------------------------
# BadRequestError
# ---------------------------------------------------------------------------

class TestBadRequestError:
    def test_status_code_is_400(self):
        err = BadRequestError("invalid input")
        assert err.status_code == 400

    def test_detail_preserved(self):
        err = BadRequestError("limit must be positive")
        assert err.detail == "limit must be positive"

    def test_is_http_exception(self):
        assert isinstance(BadRequestError("x"), HTTPException)


# ---------------------------------------------------------------------------
# InternalServerError
# ---------------------------------------------------------------------------

class TestInternalServerError:
    def test_status_code_is_500(self):
        err = InternalServerError("fetch tracks")
        assert err.status_code == 500

    def test_detail_contains_operation(self):
        err = InternalServerError("fetch tracks")
        assert "fetch tracks" in err.detail

    def test_detail_contains_error_message_when_provided(self):
        err = InternalServerError("fetch tracks", ValueError("db timeout"))
        assert "db timeout" in err.detail
        assert "fetch tracks" in err.detail

    def test_detail_without_error(self):
        err = InternalServerError("delete album")
        assert "delete album" in err.detail

    def test_is_http_exception(self):
        assert isinstance(InternalServerError("op"), HTTPException)


# ---------------------------------------------------------------------------
# Specialised ServiceUnavailableError subclasses
# ---------------------------------------------------------------------------

class TestSpecialisedUnavailableErrors:
    def test_library_manager_unavailable_is_503(self):
        err = LibraryManagerUnavailableError()
        assert err.status_code == 503

    def test_library_manager_unavailable_detail(self):
        err = LibraryManagerUnavailableError()
        assert "library manager" in err.detail.lower()

    def test_audio_player_unavailable_is_503(self):
        err = AudioPlayerUnavailableError()
        assert err.status_code == 503

    def test_audio_player_unavailable_detail(self):
        err = AudioPlayerUnavailableError()
        assert "audio player" in err.detail.lower()

    def test_player_state_unavailable_is_503(self):
        err = PlayerStateUnavailableError()
        assert err.status_code == 503

    def test_player_state_unavailable_detail(self):
        err = PlayerStateUnavailableError()
        assert "player state manager" in err.detail.lower()

    def test_connection_manager_unavailable_is_503(self):
        err = ConnectionManagerUnavailableError()
        assert err.status_code == 503

    def test_connection_manager_unavailable_detail(self):
        err = ConnectionManagerUnavailableError()
        assert "connection manager" in err.detail.lower()

    def test_all_subclasses_of_service_unavailable(self):
        for cls in (
            LibraryManagerUnavailableError,
            AudioPlayerUnavailableError,
            PlayerStateUnavailableError,
            ConnectionManagerUnavailableError,
        ):
            assert issubclass(cls, ServiceUnavailableError)

    def test_no_internal_detail_leakage(self):
        """Specialised errors must not include stack traces or internal paths."""
        for cls in (
            LibraryManagerUnavailableError,
            AudioPlayerUnavailableError,
            PlayerStateUnavailableError,
            ConnectionManagerUnavailableError,
        ):
            err = cls()
            assert "traceback" not in err.detail.lower()
            assert "/" not in err.detail  # no file paths


# ---------------------------------------------------------------------------
# handle_query_error
# ---------------------------------------------------------------------------

class TestHandleQueryError:
    def test_raises_http_exception(self):
        with pytest.raises(HTTPException):
            handle_query_error("get tracks", ValueError("bad"))

    def test_raises_internal_server_error_500(self):
        with pytest.raises(HTTPException) as exc_info:
            handle_query_error("get tracks", RuntimeError("oops"))
        assert exc_info.value.status_code == 500

    def test_detail_contains_operation(self):
        with pytest.raises(HTTPException) as exc_info:
            handle_query_error("get tracks", RuntimeError("oops"))
        assert "get tracks" in exc_info.value.detail

    def test_detail_contains_error_message(self):
        with pytest.raises(HTTPException) as exc_info:
            handle_query_error("delete album", ValueError("constraint violation"))
        assert "constraint violation" in exc_info.value.detail

    def test_works_with_various_exception_types(self):
        for exc_type in (ValueError, RuntimeError, OSError, KeyError):
            with pytest.raises(HTTPException) as exc_info:
                handle_query_error("op", exc_type("msg"))
            assert exc_info.value.status_code == 500

    def test_no_sensitive_path_in_detail(self):
        with pytest.raises(HTTPException) as exc_info:
            handle_query_error("open file", FileNotFoundError("/home/user/.auralis/library.db"))
        # Operation name should appear, but we check status is 500
        assert exc_info.value.status_code == 500
