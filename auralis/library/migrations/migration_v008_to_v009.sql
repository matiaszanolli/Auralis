-- Migration v008 to v009
-- Adds queue_template table for saving and restoring queue configurations
-- Date: 2025-12-01

-- Create queue_template table for saved queue configurations
CREATE TABLE IF NOT EXISTS queue_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    -- Queue configuration snapshot
    track_ids TEXT NOT NULL DEFAULT '[]',
    is_shuffled BOOLEAN NOT NULL DEFAULT 0,
    repeat_mode TEXT NOT NULL DEFAULT 'off',
    -- Template metadata
    description TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    is_favorite BOOLEAN NOT NULL DEFAULT 0,
    -- Usage statistics
    load_count INTEGER NOT NULL DEFAULT 0,
    last_loaded DATETIME,
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (repeat_mode IN ('off', 'all', 'one')),
    CHECK (is_shuffled IN (0, 1)),
    CHECK (is_favorite IN (0, 1))
);

-- Create indexes for efficient template queries
CREATE INDEX IF NOT EXISTS idx_queue_template_name ON queue_template(name);
CREATE INDEX IF NOT EXISTS idx_queue_template_created_at ON queue_template(created_at);
CREATE INDEX IF NOT EXISTS idx_queue_template_is_favorite ON queue_template(is_favorite);
CREATE INDEX IF NOT EXISTS idx_queue_template_load_count ON queue_template(load_count DESC);
