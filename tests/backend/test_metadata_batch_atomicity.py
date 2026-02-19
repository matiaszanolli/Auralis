"""
Tests for batch metadata update atomicity (#2325)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that MetadataEditor.batch_update() and the /api/metadata/batch
endpoint honour the atomic-rollback contract:

- Per-file success/failure status is returned for every track
- When backup=True and any write fails, all already-applied files are
  restored from their backups (rolled_back=True in response)
- When backup=False the batch is best-effort; no rollback is possible
- Pre-validation prevents touching any file when one is missing
- Backup creation failure aborts the whole batch before any write
- The router skips DB updates when rolled_back=True
- The router "success" field reflects actual outcome (not hard-coded True)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.metadata_editor import MetadataEditor, MetadataUpdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_editor():
    """Return a MetadataEditor with a real BackupManager (mocked methods)."""
    editor = MetadataEditor()
    return editor


def make_updates(n: int, backup: bool = True) -> list[MetadataUpdate]:
    return [
        MetadataUpdate(
            track_id=i + 1,
            filepath=f'/fake/track{i + 1}.mp3',
            updates={'title': f'Title {i + 1}'},
            backup=backup,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Unit tests: MetadataEditor.batch_update()
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not __import__('auralis.library.metadata_editor', fromlist=['MUTAGEN_AVAILABLE']).MUTAGEN_AVAILABLE,
    reason="mutagen not installed"
)
class TestBatchUpdateAtomicity:
    """batch_update() atomic rollback contract."""

    def test_all_success_returns_correct_counts(self):
        editor = make_editor()
        updates = make_updates(3)

        with patch('os.path.exists', return_value=True), \
             patch.object(editor.backup_manager, 'create_backup', return_value=True), \
             patch.object(editor.backup_manager, 'cleanup_backup', return_value=True), \
             patch.object(editor, 'write_metadata', return_value=True):
            result = editor.batch_update(updates)

        assert result['total'] == 3
        assert result['successful'] == 3
        assert result['failed'] == 0
        assert result['rolled_back'] is False

    def test_all_success_per_file_results_are_success(self):
        editor = make_editor()
        updates = make_updates(3)

        with patch('os.path.exists', return_value=True), \
             patch.object(editor.backup_manager, 'create_backup', return_value=True), \
             patch.object(editor.backup_manager, 'cleanup_backup', return_value=True), \
             patch.object(editor, 'write_metadata', return_value=True):
            result = editor.batch_update(updates)

        assert all(r['success'] for r in result['results'])
        assert {r['track_id'] for r in result['results']} == {1, 2, 3}

    def test_all_success_cleans_up_backups(self):
        editor = make_editor()
        updates = make_updates(3)

        with patch('os.path.exists', return_value=True), \
             patch.object(editor.backup_manager, 'create_backup', return_value=True), \
             patch.object(editor.backup_manager, 'cleanup_backup', return_value=True) as mock_cleanup, \
             patch.object(editor, 'write_metadata', return_value=True):
            editor.batch_update(updates)

        assert mock_cleanup.call_count == 3

    def test_middle_failure_triggers_rollback(self):
        """When file 2-of-3 fails, file 1 must be restored."""
        editor = make_editor()
        updates = make_updates(3)

        def _write(filepath, metadata, backup=True):
            if 'track2' in filepath:
                raise OSError("Disk full")
            return True

        with patch('os.path.exists', return_value=True), \
             patch.object(editor.backup_manager, 'create_backup', return_value=True), \
             patch.object(editor.backup_manager, 'restore_backup', return_value=True) as mock_restore, \
             patch.object(editor, 'write_metadata', side_effect=_write):
            result = editor.batch_update(updates)

        assert result['rolled_back'] is True
        assert result['successful'] == 0   # all rolled back
        assert result['failed'] == 3

        # track1 was applied then restored
        restored_paths = {c.args[0] for c in mock_restore.call_args_list}
        assert '/fake/track1.mp3' in restored_paths

    def test_rollback_marks_all_results_failed(self):
        """After rollback, every per-file result must show success=False."""
        editor = make_editor()
        updates = make_updates(3)

        def _write(filepath, metadata, backup=True):
            if 'track3' in filepath:
                raise RuntimeError("Write error")
            return True

        with patch('os.path.exists', return_value=True), \
             patch.object(editor.backup_manager, 'create_backup', return_value=True), \
             patch.object(editor.backup_manager, 'restore_backup', return_value=True), \
             patch.object(editor, 'write_metadata', side_effect=_write):
            result = editor.batch_update(updates)

        assert all(not r.get('success') for r in result['results'])

    def test_rolled_back_items_carry_rolled_back_flag(self):
        """Items that succeeded before rollback should expose rolled_back=True."""
        editor = make_editor()
        updates = make_updates(2)

        def _write(filepath, metadata, backup=True):
            if 'track2' in filepath:
                raise OSError("Error")
            return True

        with patch('os.path.exists', return_value=True), \
             patch.object(editor.backup_manager, 'create_backup', return_value=True), \
             patch.object(editor.backup_manager, 'restore_backup', return_value=True), \
             patch.object(editor, 'write_metadata', side_effect=_write):
            result = editor.batch_update(updates)

        track1_result = next(r for r in result['results'] if r['track_id'] == 1)
        assert track1_result.get('rolled_back') is True

    def test_failure_error_message_preserved_in_results(self):
        """The per-file result for the failing track includes the error text."""
        editor = make_editor()
        updates = make_updates(2)

        def _write(filepath, metadata, backup=True):
            if 'track2' in filepath:
                raise ValueError("corrupt header")
            return True

        with patch('os.path.exists', return_value=True), \
             patch.object(editor.backup_manager, 'create_backup', return_value=True), \
             patch.object(editor.backup_manager, 'restore_backup', return_value=True), \
             patch.object(editor, 'write_metadata', side_effect=_write):
            result = editor.batch_update(updates)

        track2 = next(r for r in result['results'] if r['track_id'] == 2)
        assert 'corrupt header' in track2['error']

    def test_no_rollback_when_backup_false(self):
        """backup=False batches are best-effort: no rollback on failure."""
        editor = make_editor()
        updates = make_updates(2, backup=False)

        def _write(filepath, metadata, backup=True):
            if 'track2' in filepath:
                raise OSError("Error")
            return True

        with patch('os.path.exists', return_value=True), \
             patch.object(editor.backup_manager, 'restore_backup', return_value=True) as mock_restore, \
             patch.object(editor, 'write_metadata', side_effect=_write):
            result = editor.batch_update(updates)

        assert result['rolled_back'] is False
        mock_restore.assert_not_called()

    def test_no_rollback_when_backup_false_partial_success_reported(self):
        """Without backup, the per-file results show the actual outcome."""
        editor = make_editor()
        updates = make_updates(2, backup=False)

        def _write(filepath, metadata, backup=True):
            if 'track2' in filepath:
                raise OSError("Error")
            return True

        with patch('os.path.exists', return_value=True), \
             patch.object(editor, 'write_metadata', side_effect=_write):
            result = editor.batch_update(updates)

        assert result['successful'] == 1   # track1 committed
        assert result['failed'] == 1       # track2 failed

    def test_prevalidation_fails_fast_on_missing_file(self):
        """If one file is missing, no writes happen at all."""
        editor = make_editor()
        updates = make_updates(3)

        def _exists(path):
            return 'track2' not in path  # track2 is missing

        with patch('os.path.exists', side_effect=_exists), \
             patch.object(editor, 'write_metadata', return_value=True) as mock_write:
            result = editor.batch_update(updates)

        mock_write.assert_not_called()
        assert result['successful'] == 0
        assert result['failed'] == 3
        assert result['rolled_back'] is False

    def test_backup_failure_aborts_before_any_write(self):
        """If backing up file 2 fails, no writes are attempted."""
        editor = make_editor()
        updates = make_updates(3)

        def _backup(filepath):
            return 'track2' not in filepath  # backup of track2 fails

        with patch('os.path.exists', return_value=True), \
             patch.object(editor.backup_manager, 'create_backup', side_effect=_backup), \
             patch.object(editor.backup_manager, 'cleanup_backup', return_value=True), \
             patch.object(editor, 'write_metadata', return_value=True) as mock_write:
            result = editor.batch_update(updates)

        mock_write.assert_not_called()
        assert result['successful'] == 0
        assert result['failed'] == 3

    def test_backup_failure_cleans_up_earlier_backups(self):
        """When backup of file N fails, backups of files 1…N-1 are removed."""
        editor = make_editor()
        updates = make_updates(3)

        backed_up = []

        def _backup(filepath):
            if 'track3' in filepath:
                return False
            backed_up.append(filepath)
            return True

        with patch('os.path.exists', return_value=True), \
             patch.object(editor.backup_manager, 'create_backup', side_effect=_backup), \
             patch.object(editor.backup_manager, 'cleanup_backup', return_value=True) as mock_cleanup, \
             patch.object(editor, 'write_metadata', return_value=True):
            editor.batch_update(updates)

        cleaned = {c.args[0] for c in mock_cleanup.call_args_list}
        for path in backed_up:
            assert path in cleaned

    def test_empty_batch_returns_zeros(self):
        editor = make_editor()
        result = editor.batch_update([])

        assert result == {
            'total': 0, 'successful': 0, 'failed': 0,
            'results': [], 'rolled_back': False,
        }

    def test_first_file_failing_is_not_restored(self):
        """If the first (and only) file fails, nothing was applied → no restore."""
        editor = make_editor()
        updates = make_updates(1)

        with patch('os.path.exists', return_value=True), \
             patch.object(editor.backup_manager, 'create_backup', return_value=True), \
             patch.object(editor.backup_manager, 'restore_backup', return_value=True) as mock_restore, \
             patch.object(editor, 'write_metadata', side_effect=OSError("Error")):
            result = editor.batch_update(updates)

        # Nothing was applied, so nothing to restore
        mock_restore.assert_not_called()
        assert result['rolled_back'] is True  # flag still set
        assert result['failed'] == 1


# ---------------------------------------------------------------------------
# Router-level tests: /api/metadata/batch endpoint
# Uses the full app client + patch pattern (avoids circular import via __init__)
# ---------------------------------------------------------------------------

def _batch_track(tid: int) -> Mock:
    t = Mock()
    t.id = tid
    t.filepath = f'/fake/track{tid}.mp3'
    return t


class TestBatchEndpointAtomicity:
    """/api/metadata/batch endpoint correctly surfaces rolled_back."""

    @patch('routers.metadata.require_repository_factory')
    @patch('auralis.library.metadata_editor.MetadataEditor.batch_update')
    def test_success_response_has_success_true(
        self, mock_batch, mock_repos_fn, client
    ):
        mock_repos = Mock()
        mock_repos.tracks.get_by_id.side_effect = _batch_track
        mock_repos.tracks.update_metadata.return_value = Mock()
        mock_repos_fn.return_value = mock_repos

        mock_batch.return_value = {
            'total': 2, 'successful': 2, 'failed': 0,
            'results': [
                {'track_id': 1, 'filepath': '/f/t1.mp3', 'success': True, 'updates': {'title': 'T1'}},
                {'track_id': 2, 'filepath': '/f/t2.mp3', 'success': True, 'updates': {'title': 'T2'}},
            ],
            'rolled_back': False,
        }

        resp = client.post("/api/metadata/batch", json={
            "updates": [
                {"track_id": 1, "metadata": {"title": "T1"}},
                {"track_id": 2, "metadata": {"title": "T2"}},
            ]
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['rolled_back'] is False

    @patch('routers.metadata.require_repository_factory')
    @patch('auralis.library.metadata_editor.MetadataEditor.batch_update')
    def test_partial_failure_response_has_success_false(
        self, mock_batch, mock_repos_fn, client
    ):
        mock_repos = Mock()
        mock_repos.tracks.get_by_id.side_effect = _batch_track
        mock_repos_fn.return_value = mock_repos

        mock_batch.return_value = {
            'total': 2, 'successful': 0, 'failed': 2,
            'results': [
                {'track_id': 1, 'success': False, 'rolled_back': True},
                {'track_id': 2, 'success': False, 'error': 'Disk full'},
            ],
            'rolled_back': True,
        }

        resp = client.post("/api/metadata/batch", json={
            "updates": [
                {"track_id": 1, "metadata": {"title": "T1"}},
                {"track_id": 2, "metadata": {"title": "T2"}},
            ]
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is False
        assert data['rolled_back'] is True

    @patch('routers.metadata.require_repository_factory')
    @patch('auralis.library.metadata_editor.MetadataEditor.batch_update')
    def test_rolled_back_response_skips_db_updates(
        self, mock_batch, mock_repos_fn, client
    ):
        """When rolled_back=True no DB update calls should be made."""
        mock_repos = Mock()
        mock_repos.tracks.get_by_id.side_effect = _batch_track
        mock_repos_fn.return_value = mock_repos

        mock_batch.return_value = {
            'total': 2, 'successful': 0, 'failed': 2,
            'results': [
                {'track_id': 1, 'success': False, 'rolled_back': True},
                {'track_id': 2, 'success': False, 'error': 'Disk full'},
            ],
            'rolled_back': True,
        }

        client.post("/api/metadata/batch", json={
            "updates": [
                {"track_id": 1, "metadata": {"title": "T1"}},
                {"track_id": 2, "metadata": {"title": "T2"}},
            ]
        })

        mock_repos.tracks.update_metadata.assert_not_called()

    @patch('routers.metadata.require_repository_factory')
    @patch('auralis.library.metadata_editor.MetadataEditor.batch_update')
    def test_no_rollback_response_updates_db_for_successful_tracks(
        self, mock_batch, mock_repos_fn, client
    ):
        mock_repos = Mock()
        mock_repos.tracks.get_by_id.side_effect = _batch_track
        mock_repos.tracks.update_metadata.return_value = Mock()
        mock_repos_fn.return_value = mock_repos

        mock_batch.return_value = {
            'total': 2, 'successful': 2, 'failed': 0,
            'results': [
                {'track_id': 1, 'success': True, 'updates': {'title': 'T1'}},
                {'track_id': 2, 'success': True, 'updates': {'title': 'T2'}},
            ],
            'rolled_back': False,
        }

        client.post("/api/metadata/batch", json={
            "updates": [
                {"track_id": 1, "metadata": {"title": "T1"}},
                {"track_id": 2, "metadata": {"title": "T2"}},
            ]
        })

        assert mock_repos.tracks.update_metadata.call_count == 2

    @patch('routers.metadata.require_repository_factory')
    @patch('auralis.library.metadata_editor.MetadataEditor.batch_update')
    def test_response_includes_per_file_results(
        self, mock_batch, mock_repos_fn, client
    ):
        mock_repos = Mock()
        mock_repos.tracks.get_by_id.side_effect = _batch_track
        mock_repos_fn.return_value = mock_repos

        mock_batch.return_value = {
            'total': 1, 'successful': 0, 'failed': 1,
            'results': [
                {'track_id': 1, 'success': False, 'error': 'Write failed'},
            ],
            'rolled_back': True,
        }

        resp = client.post("/api/metadata/batch", json={
            "updates": [{"track_id": 1, "metadata": {"title": "X"}}]
        })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data['results']) == 1
        assert data['results'][0]['track_id'] == 1
        assert data['results'][0]['success'] is False

    def test_empty_updates_returns_400(self, client):
        resp = client.post("/api/metadata/batch", json={"updates": []})
        assert resp.status_code == 400
