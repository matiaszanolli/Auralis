-- Migration v029 to v030
-- Makes an album unique per (title, artist). Date: 2026-10-26
--
-- #5595: albums had no uniqueness at all, so the IntegrityError guard in
-- _get_or_create_album could never fire and two concurrent scans adding tracks
-- of one new album each inserted their own row. The lookup also ignored
-- artist-less albums. The repository now inserts with ON CONFLICT DO NOTHING
-- and re-selects, which needs these constraints to mean anything.
--
-- Existing duplicates are merged first (a unique index cannot be built over
-- them): every track is repointed at the lowest-id album of its (title, artist)
-- group and the other rows are deleted. NULL artists compare equal here (IS,
-- GROUP BY), matching the ownerless index below. Titles compare exactly, as
-- the repository's lookup does. A duplicate's artwork file is left on disk.

UPDATE tracks
SET album_id = (
    SELECT MIN(b.id)
    FROM albums a
    JOIN albums b ON b.title = a.title AND b.artist_id IS a.artist_id
    WHERE a.id = tracks.album_id
)
WHERE album_id IN (SELECT id FROM albums);

DELETE FROM albums
WHERE id NOT IN (SELECT MIN(id) FROM albums GROUP BY title, artist_id);

-- NULLs are distinct in a SQLite unique index, hence one partial index per case.
CREATE UNIQUE INDEX IF NOT EXISTS uq_albums_title_artist
    ON albums(title, artist_id) WHERE artist_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_albums_title_ownerless
    ON albums(title) WHERE artist_id IS NULL;
