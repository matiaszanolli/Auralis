-- Migration v031 to v032
-- Makes tracks.filepath_key unique on upgraded databases. Date: 2026-11-17
--
-- #6335: a fresh create_all database has a UNIQUE ix_tracks_filepath_key, but v017->v018
-- created it non-unique (an upgraded library might already hold the duplicates the key
-- exists to prevent, and a unique index would have aborted the migration for exactly those
-- users). So on an upgraded library two concurrent adds of case-variant spellings of one
-- file, or relocate_missing_track() re-pointing onto an existing key, could still store two
-- rows for one file, which get_by_path(...).first() and update_by_filepath assume cannot be.
--
-- Rows sharing a filepath_key are merged onto the lowest id first (a unique index cannot be
-- built over them): play_count is summed, favorite and last_played take the group's maximum,
-- playlist memberships and a missing fingerprint move to the surviving row, and the other
-- rows are deleted with their artist/genre links and similarity edges (derived data, rebuilt
-- on demand; the survivor keeps its own artists and genres). NULL keys are left alone: they
-- are distinct in a unique index and are filled in by the first-connection backfill.
-- Every statement derives the merge from filepath_key rather than a scratch table, so a
-- replay over an already-unique schema (a fresh database walking the chain) changes nothing.

UPDATE tracks
SET play_count = (SELECT SUM(COALESCE(g.play_count, 0)) FROM tracks g WHERE g.filepath_key = tracks.filepath_key),
    favorite = (SELECT MAX(COALESCE(g.favorite, 0)) FROM tracks g WHERE g.filepath_key = tracks.filepath_key),
    last_played = (SELECT MAX(g.last_played) FROM tracks g WHERE g.filepath_key = tracks.filepath_key)
WHERE filepath_key IS NOT NULL
  AND id = (SELECT MIN(m.id) FROM tracks m WHERE m.filepath_key = tracks.filepath_key)
  AND EXISTS (SELECT 1 FROM tracks d WHERE d.filepath_key = tracks.filepath_key AND d.id > tracks.id);

-- (track_id, playlist_id) is the primary key: a playlist that already holds the survivor
-- keeps that row and the duplicate's is dropped below.
UPDATE OR IGNORE track_playlist
SET track_id = (
    SELECT MIN(m.id) FROM tracks m
    WHERE m.filepath_key = (SELECT d.filepath_key FROM tracks d WHERE d.id = track_playlist.track_id)
)
WHERE track_id IN (
    SELECT d.id FROM tracks d
    WHERE d.filepath_key IS NOT NULL
      AND d.id > (SELECT MIN(m.id) FROM tracks m WHERE m.filepath_key = d.filepath_key)
);

-- One fingerprint per track (unique track_id): a survivor without one adopts a duplicate's.
UPDATE OR IGNORE track_fingerprints
SET track_id = (
    SELECT MIN(m.id) FROM tracks m
    WHERE m.filepath_key = (SELECT d.filepath_key FROM tracks d WHERE d.id = track_fingerprints.track_id)
)
WHERE track_id IN (
    SELECT d.id FROM tracks d
    WHERE d.filepath_key IS NOT NULL
      AND d.id > (SELECT MIN(m.id) FROM tracks m WHERE m.filepath_key = d.filepath_key)
);

DELETE FROM track_playlist WHERE track_id IN (
    SELECT d.id FROM tracks d
    WHERE d.filepath_key IS NOT NULL
      AND d.id > (SELECT MIN(m.id) FROM tracks m WHERE m.filepath_key = d.filepath_key)
);
DELETE FROM track_fingerprints WHERE track_id IN (
    SELECT d.id FROM tracks d
    WHERE d.filepath_key IS NOT NULL
      AND d.id > (SELECT MIN(m.id) FROM tracks m WHERE m.filepath_key = d.filepath_key)
);
DELETE FROM track_artist WHERE track_id IN (
    SELECT d.id FROM tracks d
    WHERE d.filepath_key IS NOT NULL
      AND d.id > (SELECT MIN(m.id) FROM tracks m WHERE m.filepath_key = d.filepath_key)
);
DELETE FROM track_genre WHERE track_id IN (
    SELECT d.id FROM tracks d
    WHERE d.filepath_key IS NOT NULL
      AND d.id > (SELECT MIN(m.id) FROM tracks m WHERE m.filepath_key = d.filepath_key)
);
DELETE FROM similarity_graph
WHERE track_id IN (
    SELECT d.id FROM tracks d
    WHERE d.filepath_key IS NOT NULL
      AND d.id > (SELECT MIN(m.id) FROM tracks m WHERE m.filepath_key = d.filepath_key)
)
OR similar_track_id IN (
    SELECT d.id FROM tracks d
    WHERE d.filepath_key IS NOT NULL
      AND d.id > (SELECT MIN(m.id) FROM tracks m WHERE m.filepath_key = d.filepath_key)
);

DELETE FROM tracks
WHERE filepath_key IS NOT NULL
  AND id > (SELECT MIN(m.id) FROM tracks m WHERE m.filepath_key = tracks.filepath_key);

DROP INDEX IF EXISTS ix_tracks_filepath_key;
CREATE UNIQUE INDEX IF NOT EXISTS ix_tracks_filepath_key ON tracks(filepath_key);
