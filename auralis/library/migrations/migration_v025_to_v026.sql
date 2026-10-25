-- Migration v025 to v026
-- Drop the three unread tracks.fingerprint_* indexes and the unused
-- library_stats table. Date: 2026-10-25
--
-- #5755: idx_tracks_fingerprint_status, idx_tracks_fingerprint_queue and
-- idx_tracks_fingerprint_computed_at (migration_v005_to_v006.sql) serve a
-- "WHERE fingerprint_status = 'pending' ORDER BY created_at" queue query that
-- no longer exists: the fingerprint queue reads the track_fingerprints table,
-- FingerprintStatsRepository.update_status() has no production caller, so
-- tracks.fingerprint_status stays 'pending' forever and
-- fingerprint_computed_at is never written. The indexes only cost write
-- amplification on every track insert and update.
--
-- library_stats (migration_v000_to_v001) backed the LibraryStats model, which
-- nothing read or wrote: StatsRepository computes the figures live.
--
-- @ALLOW_DROP_TABLE
--
-- Only the indexes and that table go here. The columns themselves are left for the column
-- removal tracked in #6261 (DROP COLUMN needs SQLite >= 3.35 or a table
-- rebuild). They are also removed from Track.__table_args__ so
-- schema_indexes.create_missing_declared_indexes() does not re-create them on
-- startup.

DROP INDEX IF EXISTS idx_tracks_fingerprint_status;
DROP INDEX IF EXISTS idx_tracks_fingerprint_queue;
DROP INDEX IF EXISTS idx_tracks_fingerprint_computed_at;

DROP TABLE IF EXISTS library_stats;
