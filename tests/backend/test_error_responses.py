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
    InternalServerError,
    LibraryUnavailableError,
    NotFoundError,
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

    def test_error_message_is_logged_not_sent_to_the_client(self, caplog):
        with caplog.at_level("ERROR"):
            err = InternalServerError("fetch tracks", ValueError("db timeout"))
        assert "db timeout" not in err.detail
        assert "fetch tracks" in err.detail
        assert "db timeout" in caplog.text

    def test_detail_without_error(self):
        err = InternalServerError("delete album")
        assert "delete album" in err.detail

    def test_is_http_exception(self):
        assert isinstance(InternalServerError("op"), HTTPException)


# ---------------------------------------------------------------------------
# Specialised ServiceUnavailableError subclasses
# ---------------------------------------------------------------------------

class TestSpecialisedUnavailableErrors:
    def test_library_database_unavailable_is_503(self):
        err = LibraryUnavailableError()
        assert err.status_code == 503

    def test_library_database_unavailable_detail(self):
        err = LibraryUnavailableError()
        assert "library" in err.detail.lower()

    def test_audio_player_unavailable_is_503(self):
        err = AudioPlayerUnavailableError()
        assert err.status_code == 503

    def test_audio_player_unavailable_detail(self):
        err = AudioPlayerUnavailableError()
        assert "audio player" in err.detail.lower()

    def test_all_subclasses_of_service_unavailable(self):
        for cls in (
            LibraryUnavailableError,
            AudioPlayerUnavailableError,
                        ):
            assert issubclass(cls, ServiceUnavailableError)

    def test_no_internal_detail_leakage(self):
        """Specialised errors must not include stack traces or internal paths."""
        for cls in (
            LibraryUnavailableError,
            AudioPlayerUnavailableError,
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

    def test_error_message_is_logged_not_sent_to_the_client(self, caplog):
        with caplog.at_level("ERROR"), pytest.raises(HTTPException) as exc_info:
            handle_query_error("delete album", ValueError("constraint violation"))
        assert "constraint violation" not in exc_info.value.detail
        assert "constraint violation" in caplog.text

    def test_a_vanished_file_is_a_404_not_a_500(self):
        """#5081: a file removed between the DB lookup and the read."""
        with pytest.raises(HTTPException) as exc_info:
            handle_query_error("get artwork", FileNotFoundError(2, "No such file", "/home/u/Music/a.flac"))
        assert exc_info.value.status_code == 404
        assert "/" not in exc_info.value.detail  # the path stays in the log

    def test_an_unreadable_file_is_a_403_not_a_500(self):
        with pytest.raises(HTTPException) as exc_info:
            handle_query_error("get artwork", PermissionError(13, "Permission denied", "/home/u/Music/a.flac"))
        assert exc_info.value.status_code == 403
        assert "/" not in exc_info.value.detail

    def test_an_integer_too_large_for_sqlite_is_a_404_without_a_traceback(self, caplog):
        """#6162: an id such as 10**30 raises OverflowError in the SQLite binding."""
        with caplog.at_level("WARNING"), pytest.raises(HTTPException) as exc_info:
            handle_query_error("get track", OverflowError("Python int too large to convert to SQLite INTEGER"))
        assert exc_info.value.status_code == 404
        assert not [r for r in caplog.records if r.exc_info]

    def test_other_os_errors_stay_500(self):
        with pytest.raises(HTTPException) as exc_info:
            handle_query_error("get artwork", OSError(5, "Input/output error"))
        assert exc_info.value.status_code == 500

    def test_works_with_various_exception_types(self):
        for exc_type in (ValueError, RuntimeError, OSError, KeyError):
            with pytest.raises(HTTPException) as exc_info:
                handle_query_error("op", exc_type("msg"))
            assert exc_info.value.status_code == 500

    def test_no_sensitive_path_in_detail(self):
        with pytest.raises(HTTPException) as exc_info:
            handle_query_error("open file", FileNotFoundError("/home/user/.auralis/library.db"))
        # A vanished file is a 404 now (#5081); the point of this test is that the
        # path in the exception text never reaches the client.
        assert exc_info.value.status_code == 404
        assert "/home/user" not in exc_info.value.detail
        assert "library.db" not in exc_info.value.detail
