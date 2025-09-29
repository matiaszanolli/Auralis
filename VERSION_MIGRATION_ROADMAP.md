# Version Management & Database Migration Roadmap 🔄

**Date:** September 29, 2025
**Status:** 📋 Planning Phase
**Priority:** 🔴 Critical for Production

---

## Executive Summary

Before launching Auralis to users, we need a robust version management and database migration system to handle:
- App version updates
- Database schema changes
- User data preservation
- Backward compatibility
- Seamless user experience

---

## Current State Analysis

### Database Schema (SQLite)

**Location:** `~/.auralis/library.db` (or user config directory)

**Current Tables:**
```sql
tracks          -- Audio track metadata & analysis
albums          -- Album information
artists         -- Artist information
genres          -- Genre tags
playlists       -- User playlists
track_artist    -- Many-to-many: tracks ↔ artists
track_genre     -- Many-to-many: tracks ↔ genres
track_playlist  -- Many-to-many: tracks ↔ playlists
```

**Key Fields in `tracks` table:**
- Core: id, title, filepath, duration, format
- Audio: sample_rate, bit_depth, channels, filesize
- Analysis: peak_level, rms_level, dr_rating, lufs_level
- Auralis: mastering_quality, recommended_reference, processing_profile
- Metadata: album_id, track_number, year, comments
- Stats: play_count, last_played, skip_count, favorite
- Timestamps: created_at, updated_at

### Current Version Info

**No version tracking currently implemented!** ⚠️

Current files lack version information:
- No `__version__` in package
- No database schema version table
- No migration scripts
- No version checking on startup

---

## Version Management Strategy

### 1. Application Versioning (Semantic Versioning)

**Format:** `MAJOR.MINOR.PATCH` (e.g., `1.0.0`)

- **MAJOR:** Breaking changes (incompatible API/DB changes)
- **MINOR:** New features (backward compatible)
- **PATCH:** Bug fixes (backward compatible)

**Version Storage Locations:**
```
auralis/__version__.py          # Python package version
auralis-web/package.json        # Frontend/Electron version
auralis-web/backend/version.py  # Backend API version
```

### 2. Database Schema Versioning

**Add new table: `schema_version`**
```sql
CREATE TABLE schema_version (
    id INTEGER PRIMARY KEY,
    version INTEGER NOT NULL,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    migration_script TEXT
);
```

**Schema Version Timeline:**
```
v1 (1.0.0): Initial schema (current state)
v2 (1.1.0): Add processing_history table (planned)
v3 (1.2.0): Add user_preferences table (planned)
v4 (2.0.0): Major schema refactor (future)
```

### 3. Migration Script Naming

**Format:** `migration_vXXX_to_vYYY_description.sql`

**Examples:**
```
migrations/
├── migration_v001_initial_schema.sql
├── migration_v002_add_processing_history.sql
├── migration_v003_add_user_preferences.sql
├── migration_v004_add_cached_analysis.sql
└── migration_v005_add_preset_favorites.sql
```

---

## Implementation Plan

### Phase 1: Version Infrastructure (1-2 hours)

#### Task 1.1: Add Version Files
```python
# auralis/__version__.py
__version__ = "1.0.0"
__version_info__ = (1, 0, 0)
__db_schema_version__ = 1

# auralis-web/backend/version.py
API_VERSION = "1.0.0"
MIN_CLIENT_VERSION = "1.0.0"
```

#### Task 1.2: Create Schema Version Table
```python
# auralis/library/migrations.py
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, DateTime, String, Text
from datetime import datetime

def create_schema_version_table(engine):
    """Create schema_version tracking table"""
    metadata = MetaData()
    schema_version = Table(
        'schema_version', metadata,
        Column('id', Integer, primary_key=True),
        Column('version', Integer, nullable=False, unique=True),
        Column('applied_at', DateTime, default=datetime.utcnow),
        Column('description', Text),
        Column('migration_script', Text)
    )
    metadata.create_all(engine)
```

#### Task 1.3: Add Version Check on Startup
```python
# auralis/library/manager.py
def check_database_version(self):
    """Check and upgrade database if needed"""
    current_version = self._get_current_schema_version()
    required_version = __db_schema_version__

    if current_version < required_version:
        logger.info(f"Database migration needed: v{current_version} → v{required_version}")
        self._run_migrations(current_version, required_version)
    elif current_version > required_version:
        raise Exception(f"Database version too new! App: v{required_version}, DB: v{current_version}")
```

### Phase 2: Migration System (2-3 hours)

#### Task 2.1: Create Migration Manager
```python
# auralis/library/migrations.py

class MigrationManager:
    """Handles database schema migrations"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')

    def get_current_version(self) -> int:
        """Get current database schema version"""
        try:
            result = self.engine.execute("SELECT MAX(version) FROM schema_version")
            version = result.scalar()
            return version if version else 0
        except:
            return 0  # Fresh database

    def apply_migration(self, from_version: int, to_version: int):
        """Apply migration from one version to another"""
        migration_file = f"migration_v{from_version:03d}_to_v{to_version:03d}.sql"
        migration_path = Path(__file__).parent / "migrations" / migration_file

        if not migration_path.exists():
            raise FileNotFoundError(f"Migration script not found: {migration_file}")

        # Read and execute migration
        with open(migration_path) as f:
            sql = f.read()

        with self.engine.begin() as conn:
            conn.execute(sql)

        # Record migration
        self._record_migration(to_version, f"Migrated from v{from_version} to v{to_version}")

    def migrate_to_latest(self):
        """Migrate database to latest schema version"""
        current = self.get_current_version()
        target = __db_schema_version__

        while current < target:
            next_version = current + 1
            logger.info(f"Applying migration to v{next_version}...")
            self.apply_migration(current, next_version)
            current = next_version
```

#### Task 2.2: Create Initial Migrations
```sql
-- migrations/migration_v000_to_v001_initial_schema.sql
-- Initial schema (current state)

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR NOT NULL,
    filepath VARCHAR NOT NULL UNIQUE,
    duration FLOAT,
    -- ... (all current fields)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ... (all other tables)

INSERT INTO schema_version (version, description)
VALUES (1, 'Initial schema');
```

#### Task 2.3: Create Backup System
```python
def backup_database_before_migration(db_path: str) -> str:
    """Create backup before migration"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"

    import shutil
    shutil.copy2(db_path, backup_path)

    logger.info(f"Database backed up to: {backup_path}")
    return backup_path
```

### Phase 3: App Update System (3-4 hours)

#### Task 3.1: Version Check on Startup
```python
# main.py or startup code

from auralis.__version__ import __version__, __db_schema_version__
from auralis.library.migrations import MigrationManager

async def startup_checks():
    """Perform startup version and migration checks"""
    logger.info(f"Auralis v{__version__} starting...")

    # Check database version
    db_path = get_database_path()
    migration_manager = MigrationManager(db_path)

    current_db_version = migration_manager.get_current_version()
    logger.info(f"Database schema: v{current_db_version}")

    if current_db_version < __db_schema_version__:
        logger.warning(f"Database migration required: v{current_db_version} → v{__db_schema_version__}")

        # Backup first
        backup_path = backup_database_before_migration(db_path)

        try:
            # Run migrations
            migration_manager.migrate_to_latest()
            logger.info("✅ Database migration successful!")
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            # Restore backup
            restore_database_backup(backup_path, db_path)
            raise
```

#### Task 3.2: Auto-Update System (Electron)
```javascript
// desktop/main.js

const { autoUpdater } = require('electron-updater');

autoUpdater.on('update-available', () => {
  dialog.showMessageBox({
    type: 'info',
    title: 'Update Available',
    message: 'A new version of Auralis is available. Download now?',
    buttons: ['Yes', 'Later']
  }).then((result) => {
    if (result.response === 0) {
      autoUpdater.downloadUpdate();
    }
  });
});

autoUpdater.on('update-downloaded', () => {
  dialog.showMessageBox({
    type: 'info',
    title: 'Update Ready',
    message: 'Update downloaded. Restart to install?',
    buttons: ['Restart', 'Later']
  }).then((result) => {
    if (result.response === 0) {
      autoUpdater.quitAndInstall();
    }
  });
});
```

### Phase 4: User Communication (1-2 hours)

#### Task 4.1: Migration UI
```typescript
// frontend/src/components/MigrationDialog.tsx

interface MigrationDialogProps {
  oldVersion: string;
  newVersion: string;
  onComplete: () => void;
}

export function MigrationDialog({ oldVersion, newVersion, onComplete }: MigrationDialogProps) {
  return (
    <Dialog open={true}>
      <DialogTitle>Database Update Required</DialogTitle>
      <DialogContent>
        <Typography>
          Auralis needs to update your library database from v{oldVersion} to v{newVersion}.
        </Typography>
        <Typography variant="body2" color="textSecondary">
          This is a one-time process and your data will be preserved.
        </Typography>
        <LinearProgress />
      </DialogContent>
    </Dialog>
  );
}
```

#### Task 4.2: Changelog Display
```typescript
// Show what's new after update
const CHANGELOG = {
  "1.1.0": [
    "Added processing history tracking",
    "Improved audio analysis accuracy",
    "Bug fixes and performance improvements"
  ],
  "1.2.0": [
    "New user preferences system",
    "Customizable presets",
    "Enhanced library management"
  ]
};
```

---

## Planned Migrations

### v1 → v2: Processing History (Version 1.1.0)

**New Table: `processing_history`**
```sql
CREATE TABLE processing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER REFERENCES tracks(id),
    preset_name VARCHAR,
    settings_json TEXT,
    output_path VARCHAR,
    processing_time FLOAT,
    quality_metrics_json TEXT,
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose:** Track all processing jobs for history/undo

### v2 → v3: User Preferences (Version 1.2.0)

**New Table: `user_preferences`**
```sql
CREATE TABLE user_preferences (
    id INTEGER PRIMARY KEY,
    key VARCHAR UNIQUE NOT NULL,
    value TEXT,
    category VARCHAR,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose:** Store user settings persistently

### v3 → v4: Analysis Cache (Version 1.3.0)

**New Table: `cached_analysis`**
```sql
CREATE TABLE cached_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER REFERENCES tracks(id),
    analysis_type VARCHAR,
    analysis_data TEXT,  -- JSON
    computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(track_id, analysis_type)
);
```

**Purpose:** Cache expensive audio analysis results

---

## Testing Strategy

### Migration Testing Checklist

- [ ] **Fresh Install** - Test on empty database
- [ ] **v1 → v2 Migration** - Test first upgrade path
- [ ] **v1 → v3 Skip** - Test skipping versions
- [ ] **Rollback** - Test backup/restore
- [ ] **Large Library** - Test with 10,000+ tracks
- [ ] **Corrupted DB** - Test error handling
- [ ] **Concurrent Access** - Test multi-instance safety

### Test Scenarios

```python
# tests/test_migrations.py

def test_fresh_database():
    """Test initializing new database"""
    db_path = ":memory:"
    manager = MigrationManager(db_path)
    manager.migrate_to_latest()
    assert manager.get_current_version() == __db_schema_version__

def test_v1_to_v2_migration():
    """Test migration from v1 to v2"""
    # Create v1 database
    # Apply migration
    # Verify schema and data integrity
    pass

def test_migration_rollback():
    """Test backup/restore on failed migration"""
    # Backup database
    # Simulate failed migration
    # Verify rollback works
    pass
```

---

## Deployment Checklist

### Before First Public Release

- [ ] **Add version files** to all packages
- [ ] **Create schema_version table** in existing databases
- [ ] **Set initial version** to v1 (current schema)
- [ ] **Create migration_v001_initial.sql** documenting current state
- [ ] **Add version check** to startup sequence
- [ ] **Test migration system** with sample databases
- [ ] **Document migration process** for developers

### Before Each New Release

- [ ] **Update version numbers** in all files
- [ ] **Create migration scripts** if schema changed
- [ ] **Test migrations** on various scenarios
- [ ] **Create changelog** entry
- [ ] **Tag release** in git
- [ ] **Build and test** packages
- [ ] **Update documentation**

### After Release

- [ ] **Monitor migration success** rates
- [ ] **Collect error reports**
- [ ] **Prepare hotfix** if needed
- [ ] **Update migration docs** with learnings

---

## File Structure

```
auralis/
├── __version__.py                    # Main version file
├── library/
│   ├── models.py                     # Database models
│   ├── manager.py                    # Library manager (add version check)
│   ├── migrations.py                 # NEW: Migration manager
│   └── migrations/                   # NEW: Migration scripts directory
│       ├── migration_v000_to_v001_initial_schema.sql
│       ├── migration_v001_to_v002_processing_history.sql
│       ├── migration_v002_to_v003_user_preferences.sql
│       └── README.md

auralis-web/
├── backend/
│   ├── version.py                    # NEW: Backend version
│   └── main.py                       # Add version check on startup
├── frontend/
│   ├── package.json                  # Update version
│   └── src/
│       └── components/
│           └── MigrationDialog.tsx   # NEW: Migration UI

desktop/
├── package.json                      # Update version
└── main.js                           # Add auto-update support

tests/
└── test_migrations.py                # NEW: Migration tests
```

---

## Best Practices

### ✅ DO:
1. **Always backup** before migration
2. **Test migrations** thoroughly before release
3. **Document changes** in migration files
4. **Version everything** (DB, API, UI)
5. **Use transactions** for migrations
6. **Log all operations** during migration
7. **Provide rollback** mechanism
8. **Show progress** to users during long migrations

### ❌ DON'T:
1. **Never modify** old migration files
2. **Never delete** user data without confirmation
3. **Never force** immediate updates
4. **Don't skip** version checks
5. **Don't ignore** migration errors
6. **Don't remove** backward compatibility hastily

---

## Emergency Procedures

### If Migration Fails

1. **Automatic Rollback**
   ```python
   try:
       apply_migration()
   except Exception as e:
       logger.error(f"Migration failed: {e}")
       restore_backup()
       raise
   ```

2. **User Instructions**
   - Show error dialog
   - Provide backup location
   - Offer manual restore option
   - Contact support information

3. **Developer Response**
   - Hotfix release ASAP
   - Provide migration repair tool
   - Update migration script
   - Add more validation

---

## Success Metrics

### Key Performance Indicators

- **Migration Success Rate:** Target >99.5%
- **Average Migration Time:** <5 seconds
- **User Data Loss:** 0%
- **Rollback Success Rate:** 100%
- **Version Compatibility:** 100% backward compatible within major version

---

## Timeline

### Immediate (Before Launch)
**Week 1:** Implement version infrastructure
- Create version files
- Add schema_version table
- Basic migration system

### Short-term (First Month)
**Week 2-4:** Testing and refinement
- Comprehensive migration tests
- User communication UI
- Documentation

### Long-term (Ongoing)
**Month 2+:** Maintenance and improvements
- Monitor migration metrics
- Refine migration scripts
- Add new features with proper migrations

---

## Resources

### Tools Needed
- **Alembic** - Consider for advanced migrations (optional)
- **SQLAlchemy** - Already using for ORM
- **pytest** - For migration testing
- **electron-updater** - For auto-updates

### Documentation Links
- SQLAlchemy Migrations: https://docs.sqlalchemy.org/en/14/core/metadata.html
- Electron Auto Update: https://www.electron.build/auto-update
- Semantic Versioning: https://semver.org/

---

## Conclusion

**Status:** 📋 **Comprehensive Plan Ready**

This roadmap provides a complete strategy for version management and database migrations. Implementation will ensure:

✅ Smooth user updates
✅ Zero data loss
✅ Professional user experience
✅ Developer-friendly migration system
✅ Production-grade reliability

**Next Step:** Implement Phase 1 (Version Infrastructure) before public launch.

---

**Created:** September 29, 2025
**Priority:** 🔴 Critical
**Estimated Implementation:** 8-12 hours
**Status:** Ready for implementation