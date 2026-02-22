-- Migration v012 to v013
-- Adds bitrate column to tracks table
-- Date: 2026-02-22
--
-- Stores bitrate in kbps. Added to Track model in batch 8 but migration was missing.
ALTER TABLE tracks ADD COLUMN bitrate INTEGER;
