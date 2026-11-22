-- Migration v032 to v033
-- Adds track_artist.position, the artist's index in the file's tag. Date: 2026-11-22
--
-- #6714: track_artist stored no order, so SQLite returned a track's artists in
-- whatever order its query plan read them, and every reader that takes
-- artists[0] as the primary artist (now playing, similarity results, search)
-- could show a featured artist instead. Track.artists is now ordered by this
-- column, and the repositories write it from the tag order.
--
-- Databases that already have the column (fresh installs) are unaffected: the
-- runner skips "duplicate column". Existing links cannot recover the tag order
-- without a rescan, but the scanner inserted each track's links in tag order,
-- so rowid order within a track is the best signal there is. Only tracks whose
-- links all still hold the default 0 are backfilled, so a replay never
-- overwrites positions the repositories wrote.

ALTER TABLE track_artist ADD COLUMN position INTEGER NOT NULL DEFAULT 0;

UPDATE track_artist
SET position = (
    SELECT COUNT(*) FROM track_artist earlier
    WHERE earlier.track_id = track_artist.track_id
      AND earlier.rowid < track_artist.rowid
)
WHERE track_id IN (
    SELECT track_id FROM track_artist
    GROUP BY track_id
    HAVING COUNT(*) > 1 AND MAX(position) = 0
);
