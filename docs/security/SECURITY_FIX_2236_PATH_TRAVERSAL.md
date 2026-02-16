# Security Fix: Path Traversal Vulnerability (Issue #2236)

**Date**: 2026-02-16
**Severity**: HIGH
**CVE**: N/A (internal project)
**Status**: FIXED

## Vulnerability Description

Two endpoints in the player router accepted arbitrary file paths from user input without validation:

1. `POST /api/player/load` - Accepted `track_path` parameter
2. `POST /api/player/queue/add` - Accepted `track_path` parameter

This allowed attackers to load arbitrary files from the filesystem using path traversal attacks:

```bash
# Example exploit
curl -X POST "http://localhost:8765/api/player/load?track_path=../../../etc/passwd"
```

## Root Cause

The endpoints directly used user-supplied file paths without validation:

```python
# VULNERABLE CODE
@router.post("/api/player/load")
async def load_track(track_path: str, track_id: int | None = None):
    track_info = {
        'filepath': track_path,  # NO VALIDATION - accepts arbitrary paths
        'id': track_id
    }
    audio_player.add_to_queue(track_info)
```

## Fix Implementation

### Backend Changes

1. **Removed `track_path` parameter** - No longer accepts arbitrary file paths
2. **Made `track_id` required** - Forces database-backed validation
3. **Added database lookup** - Validates track exists and retrieves validated filepath
4. **Added Pydantic models** - Type-safe request validation

```python
# SECURE CODE
class LoadTrackRequest(BaseModel):
    track_id: int

@router.post("/api/player/load")
async def load_track(request: LoadTrackRequest, background_tasks: BackgroundTasks = None):
    # Security: Query track from database to validate file path
    library_manager = get_library_manager()
    track = library_manager.tracks.get_by_id(request.track_id)
    if not track:
        raise HTTPException(status_code=404, detail=f"Track {request.track_id} not found")

    track_info = {
        'filepath': track.filepath,  # Security: Use validated path from database
        'id': track.id
    }
    audio_player.add_to_queue(track_info)
```

### Files Modified

- `auralis-web/backend/routers/player.py`:
  - Lines 159-213: Fixed `load_track` endpoint
  - Lines 315-333: Fixed `add_to_queue` endpoint
  - Lines 67-75: Added `LoadTrackRequest` Pydantic model
- `tests/backend/test_main_api.py`:
  - Lines 452-462: Updated test to use new API contract

### API Contract Changes

#### Before (VULNERABLE)
```bash
# Query parameters
POST /api/player/load?track_path=/path/to/file.mp3&track_id=1
POST /api/player/queue/add?track_path=/path/to/file.mp3
```

#### After (SECURE)
```bash
# JSON body with required track_id
POST /api/player/load
Content-Type: application/json
{"track_id": 1}

POST /api/player/queue/add
Content-Type: application/json
{"track_id": 1, "position": null}
```

## Testing

### Security Tests

All existing tests pass, including:

1. **Backend Tests**:
   - `test_player_api_comprehensive.py::TestLoadTrack` (4 tests) ✅
   - `test_main_api.py::TestPlayerEndpoints::test_load_track` (1 test) ✅

2. **Frontend Tests**:
   - `usePlaybackQueue.test.ts` (19 tests) ✅

### Manual Verification

```bash
# Test 1: Valid track ID (should succeed)
curl -X POST http://localhost:8765/api/player/load \
  -H "Content-Type: application/json" \
  -d '{"track_id": 1}'

# Test 2: Invalid track ID (should return 404)
curl -X POST http://localhost:8765/api/player/load \
  -H "Content-Type: application/json" \
  -d '{"track_id": 999999}'

# Test 3: Path traversal attempt (should return 422 - invalid request format)
curl -X POST http://localhost:8765/api/player/load \
  -H "Content-Type: application/json" \
  -d '{"track_path": "../../../etc/passwd"}'
```

## Impact Assessment

### Security Impact
- **Before**: HIGH - Arbitrary file read via path traversal
- **After**: NONE - All file paths validated against database

### Compatibility Impact
- **Frontend**: NO BREAKING CHANGES - Frontend already uses correct API contract
- **Backend**: BREAKING CHANGE - Old query parameter API no longer supported
- **Migration**: None required - frontend already compatible

## References

- GitHub Issue: #2236
- OWASP: [Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory

## Lessons Learned

1. **Never trust user input** - All file paths must be validated
2. **Use database-backed validation** - Query from trusted source of truth
3. **Defense in depth** - Combine multiple validation layers
4. **Fail securely** - Return 404 instead of error details on invalid input

## Follow-up Actions

- [ ] Security audit of other endpoints accepting file paths
- [ ] Add input validation tests for all endpoints
- [ ] Document secure coding patterns in CLAUDE.md
- [ ] Add pre-commit hook to detect path traversal vulnerabilities
