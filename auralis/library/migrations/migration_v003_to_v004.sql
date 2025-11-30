-- Migration from schema v3 to v4
-- Description: Add track_fingerprints table for 25D audio fingerprint storage and similarity system
-- Date: 2025-10-28

-- Track Fingerprints table
-- Stores 25-dimensional audio fingerprints for similarity analysis and music discovery
CREATE TABLE IF NOT EXISTS track_fingerprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL UNIQUE,

    -- Frequency Distribution (7 dimensions)
    sub_bass_pct REAL NOT NULL,      -- % energy in sub-bass (20-60 Hz)
    bass_pct REAL NOT NULL,           -- % energy in bass (60-250 Hz)
    low_mid_pct REAL NOT NULL,        -- % energy in low-mids (250-500 Hz)
    mid_pct REAL NOT NULL,            -- % energy in mids (500-2k Hz)
    upper_mid_pct REAL NOT NULL,      -- % energy in upper-mids (2k-4k Hz)
    presence_pct REAL NOT NULL,       -- % energy in presence (4k-6k Hz)
    air_pct REAL NOT NULL,            -- % energy in air (6k-20k Hz)

    -- Dynamics (3 dimensions)
    lufs REAL NOT NULL,               -- Integrated loudness (LUFS)
    crest_db REAL NOT NULL,           -- Crest factor in dB (dynamic range indicator)
    bass_mid_ratio REAL NOT NULL,     -- Bass to mid energy ratio

    -- Temporal (4 dimensions)
    tempo_bpm REAL NOT NULL,          -- Detected tempo in BPM
    rhythm_stability REAL NOT NULL,   -- Rhythm consistency (0-1)
    transient_density REAL NOT NULL,  -- Average transients per second
    silence_ratio REAL NOT NULL,      -- % of track below -60 dB

    -- Spectral (3 dimensions)
    spectral_centroid REAL NOT NULL,  -- Brightness (weighted mean frequency)
    spectral_rolloff REAL NOT NULL,   -- Frequency below which 85% of energy lies
    spectral_flatness REAL NOT NULL,  -- Tonality vs noise (0=pure tone, 1=white noise)

    -- Harmonic (3 dimensions)
    harmonic_ratio REAL NOT NULL,     -- Harmonic vs percussive energy
    pitch_stability REAL NOT NULL,    -- Pitch consistency (0-1)
    chroma_energy REAL NOT NULL,      -- Chroma feature strength

    -- Variation (3 dimensions)
    dynamic_range_variation REAL NOT NULL,    -- STD of dynamic range over time
    loudness_variation_std REAL NOT NULL,     -- STD of loudness over time
    peak_consistency REAL NOT NULL,           -- Consistency of peak levels

    -- Stereo (2 dimensions)
    stereo_width REAL NOT NULL,       -- Stereo width (0=mono, 1=wide)
    phase_correlation REAL NOT NULL,  -- L/R phase correlation (-1 to 1)

    -- Metadata
    fingerprint_version INTEGER NOT NULL DEFAULT 1,  -- Schema version for future updates
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraint
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
);

-- Indexes for fingerprint queries

-- Index on track_id for lookups (most common operation)
CREATE INDEX IF NOT EXISTS idx_fingerprints_track_id ON track_fingerprints(track_id);

-- Indexes for range queries on key dimensions (used in similarity search)
-- These enable efficient filtering before distance calculation

-- Frequency dimensions (most distinctive)
CREATE INDEX IF NOT EXISTS idx_fingerprints_bass_pct ON track_fingerprints(bass_pct);
CREATE INDEX IF NOT EXISTS idx_fingerprints_mid_pct ON track_fingerprints(mid_pct);

-- Dynamics dimensions (very distinctive)
CREATE INDEX IF NOT EXISTS idx_fingerprints_lufs ON track_fingerprints(lufs);
CREATE INDEX IF NOT EXISTS idx_fingerprints_crest_db ON track_fingerprints(crest_db);

-- Temporal dimensions (genre-specific)
CREATE INDEX IF NOT EXISTS idx_fingerprints_tempo_bpm ON track_fingerprints(tempo_bpm);

-- Composite index for multi-dimensional filtering
-- Enables fast filtering on most distinctive dimensions before distance calculation
CREATE INDEX IF NOT EXISTS idx_fingerprints_composite
    ON track_fingerprints(lufs, crest_db, bass_pct, tempo_bpm);

-- Index for fingerprint version (for future migrations)
CREATE INDEX IF NOT EXISTS idx_fingerprints_version ON track_fingerprints(fingerprint_version);
