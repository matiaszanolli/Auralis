"""
Queue Models
~~~~~~~~~~~~

ORM models for persisted playback queue state and history
(#4511 split of `models/core.py`).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class QueueState(Base, TimestampMixin):
    """
    Model for persisting playback queue state.

    Stores the current playback queue configuration including:
    - List of tracks in queue
    - Current playback index
    - Shuffle mode state
    - Repeat mode setting
    """
    __tablename__ = 'queue_state'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Queue composition - stored as JSON list of track IDs
    # Example: "[1, 5, 3, 7]" - order matters
    track_ids: Mapped[str] = mapped_column(Text, default='[]', nullable=False)

    # Current playback position in queue
    current_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Shuffle mode toggle
    is_shuffled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Repeat mode: 'off', 'all', or 'one'
    repeat_mode: Mapped[str] = mapped_column(String, default='off', nullable=False)

    # Timestamp for optimistic sync detection
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert queue state to dictionary"""
        import json
        try:
            parsed_track_ids = json.loads(self.track_ids) if self.track_ids else []
            track_ids: list[int] = parsed_track_ids if isinstance(parsed_track_ids, list) else []
        except (json.JSONDecodeError, TypeError):
            track_ids = []

        return {
            'id': self.id,
            'track_ids': track_ids,
            'current_index': self.current_index,
            'is_shuffled': self.is_shuffled,
            'repeat_mode': self.repeat_mode,
            'synced_at': self.synced_at.isoformat() if self.synced_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> QueueState:
        """Create QueueState from dictionary"""
        import json
        state = QueueState()
        state.track_ids = json.dumps(data.get('track_ids', []))
        state.current_index = int(data.get('current_index', 0))
        state.is_shuffled = bool(data.get('is_shuffled', False))
        state.repeat_mode = str(data.get('repeat_mode', 'off'))
        return state


class QueueHistory(Base, TimestampMixin):
    """
    Model for tracking queue state history for undo/redo operations.

    Stores snapshots of queue state at each operation, limiting to 20 most recent
    for memory efficiency while preserving undo/redo functionality.
    """
    __tablename__ = 'queue_history'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Reference to queue state (for tracking which queue this history belongs to)
    queue_state_id: Mapped[int] = mapped_column(Integer, ForeignKey('queue_state.id'), nullable=False)

    # Type of operation that triggered this history entry
    # Valid values: 'set', 'add', 'remove', 'reorder', 'shuffle', 'clear'
    operation: Mapped[str] = mapped_column(String, nullable=False)

    # Full snapshot of queue state before the operation
    # Stored as JSON to capture: track_ids, current_index, is_shuffled, repeat_mode
    state_snapshot: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional metadata about the operation
    # For 'add'/'remove': contains index or track_id
    # For 'reorder': contains fromIndex and toIndex
    # For 'shuffle': contains shuffle_mode info
    operation_metadata: Mapped[str | None] = mapped_column(Text, default='{}')

    def to_dict(self) -> dict[str, Any]:
        """Convert history entry to dictionary"""
        import json
        try:
            parsed_snapshot = json.loads(self.state_snapshot) if self.state_snapshot else {}
            state_snapshot: dict[str, Any] = parsed_snapshot if isinstance(parsed_snapshot, dict) else {}
        except (json.JSONDecodeError, TypeError):
            state_snapshot = {}

        try:
            parsed_metadata = json.loads(self.operation_metadata) if self.operation_metadata else {}
            operation_metadata: dict[str, Any] = parsed_metadata if isinstance(parsed_metadata, dict) else {}
        except (json.JSONDecodeError, TypeError):
            operation_metadata = {}

        return {
            'id': self.id,
            'queue_state_id': self.queue_state_id,
            'operation': self.operation,
            'state_snapshot': state_snapshot,
            'operation_metadata': operation_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> QueueHistory:
        """Create QueueHistory from dictionary"""
        import json
        entry = QueueHistory()
        entry.queue_state_id = int(data.get('queue_state_id', 1))
        entry.operation = str(data.get('operation', 'set'))
        entry.state_snapshot = json.dumps(data.get('state_snapshot', {}))
        entry.operation_metadata = json.dumps(data.get('operation_metadata', {}))
        return entry
