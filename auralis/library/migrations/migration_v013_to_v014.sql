-- Migration v013 to v014
-- Adds indexes on frequently-filtered and frequently-sorted columns
-- Date: 2026-03-05
--
-- Track.favorite: filtered in get_favorites() (Favorites page)
-- Track.play_count: ORDER BY in get_popular() (Popular page)
-- Track.created_at: ORDER BY in get_recent() (Recent page)
-- SimilarityGraph.track_id: filtered in get_neighbors() (SQLite does NOT auto-index FK columns)
-- SimilarityGraph(track_id, rank): composite for sorted neighbor lookups
CREATE INDEX IF NOT EXISTS ix_tracks_favorite ON tracks (favorite);
CREATE INDEX IF NOT EXISTS ix_tracks_play_count ON tracks (play_count);
CREATE INDEX IF NOT EXISTS ix_tracks_created_at ON tracks (created_at);
CREATE INDEX IF NOT EXISTS ix_similarity_graph_track_id ON similarity_graph (track_id);
CREATE INDEX IF NOT EXISTS ix_similarity_graph_track_id_rank ON similarity_graph (track_id, rank);
