# Phase 4 API Audit - Backend vs Frontend Contract Mismatch

**Date:** November 30, 2025
**Status:** ASSESSMENT IN PROGRESS

---

## 🔍 Player Endpoints Audit

### 1. GET /api/player/status
**Backend:** No parameters
**Frontend expects:** No parameters ✅
**Status:** COMPATIBLE

---

### 2. POST /api/player/load
**Backend:** `track_path: str (required, query)`, `track_id: int (optional, query)`
**Frontend expects:** `{track_id}` in JSON body
**Status:** ❌ MISMATCH - Need to fix

**Current Frontend Code:**
```typescript
await api.post('/api/player/load', { track_id }); // Wrong!
```

**Should Be:**
```typescript
await api.post('/api/player/load?track_path={path}&track_id={id}'); // Correct
```

---

### 3. POST /api/player/play
**Backend:** No parameters
**Frontend expects:** No parameters
**Status:** ✅ COMPATIBLE

---

### 4. POST /api/player/pause
**Backend:** No parameters
**Frontend expects:** No parameters
**Status:** ✅ COMPATIBLE

---

### 5. POST /api/player/stop
**Backend:** No parameters
**Frontend expects:** No parameters
**Status:** ✅ COMPATIBLE

---

### 6. POST /api/player/seek
**Backend:** `position: float (query, required)`
**Frontend expects:** `{position}` in JSON body
**Status:** ❌ MISMATCH - Need to fix

**Current Frontend:**
```typescript
await api.post('/api/player/seek', { position }); // Wrong!
```

**Should Be:**
```typescript
await api.post('/api/player/seek?position={value}'); // Correct
```

---

### 7. GET /api/player/volume
**Backend:** No parameters
**Frontend expects:** No parameters
**Status:** ✅ COMPATIBLE

---

### 8. POST /api/player/volume
**Backend:** `volume: int (query, required)` - 0-100
**Frontend expects:** `{volume}` in JSON body
**Status:** ❌ MISMATCH - Need to fix

**Current Frontend:**
```typescript
await api.post('/api/player/volume', { volume }); // Wrong!
```

**Should Be:**
```typescript
await api.post('/api/player/volume?volume={value}'); // Correct
```

---

### 9. GET /api/player/queue
**Backend:** No parameters
**Frontend expects:** No parameters
**Status:** ✅ COMPATIBLE

---

### 10. POST /api/player/queue
**Backend:** `tracks: List[int] (JSON body)`, `start_index: int (JSON body, optional)`
**Frontend expects:** Same structure
**Status:** ✅ COMPATIBLE

---

### 11. POST /api/player/queue/add
**Backend:** `track_path: str (query, required)`, `position: int (query, optional)`
**Frontend expects:** `{track_id, position}` in JSON body
**Status:** ❌ MISMATCH - Backend expects track_path, frontend has track_id

---

### 12. DELETE /api/player/queue/{index}
**Backend:** `index: int (path parameter)`
**Frontend expects:** Same
**Status:** ✅ COMPATIBLE

---

### 13. PUT /api/player/queue/reorder
**Backend:** `new_order: List[int] (JSON body)`
**Frontend expects:** Same
**Status:** ✅ COMPATIBLE

---

### 14. POST /api/player/queue/clear
**Backend:** No parameters
**Frontend expects:** No parameters
**Status:** ✅ COMPATIBLE

---

### 15. POST /api/player/queue/add-track
**Backend:** `track_path: str (query)`, `position: int (query, optional)`
**Frontend expects:** Different endpoint or payload
**Status:** ❓ UNCLEAR - Might be deprecated

---

### 16. PUT /api/player/queue/move
**Backend:** `from_index: int (JSON)`, `to_index: int (JSON)`
**Frontend expects:** Same
**Status:** ✅ COMPATIBLE

---

### 17. POST /api/player/queue/shuffle
**Backend:** No parameters
**Frontend expects:** No parameters
**Status:** ✅ COMPATIBLE

---

### 18. POST /api/player/next
**Backend:** No parameters
**Frontend expects:** No parameters
**Status:** ✅ COMPATIBLE

---

### 19. POST /api/player/previous
**Backend:** No parameters
**Frontend expects:** No parameters
**Status:** ✅ COMPATIBLE

---

## Summary of Mismatches

| Endpoint | Issue | Severity |
|----------|-------|----------|
| `/api/player/load` | Expects `track_path` query param, frontend sends `track_id` JSON | **CRITICAL** |
| `/api/player/seek` | Expects `position` query param, frontend sends JSON body | **CRITICAL** |
| `/api/player/volume` | Expects `volume` query param, frontend sends JSON body | **CRITICAL** |
| `/api/player/queue/add` | Expects `track_path`, frontend has `track_id` | **CRITICAL** |
| `/api/player/queue/add-track` | Unclear if this is duplicate endpoint | **HIGH** |

---

## Enhancement Endpoints

### POST /api/player/enhancement/toggle
**Backend:** `enabled: bool (query)`
**Frontend expects:** `{enabled}` in JSON body
**Status:** ❌ MISMATCH

### POST /api/player/enhancement/preset
**Backend:** `preset: str (query)` - adaptive, gentle, warm, bright, punchy
**Frontend expects:** `{preset}` in JSON body
**Status:** ❌ MISMATCH

### POST /api/player/enhancement/intensity
**Backend:** `intensity: float (query)` - 0.0-1.0
**Frontend expects:** `{intensity}` in JSON body
**Status:** ❌ MISMATCH

### GET /api/player/enhancement/status
**Backend:** No parameters
**Frontend expects:** No parameters
**Status:** ✅ COMPATIBLE

---

## Pattern Discovery

**Backend Consistency:** ALL POST endpoints use **query parameters**, NOT JSON bodies.
- `/api/player/load?track_path=...&track_id=...`
- `/api/player/seek?position=...`
- `/api/player/volume?volume=...`
- `/api/player/enhancement/toggle?enabled=...`
- etc.

**Frontend Design:** ALL hooks expect **JSON bodies**.
```typescript
// Frontend assumes this pattern:
await api.post('/endpoint', { key: value });
```

---

## Decision Required

**The backend is consistent (all query params).**

**Recommendation:**
- **FIX FRONTEND** to match backend's established pattern (query parameters)
- This is less risky than changing backend APIs
- Backend is already deployed and working
- Frontend is new code

---

## Scope of Work

This will require:
1. **Update usePlaybackControl** to use query params
2. **Update useLibraryQuery** (if any mismatches)
3. **Update useEnhancementControl** to use query params
4. **Update all useRestAPI calls** in hooks
5. **Retest all Phase 1-3 component tests** (they mock API, so should still pass)
6. **Continue Phase 4 integration tests** with corrected API calls

**Estimated Impact:** Medium - affects 3 hooks, but tests already exist to validate

---

## Next Steps

1. **Fix frontend hooks** to use query parameters
2. **Run Phase 1-3 tests** to ensure no regression
3. **Continue Phase 4 integration tests** with corrected API contract

