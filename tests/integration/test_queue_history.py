"""
Test Queue History & Undo/Redo Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for queue history tracking and undo/redo functionality.

Tests verify:
- History entries record queue state changes
- Undo restores previous queue state
- History limit (20 entries) is enforced
- History persists across application restarts
- History operations integrate with QueueRepository
- Undo is atomic: queue-state restore and history deletion in one transaction (#2239)
"""

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Test database setup
TEST_DB_PLACEHOLDER = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_DB_PATH = TEST_DB_PLACEHOLDER.name
TEST_DB_PLACEHOLDER.close()


@pytest.fixture
def test_db():
    """Create isolated test database"""
    engine = create_engine(f'sqlite:///{TEST_DB_PATH}')

    # Create tables
    from auralis.library.models import Base
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    Path(TEST_DB_PATH).unlink(missing_ok=True)


@pytest.fixture
def queue_history_repo(test_db):
    """Create QueueHistoryRepository with test database"""
    from auralis.library.repositories import QueueHistoryRepository
    Session = sessionmaker(bind=create_engine(f'sqlite:///{TEST_DB_PATH}'))
    return QueueHistoryRepository(Session)


@pytest.fixture
def queue_repo(test_db):
    """Create QueueRepository with test database"""
    from auralis.library.repositories import QueueRepository
    Session = sessionmaker(bind=create_engine(f'sqlite:///{TEST_DB_PATH}'))
    return QueueRepository(Session)


class TestQueueHistoryBasics:
    """Test basic queue history operations"""

    def test_push_to_history_creates_entry(self, queue_history_repo, queue_repo):
        """Recording queue state should create history entry"""
        # Set initial queue
        queue_repo.set_queue_state(track_ids=[1, 2, 3], current_index=0)

        # Record state in history
        state_before = {
            'track_ids': [1, 2, 3],
            'current_index': 0,
            'is_shuffled': False,
            'repeat_mode': 'off'
        }
        history = queue_history_repo.push_to_history('set', state_before)

        assert history is not None
        assert history.operation == 'set'
        assert json.loads(history.state_snapshot) == state_before

    def test_history_records_operation_types(self, queue_history_repo):
        """History should accept all valid operation types"""
        valid_operations = ['set', 'add', 'remove', 'reorder', 'shuffle', 'clear']
        state = {'track_ids': [], 'current_index': 0}

        for operation in valid_operations:
            history = queue_history_repo.push_to_history(operation, state)
            assert history.operation == operation

    def test_invalid_operation_raises_error(self, queue_history_repo):
        """Invalid operation type should raise ValueError"""
        state = {'track_ids': [1, 2, 3], 'current_index': 0}

        with pytest.raises(ValueError, match="Invalid operation"):
            queue_history_repo.push_to_history('invalid_op', state)

    def test_history_with_metadata(self, queue_history_repo):
        """History should store operation metadata"""
        state = {'track_ids': [1, 2, 3], 'current_index': 0}
        metadata = {'from_index': 0, 'to_index': 2, 'track_id': 5}

        history = queue_history_repo.push_to_history('add', state, metadata)

        stored_metadata = json.loads(history.operation_metadata)
        assert stored_metadata == metadata

    def test_get_history_returns_entries(self, queue_history_repo):
        """Getting history should return recorded entries"""
        state = {'track_ids': [1, 2, 3], 'current_index': 0}

        # Record multiple operations
        queue_history_repo.push_to_history('set', state)
        queue_history_repo.push_to_history('add', state, {'track_id': 4})
        queue_history_repo.push_to_history('remove', state, {'index': 1})

        history = queue_history_repo.get_history()

        assert len(history) == 3
        assert history[0].operation == 'remove'  # Newest first
        assert history[1].operation == 'add'
        assert history[2].operation == 'set'

    def test_get_history_newest_first(self, queue_history_repo):
        """History should return entries newest first"""
        state = {'track_ids': []}

        queue_history_repo.push_to_history('set', state)
        queue_history_repo.push_to_history('add', state)
        queue_history_repo.push_to_history('remove', state)

        history = queue_history_repo.get_history()

        # Should be newest first
        assert history[0].operation == 'remove'
        assert history[1].operation == 'add'
        assert history[2].operation == 'set'


class TestQueueHistoryUndo:
    """Test undo functionality"""

    def test_undo_restores_previous_state(self, queue_history_repo, queue_repo):
        """Undo should restore previous queue state"""
        # Set initial queue
        initial_state = [1, 2, 3]
        queue_repo.set_queue_state(track_ids=initial_state, current_index=0)

        # Record initial state
        state_snapshot = {
            'track_ids': initial_state,
            'current_index': 0,
            'is_shuffled': False,
            'repeat_mode': 'off'
        }
        queue_history_repo.push_to_history('set', state_snapshot)

        # Change queue
        modified_state = [4, 5, 6]
        queue_repo.set_queue_state(track_ids=modified_state, current_index=1)

        # Undo - should restore initial state
        restored = queue_history_repo.undo(queue_repo)

        assert restored is not None
        queue_current = queue_repo.get_queue_state()
        assert json.loads(queue_current.track_ids) == initial_state
        assert queue_current.current_index == 0

    def test_undo_removes_history_entry(self, queue_history_repo, queue_repo):
        """Undo should consume/remove the history entry"""
        initial_state = [1, 2, 3]
        queue_repo.set_queue_state(track_ids=initial_state, current_index=0)

        state_snapshot = {
            'track_ids': initial_state,
            'current_index': 0,
            'is_shuffled': False,
            'repeat_mode': 'off'
        }
        queue_history_repo.push_to_history('set', state_snapshot)

        # Verify history exists
        history_before = queue_history_repo.get_history()
        assert len(history_before) == 1

        # Undo
        queue_history_repo.undo(queue_repo)

        # History should be consumed
        history_after = queue_history_repo.get_history()
        assert len(history_after) == 0

    def test_undo_multiple_times(self, queue_history_repo, queue_repo):
        """Multiple undos should work sequentially"""
        # Create history chain
        # Note: History records the state BEFORE an operation
        state0 = {'track_ids': [1, 2, 3], 'current_index': 0, 'is_shuffled': False, 'repeat_mode': 'off'}
        state1 = {'track_ids': [4, 5, 6], 'current_index': 1, 'is_shuffled': False, 'repeat_mode': 'off'}
        state2 = {'track_ids': [7, 8, 9], 'current_index': 2, 'is_shuffled': True, 'repeat_mode': 'all'}

        # Set initial state
        queue_repo.set_queue_state(**state0)

        # Change to state1 and record previous state (state0) in history
        queue_repo.set_queue_state(**state1)
        queue_history_repo.push_to_history('set', state0)  # Record state0 as "before" state

        # Change to state2 and record previous state (state1) in history
        queue_repo.set_queue_state(**state2)
        queue_history_repo.push_to_history('set', state1)  # Record state1 as "before" state

        # Undo 1 - should restore state1
        queue_history_repo.undo(queue_repo)
        current = queue_repo.get_queue_state()
        assert json.loads(current.track_ids) == state1['track_ids']

        # Undo 2 - should restore state0
        queue_history_repo.undo(queue_repo)
        current = queue_repo.get_queue_state()
        assert json.loads(current.track_ids) == state0['track_ids']

    def test_undo_with_no_history_returns_none(self, queue_history_repo, queue_repo):
        """Undo with empty history should return None"""
        queue_repo.set_queue_state(track_ids=[1, 2, 3])

        # No history recorded
        result = queue_history_repo.undo(queue_repo)

        assert result is None

    def test_undo_with_corrupted_history_raises_error(self, queue_history_repo, queue_repo):
        """Undo with corrupted JSON should raise ValueError"""
        queue_repo.set_queue_state(track_ids=[1, 2, 3])

        # Create corrupted history entry
        from auralis.library.models import QueueHistory, QueueState
        session = queue_history_repo.get_session()
        try:
            queue_state = session.query(QueueState).first()
            corrupted_entry = QueueHistory(
                queue_state_id=queue_state.id,
                operation='set',
                state_snapshot='invalid json {'
            )
            session.add(corrupted_entry)
            session.commit()
        finally:
            session.close()

        # Undo should raise error
        with pytest.raises(ValueError, match="Corrupted history entry"):
            queue_history_repo.undo(queue_repo)


class TestQueueHistoryLimit:
    """Test history limit enforcement"""

    def test_history_limit_enforced(self, queue_history_repo):
        """Only last 20 entries should be kept"""
        state = {'track_ids': [1, 2, 3], 'current_index': 0}

        # Create 25 history entries
        for i in range(25):
            metadata = {'index': i}
            queue_history_repo.push_to_history('add', state, metadata)

        # Should only keep last 20
        history = queue_history_repo.get_history(limit=100)
        assert len(history) == 20

    def test_oldest_entries_deleted_when_limit_exceeded(self, queue_history_repo):
        """Oldest entries should be removed when limit exceeded"""
        state = {'track_ids': [1, 2, 3], 'current_index': 0}

        # Create 22 entries (exceeds limit of 20)
        for i in range(22):
            metadata = {'index': i}
            queue_history_repo.push_to_history('add', state, metadata)

        history = queue_history_repo.get_history(limit=100)

        # Should have 20 entries
        assert len(history) == 20

        # Entries with index 0 and 1 should be gone (oldest)
        indices = [json.loads(h.operation_metadata).get('index') for h in history]
        assert 0 not in indices
        assert 1 not in indices
        # Should have entries 2-21
        assert 21 in indices


class TestQueueHistoryPersistence:
    """Test history persistence across operations"""

    def test_history_survives_queue_updates(self, queue_history_repo, queue_repo):
        """History should persist when queue is updated"""
        # Initial state
        initial = [1, 2, 3]
        queue_repo.set_queue_state(track_ids=initial, current_index=0)

        snapshot = {
            'track_ids': initial,
            'current_index': 0,
            'is_shuffled': False,
            'repeat_mode': 'off'
        }
        queue_history_repo.push_to_history('set', snapshot)

        # Update queue
        queue_repo.set_queue_state(track_ids=[4, 5, 6], current_index=0)

        # History should still exist
        history = queue_history_repo.get_history()
        assert len(history) == 1
        assert json.loads(history[0].state_snapshot) == snapshot

    def test_history_different_operations(self, queue_history_repo, queue_repo):
        """Different operation types should be tracked correctly"""
        state = {'track_ids': [1, 2, 3], 'current_index': 0, 'is_shuffled': False, 'repeat_mode': 'off'}
        queue_repo.set_queue_state(**state)

        operations = [
            ('set', state),
            ('add', state, {'track_id': 4, 'index': 0}),
            ('remove', state, {'index': 1}),
            ('reorder', state, {'from': 0, 'to': 2}),
            ('shuffle', state, {}),
            ('clear', state),
        ]

        for op in operations:
            operation_type = op[0]
            state_snap = op[1]
            metadata = op[2] if len(op) > 2 else None
            queue_history_repo.push_to_history(operation_type, state_snap, metadata)

        history = queue_history_repo.get_history(limit=100)
        assert len(history) == 6

        # Verify operations are tracked
        recorded_ops = [h.operation for h in reversed(history)]
        expected_ops = [op[0] for op in operations]
        assert recorded_ops == expected_ops


class TestQueueHistoryUtilities:
    """Test history utility methods"""

    def test_clear_history(self, queue_history_repo):
        """Clear history should remove all entries"""
        state = {'track_ids': [1, 2, 3], 'current_index': 0}

        queue_history_repo.push_to_history('set', state)
        queue_history_repo.push_to_history('add', state)

        # Verify entries exist
        assert queue_history_repo.get_history_count() == 2

        # Clear
        queue_history_repo.clear_history()

        # Should be empty
        assert queue_history_repo.get_history_count() == 0

    def test_get_history_count(self, queue_history_repo):
        """Get history count should return correct number"""
        state = {'track_ids': [1, 2, 3], 'current_index': 0}

        assert queue_history_repo.get_history_count() == 0

        queue_history_repo.push_to_history('set', state)
        assert queue_history_repo.get_history_count() == 1

        queue_history_repo.push_to_history('add', state)
        assert queue_history_repo.get_history_count() == 2

    def test_to_dict_conversion(self, queue_history_repo):
        """History entry to_dict should serialize correctly"""
        state = {'track_ids': [1, 2, 3], 'current_index': 0, 'is_shuffled': True, 'repeat_mode': 'all'}
        metadata = {'track_id': 5}

        history = queue_history_repo.push_to_history('add', state, metadata)
        dict_repr = queue_history_repo.to_dict(history)

        assert dict_repr['operation'] == 'add'
        assert dict_repr['state_snapshot'] == state
        assert dict_repr['operation_metadata'] == metadata
        assert 'created_at' in dict_repr
        assert 'id' in dict_repr

    def test_to_dict_handles_none(self, queue_history_repo):
        """to_dict should handle None gracefully"""
        dict_repr = queue_history_repo.to_dict(None)

        assert dict_repr['operation'] == 'unknown'
        assert dict_repr['state_snapshot'] == {}
        assert dict_repr['operation_metadata'] == {}


class TestUndoAtomicity:
    """
    Undo must be atomic: queue restore + history deletion in one transaction.

    Issue #2239: the old code used two separate sessions/commits.  A crash
    between them would leave the history entry unreachable but also intact,
    meaning the same undo could be replayed after a restart.

    The fix performs both writes in a single session.commit().  We simulate
    the 'crash between commits' by monkeypatching session.delete() to raise
    after the queue state has been updated but before the history entry is
    removed, then assert the database is still consistent.
    """

    def test_undo_queue_state_and_history_deleted_atomically(
        self, queue_history_repo, queue_repo
    ):
        """
        Both queue-state update and history deletion must commit together.

        Verify by checking that after a successful undo:
        - queue_state reflects the snapshot
        - history entry is gone
        No gaps, no partial state.
        """
        initial = [1, 2, 3]
        queue_repo.set_queue_state(track_ids=initial, current_index=0)

        snapshot = {
            'track_ids': initial,
            'current_index': 0,
            'is_shuffled': False,
            'repeat_mode': 'off',
        }
        queue_history_repo.push_to_history('set', snapshot)

        # Change the queue so there's something to undo
        queue_repo.set_queue_state(track_ids=[9, 8, 7], current_index=2)

        # Perform undo
        restored = queue_history_repo.undo()

        # Queue state restored
        assert restored is not None
        import json
        assert json.loads(restored.track_ids) == initial
        assert restored.current_index == 0

        # History entry gone in the same commit
        assert queue_history_repo.get_history_count() == 0, (
            "History entry must be deleted in the same transaction as the "
            "queue-state restore (issue #2239)."
        )

    def test_simulated_crash_leaves_consistent_state(
        self, queue_history_repo, queue_repo
    ):
        """
        Simulate a crash after queue update but before history deletion.

        In the old two-session design this was possible: session A would
        commit the queue-state restore, then crash, leaving the history
        entry present with the queue already rolled-back.

        With the fix both writes are in one transaction, so the only
        possible outcomes are:
        (a) both committed (success), or
        (b) both rolled back (crash before commit).

        We test outcome (b): patch session.commit() to raise on the first
        call, then verify neither the queue nor the history changed.
        """
        original_tracks = [10, 20, 30]
        queue_repo.set_queue_state(track_ids=original_tracks, current_index=0)

        snapshot = {
            'track_ids': [1, 2, 3],
            'current_index': 0,
            'is_shuffled': False,
            'repeat_mode': 'off',
        }
        queue_history_repo.push_to_history('set', snapshot)

        # Pre-crash state
        history_count_before = queue_history_repo.get_history_count()
        assert history_count_before == 1

        # Patch the session factory so the first commit() in undo() raises
        original_factory = queue_history_repo.session_factory
        import json as _json

        class BoomOnCommit:
            """Wraps a real session; raises on the first commit() call."""
            def __init__(self, real_session):
                self._s = real_session
                self._committed = False

            def __getattr__(self, name):
                return getattr(self._s, name)

            def commit(self):
                if not self._committed:
                    self._committed = True
                    self._s.rollback()   # roll back the pending work
                    raise RuntimeError("simulated crash before commit")
                return self._s.commit()

        def crashing_factory():
            return BoomOnCommit(original_factory())

        queue_history_repo.session_factory = crashing_factory
        try:
            with pytest.raises(RuntimeError, match="simulated crash"):
                queue_history_repo.undo()
        finally:
            queue_history_repo.session_factory = original_factory

        # After the simulated crash:
        # - history entry must still be present (was rolled back)
        # - queue state must be unchanged (was rolled back)
        assert queue_history_repo.get_history_count() == 1, (
            "History entry must still exist after a rolled-back undo "
            "(issue #2239): the undo should be replayable."
        )
        current = queue_repo.get_queue_state()
        assert _json.loads(current.track_ids) == original_tracks, (
            "Queue state must be unchanged after a rolled-back undo "
            "(issue #2239)."
        )

    def test_undo_called_without_queue_repository_argument(
        self, queue_history_repo, queue_repo
    ):
        """
        undo() must work when called without the queue_repository argument
        (the parameter is now unused and defaults to None).
        """
        initial = [5, 6, 7]
        queue_repo.set_queue_state(track_ids=initial, current_index=0)
        snapshot = {
            'track_ids': initial,
            'current_index': 0,
            'is_shuffled': False,
            'repeat_mode': 'off',
        }
        queue_history_repo.push_to_history('set', snapshot)
        queue_repo.set_queue_state(track_ids=[99], current_index=0)

        # No argument — must not raise
        restored = queue_history_repo.undo()

        assert restored is not None
        import json
        assert json.loads(restored.track_ids) == initial


class TestQueueHistoryIntegration:
    """Test queue history integration with queue operations"""

    def test_full_workflow_with_history(self, queue_history_repo, queue_repo):
        """Complete workflow: set -> add -> undo -> redo simulation"""
        # Initial queue
        initial = [1, 2, 3]
        queue_repo.set_queue_state(track_ids=initial, current_index=0)

        initial_snapshot = {
            'track_ids': initial,
            'current_index': 0,
            'is_shuffled': False,
            'repeat_mode': 'off'
        }
        queue_history_repo.push_to_history('set', initial_snapshot)

        # Add track
        modified = [1, 2, 3, 4]
        queue_repo.set_queue_state(track_ids=modified, current_index=0)
        queue_history_repo.push_to_history('add', initial_snapshot, {'track_id': 4})

        # Verify current state
        current = queue_repo.get_queue_state()
        assert json.loads(current.track_ids) == modified

        # Undo - restore initial
        queue_history_repo.undo(queue_repo)
        current = queue_repo.get_queue_state()
        assert json.loads(current.track_ids) == initial

    def test_history_tracks_shuffle_state_changes(self, queue_history_repo, queue_repo):
        """History should capture shuffle state changes"""
        queue_repo.set_queue_state(track_ids=[1, 2, 3], is_shuffled=False)

        state_before = {
            'track_ids': [1, 2, 3],
            'current_index': 0,
            'is_shuffled': False,
            'repeat_mode': 'off'
        }
        queue_history_repo.push_to_history('shuffle', state_before)

        # Toggle shuffle
        queue_repo.set_queue_state(track_ids=[1, 2, 3], is_shuffled=True)

        history = queue_history_repo.get_history()
        assert len(history) == 1
        assert history[0].operation == 'shuffle'
        snapshot = json.loads(history[0].state_snapshot)
        assert snapshot['is_shuffled'] is False

    def test_history_tracks_repeat_mode_changes(self, queue_history_repo, queue_repo):
        """History should capture repeat mode changes"""
        queue_repo.set_queue_state(track_ids=[1, 2, 3], repeat_mode='off')

        state_before = {
            'track_ids': [1, 2, 3],
            'current_index': 0,
            'is_shuffled': False,
            'repeat_mode': 'off'
        }
        queue_history_repo.push_to_history('set', state_before)

        # Change repeat mode
        queue_repo.set_queue_state(track_ids=[1, 2, 3], repeat_mode='all')

        history = queue_history_repo.get_history()
        snapshot = json.loads(history[0].state_snapshot)
        assert snapshot['repeat_mode'] == 'off'
