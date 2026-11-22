# Database Migrations

This directory contains SQL migration scripts for the Auralis database schema.

## Migration File Naming

Format: `migration_vXXX_to_vYYY.sql`

Examples:
- `migration_v000_to_v001_initial_schema.sql` - Initial schema (the only file with a description suffix)
- `migration_v001_to_v002.sql` - Adds lyrics column to tracks and artwork_path to albums
- `migration_v029_to_v030.sql` - Merges duplicate albums, makes albums unique per title and artist
- `migration_v030_to_v031.sql` - Clears `tracks.file_mtime` so the next scan re-reads every track's tags
- `migration_v031_to_v032.sql` - Merges tracks that share a `filepath_key` onto the lowest id, then makes `ix_tracks_filepath_key` unique like a fresh database's
- `migration_v032_to_v033.sql` - Adds `track_artist.position` so a track's artists keep their tag order; existing links are backfilled from insertion order (#6714)
- `migration_v033_to_v034.sql` - Current schema version (drops the unconsumed `user_settings` crossfade/gapless/replay-gain columns, #6683)

## How Migrations Work

1. When the app starts, it checks the current database schema version
2. If the database version is older than the app version, migrations are applied
3. Each migration is applied sequentially (v1→v2→v3, etc.)
4. A backup is automatically created before applying migrations
5. Each successful migration is recorded in the `schema_version` table

## Creating a New Migration

1. Increment the version number in `auralis/__version__.py`
2. Create a new migration SQL file in this directory
3. Test the migration thoroughly before release
4. Document any breaking changes in the changelog

## Migration File Structure

```sql
-- Migration from v1 to v2: Add processing history
-- Author: Your Name
-- Date: 2024-XX-XX

-- Add new table
CREATE TABLE processing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER REFERENCES tracks(id),
    preset_name VARCHAR,
    -- ... other fields
);

-- Add new column to existing table (if needed)
ALTER TABLE tracks ADD COLUMN new_field VARCHAR;

-- Migration complete
```

## Important Notes

- Never modify existing migration files after they've been released
- Always test migrations with both fresh databases and existing data
- Include rollback instructions in comments if possible
- Keep migrations idempotent when possible (use IF NOT EXISTS, etc.)
