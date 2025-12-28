-- Migration v009 to v010
-- Adds artist artwork columns for fetching images from external sources
-- Date: 2025-12-27

-- Add artwork metadata columns to artists table
ALTER TABLE artists ADD COLUMN artwork_url TEXT;
ALTER TABLE artists ADD COLUMN artwork_source TEXT;
ALTER TABLE artists ADD COLUMN artwork_fetched_at DATETIME;
