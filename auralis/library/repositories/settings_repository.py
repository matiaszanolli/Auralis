"""
Settings Repository
~~~~~~~~~~~~~~~~~~~

Data access layer for user settings operations

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json
import threading
from typing import Any

from sqlalchemy import delete, select

from ..models import UserSettings
from .base import BaseRepository


class SettingsRepository(BaseRepository):
    """Repository for user settings database operations"""

    # Serializes every read-modify-write on the singleton settings row.
    # `select(...).with_for_update()` compiles to `SELECT ... FOR
    # UPDATE` only on dialects with row-level locking; SQLAlchemy's SQLite
    # dialect silently drops the clause, so it was a no-op there (#4956,
    # regression of #3339). This project is SQLite-only (single-file
    # `~/.auralis/library.db`), so an in-process lock is sufficient — it
    # does not help multi-process/multi-host access, but the desktop app
    # never does that.
    #
    # Until #5334 only add_scan_folder/remove_scan_folder took it. The other
    # writers of the same row — update_settings (PUT /api/settings, which can
    # carry scan_folders), reset_to_defaults (which deletes the row) and
    # get_settings' default-row creation — ran unlocked, so they could drop a
    # locked add/remove's edit or delete the row underneath it. Class-level,
    # so every repository instance shares the one lock.
    _settings_lock = threading.RLock()

    @staticmethod
    def _scan_folder_list(settings: UserSettings) -> list[str]:
        """The stored scan_folders JSON as a list ([] when unset)."""
        folders: list[str] = json.loads(str(settings.scan_folders)) if settings.scan_folders else []
        return folders

    def get_settings(self) -> UserSettings | None:
        """
        Get user settings (always returns the first/only settings record)
        Creates default settings if none exist
        """
        with self._settings_lock, self._session_scope() as session:
            settings = session.execute(select(UserSettings)).scalars().first()

            # Create default settings if none exist
            if not settings:
                settings = UserSettings()
                session.add(settings)
                session.commit()
                session.refresh(settings)

            session.expunge(settings)
            return settings

    def update_settings(self, updates: dict[str, Any]) -> UserSettings:
        """
        Update user settings with provided dictionary

        Args:
            updates: Dictionary of setting keys and values to update

        Returns:
            Updated UserSettings object
        """
        settings, _previous_folders = self.update_settings_with_previous_folders(updates)
        return settings

    def update_settings_with_previous_folders(
        self, updates: dict[str, Any]
    ) -> tuple[UserSettings, list[str]]:
        """Apply ``updates`` and return the scan folders stored just before.

        The snapshot and the write happen in one locked transaction, so a
        caller diffing old against new folders (PUT /api/settings registers
        added folders and unregisters removed ones) cannot diff against a list
        a concurrent add/remove/reset has already replaced (#5334). The
        previous list is only read when ``updates`` writes scan_folders; it is
        ``[]`` otherwise.
        """
        # Work on a shallow copy: scan_folders and file_types are removed from
        # the working mapping after their custom serialization, and callers
        # still need the original payload for post-write side effects (#5259).
        updates = dict(updates)

        with self._settings_lock, self._session_scope() as session:
            settings = session.execute(select(UserSettings)).scalars().first()

            if not settings:
                settings = UserSettings()
                session.add(settings)

            previous_folders = (
                self._scan_folder_list(settings) if 'scan_folders' in updates else []
            )

            # Handle scan_folders separately as it needs JSON serialization
            if 'scan_folders' in updates:
                if isinstance(updates['scan_folders'], list):
                    settings.scan_folders = json.dumps(updates['scan_folders'])
                else:
                    settings.scan_folders = updates['scan_folders']
                del updates['scan_folders']

            # Handle file_types as comma-separated string
            if 'file_types' in updates:
                if isinstance(updates['file_types'], list):
                    settings.file_types = ','.join(updates['file_types'])
                else:
                    settings.file_types = updates['file_types']
                del updates['file_types']

            # Whitelist of mutable settings fields — prevents ORM internal state
            # corruption via _sa_instance_state, id, created_at, etc. (fixes #2240)
            ALLOWED_SETTINGS_FIELDS = {
                'auto_scan', 'scan_interval',
                'crossfade_enabled', 'crossfade_duration', 'gapless_enabled',
                'replay_gain_enabled', 'volume',
                'output_device', 'bit_depth', 'sample_rate',
                'theme', 'language', 'show_visualizations', 'mini_player_on_close',
                'default_preset', 'auto_enhance', 'enhancement_intensity',
                'cache_size', 'max_concurrent_scans', 'enable_analytics', 'debug_mode',
            }
            for key, value in updates.items():
                if key in ALLOWED_SETTINGS_FIELDS:
                    setattr(settings, key, value)

            session.commit()
            session.refresh(settings)
            session.expunge(settings)
            return settings, previous_folders

    def reset_to_defaults(self) -> UserSettings:
        """
        Reset all settings to default values

        Returns:
            UserSettings object with default values
        """
        with self._settings_lock, self._session_scope() as session:
            # Delete existing settings
            session.execute(delete(UserSettings))

            # Create new default settings
            settings = UserSettings()
            session.add(settings)
            session.commit()
            session.refresh(settings)
            session.expunge(settings)
            return settings

    def update_scan_folders(self, folders: list[str]) -> UserSettings:
        """
        Update the list of scan folders

        Args:
            folders: List of folder paths to scan

        Returns:
            Updated UserSettings object
        """
        return self.update_settings({'scan_folders': folders})

    def add_scan_folder(self, folder: str) -> UserSettings:
        """Add a new folder to scan list (atomic read-modify-write, #3339, #4956)."""
        with self._settings_lock, self._session_scope() as session:
            try:
                settings = session.execute(select(UserSettings)).scalars().first()
                if not settings:
                    settings = UserSettings()
                    session.add(settings)

                folders = self._scan_folder_list(settings)
                if folder not in folders:
                    folders.append(folder)
                    settings.scan_folders = json.dumps(folders)

                session.commit()
                session.refresh(settings)
                session.expunge(settings)
                return settings
            except Exception:
                session.rollback()
                raise

    def remove_scan_folder(self, folder: str) -> UserSettings:
        """Remove a folder from scan list (atomic read-modify-write, #3339, #4956)."""
        with self._settings_lock, self._session_scope() as session:
            try:
                settings = session.execute(select(UserSettings)).scalars().first()
                if not settings:
                    settings = UserSettings()
                    session.add(settings)

                folders = self._scan_folder_list(settings)
                if folder in folders:
                    folders.remove(folder)
                    settings.scan_folders = json.dumps(folders)

                session.commit()
                session.refresh(settings)
                session.expunge(settings)
                return settings
            except Exception:
                session.rollback()
                raise
