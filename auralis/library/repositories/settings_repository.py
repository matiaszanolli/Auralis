# -*- coding: utf-8 -*-

"""
Settings Repository
~~~~~~~~~~~~~~~~~~~

Data access layer for user settings operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
from typing import Optional, Dict, Any, Callable
from sqlalchemy.orm import Session

from ..models import UserSettings


class SettingsRepository:
    """Repository for user settings database operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """
        Initialize settings repository

        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def get_settings(self) -> Optional[UserSettings]:
        """
        Get user settings (always returns the first/only settings record)
        Creates default settings if none exist
        """
        session = self.get_session()
        try:
            settings = session.query(UserSettings).first()

            # Create default settings if none exist
            if not settings:
                settings = UserSettings()
                session.add(settings)
                session.commit()
                session.refresh(settings)

            return settings
        finally:
            session.close()

    def update_settings(self, updates: Dict[str, Any]) -> UserSettings:
        """
        Update user settings with provided dictionary

        Args:
            updates: Dictionary of setting keys and values to update

        Returns:
            Updated UserSettings object
        """
        session = self.get_session()
        try:
            settings = session.query(UserSettings).first()

            if not settings:
                settings = UserSettings()
                session.add(settings)

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

            # Update remaining attributes
            for key, value in updates.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)

            session.commit()
            session.refresh(settings)
            return settings
        finally:
            session.close()

    def reset_to_defaults(self) -> UserSettings:
        """
        Reset all settings to default values

        Returns:
            UserSettings object with default values
        """
        session = self.get_session()
        try:
            # Delete existing settings
            session.query(UserSettings).delete()

            # Create new default settings
            settings = UserSettings()
            session.add(settings)
            session.commit()
            session.refresh(settings)
            return settings
        finally:
            session.close()

    def update_scan_folders(self, folders: list) -> UserSettings:
        """
        Update the list of scan folders

        Args:
            folders: List of folder paths to scan

        Returns:
            Updated UserSettings object
        """
        return self.update_settings({'scan_folders': folders})

    def add_scan_folder(self, folder: str) -> UserSettings:
        """
        Add a new folder to scan list

        Args:
            folder: Folder path to add

        Returns:
            Updated UserSettings object
        """
        settings = self.get_settings()
        folders = json.loads(settings.scan_folders) if settings.scan_folders else []

        if folder not in folders:
            folders.append(folder)

        return self.update_settings({'scan_folders': folders})

    def remove_scan_folder(self, folder: str) -> UserSettings:
        """
        Remove a folder from scan list

        Args:
            folder: Folder path to remove

        Returns:
            Updated UserSettings object
        """
        settings = self.get_settings()
        folders = json.loads(settings.scan_folders) if settings.scan_folders else []

        if folder in folders:
            folders.remove(folder)

        return self.update_settings({'scan_folders': folders})
