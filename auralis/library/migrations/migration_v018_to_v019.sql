-- Migration v018 to v019
-- Backfills albums.artist_id for albums the rescan paths created without one. Date: 2026-09-13
--
-- #5457: TrackRepository.update_by_filepath() and update() looked an album up
-- by title alone and created a missing one with no artist_id, so every
-- "retag a track into a new album, then rescan" left an album that no artist
-- page lists. Both paths now resolve the album for the track's artist, like
-- the first scan always has; this repairs the albums already created.
--
-- Each artist-less album takes the artist credited on most of its tracks,
-- with the lowest artist id breaking a tie so the result is deterministic.
-- Albums whose tracks carry no artist at all are left NULL and serialize as
-- 'Unknown Artist'. albums has no UNIQUE(title, artist_id) constraint, so
-- giving an orphan an owner cannot collide with an existing album row.

UPDATE albums
SET artist_id = (
    SELECT ta.artist_id
    FROM tracks t
    JOIN track_artist ta ON ta.track_id = t.id
    WHERE t.album_id = albums.id
      AND ta.artist_id IS NOT NULL
    GROUP BY ta.artist_id
    ORDER BY COUNT(*) DESC, ta.artist_id ASC
    LIMIT 1
)
WHERE artist_id IS NULL;
