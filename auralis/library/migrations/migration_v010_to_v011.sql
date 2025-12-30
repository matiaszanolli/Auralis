-- Migration v010 to v011
-- Adds artist name normalization support for duplicate detection and merging
-- Date: 2025-12-29

-- Add normalized_name column for duplicate detection (if not exists)
-- This stores a canonical form of the artist name (lowercase, no special chars)
-- Used for matching variations like AC/DC, ACDC, AC-DC
-- Note: SQLite doesn't support IF NOT EXISTS for ADD COLUMN, so this migration
-- should be run after checking if the column exists in the MigrationManager.
-- If the column was already added by normalize_existing_artists.py, this migration
-- should be skipped (schema version already set to 11).
ALTER TABLE artists ADD COLUMN normalized_name VARCHAR;

-- Create index for fast lookups by normalized name
CREATE INDEX IF NOT EXISTS idx_artists_normalized_name ON artists(normalized_name);
