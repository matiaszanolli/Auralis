-- Migration from schema v5 to v6
-- Description: Add fingerprint status tracking columns to tracks table
-- Date: 2025-11-24
-- Purpose: Enable background fingerprint extraction with status, timestamps, and error messages

-- Add fingerprint status column
-- Values: 'pending' (not yet processed), 'processing' (currently extracting),
--         'complete' (fingerprint extracted), 'error' (extraction failed)
ALTER TABLE tracks ADD COLUMN fingerprint_status TEXT DEFAULT 'pending';

-- Add timestamp for when fingerprint was last computed
ALTER TABLE tracks ADD COLUMN fingerprint_computed_at DATETIME;

-- Add error message field for failed fingerprint extractions
ALTER TABLE tracks ADD COLUMN fingerprint_error_message TEXT;

-- Add JSON-serialized 25D fingerprint vector
-- Stored as JSON string for direct integration with fingerprint extraction pipeline
-- Format: {"sub_bass_pct": 0.1, "bass_pct": 0.2, ...}
ALTER TABLE tracks ADD COLUMN fingerprint_vector TEXT;

-- Index on fingerprint_status for efficient queue queries
-- Used to find tracks that need fingerprinting or are currently processing
CREATE INDEX IF NOT EXISTS idx_tracks_fingerprint_status
    ON tracks(fingerprint_status);

-- Composite index for background extraction queue
-- Enables efficient queries like: WHERE fingerprint_status = 'pending' ORDER BY created_at
CREATE INDEX IF NOT EXISTS idx_tracks_fingerprint_queue
    ON tracks(fingerprint_status, created_at);

-- Index on fingerprint_computed_at for timing analysis
-- Useful for finding recently computed fingerprints
CREATE INDEX IF NOT EXISTS idx_tracks_fingerprint_computed_at
    ON tracks(fingerprint_computed_at DESC);

-- Update schema version
UPDATE schema_version SET version = 6, applied_at = CURRENT_TIMESTAMP,
       description = 'Added fingerprint status tracking columns to tracks table',
       migration_script = 'migration_v005_to_v006_fingerprint_status.sql'
WHERE id = 1;
