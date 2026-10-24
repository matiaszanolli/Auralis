"""
Atomic multi-file metadata updates (split from metadata_editor.py, #5837):
validate, back up everything, apply, and roll the whole set back on any failure.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path
from typing import Any
from collections.abc import Callable

from ...utils.logging import info
from .backup import BackupManager, lock_files
from .models import MetadataUpdate


class BatchUpdateMixin:
    """``batch_update``; ``write_metadata`` and ``backup_manager`` belong to MetadataEditor."""

    backup_manager: BackupManager

    # Provided by MetadataEditor.
    write_metadata: "Callable[..., bool]"

    def batch_update(self, updates: list[MetadataUpdate]) -> dict[str, Any]:
        """
        Update metadata for multiple tracks atomically.

        When backup=True (the default), all files are backed up before any
        write is attempted.  If any write fails, every file that was already
        modified is restored from its backup so the collection is left in a
        consistent state.  Backups are deleted only on a fully-successful run.

        When backup=False the batch is best-effort (no rollback possible).

        Args:
            updates: List of MetadataUpdate objects

        Returns:
            Dictionary with:
            - total (int): updates attempted
            - successful (int): updates that committed
            - failed (int): updates that did not commit
            - results (list): per-file {track_id, success, [error], [updates]}
            - rolled_back (bool): True when a failure triggered a full rollback
        """
        if not updates:
            return {
                'total': 0, 'successful': 0, 'failed': 0,
                'results': [], 'rolled_back': False,
            }

        # Guard: mixing backup=True and backup=False entries in a single batch
        # leads to an inconsistent state where backup=False files are marked as
        # rolled_back=True in the result (and skipped by the router's DB update)
        # even though their on-disk write is NOT reverted (#2460).
        backup_flags = {u.backup for u in updates}
        if len(backup_flags) > 1:
            raise ValueError(
                "All updates in a batch must share the same backup setting. "
                "Got mixed backup=True and backup=False entries."
            )

        total = len(updates)

        # Phase 1 — Validate all files exist before touching any.
        for update in updates:
            if not Path(update.filepath).exists():
                return {
                    'total': total,
                    'successful': 0,
                    'failed': total,
                    'results': [
                        {
                            'track_id': u.track_id,
                            'success': False,
                            'error': (
                                "File not found"
                                if u.filepath == update.filepath
                                else "Aborted: another batch file was not found"
                            ),
                        }
                        for u in updates
                    ],
                    'rolled_back': False,
                }

        # #5307: hold every file's lock across backup → apply → rollback so a
        # concurrent single-track write cannot interleave with the batch.
        with lock_files(u.filepath for u in updates):
            # Phase 2 — Back up every file (fail-fast: any backup failure aborts
            # all). Maps each filepath to its own unique backup copy.
            backups: dict[str, str] = {}
            for update in updates:
                if not update.backup or update.filepath in backups:
                    continue
                backup_path = self.backup_manager.create_backup(update.filepath)
                if backup_path is None:
                    for path in backups.values():
                        self.backup_manager.cleanup_backup(path)
                    return {
                        'total': total,
                        'successful': 0,
                        'failed': total,
                        'results': [
                            {
                                'track_id': u.track_id,
                                'success': False,
                                'error': (
                                    "Failed to create backup"
                                    if u.filepath == update.filepath
                                    else "Aborted: another batch backup failed"
                                ),
                            }
                            for u in updates
                        ],
                        'rolled_back': False,
                    }
                backups[update.filepath] = backup_path

            # Phase 3 — Apply all updates (skip per-file backup; batch backup done above).
            per_file_results: list[dict[str, Any]] = []
            any_failed = False

            for update in updates:
                try:
                    self.write_metadata(update.filepath, update.updates, backup=False)
                    per_file_results.append({
                        'track_id': update.track_id,
                        'success': True,
                        'updates': update.updates,
                    })
                except Exception as e:
                    any_failed = True
                    per_file_results.append({
                        'track_id': update.track_id,
                        'success': False,
                        'error': str(e).replace(update.filepath, Path(update.filepath).name),
                    })

            # Phase 4 — On any failure, restore EVERY backed-up file — including
            # the one whose save raised, which may have been left half-written
            # (write_metadata restores in that case too, #5307). Otherwise
            # delete the backups; either way none is left behind.
            rolled_back = False
            if any_failed and backups:
                for filepath, backup_path in backups.items():
                    self.backup_manager.restore_backup(filepath, backup_path)
                rolled_back = True
                # Mark previously-succeeded items as rolled back.
                per_file_results = [
                    {**r, 'success': False, 'rolled_back': True} if r.get('success') else r
                    for r in per_file_results
                ]
            else:
                for backup_path in backups.values():
                    self.backup_manager.cleanup_backup(backup_path)

        successful = sum(1 for r in per_file_results if r.get('success'))
        failed = total - successful

        info(f"Batch update: {successful}/{total} successful, rolled_back={rolled_back}")
        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'results': per_file_results,
            'rolled_back': rolled_back,
        }
