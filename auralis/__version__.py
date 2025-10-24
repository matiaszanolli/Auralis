"""Auralis version information."""

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)
__db_schema_version__ = 3  # Added performance indexes for large libraries

# Version history
# 1.0.0 - Initial release with adaptive mastering, web UI, and desktop app
# Schema v2 - Added lyrics column to tracks table
# Schema v3 - Added database indexes for improved query performance (created_at, title, play_count, favorite)
