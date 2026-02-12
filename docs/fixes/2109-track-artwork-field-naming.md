# Fix for Issue #2109: Track Artwork Field Naming Chaos

**Date**: 2026-02-12
**Issue**: [#2109](https://github.com/matiaszanolli/Auralis/issues/2109)
**Severity**: HIGH

## Problem Fixed

### Issue Description
Track artwork used inconsistent field names across multiple layers:

| Layer | Field Name | Type | Status |
|-------|-----------|------|--------|
| Backend `Track.to_dict()` | `album_art` | snake_case | ❌ Wrong |
| Backend API Types | `artwork_url` | snake_case | ✅ Correct |
| Frontend Transformer | `artwork_url` → `artworkUrl` | Conversion | ✅ Correct |
| Frontend Domain | `artworkUrl` | camelCase | ✅ Correct |
| Frontend WebSocket | `artwork_url` | snake_case | ✅ Correct |
| Frontend PlayerSlice | `coverUrl` | camelCase | ❌ Wrong |

### Impact
1. **Functionality**: Components using wrong field name fail to display artwork
2. **Maintainability**: Inconsistent naming causes confusion
3. **Type Safety**: Mismatched types break TypeScript contracts

### Root Cause
- Backend returned `album_art` instead of `artwork_url`
- PlayerSlice used `coverUrl` instead of `artworkUrl`
- No standardization across layers

## Solution Implemented

### 1. Backend - Standardize on `artwork_url`

**File**: `auralis/library/models/core.py`

**Before**:
```python
return {
    ...
    'album_art': album_artwork,  # Non-standard name
    ...
}
```

**After**:
```python
return {
    ...
    'artwork_url': album_artwork,  # Standardized field name
    ...
}
```

### 2. Frontend PlayerSlice - Standardize on `artworkUrl`

**File**: `auralis-web/frontend/src/store/slices/playerSlice.ts`

**Before**:
```typescript
export interface Track {
  ...
  coverUrl?: string;  // Non-standard name
}
```

**After**:
```typescript
export interface Track {
  ...
  artworkUrl?: string;  // Standardized field name (was coverUrl)
}
```

### 3. Data Flow After Fix

```
Backend (Python)
  ↓
Track.to_dict()
  ↓ artwork_url (snake_case)
  ↓
FastAPI Response
  ↓
Frontend Transformer (trackTransformer.ts)
  ↓ artwork_url → artworkUrl
  ↓
Domain Model (types/domain.ts)
  ↓ artworkUrl (camelCase)
  ↓
React Components
```

## Test Coverage

### New Tests (7 tests)
**File**: `tests/backend/test_track_artwork_field_naming.py`

#### TestTrackArtworkFieldNaming (3 tests)
- ✅ `test_track_uses_artwork_url_not_album_art` - Verifies correct field name
- ✅ `test_track_without_artwork_returns_none` - Handles missing artwork
- ✅ `test_orphan_track_returns_none_artwork` - Handles tracks without albums

#### TestFieldNamingConsistency (3 tests)
- ✅ `test_no_deprecated_field_names_in_track_dict` - No `album_art`, `coverUrl`, etc.
- ✅ `test_artwork_url_is_api_url_not_filesystem_path` - Returns API URL
- ✅ `test_field_name_snake_case_at_api_boundary` - Snake_case at Python layer

#### TestAPIContractCompliance (1 test)
- ✅ `test_track_dict_matches_TrackApiResponse_contract` - Matches TypeScript interface

**Result**: 7 tests PASSING

## Field Naming Standard

### Established Convention

**Backend (Python)**:
- Use `artwork_url` (snake_case)
- Example: `{'artwork_url': '/api/albums/123/artwork'}`

**Frontend (TypeScript)**:
- Use `artworkUrl` (camelCase)
- Example: `{artworkUrl: '/api/albums/123/artwork'}`

### Deprecated Names (Do Not Use)

❌ `album_art` - Old backend name
❌ `cover_url` / `coverUrl` - Old alternative name
❌ `albumArt` - Never use (inconsistent with domain model)

## Acceptance Criteria ✅

- ✅ Backend returns `artwork_url` (snake_case)
- ✅ Frontend domain uses `artworkUrl` (camelCase)
- ✅ PlayerSlice uses `artworkUrl` (matches domain)
- ✅ All deprecated field names removed
- ✅ Comprehensive test coverage
- ✅ Type safety preserved

## Impact on Components

### Components Already Using Correct Names ✅

These components use the transformer/domain types and work correctly:
- `AlbumCard` - Uses `artworkUrl` from domain
- `TrackCard` - Uses `albumArt` prop (local name, not API field)
- `LibraryComponents` - Uses `artworkUrl` from domain
- All WebSocket handlers - Use `artwork_url` from API

### No Breaking Changes

**Why No Component Updates Needed**:
1. Frontend transformer already mapped `artwork_url` → `artworkUrl`
2. Components already used domain types with `artworkUrl`
3. Only backend and PlayerSlice had mismatched names
4. Fixing backend makes existing transformer work correctly

## Verification Steps

### Manual Testing
1. Start Auralis: `python launch-auralis-web.py --dev`
2. Play a track
3. Check Redux DevTools → Player State
4. Verify `currentTrack` has `artworkUrl`, not `coverUrl`
5. Verify track artwork displays in player

### Automated Testing
```bash
# Run new tests
python -m pytest tests/backend/test_track_artwork_field_naming.py -v

# Verify no regressions
python -m pytest tests/backend/test_albums_api.py tests/backend/test_artwork_url_fix.py -v
```

## Files Changed

1. `auralis/library/models/core.py` - Track model `to_dict()`
2. `auralis-web/frontend/src/store/slices/playerSlice.ts` - Track interface
3. `tests/backend/test_track_artwork_field_naming.py` - New tests (7 tests)
4. `docs/fixes/2109-track-artwork-field-naming.md` - This documentation

**Total**: 2 code files, 1 test file, 1 doc file, +7 tests

## Future Improvements (Optional)

1. **Generate TypeScript types from Python models** - Prevents drift
2. **Add ESLint rule** - Prevent deprecated field names
3. **Migration guide** - Document naming conventions for contributors

## Related Issues

- [#2107](https://github.com/matiaszanolli/Auralis/issues/2107) - Album artwork path leakage (also fixed `artwork_path` → URL)
- Both issues part of larger artwork API standardization effort

## Summary

**Problem**: Track artwork used 5 different field names across layers
**Solution**: Standardized on `artwork_url` (backend) and `artworkUrl` (frontend)
**Result**: ✅ Type-safe, consistent naming across entire stack
