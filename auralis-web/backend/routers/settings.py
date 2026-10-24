"""
Settings Router
~~~~~~~~~~~~~~~

REST API for user settings management.

Endpoints:
- GET  /api/settings                    — get current settings
- PUT  /api/settings                    — update settings
- POST /api/settings/scan-folders       — add a scan folder
- POST /api/settings/scan-folders/delete — remove a scan folder
- POST /api/settings/reset              — reset to defaults

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from security.path_allowlist import (
    clear_extra_allowed_directories,
    register_allowed_directory,
    unregister_allowed_directory,
)
from security.path_security import (
    PathValidationError,
    validate_directory_list,
    validate_user_chosen_directory,
)

from .dependencies import with_error_handling
from .errors import BadRequestError, NotFoundError
from services.missing_tracks import prune_tracks_under_folder
from .settings_sync import _notify_scanner, _sync_enhancement_settings
from .settings_deps import (  # noqa: F401
    _SettingsDeps,
    _deps,
    _get_deps,
    _get_repo,
)
from .settings_models import (  # noqa: F401
    SettingsResponse,
    SettingsUpdateRequest,
    SettingsUpdateResponse,
    _ENHANCEMENT_SETTINGS_FIELDS,
    _ScanFolderRequest,
)

logger = logging.getLogger(__name__)


# ============================================================================
# SHARED STEPS
# ============================================================================


async def _revoke_folder(deps: _SettingsDeps, folder: str) -> None:
    """Unregister a folder's path trust and prune its Track rows.

    Shared by remove_scan_folder and update_settings' scan_folders diff:
    the two routes must behave identically for this column, and revoking
    trust without the prune leaves the folder's rows visible-but-broken
    (#5467 fixed the dedicated endpoint only; #5523 is the generic one).
    """
    unregister_allowed_directory(Path(folder))
    library_database = deps.get_library_database() if deps.get_library_database else None
    if library_database is not None:
        await prune_tracks_under_folder(library_database, folder, deps.connection_manager)


# ============================================================================
# HANDLERS
# ============================================================================


@with_error_handling("get settings")
async def get_settings(repo: Any = Depends(_get_repo)) -> dict[str, Any]:
    """Get current user settings."""
    settings = await asyncio.to_thread(repo.get_settings)
    if not settings:
        raise NotFoundError("Settings")
    data: dict[str, Any] = settings.to_dict()
    return data


@with_error_handling("update settings")
async def update_settings(
    updates: SettingsUpdateRequest,
    repo: Any = Depends(_get_repo),
    deps: _SettingsDeps = Depends(_get_deps),
) -> dict[str, Any]:
    """
    Update user settings.

    Accepts a partial, typed set of settings fields. Unknown field names are
    rejected with HTTP 422 (``extra='forbid'``) instead of silently no-op'ing
    through the SettingsRepository whitelist (#3837 / BE-SCH-2). Only fields the
    client actually sent are applied (``exclude_unset``), preserving partial-update
    semantics.

    ``scan_folders`` is the same column POST /api/settings/scan-folders writes,
    so it gets the identical path validation and allowlist-registration
    treatment here (#4765) — otherwise a folder added via this generic route
    skips both, and files under it 400 as "invalid filepath" until restart.
    """
    payload = updates.model_dump(exclude_unset=True)

    if 'scan_folders' in payload and payload['scan_folders'] is not None:
        try:
            payload['scan_folders'] = validate_directory_list(payload['scan_folders'])
        except PathValidationError:
            # str(e) used to be reflected verbatim -- validate_file_path's
            # variant of this exception names every allowed directory,
            # i.e. the user's entire configured library layout (#4807).
            # validate_directory_list's own validator already logs the
            # rejection once (_logs_rejections); the client gets a fixed,
            # generic detail regardless of which check failed.
            raise BadRequestError("One or more scan folders failed validation")

    # The repository returns the list stored just before this write, read
    # in the same locked transaction (#5334), so the allowlist diff below
    # — additions registered, removals unregistered, regardless of which
    # route made the change (#3842) — cannot run against a list a
    # concurrent add/remove/reset already replaced. The separate, unlocked
    # get_settings() snapshot this used to take could.
    settings, previous_list = await asyncio.to_thread(
        repo.update_settings_with_previous_folders, payload
    )

    if 'scan_folders' in payload:
        previous_folders = set(previous_list)
        new_folders = set(payload['scan_folders'] or [])
        for added in new_folders - previous_folders:
            register_allowed_directory(Path(added))
        for removed in previous_folders - new_folders:
            # Same revoke+prune as the dedicated delete endpoint (#5523):
            # unregistering trust alone left the removed folder's tracks
            # in the library while every path-validated endpoint started
            # rejecting their files with an unexplained 400.
            await _revoke_folder(deps, removed)

    await _notify_scanner(deps)

    # #4587: only re-seed/broadcast when this save actually touched an
    # enhancement-related field — an unrelated save (e.g. theme) should
    # not fire a WS message enhancement consumers have no reason to see.
    if _ENHANCEMENT_SETTINGS_FIELDS & payload.keys():
        await _sync_enhancement_settings(deps, settings)

    return {"message": "Settings updated", "settings": settings.to_dict()}


@with_error_handling("add scan folder")
async def add_scan_folder(
    body: _ScanFolderRequest,
    repo: Any = Depends(_get_repo),
    deps: _SettingsDeps = Depends(_get_deps),
) -> dict[str, Any]:
    """Add a folder to the list of scanned directories."""
    if not body.folder or not body.folder.strip():
        raise BadRequestError("folder must be a non-empty path")
    try:
        validated = validate_user_chosen_directory(body.folder.strip())
    except PathValidationError:
        # str(e) used to be reflected verbatim (#4807). validate_user_chosen_directory
        # already logs the rejection once (_logs_rejections); the client
        # gets a fixed, generic detail regardless of which check failed.
        raise BadRequestError("Invalid or inaccessible folder path")
    settings = await asyncio.to_thread(repo.add_scan_folder, str(validated))
    # Register so validate_file_path accepts files under this folder
    register_allowed_directory(validated)
    await _notify_scanner(deps)
    return {"message": f"Scan folder added: {body.folder}", "settings": settings.to_dict()}


@with_error_handling("remove scan folder")
async def remove_scan_folder(
    body: _ScanFolderRequest,
    repo: Any = Depends(_get_repo),
    deps: _SettingsDeps = Depends(_get_deps),
) -> dict[str, Any]:
    """Remove a folder from the list of scanned directories."""
    settings = await asyncio.to_thread(repo.remove_scan_folder, body.folder)
    # Undo the registration made in add_scan_folder so validate_file_path()
    # stops trusting this folder for the rest of the session (fixes #3842),
    # instead of only reverting on the next backend restart, and prune the
    # folder's Track rows (#5467) — revoke+prune is one shared step so this
    # endpoint and PUT /api/settings' scan_folders diff can't drift (#5523).
    await _revoke_folder(deps, body.folder)
    await _notify_scanner(deps)
    return {"message": f"Scan folder removed: {body.folder}", "settings": settings.to_dict()}


@with_error_handling("reset settings")
async def reset_settings(
    repo: Any = Depends(_get_repo),
    deps: _SettingsDeps = Depends(_get_deps),
) -> dict[str, Any]:
    """Reset all settings to their default values."""
    settings = await asyncio.to_thread(repo.reset_to_defaults)
    # reset_to_defaults wipes the configured scan_folders list, so no
    # previously-registered extra directory should remain trusted (#3842).
    clear_extra_allowed_directories()
    await _notify_scanner(deps)
    # #4587: reset_to_defaults() always rewrites every column (unlike the
    # partial-update PUT above), so the enhancement fields are always
    # touched here — re-seed/broadcast unconditionally rather than
    # checking payload keys, since there is no payload to check.
    await _sync_enhancement_settings(deps, settings)
    return {"message": "Settings reset to defaults", "settings": settings.to_dict()}


def create_settings_router(
    get_settings_repo: Callable[[], Any],
    get_auto_scanner: Callable[[], Any] | None = None,
    get_enhancement_settings: Callable[[], dict[str, Any]] | None = None,
    connection_manager: Any = None,
    get_library_database: Callable[[], Any] | None = None,
) -> APIRouter:
    """
    Factory function to create the settings router.

    Args:
        get_settings_repo: Callable returning a SettingsRepository instance
        get_auto_scanner: Optional callable returning a LibraryAutoScanner (for
                          reload_config() calls after settings changes)
        get_enhancement_settings: Optional callable returning the shared,
                          shared-by-reference runtime `enhancement_settings`
                          dict (auralis-web/backend/main.py). When given, a
                          PUT/reset that touches an enhancement-related field
                          re-seeds this dict and broadcasts the change so it
                          takes effect on the live session immediately,
                          instead of only at the next backend restart (#4587)
                          — the write-back half of the sync #4409 started.
        connection_manager: Optional WebSocket connection manager used to
                          broadcast `enhancement_settings_changed` after a
                          re-seed. No-op (re-seed only, no broadcast) if not
                          given.
        get_library_database: Optional callable returning the LibraryDatabase
                          instance. When given, removing a scan folder — via
                          the dedicated delete endpoint or a PUT /api/settings
                          scan_folders diff — also prunes Track rows under it
                          (#5467, #5523) instead of leaving them visible but
                          path-untrusted. No-op (folder removed from settings
                          only) if not given.

    Returns:
        APIRouter: Configured router instance
    """
    deps = _SettingsDeps(
        get_settings_repo,
        get_auto_scanner,
        get_enhancement_settings,
        connection_manager,
        get_library_database,
    )
    router = APIRouter(tags=["settings"], dependencies=[Depends(_deps.bind(deps))])
    router.add_api_route(
        "/api/settings", get_settings, methods=["GET"], response_model=SettingsResponse
    )
    router.add_api_route(
        "/api/settings", update_settings, methods=["PUT"], response_model=SettingsUpdateResponse
    )
    router.add_api_route(
        "/api/settings/scan-folders",
        add_scan_folder,
        methods=["POST"],
        response_model=SettingsUpdateResponse,
    )
    router.add_api_route(
        "/api/settings/scan-folders/delete",
        remove_scan_folder,
        methods=["POST"],
        response_model=SettingsUpdateResponse,
    )
    router.add_api_route(
        "/api/settings/reset", reset_settings, methods=["POST"], response_model=SettingsUpdateResponse
    )
    return router
