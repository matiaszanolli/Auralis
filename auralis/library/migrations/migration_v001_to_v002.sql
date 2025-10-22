-- Migration from schema v1 to v2
-- Adds lyrics column to tracks table and artwork_path to albums table

-- Add lyrics column to tracks (TEXT, nullable)
ALTER TABLE tracks ADD COLUMN lyrics TEXT;

-- Add artwork_path column to albums (VARCHAR, nullable)
ALTER TABLE albums ADD COLUMN artwork_path VARCHAR;
