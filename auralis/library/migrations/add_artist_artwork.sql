-- Add artwork_url column to artists table
-- Migration: add_artist_artwork
-- Date: 2025-12-27

ALTER TABLE artists ADD COLUMN artwork_url TEXT;

-- Create index for faster lookups
CREATE INDEX idx_artists_artwork_url ON artists(artwork_url);

-- Add metadata tracking columns
ALTER TABLE artists ADD COLUMN artwork_source TEXT;
ALTER TABLE artists ADD COLUMN artwork_fetched_at TIMESTAMP;
