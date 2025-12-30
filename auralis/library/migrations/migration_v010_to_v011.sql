-- Migration v010 to v011
-- Adds artist name normalization support for duplicate detection and merging
-- Date: 2025-12-29

-- Add normalized_name column for duplicate detection
-- This stores a canonical form of the artist name (lowercase, no special chars)
-- Used for matching variations like AC/DC, ACDC, AC-DC
ALTER TABLE artists ADD COLUMN normalized_name VARCHAR;

-- Create index for fast lookups by normalized name
CREATE INDEX idx_artists_normalized_name ON artists(normalized_name);
