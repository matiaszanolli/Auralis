# Database Migrations

This directory contains SQL migration scripts for the Auralis database schema.

## Migration File Naming

Format: `migration_vXXX_to_vYYY_description.sql`

Examples:
- `migration_v000_to_v001_initial_schema.sql` - Initial schema (documented but not used)
- `migration_v001_to_v002_add_processing_history.sql` - Add processing history tracking
- `migration_v002_to_v003_add_user_preferences.sql` - Add user preferences

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
