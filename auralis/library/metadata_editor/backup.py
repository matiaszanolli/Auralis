# -*- coding: utf-8 -*-

"""
Backup Operations
~~~~~~~~~~~~~~~~~

File backup and restore operations for safe metadata editing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import shutil

from ...utils.logging import info, warning, error, debug


class BackupManager:
    """Manages file backups for safe metadata editing"""

    @staticmethod
    def create_backup(filepath: str) -> bool:
        """
        Create backup of file before modification

        Args:
            filepath: Path to file to backup

        Returns:
            True if backup created successfully, False otherwise
        """
        backup_path = filepath + '.bak'
        try:
            shutil.copy2(filepath, backup_path)
            debug(f"Created backup: {backup_path}")
            return True
        except Exception as e:
            warning(f"Failed to create backup: {e}")
            return False

    @staticmethod
    def restore_backup(filepath: str) -> bool:
        """
        Restore file from backup

        Args:
            filepath: Path to original file

        Returns:
            True if restored successfully, False otherwise
        """
        backup_path = filepath + '.bak'
        if os.path.exists(backup_path):
            try:
                shutil.move(backup_path, filepath)
                info(f"Restored from backup: {filepath}")
                return True
            except Exception as e:
                error(f"Failed to restore backup: {e}")
                return False
        return False

    @staticmethod
    def cleanup_backup(filepath: str) -> bool:
        """
        Remove backup file after successful operation

        Args:
            filepath: Path to original file

        Returns:
            True if backup removed, False otherwise
        """
        backup_path = filepath + '.bak'
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
                debug(f"Removed backup: {backup_path}")
                return True
            except Exception as e:
                warning(f"Failed to remove backup: {e}")
                return False
        return False
