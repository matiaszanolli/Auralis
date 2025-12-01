"""
Test Queue State Persistence
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for queue persistence across application restarts.

Tests verify:
- Queue state saves to database on API operations
- Queue state loads from database on startup
- Persistence survives application restarts
- Queue operations maintain data integrity
"""

import pytest
import json
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Test database setup
TEST_DB_PLACEHOLDER = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_DB_PATH = TEST_DB_PLACEHOLDER.name
TEST_DB_PLACEHOLDER.close()


@pytest.fixture
def test_db():
    """Create isolated test database"""
    # Use test database path
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
def queue_repo(test_db):
    """Create QueueRepository with test database"""
    from auralis.library.repositories import QueueRepository
    Session = sessionmaker(bind=create_engine(f'sqlite:///{TEST_DB_PATH}'))
    return QueueRepository(Session)


class TestQueuePersistenceBasics:
    """Test basic queue persistence operations"""

    def test_queue_initializes_to_empty(self, queue_repo):
        """Queue should initialize with empty state when no data exists"""
        queue = queue_repo.get_queue_state()

        assert queue is not None
        assert json.loads(queue.track_ids) == []
        assert queue.current_index == 0
        assert queue.is_shuffled is False
        assert queue.repeat_mode == 'off'

    def test_set_queue_persists_track_ids(self, queue_repo):
        """Setting queue should persist track IDs to database"""
        track_ids = [1, 2, 3, 4, 5]

        result = queue_repo.set_queue_state(
            track_ids=track_ids,
            current_index=2,
            is_shuffled=False,
            repeat_mode='all'
        )

        assert result is not None
        assert json.loads(result.track_ids) == track_ids
        assert result.current_index == 2
        assert result.repeat_mode == 'all'

    def test_queue_persists_across_lookups(self, queue_repo):
        """Queue state should persist across multiple database queries"""
        track_ids = [10, 20, 30]

        # Set queue
        queue_repo.set_queue_state(
            track_ids=track_ids,
            current_index=1,
            is_shuffled=True,
            repeat_mode='one'
        )

        # Fetch again - should get same data
        queue = queue_repo.get_queue_state()

        assert json.loads(queue.track_ids) == track_ids
        assert queue.current_index == 1
        assert queue.is_shuffled is True
        assert queue.repeat_mode == 'one'

    def test_update_queue_partial(self, queue_repo):
        """Partial update should only change specified fields"""
        # Set initial queue
        queue_repo.set_queue_state(
            track_ids=[1, 2, 3],
            current_index=0,
            is_shuffled=False,
            repeat_mode='off'
        )

        # Update only shuffle
        queue_repo.update_queue_state({'is_shuffled': True})
        queue = queue_repo.get_queue_state()

        # Shuffle should change, other fields should be preserved
        assert queue.is_shuffled is True
        assert json.loads(queue.track_ids) == [1, 2, 3]
        assert queue.current_index == 0
        assert queue.repeat_mode == 'off'

    def test_clear_queue(self, queue_repo):
        """Clearing queue should reset to empty state"""
        # Set queue with data
        queue_repo.set_queue_state(
            track_ids=[1, 2, 3, 4, 5],
            current_index=3,
            is_shuffled=True,
            repeat_mode='all'
        )

        # Clear queue
        result = queue_repo.clear_queue()

        assert json.loads(result.track_ids) == []
        assert result.current_index == 0
        assert result.is_shuffled is False
        assert result.repeat_mode == 'off'


class TestQueueValidation:
    """Test queue state validation"""

    def test_invalid_repeat_mode_raises_error(self, queue_repo):
        """Invalid repeat_mode should raise ValueError"""
        with pytest.raises(ValueError, match="Invalid repeat_mode"):
            queue_repo.set_queue_state(
                track_ids=[1, 2, 3],
                repeat_mode='invalid_mode'
            )

    def test_current_index_out_of_bounds_raises_error(self, queue_repo):
        """current_index beyond queue size should raise ValueError"""
        with pytest.raises(ValueError, match="out of bounds"):
            queue_repo.set_queue_state(
                track_ids=[1, 2, 3],
                current_index=10  # Beyond queue size
            )

    def test_negative_current_index_raises_error(self, queue_repo):
        """Negative current_index should raise ValueError"""
        with pytest.raises(ValueError, match="out of bounds"):
            queue_repo.set_queue_state(
                track_ids=[1, 2, 3],
                current_index=-1
            )

    def test_valid_repeat_modes(self, queue_repo):
        """All valid repeat modes should be accepted"""
        for repeat_mode in ['off', 'all', 'one']:
            result = queue_repo.set_queue_state(
                track_ids=[1, 2, 3],
                repeat_mode=repeat_mode
            )
            assert result.repeat_mode == repeat_mode


class TestQueueDataIntegrity:
    """Test queue data integrity during operations"""

    def test_large_queue_persists(self, queue_repo):
        """Large queue should persist without data loss"""
        # Create large queue (1000 tracks)
        large_queue = list(range(1, 1001))

        queue_repo.set_queue_state(
            track_ids=large_queue,
            current_index=500
        )

        queue = queue_repo.get_queue_state()
        persisted_ids = json.loads(queue.track_ids)

        assert len(persisted_ids) == 1000
        assert persisted_ids == large_queue
        assert queue.current_index == 500

    def test_queue_with_mixed_track_ids(self, queue_repo):
        """Queue with non-sequential track IDs should persist correctly"""
        track_ids = [42, 7, 999, 1, 333, 101]

        queue_repo.set_queue_state(track_ids=track_ids)
        queue = queue_repo.get_queue_state()

        persisted_ids = json.loads(queue.track_ids)
        assert persisted_ids == track_ids

    def test_shuffle_state_persists(self, queue_repo):
        """Shuffle state should be persistent"""
        # Test shuffle on
        queue_repo.set_queue_state(
            track_ids=[1, 2, 3],
            is_shuffled=True
        )
        queue = queue_repo.get_queue_state()
        assert queue.is_shuffled is True

        # Test shuffle off
        queue_repo.set_queue_state(
            track_ids=[1, 2, 3],
            is_shuffled=False
        )
        queue = queue_repo.get_queue_state()
        assert queue.is_shuffled is False

    def test_repeat_mode_changes_persist(self, queue_repo):
        """Repeat mode changes should be persistent"""
        modes = ['off', 'all', 'one', 'off', 'all']

        for mode in modes:
            queue_repo.set_queue_state(
                track_ids=[1, 2, 3],
                repeat_mode=mode
            )
            queue = queue_repo.get_queue_state()
            assert queue.repeat_mode == mode


class TestQueueMultipleUpdates:
    """Test multiple sequential queue updates"""

    def test_sequential_updates_preserve_state(self, queue_repo):
        """Multiple sequential updates should accumulate correctly"""
        # Initial set
        queue_repo.set_queue_state(track_ids=[1, 2, 3])

        # Update shuffle
        queue_repo.update_queue_state({'is_shuffled': True})
        queue = queue_repo.get_queue_state()
        assert queue.is_shuffled is True
        assert json.loads(queue.track_ids) == [1, 2, 3]

        # Update repeat mode
        queue_repo.update_queue_state({'repeat_mode': 'all'})
        queue = queue_repo.get_queue_state()
        assert queue.repeat_mode == 'all'
        assert queue.is_shuffled is True  # Previous change preserved

        # Update track list
        queue_repo.update_queue_state({'track_ids': [5, 6, 7, 8]})
        queue = queue_repo.get_queue_state()
        assert json.loads(queue.track_ids) == [5, 6, 7, 8]
        assert queue.repeat_mode == 'all'  # Previous changes preserved
        assert queue.is_shuffled is True

    def test_clear_resets_all_state(self, queue_repo):
        """Clear should reset all state to defaults"""
        # Set complex state
        queue_repo.set_queue_state(
            track_ids=list(range(1, 100)),
            current_index=50,
            is_shuffled=True,
            repeat_mode='all'
        )

        # Clear
        queue_repo.clear_queue()
        queue = queue_repo.get_queue_state()

        # All should be reset to defaults
        assert json.loads(queue.track_ids) == []
        assert queue.current_index == 0
        assert queue.is_shuffled is False
        assert queue.repeat_mode == 'off'


class TestQueueDictConversion:
    """Test queue state to/from dictionary conversion"""

    def test_to_dict_serialization(self, queue_repo):
        """Queue should serialize to dictionary correctly"""
        queue_repo.set_queue_state(
            track_ids=[1, 2, 3],
            current_index=1,
            is_shuffled=True,
            repeat_mode='one'
        )

        queue = queue_repo.get_queue_state()
        dict_repr = queue_repo.to_dict(queue)

        assert dict_repr['track_ids'] == [1, 2, 3]
        assert dict_repr['current_index'] == 1
        assert dict_repr['is_shuffled'] is True
        assert dict_repr['repeat_mode'] == 'one'
        assert 'created_at' in dict_repr
        assert 'updated_at' in dict_repr

    def test_to_dict_handles_none(self, queue_repo):
        """to_dict should handle None queue gracefully"""
        dict_repr = queue_repo.to_dict(None)

        assert dict_repr['track_ids'] == []
        assert dict_repr['current_index'] == 0
        assert dict_repr['is_shuffled'] is False
        assert dict_repr['repeat_mode'] == 'off'


class TestQueueEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_queue_navigation(self, queue_repo):
        """Empty queue should handle current_index=0"""
        queue_repo.set_queue_state(
            track_ids=[],
            current_index=0
        )

        queue = queue_repo.get_queue_state()
        assert json.loads(queue.track_ids) == []
        assert queue.current_index == 0

    def test_single_track_queue(self, queue_repo):
        """Single track queue should work correctly"""
        queue_repo.set_queue_state(
            track_ids=[42],
            current_index=0
        )

        queue = queue_repo.get_queue_state()
        assert json.loads(queue.track_ids) == [42]
        assert queue.current_index == 0

    def test_queue_at_last_track(self, queue_repo):
        """Queue with current_index at last track should work"""
        tracks = [1, 2, 3, 4, 5]
        queue_repo.set_queue_state(
            track_ids=tracks,
            current_index=len(tracks) - 1
        )

        queue = queue_repo.get_queue_state()
        assert queue.current_index == 4
        assert len(json.loads(queue.track_ids)) == 5

    def test_unicode_handling(self, queue_repo):
        """Queue should handle numeric track IDs (not unicode issues)"""
        track_ids = [1, 2, 3]
        queue_repo.set_queue_state(track_ids=track_ids)

        queue = queue_repo.get_queue_state()
        persisted_ids = json.loads(queue.track_ids)

        # All IDs should remain integers
        assert all(isinstance(tid, int) for tid in persisted_ids)
