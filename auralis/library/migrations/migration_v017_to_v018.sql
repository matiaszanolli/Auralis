-- Migration v017 to v018
-- Adds tracks.filepath_key, the value path lookups compare against. Date: 2026-08-13
--
-- #4842: Windows (NTFS) and macOS (default APFS) are case-insensitive but
-- case-preserving, so one physical file is reachable via several differently
-- cased path strings. `filepath == ?` treated those as different tracks, and
-- `filepath`'s UNIQUE constraint did not help — it only rejects an *identical*
-- string. Rescanning with any case variance inserted a duplicate row.
--
-- `filepath` keeps its real case (it is the string used to open the file);
-- `filepath_key` is the derived matching value and carries the index.
--
-- The column is deliberately left NULL here rather than backfilled in SQL.
-- The key is NOT simply lower(filepath): it is case-folded only on
-- case-insensitive platforms, and preserves case on Linux, where two
-- differently-cased paths are genuinely different files. A `lower()` backfill
-- would therefore be actively wrong on Linux — every existing row would get a
-- key that no lookup ever computes, making every track unfindable and causing
-- the whole library to be re-added on the next scan. SQLite's lower() is also
-- ASCII-only, so it disagrees with Python's str.casefold() on the non-ASCII
-- paths a music library is full of.
--
-- auralis.library.path_key.make_filepath_key() is the single authority, and
-- TrackRepository.backfill_filepath_keys() applies it to the NULL rows on the
-- first connection after migrating.
--
-- The index is intentionally non-UNIQUE: an existing database may already hold
-- the duplicates this fixes, and a unique index would abort the migration on
-- exactly the users who most need it. Lookups are index-backed either way.

ALTER TABLE tracks ADD COLUMN filepath_key TEXT;

CREATE INDEX IF NOT EXISTS ix_tracks_filepath_key ON tracks(filepath_key);
