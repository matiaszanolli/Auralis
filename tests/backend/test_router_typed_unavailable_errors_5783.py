"""#5783 — "service unavailable" is spelled once in the routers.

``errors.py`` had typed 503/400/404 classes, but routers re-typed the
``HTTPException(status_code=503, ...)`` inline in ~25 places (nine times for the
processing engine alone) and the wording drifted. ``dependencies.require_service``
and friends are now the single spelling.
"""

import asyncio
import re
import sys
import types
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if "routers" not in sys.modules:
    _stub = types.ModuleType("routers")
    _stub.__path__ = [str(_BACKEND / "routers")]
    _stub.__package__ = "routers"
    sys.modules["routers"] = _stub

from fastapi import HTTPException  # noqa: E402
from routers.dependencies import (  # noqa: E402
    require_processing_engine,
    require_repository_factory,
    require_service,
)
from routers.errors import ServiceUnavailableError  # noqa: E402
from routers.similarity_common import require_fitted, require_similarity_system  # noqa: E402

from auralis.player.repository_access import resolve_repository_factory  # noqa: E402


class TestRequireService:
    def test_returns_the_service_when_present(self) -> None:
        sentinel = object()
        assert require_service(sentinel, "Thing") is sentinel

    @pytest.mark.parametrize("missing", [None, 0, "", []])
    def test_raises_a_typed_503_with_the_canonical_detail(self, missing: object) -> None:
        with pytest.raises(ServiceUnavailableError) as exc:
            require_service(missing, "Metadata editor")
        assert exc.value.status_code == 503
        assert exc.value.detail == "Metadata editor not available"

    def test_processing_engine_wording(self) -> None:
        with pytest.raises(ServiceUnavailableError) as exc:
            require_processing_engine(None)
        assert exc.value.detail == "Processing engine not available"
        engine = object()
        assert require_processing_engine(engine) is engine


class TestRequireRepositoryFactory:
    def test_returns_the_factory(self) -> None:
        factory = object()
        assert require_repository_factory(lambda: factory) is factory

    @pytest.mark.parametrize("getter", [None, lambda: None])
    def test_unwired_or_empty_getter_is_a_typed_503(self, getter) -> None:
        with pytest.raises(ServiceUnavailableError) as exc:
            require_repository_factory(getter)
        assert (exc.value.status_code, exc.value.detail) == (503, "Repository factory not available")

    def test_files_router_uses_the_same_guard(self) -> None:
        from routers import files_deps

        from routers import files

        files.create_files_router(lambda: None)  # binds a getter that yields no factory
        with pytest.raises(ServiceUnavailableError) as exc:
            files_deps._repo_deps.get_repos()
        assert exc.value.detail == "Repository factory not available"


class TestRequireFitted:
    class _System:
        def __init__(self, fitted: bool) -> None:
            self.fitted = fitted

        def is_fitted(self) -> bool:
            return self.fitted

    def test_unavailable_system_is_still_caught_by_the_resolver(self) -> None:
        with pytest.raises(ServiceUnavailableError):
            require_similarity_system(lambda: None)

    def test_unfitted_system_has_one_wording(self) -> None:
        with pytest.raises(ServiceUnavailableError) as exc:
            asyncio.run(require_fitted(self._System(False)))
        assert exc.value.detail == "Similarity system not initialized. Please wait for initialization."

    def test_fitted_system_is_returned(self) -> None:
        system = self._System(True)
        assert asyncio.run(require_fitted(system)) is system


class TestPlayerRepositoryAccess:
    def test_returns_factory(self) -> None:
        factory = object()
        assert resolve_repository_factory(lambda: factory) is factory

    @pytest.mark.parametrize("getter", [lambda: None, lambda: (_ for _ in ()).throw(AttributeError("x")), None])
    def test_missing_or_broken_getter_raises_runtimeerror(self, getter) -> None:
        with pytest.raises(RuntimeError, match="Repository factory not available"):
            resolve_repository_factory(getter)

    def test_both_engine_classes_share_it(self) -> None:
        # The resolver call sits in the module that owns each class's library
        # access: both moved out of their controllers in #5836 (the queue's to
        # queue_loading.py, IntegrationManager's to integration_library.py).
        import auralis.player.integration_library as integration_library
        import auralis.player.queue_loading as queue_loading

        for module in (integration_library, queue_loading):
            src = Path(module.__file__).read_text()
            assert "resolve_repository_factory(self.get_repository_factory)" in src, module.__name__
            assert "Ensure get_repository_factory is properly configured" not in src, module.__name__


def test_no_router_hand_raises_503_or_400() -> None:
    """The typed classes are the only way to spell 503/400 in routers."""
    offenders: list[str] = []
    pattern = re.compile(r"HTTPException\(\s*status_code\s*=\s*(503|400)\b")
    for path in sorted((_BACKEND / "routers").glob("*.py")):
        if path.name == "errors.py":
            continue
        for match in pattern.finditer(path.read_text()):
            offenders.append(f"{path.name}:{path.read_text().count(chr(10), 0, match.start()) + 1}")
    assert offenders == []


def test_typed_errors_are_still_http_exceptions() -> None:
    assert issubclass(ServiceUnavailableError, HTTPException)
