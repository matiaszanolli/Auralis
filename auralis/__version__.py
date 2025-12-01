"""Auralis version information."""

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)
__db_schema_version__ = 9  # Added queue_template table for saved queue configurations

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
