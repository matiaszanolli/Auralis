-- Migration from schema v4 to v5
-- Description: Add similarity_graph table for K-nearest neighbors storage
-- Date: 2025-10-28

-- Similarity Graph table
-- Stores pre-computed K-nearest neighbors for fast similarity queries
CREATE TABLE IF NOT EXISTS similarity_graph (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    similar_track_id INTEGER NOT NULL,
    distance REAL NOT NULL,
    similarity_score REAL NOT NULL,
    rank INTEGER NOT NULL,  -- Rank of similarity (1=most similar, 2=second most, etc.)

    -- Metadata
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraints
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    FOREIGN KEY (similar_track_id) REFERENCES tracks(id) ON DELETE CASCADE,

    -- Ensure no duplicate edges
    UNIQUE(track_id, similar_track_id)
);

-- Indexes for similarity graph queries

-- Index on track_id for getting neighbors of a specific track (most common query)
CREATE INDEX IF NOT EXISTS idx_similarity_graph_track_id ON similarity_graph(track_id, rank);

-- Index on similar_track_id for reverse lookups (which tracks are similar to this one?)
CREATE INDEX IF NOT EXISTS idx_similarity_graph_similar_track_id ON similarity_graph(similar_track_id);

-- Index on distance for finding globally most similar pairs
CREATE INDEX IF NOT EXISTS idx_similarity_graph_distance ON similarity_graph(distance);

-- Composite index for efficient rank-ordered queries
CREATE INDEX IF NOT EXISTS idx_similarity_graph_track_rank ON similarity_graph(track_id, rank, distance);
