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
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from security.path_security import (
    validate_user_chosen_directory,
    register_allowed_directory,
    unregister_allowed_directory,
    clear_extra_allowed_directories,
    PathValidationError,
)

from .dependencies import with_error_handling

logger = logging.getLogger(__name__)


class _ScanFolderRequest(BaseModel):
    folder: str


class SettingsUpdateRequest(BaseModel):
    """Typed, validated body for ``PUT /api/settings`` (#3837 / BE-SCH-2).

    Every field is optional so the endpoint remains a partial update. ``extra='forbid'``
    turns a misspelled field name into a 422 instead of a silent no-op (the
    SettingsRepository whitelist would otherwise drop unknown keys without complaint).
    Field set mirrors ``SettingsRepository.update_settings`` whitelist plus the
    separately-handled ``scan_folders`` (JSON) and ``file_types`` (CSV) columns.
    """

    model_config = ConfigDict(extra="forbid")

    # Library
    scan_folders: list[str] | None = None
    file_types: list[str] | None = None
    auto_scan: bool | None = None
    scan_interval: int | None = Field(default=None, ge=0)
    # Playback
    crossfade_enabled: bool | None = None
    crossfade_duration: float | None = Field(default=None, ge=0)
    gapless_enabled: bool | None = None
    replay_gain_enabled: bool | None = None
    volume: float | None = Field(default=None, ge=0.0, le=1.0)
    # Audio output
    output_device: str | None = None
    bit_depth: int | None = None
    sample_rate: int | None = Field(default=None, gt=0)
    # Interface
    theme: str | None = None
    language: str | None = None
    show_visualizations: bool | None = None
    mini_player_on_close: bool | None = None
    # Enhancement
    default_preset: str | None = None
    auto_enhance: bool | None = None
    enhancement_intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    # Advanced
    cache_size: int | None = Field(default=None, ge=0)
    max_concurrent_scans: int | None = Field(default=None, ge=1)
    enable_analytics: bool | None = None
    debug_mode: bool | None = None


class SettingsResponse(BaseModel):
    """Response shape for settings endpoints (mirrors ``UserSettings.to_dict()``).

    ``extra='allow'`` keeps forward-compatibility with the dict the repository emits
    (e.g. ``id`` / ``created_at`` / ``updated_at``) without having to enumerate them.
    """

    model_config = ConfigDict(extra="allow")

    scan_folders: list[str] = Field(default_factory=list)
    file_types: list[str] = Field(default_factory=list)
    auto_scan: bool | None = None
    scan_interval: int | None = None
    crossfade_enabled: bool | None = None
    crossfade_duration: float | None = None
    gapless_enabled: bool | None = None
    replay_gain_enabled: bool | None = None
    volume: float | None = None
    output_device: str | None = None
    bit_depth: int | None = None
    sample_rate: int | None = None
    theme: str | None = None
    language: str | None = None
    show_visualizations: bool | None = None
    mini_player_on_close: bool | None = None
    default_preset: str | None = None
    auto_enhance: bool | None = None
    enhancement_intensity: float | None = None
    cache_size: int | None = None
    max_concurrent_scans: int | None = None
    enable_analytics: bool | None = None
    debug_mode: bool | None = None


class SettingsUpdateResponse(BaseModel):
    """Envelope returned by mutating settings endpoints."""

    model_config = ConfigDict(extra="forbid")

    message: str
    settings: SettingsResponse


def create_settings_router(
    get_settings_repo: Callable[[], Any],
    get_auto_scanner: Callable[[], Any] | None = None,
) -> APIRouter:
    """
    Factory function to create the settings router.

    Args:
        get_settings_repo: Callable returning a SettingsRepository instance
        get_auto_scanner: Optional callable returning a LibraryAutoScanner (for
                          reload_config() calls after settings changes)

    Returns:
        APIRouter: Configured router instance
    """
    router = APIRouter(tags=["settings"])

    def _repo() -> Any:
        repo = get_settings_repo()
        if not repo:
            raise HTTPException(status_code=503, detail="Settings not available")
        return repo

    async def _notify_scanner() -> None:
        """Tell the auto-scanner to reload its config immediately."""
        if get_auto_scanner is None:
            return
        scanner = get_auto_scanner()
        if scanner and hasattr(scanner, 'reload_config'):
            try:
                await scanner.reload_config()
            except Exception as exc:
                logger.warning(f"Failed to notify auto-scanner of settings change: {exc}")

    @router.get("/api/settings", response_model=SettingsResponse)
    @with_error_handling("get settings")
    async def get_settings() -> dict[str, Any]:
        """Get current user settings."""
        settings = await asyncio.to_thread(_repo().get_settings)
        if not settings:
            raise HTTPException(status_code=404, detail="Settings not found")
        return settings.to_dict()

    @router.put("/api/settings", response_model=SettingsUpdateResponse)
    @with_error_handling("update settings")
    async def update_settings(updates: SettingsUpdateRequest) -> dict[str, Any]:
        """
        Update user settings.

        Accepts a partial, typed set of settings fields. Unknown field names are
        rejected with HTTP 422 (``extra='forbid'``) instead of silently no-op'ing
        through the SettingsRepository whitelist (#3837 / BE-SCH-2). Only fields the
        client actually sent are applied (``exclude_unset``), preserving partial-update
        semantics.
        """
        payload = updates.model_dump(exclude_unset=True)
        settings = await asyncio.to_thread(_repo().update_settings, payload)
        await _notify_scanner()
        return {"message": "Settings updated", "settings": settings.to_dict()}

    @router.post("/api/settings/scan-folders", response_model=SettingsUpdateResponse)
    @with_error_handling("add scan folder")
    async def add_scan_folder(body: _ScanFolderRequest) -> dict[str, Any]:
        """Add a folder to the list of scanned directories."""
        if not body.folder or not body.folder.strip():
            raise HTTPException(status_code=400, detail="folder must be a non-empty path")
        try:
            validated = validate_user_chosen_directory(body.folder.strip())
        except PathValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        settings = await asyncio.to_thread(_repo().add_scan_folder, str(validated))
        # Register so validate_file_path accepts files under this folder
        register_allowed_directory(validated)
        await _notify_scanner()
        return {"message": f"Scan folder added: {body.folder}", "settings": settings.to_dict()}

    @router.post("/api/settings/scan-folders/delete", response_model=SettingsUpdateResponse)
    @with_error_handling("remove scan folder")
    async def remove_scan_folder(body: _ScanFolderRequest) -> dict[str, Any]:
        """Remove a folder from the list of scanned directories."""
        settings = await asyncio.to_thread(_repo().remove_scan_folder, body.folder)
        # Undo the registration made in add_scan_folder so validate_file_path()
        # stops trusting this folder for the rest of the session (fixes #3842),
        # instead of only reverting on the next backend restart.
        unregister_allowed_directory(Path(body.folder))
        await _notify_scanner()
        return {"message": f"Scan folder removed: {body.folder}", "settings": settings.to_dict()}

    @router.post("/api/settings/reset", response_model=SettingsUpdateResponse)
    @with_error_handling("reset settings")
    async def reset_settings() -> dict[str, Any]:
        """Reset all settings to their default values."""
        settings = await asyncio.to_thread(_repo().reset_to_defaults)
        # reset_to_defaults wipes the configured scan_folders list, so no
        # previously-registered extra directory should remain trusted (#3842).
        clear_extra_allowed_directories()
        await _notify_scanner()
        return {"message": "Settings reset to defaults", "settings": settings.to_dict()}

    return router
