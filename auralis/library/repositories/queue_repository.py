"""
Queue State Repository
~~~~~~~~~~~~~~~~~~~~~~

Data access layer for queue state persistence operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
from typing import Any
from collections.abc import Callable

from sqlalchemy.orm import Session

from ..models import QueueState


class QueueRepository:
    """Repository for queue state database operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """
        Initialize queue repository

        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def get_queue_state(self) -> QueueState | None:
        """
        Get current queue state (always returns the first/only queue_state record)
        Creates default queue state if none exist

        Returns:
            QueueState object with current queue configuration
        """
        session = self.get_session()
        try:
            queue_state = session.query(QueueState).first()

            # Create default queue state if none exist
            if not queue_state:
                queue_state = QueueState()
                session.add(queue_state)
                session.commit()
                session.refresh(queue_state)

            return queue_state
        finally:
            session.close()

    def set_queue_state(self, track_ids: list[int], current_index: int = 0,
                        is_shuffled: bool = False, repeat_mode: str = 'off') -> QueueState:
        """
        Update queue state with new configuration

        Args:
            track_ids: List of track IDs in queue order
            current_index: Current playback position in queue
            is_shuffled: Whether shuffle mode is enabled
            repeat_mode: Repeat mode ('off', 'all', or 'one')

        Returns:
            Updated QueueState object

        Raises:
            ValueError: If repeat_mode is not valid or current_index out of bounds
        """
        if repeat_mode not in ('off', 'all', 'one'):
            raise ValueError(f"Invalid repeat_mode: {repeat_mode}")

        if current_index < 0 or current_index > len(track_ids):
            raise ValueError(f"current_index {current_index} out of bounds for queue of size {len(track_ids)}")

        session = self.get_session()
        try:
            queue_state = session.query(QueueState).first()

            if not queue_state:
                queue_state = QueueState()
                session.add(queue_state)

            # Update queue state
            queue_state.track_ids = json.dumps(track_ids)  # type: ignore[assignment]
            queue_state.current_index = current_index  # type: ignore[assignment]
            queue_state.is_shuffled = is_shuffled  # type: ignore[assignment]
            queue_state.repeat_mode = repeat_mode  # type: ignore[assignment]

            session.commit()
            session.refresh(queue_state)
            return queue_state
        finally:
            session.close()

    def update_queue_state(self, updates: dict[str, Any]) -> QueueState:
        """
        Update queue state with provided dictionary

        Args:
            updates: Dictionary containing optional keys:
                - track_ids: List[int] - track IDs in queue
                - current_index: int - current playback position
                - is_shuffled: bool - shuffle mode flag
                - repeat_mode: str - repeat mode ('off', 'all', 'one')

        Returns:
            Updated QueueState object
        """
        session = self.get_session()
        try:
            queue_state = session.query(QueueState).first()

            if not queue_state:
                queue_state = QueueState()
                session.add(queue_state)

            # Handle track_ids separately as it needs JSON serialization
            if 'track_ids' in updates:
                track_ids = updates['track_ids']
                if isinstance(track_ids, list):
                    queue_state.track_ids = json.dumps(track_ids)  # type: ignore[assignment]
                else:
                    queue_state.track_ids = track_ids
            else:
                track_ids_str = queue_state.track_ids if queue_state.track_ids else '[]'
                track_ids = json.loads(str(track_ids_str))

            # Validate and update current_index
            if 'current_index' in updates:
                current_index = updates['current_index']
                if current_index < 0 or current_index > len(track_ids):
                    raise ValueError(f"current_index {current_index} out of bounds for queue of size {len(track_ids)}")
                queue_state.current_index = current_index

            # Validate and update repeat_mode
            if 'repeat_mode' in updates:
                repeat_mode = updates['repeat_mode']
                if repeat_mode not in ('off', 'all', 'one'):
                    raise ValueError(f"Invalid repeat_mode: {repeat_mode}")
                queue_state.repeat_mode = repeat_mode

            # Update is_shuffled
            if 'is_shuffled' in updates:
                queue_state.is_shuffled = bool(updates['is_shuffled'])  # type: ignore[assignment]

            session.commit()
            session.refresh(queue_state)
            return queue_state
        finally:
            session.close()

    def clear_queue(self) -> QueueState:
        """
        Clear the queue (set empty track list and reset position)

        Returns:
            Updated QueueState object with empty queue
        """
        session = self.get_session()
        try:
            queue_state = session.query(QueueState).first()

            if not queue_state:
                queue_state = QueueState()
                session.add(queue_state)
            else:
                queue_state.track_ids = json.dumps([])  # type: ignore[assignment]
                queue_state.current_index = 0  # type: ignore[assignment]
                queue_state.is_shuffled = False  # type: ignore[assignment]
                queue_state.repeat_mode = 'off'  # type: ignore[assignment]

            session.commit()
            session.refresh(queue_state)
            return queue_state
        finally:
            session.close()

    def to_dict(self, queue_state: QueueState) -> dict[str, Any]:
        """
        Convert QueueState to dictionary for API responses

        Args:
            queue_state: QueueState object

        Returns:
            Dictionary representation of queue state
        """
        return queue_state.to_dict() if queue_state else {
            'track_ids': [],
            'current_index': 0,
            'is_shuffled': False,
            'repeat_mode': 'off',
        }
