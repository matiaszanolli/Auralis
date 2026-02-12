# Fix for Issue #2067: Migration Race Condition and Backup Failure Handling

**Date**: 2026-02-12
**Issue**: [#2067](https://github.com/matiaszanolli/Auralis/issues/2067)
**Severity**: CRITICAL (race condition) + HIGH (backup failure)

## Problems Fixed

### 1. Race Condition (CRITICAL)
**Problem**: Multiple processes could attempt database migration simultaneously, potentially causing corruption.

**Root Cause**: `check_and_migrate_database()` had no inter-process locking. The "check-then-act" pattern allowed:
1. Process A reads version
2. Process B reads version
3. Both decide migration needed
4. Both attempt migration concurrently on same SQLite file

**Real-world scenarios**:
- Backend + background scanner starting simultaneously
- User accidentally runs `python launch-auralis-web.py` twice
- Desktop app + web interface running concurrently
- System service auto-starting while user manually launches

### 2. Backup Failure Handling (HIGH)
**Problem**: Migration proceeded even if backup creation failed, leaving no safety net for recovery.

**Root Cause**: Line 308 in original code:
```python
except Exception as e:
    logger.error(f"Failed to create backup: {e}")
    logger.warning("Proceeding without backup...")  # BAD!
```

## Solution Implemented

### 1. Inter-Process File Locking
Added `migration_lock()` context manager using platform-specific locking:
- **Linux/macOS**: `fcntl.flock()` with `LOCK_EX | LOCK_NB`
- **Windows**: `msvcrt.locking()` with `LK_NBLCK`

**Features**:
- 30-second default timeout with configurable override
- Automatic lock file cleanup (`.{db_name}.migration.lock`)
- Exception-safe (cleanup guaranteed via `finally` block)
- Clear error messages on timeout

### 2. Double-Check Pattern
After acquiring lock, version is rechecked to handle race where another process completed migration while waiting:
```python
with migration_lock(db_path):
    # Re-check version after acquiring lock
    current_version = manager.get_current_version()
    if current_version == target_version:
        logger.info("Database already migrated by another process")
        return True
```

### 3. Fail-Fast on Backup Failure
Backup failure now aborts migration instead of proceeding:
```python
except Exception as e:
    logger.error(f"Failed to create backup: {e}")
    logger.error("❌ Aborting migration - backup failed")
    return False  # ABORT!
```

## Files Modified

1. **`auralis/library/migration_manager.py`**
   - Added imports: `platform`, `contextlib.contextmanager`, `fcntl`/`msvcrt`
   - Added `migration_lock()` context manager (79 lines)
   - Modified `check_and_migrate_database()` to use lock and fail on backup error

2. **`tests/test_migrations.py`**
   - Fixed imports from `migrations` → `migration_manager`
   - Added `TestMigrationConcurrency` class with 6 new tests

## Test Coverage

### New Tests (6)
1. `test_migration_lock_basic` - Lock acquisition and cleanup
2. `test_migration_lock_blocks_concurrent_access` - Lock prevents concurrent access
3. `test_concurrent_migration_attempts` - Multiple processes (multiprocessing)
4. `test_backup_failure_aborts_migration` - Migration aborts on backup failure
5. `test_migration_lock_cleanup_on_exception` - Lock cleanup on error
6. `test_recheck_version_after_lock_acquisition` - Double-check pattern

### Test Results
```
18 passed, 1 warning in 1.33s
```
- ✅ All existing tests still pass (backward compatible)
- ✅ All new concurrency tests pass

## Acceptance Criteria ✅

- ✅ Only one process can run migrations at a time
- ✅ Second process blocks and waits (or fails gracefully with timeout)
- ✅ Migration aborts if backup fails
- ✅ Lock file cleaned up after migration completes

## Performance Impact

**Minimal**:
- Lock acquisition adds ~100ms in contended case (waiting for lock)
- Uncontended case (normal startup): ~1ms overhead for lock file operations
- Double-check adds one extra `SELECT` query (~1ms)

## Backwards Compatibility

✅ **Fully backward compatible**:
- No API changes (same function signatures)
- No breaking changes to existing code
- All existing tests pass
- Graceful degradation on lock timeout (returns `False` instead of crashing)

## Edge Cases Handled

1. **Lock file already exists** - Waits up to timeout, then fails with clear error
2. **Permission denied** - Propagates `OSError` with clear message
3. **Database already migrated while waiting** - Double-check pattern detects and skips
4. **Exception during migration** - Lock cleanup guaranteed via `finally` block
5. **Backup directory doesn't exist** - `mkdir(parents=True, exist_ok=True)` handles it

## Future Improvements (Optional)

1. **Make migrations idempotent** - Defense-in-depth approach (would make race less critical)
2. **Add lock file location to config** - Allow customization for NFS/network shares
3. **Exponential backoff** - Instead of fixed 100ms polling interval
4. **Metrics/monitoring** - Log when processes wait for lock (observability)

## Related Issues

- [#2066](https://github.com/matiaszanolli/Auralis/issues/2066) - Shutdown cleanup
- [#2086](https://github.com/matiaszanolli/Auralis/issues/2086) - Pool config

All three are database lifecycle issues that should be addressed together.
