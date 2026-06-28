-- Migration v015 to v016
-- Adds UNIQUE(track_id, playlist_id) constraint + explicit position column
-- to track_playlist. Date: 2026-05-27
--
-- @ALLOW_DROP_TABLE — Step 4 uses the SQLite recreate-and-copy idiom (CREATE
-- new -> copy rows -> DROP old -> RENAME), the only way to add a UNIQUE
-- constraint to an existing table. Without this marker migration_manager's
-- safety check rejects the DROP TABLE and migration to v16 fails, leaving the
-- app unable to start on a v15 database.
--
-- Context (#3724, #3725 — LDB-26-1, LDB-26-2):
--
-- The original schema declared `track_playlist` with no primary key and no
-- unique constraint. PlaylistRepository.add_track defended against
-- same-thread re-adds with a SELECT EXISTS check followed by
-- `playlist.tracks.append(track)`, which leaves a wide TOCTOU window:
-- two concurrent POSTs for the same (playlist_id, track_id) both pass
-- the EXISTS check and both INSERT silently. No IntegrityError fires
-- because there's no constraint, and the rows accumulate invisibly
-- (some queries DISTINCT them away in the UI). #3340's atomic DELETE
-- fix for remove_track helped one side but left this one open.
--
-- Position ordering was equally undefined: the implicit row order in
-- the secondary table came from row-insertion order, so two concurrent
-- appends at position=None could interleave non-deterministically.
--
-- SQLite quirk: ALTER TABLE doesn't support adding constraints in
-- place, so we use the standard recreate-and-copy pattern.
--
-- Steps:
-- 1. Drop any duplicates first (keep the lowest rowid per pair).
-- 2. Recreate the table with the unique constraint + position column.
-- 3. Copy rows back, assigning position by their existing insertion
--    order within each playlist (ROW_NUMBER over partition).
-- 4. Old table is replaced by the new one.

-- Step 1: cleanup duplicates from any historical races.
DELETE FROM track_playlist
WHERE rowid NOT IN (
    SELECT MIN(rowid)
    FROM track_playlist
    GROUP BY track_id, playlist_id
);

-- Step 2: build a replacement table with the constraint + position
-- column. SQLite supports ALTER TABLE RENAME so we drop the old one
-- last to keep the transaction atomic.
CREATE TABLE track_playlist_new (
    track_id    INTEGER NOT NULL REFERENCES tracks(id),
    playlist_id INTEGER NOT NULL REFERENCES playlists(id),
    position    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (track_id, playlist_id)
);

-- Step 3: copy + backfill position from the existing insertion order.
-- ROW_NUMBER is partitioned per-playlist and ordered by rowid so the
-- visible UI order is preserved. Numbering starts at 0.
INSERT INTO track_playlist_new (track_id, playlist_id, position)
SELECT
    track_id,
    playlist_id,
    ROW_NUMBER() OVER (PARTITION BY playlist_id ORDER BY rowid) - 1 AS position
FROM track_playlist;

-- Step 4: replace.
DROP TABLE track_playlist;
ALTER TABLE track_playlist_new RENAME TO track_playlist;

-- Helpful index for the common "list tracks in a playlist" query.
CREATE INDEX IF NOT EXISTS ix_track_playlist_playlist_position
    ON track_playlist (playlist_id, position);
