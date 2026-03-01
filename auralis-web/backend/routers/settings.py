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

import logging
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class _ScanFolderRequest(BaseModel):
    folder: str


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

    @router.get("/api/settings")
    async def get_settings() -> dict[str, Any]:
        """Get current user settings."""
        settings = _repo().get_settings()
        if not settings:
            raise HTTPException(status_code=404, detail="Settings not found")
        return settings.to_dict()

    @router.put("/api/settings")
    async def update_settings(updates: dict[str, Any]) -> dict[str, Any]:
        """
        Update user settings.

        Accepts a partial dictionary of settings fields to update.
        Unknown fields are silently ignored (whitelist enforced by SettingsRepository).
        """
        try:
            settings = _repo().update_settings(updates)
            await _notify_scanner()
            return {"message": "Settings updated", "settings": settings.to_dict()}
        except Exception as exc:
            logger.error(f"Failed to update settings: {exc}")
            raise HTTPException(status_code=500, detail="Failed to update settings")

    @router.post("/api/settings/scan-folders")
    async def add_scan_folder(body: _ScanFolderRequest) -> dict[str, Any]:
        """Add a folder to the list of scanned directories."""
        if not body.folder or not body.folder.strip():
            raise HTTPException(status_code=400, detail="folder must be a non-empty path")
        try:
            settings = _repo().add_scan_folder(body.folder.strip())
            await _notify_scanner()
            return {"message": f"Scan folder added: {body.folder}", "settings": settings.to_dict()}
        except Exception as exc:
            logger.error(f"Failed to add scan folder: {exc}")
            raise HTTPException(status_code=500, detail="Failed to add scan folder")

    @router.post("/api/settings/scan-folders/delete")
    async def remove_scan_folder(body: _ScanFolderRequest) -> dict[str, Any]:
        """Remove a folder from the list of scanned directories."""
        try:
            settings = _repo().remove_scan_folder(body.folder)
            await _notify_scanner()
            return {"message": f"Scan folder removed: {body.folder}", "settings": settings.to_dict()}
        except Exception as exc:
            logger.error(f"Failed to remove scan folder: {exc}")
            raise HTTPException(status_code=500, detail="Failed to remove scan folder")

    @router.post("/api/settings/reset")
    async def reset_settings() -> dict[str, Any]:
        """Reset all settings to their default values."""
        try:
            settings = _repo().reset_to_defaults()
            await _notify_scanner()
            return {"message": "Settings reset to defaults", "settings": settings.to_dict()}
        except Exception as exc:
            logger.error(f"Failed to reset settings: {exc}")
            raise HTTPException(status_code=500, detail="Failed to reset settings")

    return router
