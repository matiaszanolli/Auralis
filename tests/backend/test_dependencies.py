"""
Tests for shared dependency injection utilities.

Covers require_* guards (503 on None), require_library_manager deprecation
warning, and the with_error_handling decorator for both sync and async endpoints.
"""

import sys
import types
import warnings
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

_backend_dir = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
sys.path.insert(0, str(_backend_dir))

# Inject routers stub to avoid circular import via routers/__init__.py.
# errors must be loaded first so the relative import inside dependencies.py resolves.
if 'routers' not in sys.modules:
    _stub = types.ModuleType('routers')
    _stub.__path__ = [str(_backend_dir / 'routers')]
    _stub.__package__ = 'routers'
    sys.modules['routers'] = _stub

import routers.errors  # noqa: F401 — ensure routers.errors is in sys.modules before dependencies

from fastapi import HTTPException

from routers.dependencies import (
    require_audio_player,
    require_connection_manager,
    require_library_manager,
    require_player_state_manager,
    require_repository_factory,
    with_error_handling,
)


# ---------------------------------------------------------------------------
# require_library_manager (deprecated)
# ---------------------------------------------------------------------------

class TestRequireLibraryManager:
    def test_returns_manager_when_available(self):
        manager = Mock()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = require_library_manager(lambda: manager)
        assert result is manager

    def test_raises_503_when_none(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(HTTPException) as exc_info:
                require_library_manager(lambda: None)
        assert exc_info.value.status_code == 503

    def test_emits_deprecation_warning(self):
        manager = Mock()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            require_library_manager(lambda: manager)
        deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 1
        assert "require_repository_factory" in str(deprecation_warnings[0].message)

    def test_503_detail_mentions_library_manager(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(HTTPException) as exc_info:
                require_library_manager(lambda: None)
        assert "library manager" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# require_audio_player
# ---------------------------------------------------------------------------

class TestRequireAudioPlayer:
    def test_returns_player_when_available(self):
        player = Mock()
        result = require_audio_player(lambda: player)
        assert result is player

    def test_raises_503_when_none(self):
        with pytest.raises(HTTPException) as exc_info:
            require_audio_player(lambda: None)
        assert exc_info.value.status_code == 503

    def test_503_detail_mentions_audio_player(self):
        with pytest.raises(HTTPException) as exc_info:
            require_audio_player(lambda: None)
        assert "audio player" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# require_player_state_manager
# ---------------------------------------------------------------------------

class TestRequirePlayerStateManager:
    def test_returns_manager_when_available(self):
        state_mgr = Mock()
        result = require_player_state_manager(lambda: state_mgr)
        assert result is state_mgr

    def test_raises_503_when_none(self):
        with pytest.raises(HTTPException) as exc_info:
            require_player_state_manager(lambda: None)
        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# require_connection_manager
# ---------------------------------------------------------------------------

class TestRequireConnectionManager:
    def test_returns_manager_when_available(self):
        conn_mgr = Mock()
        result = require_connection_manager(conn_mgr)
        assert result is conn_mgr

    def test_raises_503_when_none(self):
        with pytest.raises(HTTPException) as exc_info:
            require_connection_manager(None)
        assert exc_info.value.status_code == 503

    def test_raises_503_when_falsy(self):
        with pytest.raises(HTTPException) as exc_info:
            require_connection_manager(0)
        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# require_repository_factory
# ---------------------------------------------------------------------------

class TestRequireRepositoryFactory:
    def test_returns_factory_when_available(self):
        factory = Mock()
        result = require_repository_factory(lambda: factory)
        assert result is factory

    def test_raises_503_when_none(self):
        with pytest.raises(HTTPException) as exc_info:
            require_repository_factory(lambda: None)
        assert exc_info.value.status_code == 503

    def test_503_detail_mentions_repository_factory(self):
        with pytest.raises(HTTPException) as exc_info:
            require_repository_factory(lambda: None)
        assert "repository factory" in exc_info.value.detail.lower()

    def test_callable_is_invoked(self):
        factory = Mock()
        getter = Mock(return_value=factory)
        require_repository_factory(getter)
        getter.assert_called_once()


# ---------------------------------------------------------------------------
# with_error_handling decorator — sync
# ---------------------------------------------------------------------------

class TestWithErrorHandlingSync:
    def test_passes_through_return_value(self):
        @with_error_handling("test op")
        def endpoint():
            return {"ok": True}

        assert endpoint() == {"ok": True}

    def test_passes_through_http_exception_unchanged(self):
        @with_error_handling("test op")
        def endpoint():
            raise HTTPException(status_code=404, detail="not found")

        with pytest.raises(HTTPException) as exc_info:
            endpoint()
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "not found"

    def test_converts_generic_exception_to_500(self):
        @with_error_handling("fetch tracks")
        def endpoint():
            raise ValueError("something broke")

        with pytest.raises(HTTPException) as exc_info:
            endpoint()
        assert exc_info.value.status_code == 500

    def test_500_detail_contains_operation_name(self):
        @with_error_handling("fetch tracks")
        def endpoint():
            raise RuntimeError("db down")

        with pytest.raises(HTTPException) as exc_info:
            endpoint()
        assert "fetch tracks" in exc_info.value.detail

    def test_wraps_preserves_function_name(self):
        @with_error_handling("op")
        def my_endpoint():
            return None

        assert my_endpoint.__name__ == "my_endpoint"


# ---------------------------------------------------------------------------
# with_error_handling decorator — async
# ---------------------------------------------------------------------------

class TestWithErrorHandlingAsync:
    @pytest.mark.asyncio
    async def test_async_passes_through_return_value(self):
        @with_error_handling("async op")
        async def endpoint():
            return {"ok": True}

        result = await endpoint()
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_async_passes_through_http_exception(self):
        @with_error_handling("async op")
        async def endpoint():
            raise HTTPException(status_code=422, detail="bad input")

        with pytest.raises(HTTPException) as exc_info:
            await endpoint()
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_async_converts_generic_exception_to_500(self):
        @with_error_handling("async fetch")
        async def endpoint():
            raise ConnectionError("db unreachable")

        with pytest.raises(HTTPException) as exc_info:
            await endpoint()
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_async_500_contains_operation(self):
        @with_error_handling("async fetch")
        async def endpoint():
            raise RuntimeError("oops")

        with pytest.raises(HTTPException) as exc_info:
            await endpoint()
        assert "async fetch" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_async_wraps_preserves_name(self):
        @with_error_handling("op")
        async def my_async_endpoint():
            return None

        assert my_async_endpoint.__name__ == "my_async_endpoint"
