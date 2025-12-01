-- Migration from schema v6 to v7
-- Add queue_state table for persisting playback queue configuration
--
-- New Tables:
-- - queue_state: Stores current queue state (tracks, shuffle, repeat mode)

-- ============================================================================
-- Create queue_state table for queue persistence
-- ============================================================================
-- Stores the current playback queue configuration including track list,
-- current playback index, shuffle mode, and repeat mode setting.
--
-- Design:
-- - track_ids: JSON list of track IDs in queue order (stored as Text)
-- - current_index: Current playback position in queue
-- - is_shuffled: Boolean flag for shuffle mode
-- - repeat_mode: Repeat mode setting ('off', 'all', 'one')
-- - synced_at: Timestamp for optimistic sync detection
-- - created_at, updated_at: Standard timestamp tracking

CREATE TABLE IF NOT EXISTS queue_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_ids TEXT NOT NULL DEFAULT '[]',
    current_index INTEGER NOT NULL DEFAULT 0,
    is_shuffled BOOLEAN NOT NULL DEFAULT 0,
    repeat_mode TEXT NOT NULL DEFAULT 'off',
    synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (current_index >= 0),
    CHECK (repeat_mode IN ('off', 'all', 'one')),
    CHECK (is_shuffled IN (0, 1))
);

-- Create index for efficient queue lookups
CREATE INDEX IF NOT EXISTS idx_queue_state_current_index ON queue_state(current_index);
CREATE INDEX IF NOT EXISTS idx_queue_state_synced_at ON queue_state(synced_at);

-- ============================================================================
-- Migration metadata
-- ============================================================================
-- This migration adds queue persistence capability to Auralis v1.1.0-beta.6+
-- Allows playback queue to be restored across application restarts
-- Enables real-time queue synchronization via WebSocket
