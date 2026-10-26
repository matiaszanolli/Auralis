-- Migration v026 to v027
-- Drop the four never-written tracks.fingerprint_* columns. Date: 2026-10-25
--
-- #5755: fingerprint_status, fingerprint_computed_at, fingerprint_error_message
-- and fingerprint_vector were added in v005->v006 for a per-track fingerprint
-- queue that moved to the track_fingerprints table. The only writer was
-- FingerprintStatsRepository.update_status(), which no production code called,
-- so fingerprint_status stayed 'pending' for every row and the other three
-- stayed NULL; nothing read them. The three indexes on them went in v026, so
-- the columns are free to drop (SQLite refuses to drop an indexed column).
-- update_status() / get_fingerprint_status() and the ORM attributes are removed
-- in the same change.

ALTER TABLE tracks DROP COLUMN fingerprint_status;
ALTER TABLE tracks DROP COLUMN fingerprint_computed_at;
ALTER TABLE tracks DROP COLUMN fingerprint_error_message;
ALTER TABLE tracks DROP COLUMN fingerprint_vector;
