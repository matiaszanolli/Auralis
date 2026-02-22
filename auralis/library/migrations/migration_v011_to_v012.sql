-- Migration v011 to v012
-- Adds fingerprint_hash column for integrity verification (#2422)
-- Date: 2026-02-22
--
-- SHA-256 hash of the 25D fingerprint values, computed at insert/update time.
-- Verified on read to detect tampering or silent corruption.
ALTER TABLE tracks ADD COLUMN fingerprint_hash VARCHAR;
