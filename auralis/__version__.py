"""Auralis version information."""

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)
__db_schema_version__ = 16  # track_playlist: UNIQUE(track_id, playlist_id) + position column (#3724, #3725)

# Fingerprint algorithm version — increment this whenever the 25D extraction
# algorithm changes in a way that produces different values for the same audio.
# All existing fingerprints with a lower version will be automatically
# re-fingerprinted by background workers.
# v2 (#4136): 7-band frequency analysis now applies a Hann window before the FFT
#             (was rectangular), matching the windowed STFT spectral features and
#             removing leakage bias on transient-rich audio.
FINGERPRINT_ALGORITHM_VERSION = 3

# Version history
# 1.0.0 - Initial release with adaptive mastering, web UI, and desktop app
# Schema v2 - Added lyrics column to tracks table
# Schema v3 - Added database indexes for improved query performance (created_at, title, play_count, favorite)
# Schema v4 - Added track_fingerprints table for 25D audio fingerprint storage (2025-10-28)
# Schema v5 - Added similarity_graph table for K-nearest neighbors storage (2025-10-28)
# Schema v6 - Added fingerprint status tracking columns to tracks table (2025-11-24)
# Schema v7 - Added queue_state table for queue persistence across application restarts (2025-12-01)
# Schema v8 - Added queue_history table for undo/redo queue operations (2025-12-01)
# Schema v9 - Added queue_template table for saved queue configurations (2025-12-01)
# Schema v10 - Added artist artwork columns (artwork_url, artwork_source, artwork_fetched_at) (2025-12-27)
# Schema v11 - Added artist normalized_name for duplicate detection and merging (2025-12-29)
# Schema v12 - Added fingerprint_hash for integrity verification (2026-02-22)
# Schema v13 - Added bitrate column to tracks table (2026-02-22)
# Schema v14 - Added indexes on favorite, play_count, created_at, similarity_graph (2026-03-05)
# Schema v15 - Added is_reference flag on track_fingerprints for mastering reference cloud (2026-05-24)
# Schema v16 - track_playlist: UNIQUE(track_id, playlist_id) + position column to eliminate concurrent add_track races (2026-05-27)
