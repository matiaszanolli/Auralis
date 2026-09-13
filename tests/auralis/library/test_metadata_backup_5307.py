"""Metadata-edit backups are unique, checked, cleaned up and serialized (#5307).

The single-track write path used to back up to a fixed ``<file>.bak``, ignore
a failed backup, and never delete it — so a later failed save could restore a
stale copy from an earlier successful edit over the file. These tests drive
the real ``BackupManager`` against real files; only mutagen is faked, so a
"save" is a plain byte write the test controls.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from auralis.library.metadata_editor import MUTAGEN_AVAILABLE, MetadataEditor, MetadataUpdate
from auralis.library.metadata_editor import backup as backup_module

pytestmark = pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not installed")

_MUTAGEN_FILE = "auralis.library.metadata_editor.metadata_editor.MutagenFile"


def _editor() -> MetadataEditor:
    editor = MetadataEditor()
    editor.writers = Mock()
    return editor


def _saving(path: Path, content: bytes, fail: bool = False) -> Mock:
    """A fake mutagen file whose save() writes ``content`` (then raises if ``fail``)."""

    def _save() -> None:
        path.write_bytes(content)
        if fail:
            raise OSError("disk error mid-save")

    audio = Mock()
    audio.save.side_effect = _save
    return audio


def test_failed_backup_aborts_the_write(tmp_path: Path) -> None:
    audio = tmp_path / "track.mp3"
    audio.write_bytes(b"original")
    editor = _editor()

    with patch.object(editor.backup_manager, "create_backup", return_value=None), \
         patch.object(editor.backup_manager, "restore_backup") as restore, \
         patch(_MUTAGEN_FILE) as mutagen_file:
        with pytest.raises(OSError, match="Failed to create backup"):
            editor.write_metadata(str(audio), {"title": "B"}, backup=True)

    mutagen_file.assert_not_called()
    restore.assert_not_called()
    assert audio.read_bytes() == b"original"


def test_failed_edit_restores_its_own_pre_edit_state_not_an_earlier_one(tmp_path: Path) -> None:
    audio = tmp_path / "track.mp3"
    audio.write_bytes(b"original")
    editor = _editor()

    # Edit A succeeds and leaves no backup behind.
    with patch(_MUTAGEN_FILE, return_value=_saving(audio, b"edit-A")):
        assert editor.write_metadata(str(audio), {"title": "A"}) is True
    assert sorted(os.listdir(tmp_path)) == ["track.mp3"]

    # Edit B tears the file, then raises: restore must bring back A, not "original".
    with patch(_MUTAGEN_FILE, return_value=_saving(audio, b"torn", fail=True)):
        with pytest.raises(OSError, match="mid-save"):
            editor.write_metadata(str(audio), {"title": "B"})

    assert audio.read_bytes() == b"edit-A"
    assert sorted(os.listdir(tmp_path)) == ["track.mp3"]


def test_concurrent_writes_to_one_file_are_serialized(tmp_path: Path) -> None:
    audio = tmp_path / "track.mp3"
    audio.write_bytes(b"original")
    editor = _editor()
    active = 0
    max_active = 0
    counter_lock = threading.Lock()

    def _slow_file(_path: str) -> Mock:
        def _save() -> None:
            nonlocal active, max_active
            with counter_lock:
                active += 1
                max_active = max(max_active, active)
            name = threading.current_thread().name.encode()
            audio.write_bytes(name + b"-half")
            time.sleep(0.05)
            audio.write_bytes(name + b"-done")
            with counter_lock:
                active -= 1

        fake = Mock()
        fake.save.side_effect = _save
        return fake

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def _write() -> None:
        try:
            barrier.wait()
            editor.write_metadata(str(audio), {"title": "x"})
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
            errors.append(exc)

    with patch(_MUTAGEN_FILE, side_effect=_slow_file):
        threads = [threading.Thread(target=_write, name=f"w{i}") for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

    assert errors == []
    assert max_active == 1
    assert audio.read_bytes() in (b"w0-done", b"w1-done")
    assert sorted(os.listdir(tmp_path)) == ["track.mp3"]


def test_single_track_write_waits_for_an_in_flight_batch_on_the_same_file(tmp_path: Path) -> None:
    audio = tmp_path / "track.mp3"
    audio.write_bytes(b"original")
    editor = _editor()
    batch_saving = threading.Event()
    release_batch = threading.Event()
    single_done = threading.Event()

    def _file(_path: str) -> Mock:
        fake = Mock()
        if threading.current_thread().name == "batch":
            def _save() -> None:
                batch_saving.set()
                release_batch.wait(5)
                audio.write_bytes(b"batch")
            fake.save.side_effect = _save
        else:
            fake.save.side_effect = lambda: audio.write_bytes(b"single")
        return fake

    def _single() -> None:
        editor.write_metadata(str(audio), {"title": "single"})
        single_done.set()

    with patch(_MUTAGEN_FILE, side_effect=_file):
        batch = threading.Thread(
            target=editor.batch_update,
            args=([MetadataUpdate(1, str(audio), {"title": "batch"})],),
            name="batch",
        )
        batch.start()
        assert batch_saving.wait(5)
        single = threading.Thread(target=_single, name="single")
        single.start()
        assert not single_done.wait(0.2)  # blocked behind the batch's lock
        release_batch.set()
        batch.join(5)
        single.join(5)

    assert single_done.is_set()
    assert audio.read_bytes() == b"single"
    assert sorted(os.listdir(tmp_path)) == ["track.mp3"]


def test_batch_rollback_restores_every_file_and_leaves_no_backups(tmp_path: Path) -> None:
    first = tmp_path / "one.mp3"
    second = tmp_path / "two.mp3"
    first.write_bytes(b"one-original")
    second.write_bytes(b"two-original")
    editor = _editor()

    def _file(path: str) -> Mock:
        if path == str(first):
            return _saving(first, b"one-edited")
        return _saving(second, b"two-torn", fail=True)

    with patch(_MUTAGEN_FILE, side_effect=_file):
        result = editor.batch_update([
            MetadataUpdate(1, str(first), {"title": "1"}),
            MetadataUpdate(2, str(second), {"title": "2"}),
        ])

    assert result["rolled_back"] is True
    assert first.read_bytes() == b"one-original"
    assert second.read_bytes() == b"two-original"
    assert sorted(os.listdir(tmp_path)) == ["one.mp3", "two.mp3"]


def test_lock_registry_drops_entries_once_released(tmp_path: Path) -> None:
    path = str(tmp_path / "track.mp3")
    with backup_module.lock_files([path]):
        with backup_module.lock_files([path]):  # re-entrant on one thread
            assert os.path.realpath(path) in backup_module._file_locks
    assert os.path.realpath(path) not in backup_module._file_locks
