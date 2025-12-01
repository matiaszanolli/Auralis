-- Migration v007 to v008
-- Adds queue history table for undo/redo functionality
-- Date: 2025-12-01

-- Create queue_history table for undo/redo operations
CREATE TABLE IF NOT EXISTS queue_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_state_id INTEGER NOT NULL,
    operation TEXT NOT NULL,
    -- operation values: 'set', 'add', 'remove', 'reorder', 'shuffle', 'clear'
    state_snapshot TEXT NOT NULL,
    -- Complete queue state snapshot as JSON (track_ids, current_index, is_shuffled, repeat_mode)
    operation_metadata TEXT DEFAULT '{}',
    -- Operation-specific metadata as JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (queue_state_id) REFERENCES queue_state(id),
    CHECK (operation IN ('set', 'add', 'remove', 'reorder', 'shuffle', 'clear'))
);

-- Create indexes for efficient history queries
CREATE INDEX IF NOT EXISTS idx_queue_history_queue_state_id ON queue_history(queue_state_id);
CREATE INDEX IF NOT EXISTS idx_queue_history_created_at ON queue_history(created_at);
CREATE INDEX IF NOT EXISTS idx_queue_history_operation ON queue_history(operation);
