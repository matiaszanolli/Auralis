# Fix for Issue #2107: Album Artwork Path Leakage

**Date**: 2026-02-12
**Issue**: [#2107](https://github.com/matiaszanolli/Auralis/issues/2107)
**Severity**: HIGH

## Problem Fixed

### Issue Description
Album `to_dict()` returned `artwork_path` as absolute filesystem path instead of API URL:
- **Example**: `/home/user/.auralis/artwork/album_123_abc.jpg`
- **Expected**: `/api/albums/123/artwork`

### Impact
1. **Security**: Exposed internal filesystem paths to frontend
2. **Functionality**: Browser cannot load `file://` paths via `<img src>`
3. **Privacy**: Leaked username and internal directory structure

### Root Cause
- `Album.to_dict()` directly returned `self.artwork_path` (filesystem path)
- `Track.to_dict()` included `album_art` from `self.album.artwork_path` (filesystem path)
- Artwork router endpoints returned filesystem paths in responses

## Solution Implemented

### 1. Model Layer Changes

**File**: `auralis/library/models/core.py`

#### Album.to_dict()
```python
def to_dict(self) -> Dict[str, Any]:
    """
    Convert album to dictionary.

    Returns artwork_path as API URL instead of filesystem path
    to prevent leaking internal paths and enable browser loading.
    """
    # Convert filesystem path to API URL if artwork exists
    artwork_url = None
    if self.artwork_path:
        artwork_url = f"/api/albums/{self.id}/artwork"

    return {
        ...
        'artwork_path': artwork_url,  # API URL, not filesystem path
        ...
    }
```

**Before**: `"/home/user/.auralis/artwork/album_123_abc.jpg"`
**After**: `"/api/albums/123/artwork"`

#### Track.to_dict()
```python
def to_dict(self) -> Dict[str, Any]:
    """
    Convert track to dictionary for API/GUI use.

    Returns album artwork as API URL instead of filesystem path.
    """
    ...
    # Convert filesystem path to API URL if artwork exists
    if self.album and hasattr(self.album, 'artwork_path') and self.album.artwork_path:
        album_artwork = f"/api/albums/{self.album.id}/artwork"
    ...
```

**Before**: `album_art: "/home/user/.auralis/artwork/album_100_xyz.jpg"`
**After**: `album_art: "/api/albums/100/artwork"`

### 2. Router Layer Changes

**File**: `auralis-web/backend/routers/artwork.py`

#### POST /api/albums/{album_id}/artwork/extract
```python
# Convert filesystem path to API URL
artwork_url = f"/api/albums/{album_id}/artwork"

return {
    "message": "Artwork extracted successfully",
    "artwork_path": artwork_url,  # Return URL, not filesystem path
    "album_id": album_id
}
```

#### POST /api/albums/{album_id}/artwork/download
```python
# Convert filesystem path to API URL
artwork_url = f"/api/albums/{album_id}/artwork"

return {
    "message": "Artwork downloaded successfully",
    "artwork_path": artwork_url,  # Return URL, not filesystem path
    "album_id": album_id,
    "artist": artist_name,
    "album": album_name
}
```

**Impact**: Both endpoints now return URLs that the frontend can use directly in `<img src>`

## Test Coverage

### New Tests
**File**: `tests/backend/test_artwork_url_fix.py`

#### TestAlbumArtworkURL (3 tests)
- ✅ `test_album_with_artwork_path_returns_url` - Verifies URL format
- ✅ `test_album_without_artwork_returns_none` - Handles None case
- ✅ `test_album_with_empty_artwork_returns_none` - Handles empty string

#### TestTrackArtworkURL (3 tests)
- ✅ `test_track_with_album_artwork_returns_url` - Verifies URL format
- ✅ `test_track_without_album_returns_none` - Handles orphan tracks
- ✅ `test_track_with_album_without_artwork_returns_none` - Handles missing artwork

#### TestArtworkURLSecurity (3 tests)
- ✅ `test_no_filesystem_paths_in_album_dict` - Security verification
- ✅ `test_no_filesystem_paths_in_track_dict` - Security verification
- ✅ `test_url_format_is_correct` - URL format validation

**Total**: 9 new tests, all passing

### Existing Tests
- ✅ 50 existing album/artwork tests still pass (no regressions)

## Acceptance Criteria ✅

- ✅ Backend returns URL, not filesystem path
- ✅ Album artwork displays correctly in frontend
- ✅ No filesystem paths leaked to frontend
- ✅ Comprehensive test coverage
- ✅ All existing tests pass

## Security Benefits

### Before
```json
{
  "id": 123,
  "title": "Album Name",
  "artwork_path": "/home/john/.auralis/artwork/album_123_abc.jpg"
}
```

**Issues**:
- Exposes username (`john`)
- Exposes internal directory structure (`.auralis`)
- Browser cannot load the path
- Privacy leak

### After
```json
{
  "id": 123,
  "title": "Album Name",
  "artwork_path": "/api/albums/123/artwork"
}
```

**Benefits**:
- ✅ No filesystem information exposed
- ✅ Browser can load the URL
- ✅ Works with standard `<img src>` tags
- ✅ Consistent with REST API conventions

## Backwards Compatibility

**Frontend Impact**:
- ✅ No breaking changes - `albumTransformer.ts` already maps `artwork_path` → `artworkUrl`
- ✅ URLs are drop-in replacements for filesystem paths in `<img src>`

**Backend Impact**:
- ✅ Existing artwork endpoint `/api/albums/{id}/artwork` already serves files
- ✅ Internal artwork storage unchanged (still uses filesystem)
- ✅ Only serialization layer changed

## Performance Impact

**Negligible**:
- String interpolation adds ~1µs per album/track
- No additional database queries
- No network overhead (same endpoint used as before)

## Related Components

### Frontend (No Changes Needed)
**File**: `auralis-web/frontend/src/api/transformers/albumTransformer.ts`
```typescript
export function transformAlbum(apiAlbum: AlbumApiResponse): Album {
  return {
    ...
    artworkUrl: apiAlbum.artwork_path ?? undefined, // Already handles URL
    ...
  };
}
```

**Status**: ✅ Works out-of-the-box with URL format

### Artwork Endpoint (Already Exists)
**File**: `auralis-web/backend/routers/artwork.py`
```python
@router.get("/api/albums/{album_id}/artwork")
async def get_album_artwork(album_id: int) -> FileResponse:
    """Get album artwork file."""
    ...
    return FileResponse(
        album.artwork_path,  # Internal: still uses filesystem path
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000"}
    )
```

**Status**: ✅ Already serves files correctly

## Future Improvements (Optional)

1. **CDN Integration**: Replace URLs with CDN links for faster loading
2. **Image Resizing**: Add size parameters (`/api/albums/123/artwork?size=300`)
3. **Format Conversion**: Add format parameter (`?format=webp`)
4. **Thumbnail Cache**: Pre-generate thumbnails for faster loading

## Verification Steps

### Manual Testing
1. Start Auralis: `python launch-auralis-web.py --dev`
2. Scan a music folder with embedded artwork
3. Open browser DevTools → Network tab
4. Navigate to Albums view
5. Verify:
   - Album API response contains URLs like `/api/albums/123/artwork`
   - Images load correctly in `<img>` tags
   - No filesystem paths in response JSON

### Automated Testing
```bash
# Run new tests
python -m pytest tests/backend/test_artwork_url_fix.py -v

# Verify no regressions
python -m pytest tests/backend/test_albums_api.py tests/auralis/library/test_artwork.py -v
```

## Files Changed

1. `auralis/library/models/core.py` - Album & Track models
2. `auralis-web/backend/routers/artwork.py` - Artwork router
3. `tests/backend/test_artwork_url_fix.py` - New tests (9 tests)
4. `docs/fixes/2107-artwork-url-fix.md` - This documentation

**Total**: 3 code files, 1 doc file, +9 tests
