# Backend Refactoring - Quick Start Guide

**Read this first, then see [REFACTORING_SESSION_STATUS.md](REFACTORING_SESSION_STATUS.md) for full details.**

---

## Current Status

```
✅ System Router Complete (3 endpoints)
🔄 56 Endpoints Remaining
📊 5% Complete

main.py: 1,975 lines → Target: <200 lines
```

---

## What's Been Done

✅ **Proactive Buffering** - Instant preset switching working
✅ **Router Infrastructure** - Directory created, pattern established
✅ **System Router** - Health, version, WebSocket extracted and tested

---

## Next 6 Steps (In Order)

### 1. Files Router (30 min) ⭐ START HERE
```
3 endpoints: scan, upload, formats
Easiest - Good warm-up
```

### 2. Enhancement Router (30 min)
```
4 endpoints: toggle, preset, intensity, status
```

### 3. Artwork Router (45 min)
```
3 endpoints: get, extract, delete
```

### 4. Playlists Router (1-1.5 hrs)
```
8 endpoints: CRUD + track management
```

### 5. Library Router (1.5-2 hrs)
```
10 endpoints: tracks, albums, artists, favorites
LARGEST router
```

### 6. Player Router (2-3 hrs)
```
15 endpoints: playback + streaming
MOST COMPLEX - streaming endpoint is 150+ lines
```

---

## Proven Pattern

### Create Router
```python
# routers/files.py
from fastapi import APIRouter
router = APIRouter(tags=["files"])

def create_files_router(library_manager):
    @router.post("/api/library/scan")
    async def scan_directory(request):
        # Logic here

    return router
```

### Integrate
```python
# main.py
from routers.files import create_files_router

files_router = create_files_router(library_manager)
app.include_router(files_router)
```

### Test
```bash
curl http://localhost:8765/api/library/scan
```

---

## Quick Commands

```bash
# Start backend
cd /mnt/data/src/matchering/auralis-web/backend
fuser -k 8765/tcp
python main.py > /tmp/backend_refactor.log 2>&1 &

# Test
curl http://localhost:8765/api/health

# Check progress
wc -l /mnt/data/src/matchering/auralis-web/backend/main.py

# Run tests
python -m pytest tests/backend/ -v
```

---

## Success Criteria

- ✅ main.py under 200 lines
- ✅ Each router under 300 lines
- ✅ All 96 tests passing
- ✅ No functionality lost

---

**See [REFACTORING_SESSION_STATUS.md](REFACTORING_SESSION_STATUS.md) for complete details, endpoint line numbers, and migration strategy.**
