-- Migration from v0 to v1: Initial schema
-- This file documents the initial database schema for reference
-- It is NOT executed (fresh databases are created via SQLAlchemy models)
-- Author: Auralis Team
-- Date: 2025-09-30

-- Tracks table
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR NOT NULL,
    filepath VARCHAR NOT NULL UNIQUE,
    duration FLOAT,
    sample_rate INTEGER,
    bit_depth INTEGER,
    channels INTEGER,
    format VARCHAR,
    filesize INTEGER,
    peak_level FLOAT,
    rms_level FLOAT,
    dr_rating FLOAT,
    lufs_level FLOAT,
    mastering_quality FLOAT,
    recommended_reference VARCHAR,
    processing_profile VARCHAR,
    album_id INTEGER,
    track_number INTEGER,
    disc_number INTEGER,
    year INTEGER,
    comments TEXT,
    play_count INTEGER DEFAULT 0,
    last_played DATETIME,
    skip_count INTEGER DEFAULT 0,
    favorite BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (album_id) REFERENCES albums(id)
);

-- Albums table
CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR NOT NULL,
    artist_id INTEGER,
    year INTEGER,
    total_tracks INTEGER,
    total_discs INTEGER,
    avg_dr_rating FLOAT,
    avg_lufs FLOAT,
    mastering_consistency FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (artist_id) REFERENCES artists(id)
);

-- Artists table
CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR NOT NULL UNIQUE,
    total_plays INTEGER DEFAULT 0,
    avg_mastering_quality FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Genres table
CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR NOT NULL UNIQUE,
    preferred_profile VARCHAR DEFAULT 'balanced',
    typical_dr_range VARCHAR,
    typical_lufs_range VARCHAR,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Playlists table
CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR NOT NULL,
    description TEXT,
    is_smart BOOLEAN DEFAULT 0,
    smart_criteria TEXT,
    auto_master_enabled BOOLEAN DEFAULT 1,
    mastering_profile VARCHAR DEFAULT 'balanced',
    normalize_levels BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Library stats table
CREATE TABLE IF NOT EXISTS library_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_tracks INTEGER DEFAULT 0,
    total_artists INTEGER DEFAULT 0,
    total_albums INTEGER DEFAULT 0,
    total_genres INTEGER DEFAULT 0,
    total_playlists INTEGER DEFAULT 0,
    total_duration FLOAT DEFAULT 0.0,
    total_filesize INTEGER DEFAULT 0,
    avg_dr_rating FLOAT,
    avg_lufs FLOAT,
    avg_mastering_quality FLOAT,
    last_scan_date DATETIME,
    last_scan_duration FLOAT,
    files_scanned INTEGER DEFAULT 0,
    new_files_found INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Association table: tracks <-> artists
CREATE TABLE IF NOT EXISTS track_artist (
    track_id INTEGER,
    artist_id INTEGER,
    FOREIGN KEY (track_id) REFERENCES tracks(id),
    FOREIGN KEY (artist_id) REFERENCES artists(id)
);

-- Association table: tracks <-> genres
CREATE TABLE IF NOT EXISTS track_genre (
    track_id INTEGER,
    genre_id INTEGER,
    FOREIGN KEY (track_id) REFERENCES tracks(id),
    FOREIGN KEY (genre_id) REFERENCES genres(id)
);

-- Association table: tracks <-> playlists
CREATE TABLE IF NOT EXISTS track_playlist (
    track_id INTEGER,
    playlist_id INTEGER,
    FOREIGN KEY (track_id) REFERENCES tracks(id),
    FOREIGN KEY (playlist_id) REFERENCES playlists(id)
);

-- Schema version table (critical for migration tracking)
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL UNIQUE,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    migration_script TEXT
);

-- Record initial version
INSERT INTO schema_version (version, description, migration_script)
VALUES (1, 'Initial schema', 'migration_v000_to_v001_initial_schema.sql')
