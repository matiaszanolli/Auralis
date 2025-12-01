# -*- coding: utf-8 -*-

"""
Queue History Repository
~~~~~~~~~~~~~~~~~~~~~~~~~

Data access layer for queue history and undo/redo operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from ..models import QueueHistory, QueueState


class QueueHistoryRepository:
    """Repository for queue history management and undo/redo operations"""

    # Limit history to 20 operations for memory efficiency
    HISTORY_LIMIT = 20

    def __init__(self, session_factory):
        """
        Initialize queue history repository

        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def push_to_history(self, operation: str, state_before: Dict[str, Any],
                        metadata: Optional[Dict[str, Any]] = None) -> QueueHistory:
        """
        Record a queue state change to history for undo/redo

        Args:
            operation: Type of operation ('set', 'add', 'remove', 'reorder', 'shuffle', 'clear')
            state_before: Complete queue state snapshot before operation
            metadata: Optional operation-specific metadata

        Returns:
            Created QueueHistory entry

        Raises:
            ValueError: If operation type is invalid
        """
        valid_operations = ('set', 'add', 'remove', 'reorder', 'shuffle', 'clear')
        if operation not in valid_operations:
            raise ValueError(f"Invalid operation: {operation}. Must be one of {valid_operations}")

        session = self.get_session()
        try:
            # Get the current queue state to associate with history
            queue_state = session.query(QueueState).first()
            if not queue_state:
                queue_state = QueueState()
                session.add(queue_state)
                session.flush()

            # Create history entry
            history_entry = QueueHistory(
                queue_state_id=queue_state.id,
                operation=operation,
                state_snapshot=json.dumps(state_before),
                operation_metadata=json.dumps(metadata or {})
            )

            session.add(history_entry)
            session.commit()
            session.refresh(history_entry)

            # Cleanup old history if exceeding limit
            self._cleanup_old_history(session, queue_state.id)

            return history_entry
        finally:
            session.close()

    def get_history(self, limit: int = 20) -> List[QueueHistory]:
        """
        Get recent queue history entries (newest first)

        Args:
            limit: Maximum number of entries to return (default 20)

        Returns:
            List of QueueHistory entries ordered by creation time (newest first)
        """
        session = self.get_session()
        try:
            queue_state = session.query(QueueState).first()
            if not queue_state:
                return []

            entries = session.query(QueueHistory) \
                .filter(QueueHistory.queue_state_id == queue_state.id) \
                .order_by(QueueHistory.created_at.desc()) \
                .limit(limit) \
                .all()

            return entries
        finally:
            session.close()

    def undo(self, queue_repository) -> Optional[QueueState]:
        """
        Undo the last queue operation by restoring previous state

        Args:
            queue_repository: QueueRepository instance to update queue state

        Returns:
            Restored QueueState, or None if no history available

        Raises:
            ValueError: If history entry is invalid or corrupted
        """
        session = self.get_session()
        try:
            queue_state = session.query(QueueState).first()
            if not queue_state:
                return None

            # Get the most recent history entry
            latest_history = session.query(QueueHistory) \
                .filter(QueueHistory.queue_state_id == queue_state.id) \
                .order_by(QueueHistory.created_at.desc()) \
                .first()

            if not latest_history:
                return None

            # Parse the snapshot and restore it
            try:
                state_snapshot = json.loads(latest_history.state_snapshot)
            except json.JSONDecodeError:
                raise ValueError(f"Corrupted history entry {latest_history.id}: invalid JSON")

            # Use queue_repository to restore state
            restored = queue_repository.set_queue_state(
                track_ids=state_snapshot.get('track_ids', []),
                current_index=state_snapshot.get('current_index', 0),
                is_shuffled=state_snapshot.get('is_shuffled', False),
                repeat_mode=state_snapshot.get('repeat_mode', 'off')
            )

            # Remove the history entry after using it (undo consumes the history)
            session.delete(latest_history)
            session.commit()

            return restored
        finally:
            session.close()

    def redo(self, queue_repository) -> Optional[QueueState]:
        """
        Redo a previously undone queue operation

        Current implementation: Redo not yet supported
        Future: Could maintain separate redo stack

        Returns:
            None (not implemented)
        """
        # Redo would require tracking operations separately or maintaining a redo stack
        # For now, return None to indicate redo not available
        return None

    def clear_history(self) -> bool:
        """
        Clear all queue history

        Returns:
            True if successful, False if no queue state exists
        """
        session = self.get_session()
        try:
            queue_state = session.query(QueueState).first()
            if not queue_state:
                return False

            session.query(QueueHistory) \
                .filter(QueueHistory.queue_state_id == queue_state.id) \
                .delete()

            session.commit()
            return True
        finally:
            session.close()

    def get_history_count(self) -> int:
        """
        Get total number of history entries

        Returns:
            Number of history entries for current queue
        """
        session = self.get_session()
        try:
            queue_state = session.query(QueueState).first()
            if not queue_state:
                return 0

            count = session.query(QueueHistory) \
                .filter(QueueHistory.queue_state_id == queue_state.id) \
                .count()

            return count
        finally:
            session.close()

    def to_dict(self, entry: QueueHistory) -> Dict[str, Any]:
        """
        Convert QueueHistory entry to dictionary

        Args:
            entry: QueueHistory object

        Returns:
            Dictionary representation of history entry
        """
        return entry.to_dict() if entry else {
            'queue_state_id': 0,
            'operation': 'unknown',
            'state_snapshot': {},
            'operation_metadata': {},
        }

    def _cleanup_old_history(self, session: Session, queue_state_id: int) -> None:
        """
        Remove old history entries exceeding the limit

        Args:
            session: Database session
            queue_state_id: Queue state ID to cleanup for
        """
        # Get count of history entries
        count = session.query(QueueHistory) \
            .filter(QueueHistory.queue_state_id == queue_state_id) \
            .count()

        if count > self.HISTORY_LIMIT:
            # Delete oldest entries beyond the limit
            excess = count - self.HISTORY_LIMIT
            old_entries = session.query(QueueHistory) \
                .filter(QueueHistory.queue_state_id == queue_state_id) \
                .order_by(QueueHistory.created_at.asc()) \
                .limit(excess) \
                .all()

            for entry in old_entries:
                session.delete(entry)

            session.commit()
