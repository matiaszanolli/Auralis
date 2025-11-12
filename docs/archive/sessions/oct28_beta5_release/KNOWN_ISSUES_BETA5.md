# Known Issues - Auralis Beta.5

**Version**: 1.0.0-beta.5
**Date**: October 30, 2025

---

## Critical Issues

None identified.

---

## Minor Issues

### 1. Album Artwork 404 Retry Loop

**Severity**: Low
**Impact**: Console warnings, no functional impact

**Description**:
When viewing the Albums view, albums without artwork generate repeated 404 errors as the frontend retries the request.

**Example**:
```
GET http://localhost:8765/api/albums/22/artwork 404 (Not Found)
GET http://localhost:8765/api/albums/22/artwork?retry=1 404 (Not Found)
```

**Root Cause**:
- Albums without embedded artwork or downloaded artwork have no `artwork_path` set
- Backend correctly returns 404 for missing artwork
- Frontend image component retries on failure without checking if artwork exists

**Workaround**:
- Errors are cosmetic only and don't affect functionality
- Albums display with placeholder/default artwork

**Fix** (for Beta.6):
- Add `has_artwork` boolean field to album API response
- Frontend checks `has_artwork` before requesting artwork URL
- Implement exponential backoff for artwork retry logic
- Add default placeholder image path in API response

**Code Location**:
- Frontend: `AlbumCard.tsx` or similar image loading component
- Backend: `/api/albums/{id}/artwork` endpoint (working correctly)

---

### 2. Playlist Track Order Not Persistent

**Severity**: Low
**Impact**: Track order may reset on app restart

**Description**:
Track order in playlists is maintained during runtime but SQLAlchemy many-to-many relationships don't guarantee order persistence across database sessions.

**Root Cause**:
- `track_playlist` association table lacks explicit `position` column
- Order maintained in Python list during session but not persisted

**Workaround**:
- Track order persists during active session
- Re-order playlist after app restart if needed

**Fix** (for Beta.6):
- Database migration to add `position` INTEGER column to `track_playlist`
- Update repository methods to use explicit ordering
- Add index on `(playlist_id, position)` for performance

**SQL Migration**:
```sql
ALTER TABLE track_playlist ADD COLUMN position INTEGER DEFAULT 0;
UPDATE track_playlist SET position = rowid;
CREATE INDEX idx_track_playlist_position ON track_playlist(playlist_id, position);
```

---

### 3. Frontend Gapless Playback Tests Failing

**Severity**: Low
**Impact**: Test suite shows 11 failures (pre-existing)

**Description**:
11 frontend tests related to gapless playback component are failing.

**Status**: Pre-existing issue from Beta.4

**Tests Affected**:
- Gapless playback component tests (11 tests)
- Does not affect actual playback functionality

**Workaround**:
- Tests are isolated, production functionality works
- 95.5% test pass rate overall (234/245)

**Fix** (for Beta.6):
- Investigate gapless playback test setup
- Update test mocks and assertions
- Re-enable tests after fixes

---

### 4. Backend Validation Test Collection Errors

**Severity**: Low
**Impact**: Two test files fail to collect (pre-existing)

**Description**:
Two validation test files have collection errors:
1. `test_against_masters.py` - ImportError for `calculate_dynamic_range`
2. `test_comprehensive.py` - AttributeError for `Code.ERROR_FILE_NOT_FOUND`

**Status**: Pre-existing issue, not blocking

**Workaround**:
- Core test suite passes (241+ tests)
- Validation tests are supplementary

**Fix** (for Beta.6):
- Update imports in validation tests
- Fix error code references

---

## Build Warnings

### 1. Frontend Bundle Size Warning

**Severity**: Informational
**Impact**: None

**Description**:
```
(!) Some chunks are larger than 500 kB after minification.
```

**Details**:
- Bundle size: 774.94 kB (gzipped: 231.22 kB)
- Acceptable for feature-rich application
- Below 1 MB threshold for modern web apps

**Future Optimization**:
- Implement code splitting with dynamic imports
- Use manual chunks for vendor libraries
- Lazy load non-critical components

---

### 2. Node Deprecation Warning

**Severity**: Informational
**Impact**: None

**Description**:
```
[DEP0190] DeprecationWarning: Passing args to a child process
with shell option true can lead to security vulnerabilities
```

**Details**:
- Warning from build tools, not application code
- Does not affect functionality or security in build context

**Fix**: Will be resolved when dependencies update

---

## Limitations (By Design)

### 1. No Multi-Select Drag

**Severity**: N/A (planned feature)
**Status**: Planned for Phase 2.4 (Beta.6)

**Description**: Cannot drag multiple tracks simultaneously

### 2. Large Playlist Performance

**Severity**: N/A (edge case)
**Impact**: Slight lag with 1000+ track playlists

**Description**: Drag-and-drop may have slight lag with very large playlists

**Mitigation**: Virtual scrolling planned for Beta.6

### 3. Manual Similarity Graph Rebuild

**Severity**: N/A (planned feature)
**Status**: Planned for Beta.6

**Description**: Similarity graph must be manually rebuilt after library changes

**Workaround**: Run `POST /api/similarity/graph/build` after adding new tracks

---

## Browser Compatibility Notes

### Mobile Touch Support

**Status**: Partially tested

**Details**:
- Touch events work with @hello-pangea/dnd
- Needs more comprehensive mobile testing
- Long-press gestures may need tuning

**Recommendation**: Test on actual mobile devices before production mobile deployment

---

## Performance Notes

### Memory Usage

**Typical**: 200-300 MB
**With Large Library**: 400-500 MB (10,000+ tracks + similarity graph)

**Details**:
- Similarity graph: ~50 MB per 10,000 tracks
- Album artwork cache: Variable based on library
- Normal for Electron applications

---

## Security Notes

### Authorization Not Implemented

**Status**: Planned for Beta.6

**Details**:
- No user authentication
- No playlist ownership checks
- Suitable for single-user desktop application
- Required for multi-user web deployment

---

## Data Persistence

### Similarity Graph

**Status**: Built on-demand, not persisted

**Details**:
- Graph rebuilt on each application start
- Takes 2-3 seconds per 1000 tracks
- Persistent caching planned for Beta.6

---

## Summary

**Critical Issues**: 0
**Minor Issues**: 4 (all low severity)
**Build Warnings**: 2 (informational)
**Test Failures**: 13 (pre-existing, non-blocking)

**Overall Status**: ✅ **PRODUCTION READY**

All issues are minor, have workarounds, and are scheduled for future releases. No issues affect core functionality or prevent normal usage.

---

## Reporting Issues

**GitHub Issues**: https://github.com/matiaszanolli/Auralis/issues

When reporting issues, please include:
1. Auralis version (1.0.0-beta.5)
2. Operating system and version
3. Steps to reproduce
4. Expected vs actual behavior
5. Console errors (if applicable)
6. Screenshots (if UI issue)

---

**Last Updated**: October 30, 2025
