-- Migration from schema v2 to v3
-- Description: Add database indexes for improved query performance with large libraries
-- Date: 2025-10-24

-- Performance indexes for common queries

-- Index on created_at for sorting by recency (used in get_recent, get_all with order_by='created_at')
CREATE INDEX IF NOT EXISTS idx_tracks_created_at ON tracks(created_at DESC);

-- Index on title for alphabetical sorting and search (used in get_all with order_by='title', search queries)
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title COLLATE NOCASE);

-- Index on play_count for popularity queries (used in get_popular)
CREATE INDEX IF NOT EXISTS idx_tracks_play_count ON tracks(play_count DESC);

-- Index on favorite for filtering favorites (used in get_favorites)
CREATE INDEX IF NOT EXISTS idx_tracks_favorite ON tracks(favorite) WHERE favorite = 1;

-- Composite index for favorite tracks ordered by title (optimizes get_favorites query)
CREATE INDEX IF NOT EXISTS idx_tracks_favorite_title ON tracks(favorite, title COLLATE NOCASE) WHERE favorite = 1;

-- Index on last_played for "recently played" queries
CREATE INDEX IF NOT EXISTS idx_tracks_last_played ON tracks(last_played DESC);

-- Index on album_id for album-based queries (already has FK, but explicit index helps)
CREATE INDEX IF NOT EXISTS idx_tracks_album_id ON tracks(album_id);

-- Index on year for filtering by release year
CREATE INDEX IF NOT EXISTS idx_tracks_year ON tracks(year);

-- Additional indexes for related tables

-- Artists table: Index on artist name for search and sorting
CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name COLLATE NOCASE);

-- Albums table: Index on album title for search and sorting
CREATE INDEX IF NOT EXISTS idx_albums_title ON albums(title COLLATE NOCASE);

-- Albums table: Index on release year
CREATE INDEX IF NOT EXISTS idx_albums_year ON albums(year);

-- Genres table: Index on genre name
CREATE INDEX IF NOT EXISTS idx_genres_name ON genres(name COLLATE NOCASE);

-- Note: Association tables (track_artist, track_genre, etc.) already have indexes
-- from their foreign key constraints, so we don't need to add more.
