"""Per-router dependency isolation for the hoisted router handlers (#5262, #5762).

Every router that injects dependencies through ``RouterDeps`` must keep its own
when a second router of the same kind is built in the same process.
"""

import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers import (  # noqa: E402
    albums,
    albums_deps,
    artwork,
    artwork_deps,
    enhancement,
    enhancement_deps,
    files,
    files_deps,
    library_scan,
    metadata,
    metadata_deps,
    player,
    player_deps,
    playlists,
    playlists_deps,
    processing_api,
    processing_deps,
    similarity,
    similarity_deps,
)
from routers.dependencies import RouterDeps  # noqa: E402


def _assert_isolated(
    first_router: APIRouter,
    second_router: APIRouter,
    probe: Callable[..., Any],
) -> None:
    """Exercise the same probe through two routers built in one process."""
    first_router.add_api_route("/__deps_probe", probe, methods=["GET"])
    second_router.add_api_route("/__deps_probe", probe, methods=["GET"])
    # Routers built with a prefix (similarity, processing) mount the probe under it.
    first_path = f"{first_router.prefix}/__deps_probe"
    second_path = f"{second_router.prefix}/__deps_probe"

    first_app = FastAPI()
    first_app.include_router(first_router)
    second_app = FastAPI()
    second_app.include_router(second_router)

    with TestClient(first_app) as first_client, TestClient(second_app) as second_client:
        assert first_client.get(first_path).json() == {"marker": "first"}
        assert second_client.get(second_path).json() == {"marker": "second"}


def test_playlists_router_instances_keep_their_own_dependencies() -> None:
    first = SimpleNamespace(marker="first")
    second = SimpleNamespace(marker="second")
    first_manager = SimpleNamespace(marker="first")
    second_manager = SimpleNamespace(marker="second")

    first_router = playlists.create_playlists_router(lambda: first, first_manager)
    second_router = playlists.create_playlists_router(lambda: second, second_manager)

    async def probe(
        repos: Any = Depends(playlists_deps._get_repos),
        manager: Any = Depends(playlists_deps._get_connection_manager),
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
        manager: Any = Depends(artwork_deps._get_connection_manager),
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
        get_repos: Callable[[], Any] = Depends(metadata_deps._get_repository_factory),
        manager: Any = Depends(metadata_deps._get_broadcast_manager),
        editor: Any = Depends(metadata_deps._get_metadata_editor),
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

    async def probe(repos: Any = Depends(files_deps._get_repos)) -> dict[str, str]:
        return {"marker": repos.marker}

    _assert_isolated(first_router, second_router, probe)


def test_albums_router_instances_keep_their_own_dependencies() -> None:
    first = SimpleNamespace(marker="first")
    second = SimpleNamespace(marker="second")
    first_router = albums.create_albums_router(lambda: first)
    second_router = albums.create_albums_router(lambda: second)

    async def probe(
        get_repos: Callable[[], Any] = Depends(albums_deps._get_repository_factory),
    ) -> dict[str, str]:
        return {"marker": get_repos().marker}

    _assert_isolated(first_router, second_router, probe)


def test_enhancement_router_instances_keep_their_own_dependencies() -> None:
    first = SimpleNamespace(marker="first")
    second = SimpleNamespace(marker="second")
    first_manager = SimpleNamespace(marker="first")
    second_manager = SimpleNamespace(marker="second")

    first_router = enhancement.create_enhancement_router(
        lambda: {"marker": "first"}, first_manager, get_repository_factory=lambda: first
    )
    second_router = enhancement.create_enhancement_router(
        lambda: {"marker": "second"}, second_manager, get_repository_factory=lambda: second
    )

    async def probe(
        settings: Any = Depends(enhancement_deps._get_enhancement_settings),
        manager: Any = Depends(enhancement_deps._get_connection_manager),
        repos: Any = Depends(enhancement_deps._get_repository_factory),
    ) -> dict[str, str]:
        assert settings["marker"] == manager.marker == repos.marker
        return {"marker": repos.marker}

    _assert_isolated(first_router, second_router, probe)


def test_library_scan_router_instances_keep_their_own_dependencies() -> None:
    first = SimpleNamespace(marker="first")
    second = SimpleNamespace(marker="second")
    first_manager = SimpleNamespace(marker="first")
    second_manager = SimpleNamespace(marker="second")

    first_router = library_scan.create_library_scan_router(lambda: first, first_manager)
    second_router = library_scan.create_library_scan_router(lambda: second, second_manager)

    async def probe(
        database: Any = Depends(library_scan._get_library_database),
        manager: Any = Depends(library_scan._get_connection_manager),
    ) -> dict[str, str]:
        assert database.marker == manager.marker
        return {"marker": database.marker}

    _assert_isolated(first_router, second_router, probe)


def _player_router(marker: str) -> APIRouter:
    ns = SimpleNamespace(marker=marker)
    return player.create_player_router(
        lambda: ns, lambda: ns, lambda: ns, ns, lambda track: track
    )


def test_player_router_instances_keep_their_own_dependencies() -> None:
    first_router = _player_router("first")
    second_router = _player_router("second")

    async def probe(
        audio_player: Any = Depends(player_deps._get_audio_player),
        database: Any = Depends(player_deps._get_library_database),
        manager: Any = Depends(player_deps._get_connection_manager),
    ) -> dict[str, str]:
        assert audio_player.marker == database.marker == manager.marker
        return {"marker": audio_player.marker}

    _assert_isolated(first_router, second_router, probe)


def test_similarity_router_instances_keep_their_own_dependencies() -> None:
    first = SimpleNamespace(marker="first")
    second = SimpleNamespace(marker="second")
    first_router = similarity.create_similarity_router(lambda: first, lambda: None, lambda: first)
    second_router = similarity.create_similarity_router(lambda: second, lambda: None, lambda: second)

    async def probe(
        system: Any = Depends(similarity_deps._similarity_system_getter),
        repos: Any = Depends(similarity_deps._repository_factory_getter),
    ) -> dict[str, str]:
        assert system.marker == repos.marker
        return {"marker": system.marker}

    _assert_isolated(first_router, second_router, probe)


def test_processing_router_instances_keep_their_own_dependencies() -> None:
    first = SimpleNamespace(marker="first")
    second = SimpleNamespace(marker="second")
    first_router = processing_api.create_processing_router(lambda: first)
    second_router = processing_api.create_processing_router(lambda: second)

    async def probe(
        engine: Any = Depends(processing_deps._get_processing_engine),
    ) -> dict[str, str]:
        return {"marker": engine.marker}

    _assert_isolated(first_router, second_router, probe)


class TestRouterDeps:
    """The helper's own contract, independent of any router."""

    def test_current_falls_back_to_the_last_bound_deps_outside_a_request(self) -> None:
        holder = RouterDeps("unit", "empty")
        assert holder.current() == "empty"
        holder.bind("first")
        holder.bind("second")
        assert holder.current() == "second"

    def test_use_scopes_deps_to_the_with_block(self) -> None:
        holder = RouterDeps("unit_use", "empty")
        holder.bind("fallback")
        with holder.use("scoped"):
            assert holder.current() == "scoped"
        assert holder.current() == "fallback"

    def test_a_falsy_active_deps_object_is_still_used(self) -> None:
        holder = RouterDeps("unit_falsy", "empty")
        with holder.use(""):
            assert holder.current() == ""
