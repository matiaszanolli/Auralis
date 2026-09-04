"""Per-router dependency isolation for the hoisted router handlers (#5262)."""

import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers import artwork, files, metadata, playlists  # noqa: E402


def _assert_isolated(
    first_router: APIRouter,
    second_router: APIRouter,
    probe: Callable[..., Any],
) -> None:
    """Exercise the same probe through two routers built in one process."""
    first_router.add_api_route("/__deps_probe", probe, methods=["GET"])
    second_router.add_api_route("/__deps_probe", probe, methods=["GET"])

    first_app = FastAPI()
    first_app.include_router(first_router)
    second_app = FastAPI()
    second_app.include_router(second_router)

    with TestClient(first_app) as first_client, TestClient(second_app) as second_client:
        assert first_client.get("/__deps_probe").json() == {"marker": "first"}
        assert second_client.get("/__deps_probe").json() == {"marker": "second"}


def test_playlists_router_instances_keep_their_own_dependencies() -> None:
    first = SimpleNamespace(marker="first")
    second = SimpleNamespace(marker="second")
    first_manager = SimpleNamespace(marker="first")
    second_manager = SimpleNamespace(marker="second")

    first_router = playlists.create_playlists_router(lambda: first, first_manager)
    second_router = playlists.create_playlists_router(lambda: second, second_manager)

    async def probe(
        repos: Any = Depends(playlists._get_repos),
        manager: Any = Depends(playlists._get_connection_manager),
    ) -> dict[str, str]:
        assert repos.marker == manager.marker
        return {"marker": repos.marker}

    _assert_isolated(first_router, second_router, probe)


def test_artwork_router_instances_keep_their_own_dependencies() -> None:
    first = SimpleNamespace(marker="first")
    second = SimpleNamespace(marker="second")
    first_manager = SimpleNamespace(marker="first")
    second_manager = SimpleNamespace(marker="second")

    first_router = artwork.create_artwork_router(first_manager, lambda: first)
    second_router = artwork.create_artwork_router(second_manager, lambda: second)

    async def probe(
        repos: Any = Depends(artwork._get_repos),
        manager: Any = Depends(artwork._get_connection_manager),
    ) -> dict[str, str]:
        assert repos.marker == manager.marker
        return {"marker": repos.marker}

    _assert_isolated(first_router, second_router, probe)


def test_metadata_router_instances_keep_their_own_dependencies() -> None:
    first = SimpleNamespace(marker="first")
    second = SimpleNamespace(marker="second")
    first_manager = SimpleNamespace(marker="first")
    second_manager = SimpleNamespace(marker="second")
    first_editor = MagicMock(marker="first")
    second_editor = MagicMock(marker="second")

    first_router = metadata.create_metadata_router(
        lambda: first, first_manager, first_editor
    )
    second_router = metadata.create_metadata_router(
        lambda: second, second_manager, second_editor
    )

    async def probe(
        get_repos: Callable[[], Any] = Depends(metadata._get_repository_factory),
        manager: Any = Depends(metadata._get_broadcast_manager),
        editor: Any = Depends(metadata._get_metadata_editor),
    ) -> dict[str, str]:
        repos = get_repos()
        assert repos.marker == manager.marker == editor.marker
        return {"marker": repos.marker}

    _assert_isolated(first_router, second_router, probe)


def test_files_router_instances_keep_their_own_dependencies() -> None:
    first = SimpleNamespace(marker="first")
    second = SimpleNamespace(marker="second")
    first_router = files.create_files_router(lambda: first)
    second_router = files.create_files_router(lambda: second)

    async def probe(repos: Any = Depends(files._get_repos)) -> dict[str, str]:
        return {"marker": repos.marker}

    _assert_isolated(first_router, second_router, probe)
