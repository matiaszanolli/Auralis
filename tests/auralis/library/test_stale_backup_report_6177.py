"""
Orphaned metadata-edit backups are reported by the scan, never deleted (#6177)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A crash between BackupManager.create_backup and its cleanup leaves a full-size hidden
``.<name>.XXXXXXXX.bak`` in the music folder. It is the pre-edit copy of the user's own track, so
the scan lists it in ScanResult.stale_backups and leaves it alone.
"""

import os
import time

import pytest

from auralis.library.metadata_editor.backup import BackupManager
from auralis.library.scan_models import ScanResult
from auralis.library.scanner.file_discovery import FileDiscovery
from auralis.library.scanner.stale_backups import STALE_BACKUP_AGE_S


def _age(path, seconds):
    past = time.time() - seconds
    os.utime(path, (past, past))


def _walk(root):
    result = ScanResult()
    discovery = FileDiscovery()
    discovery.on_stale_backup = result.record_stale_backup
    files = list(discovery.discover_audio_files(str(root)))
    return result, files


def test_a_real_orphaned_backup_is_reported_and_left_in_place(tmp_path):
    track = tmp_path / "song.mp3"
    track.write_bytes(b"audio")
    backup = BackupManager.create_backup(str(track))  # what a crashed edit leaves behind
    _age(backup, STALE_BACKUP_AGE_S + 60)

    result, files = _walk(tmp_path)

    assert result.stale_backups == [backup]
    assert os.path.exists(backup), "the scan must not delete a pre-edit copy"
    assert files == [str(track)]  # the backup is not mistaken for audio


def test_a_young_backup_is_a_live_edit_and_not_reported(tmp_path):
    track = tmp_path / "song.mp3"
    track.write_bytes(b"audio")
    BackupManager.create_backup(str(track))

    result, _ = _walk(tmp_path)

    assert result.stale_backups == []


@pytest.mark.parametrize("name", ["song.bak", ".hidden.bak", ".song.mp3.bak", "backup.AAAAAAAA.bak"])
def test_other_bak_files_are_not_ours(tmp_path, name):
    other = tmp_path / name
    other.write_bytes(b"x")
    _age(str(other), STALE_BACKUP_AGE_S + 60)

    result, _ = _walk(tmp_path)

    assert result.stale_backups == []


def test_a_second_walk_does_not_duplicate_the_report(tmp_path):
    track = tmp_path / "song.mp3"
    track.write_bytes(b"audio")
    backup = BackupManager.create_backup(str(track))
    _age(backup, STALE_BACKUP_AGE_S + 60)
    result = ScanResult()
    discovery = FileDiscovery()
    discovery.on_stale_backup = result.record_stale_backup

    list(discovery.discover_audio_files(str(tmp_path)))
    list(discovery.discover_audio_files(str(tmp_path)))  # the counting pass and the scan pass

    assert result.stale_backups == [backup]
