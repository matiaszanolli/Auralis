-- Migration v024 to v025
-- Indexes track_artist / track_genre and albums.artist_id. Date: 2026-10-24
--
-- #6103: SQLite FOREIGN KEY constraints index only the parent key, never
-- the child column — migration_v002_to_v003.sql's claim that the
-- association tables "already have indexes from their foreign key
-- constraints" was wrong, and schema_indexes.create_missing_declared_indexes()
-- can only create indexes declared on the models, which these never were.
-- Every Track.artists / Track.genres join, selectinload, .any() EXISTS and
-- correlated count therefore ran a full SCAN of track_artist / track_genre:
-- find_similar (run on every library track load while
-- auto_reference_selection is on) took 20-40 s at 50k tracks, and artist
-- lists sorted by track count grew quadratically with library size.
--
-- Deliberately non-UNIQUE (mirroring ix_tracks_filepath_key, #4842): the
-- association tables have no PK/UNIQUE, so an existing database may already
-- hold duplicate (track, artist) rows, and a unique index would abort the
-- migration on exactly the users who most need it. De-duplicating and
-- rebuilding with composite PKs is left as a separate change.
--
-- The same indexes are declared on the models (models/base.py,
-- models/album.py) so fresh create_all databases match this schema, and
-- schema_indexes.create_missing_declared_indexes() repairs any drift.

CREATE INDEX IF NOT EXISTS ix_track_artist_track_id ON track_artist(track_id);
CREATE INDEX IF NOT EXISTS ix_track_artist_artist_id ON track_artist(artist_id);
CREATE INDEX IF NOT EXISTS ix_track_genre_track_id ON track_genre(track_id);
CREATE INDEX IF NOT EXISTS ix_track_genre_genre_id ON track_genre(genre_id);
CREATE INDEX IF NOT EXISTS idx_albums_artist_id ON albums(artist_id);
