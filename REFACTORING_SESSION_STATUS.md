# Backend Refactoring Session Status

**Date**: 2025-10-22
**Status**: 🟡 IN PROGRESS - Phase 1 Step 1 Complete
**Priority**: 🔴 HIGH - Critical for maintainability

---

## Session Summary

Successfully began the backend refactoring roadmap to break up the monolithic main.py (1,960 lines, 59 endpoints) into modular routers. Completed the first router extraction as a proof-of-concept and established the migration pattern.

---

## What We Accomplished This Session

### ✅ 1. Created Comprehensive Refactoring Roadmap
**File**: [BACKEND_REFACTORING_ROADMAP.md](BACKEND_REFACTORING_ROADMAP.md)
- Detailed 3-phase plan (routers → services → dependency injection)
- 8-12 hour estimated effort
- Before/after file structure
- Migration strategies (incremental vs big bang)
- Success metrics defined

**Added to CLAUDE.md** (lines 897-900):
```markdown
**⚠️ High Priority Technical Debt:**
- **Backend Refactoring**: 🔴 MEDIUM-HIGH PRIORITY - main.py has grown to 1,960 lines with 59 endpoints
- **See**: `BACKEND_REFACTORING_ROADMAP.md` for comprehensive modularization plan (8-12 hours)
- **Impact**: Maintainability, testability, team collaboration
```

### ✅ 2. Implemented Proactive Buffering System (Completed Earlier)
**File**: [auralis-web/backend/proactive_buffer.py](auralis-web/backend/proactive_buffer.py)
- Buffers first 3 chunks (90 seconds) for all 5 presets when track loads
- Enables instant preset switching with zero wait time
- Tested and working: 15 chunks buffered (3 × 5 presets)
- Integrated into stream endpoint at [main.py:1038-1048](auralis-web/backend/main.py#L1038-L1048)

### ✅ 3. Router Infrastructure Created
**Directory**: `auralis-web/backend/routers/`
- Created routers directory structure
- Created `__init__.py` with placeholder imports

### ✅ 4. System Router Extracted & Tested
**File**: [auralis-web/backend/routers/system.py](auralis-web/backend/routers/system.py) - 119 lines

**Endpoints Extracted**:
- ✅ `GET /api/health` - Health check endpoint
- ✅ `GET /api/version` - Version information
- ✅ `WebSocket /ws` - Real-time communication (ping/pong, settings updates, job progress)

**Testing Results**:
```bash
✅ GET /api/health - Working
✅ GET /api/version - Working
✅ WebSocket /ws - Working (ping/pong tested)
```

**Integration Pattern Established**:
```python
# In main.py (after line 175):
from routers.system import create_system_router

system_router = create_system_router(
    manager=manager,
    library_manager=None,  # Updated after startup
    processing_engine=None,  # Updated after startup
    HAS_AURALIS=HAS_AURALIS
)
app.include_router(system_router)
```

**Migration Safety**:
- Old endpoints kept as `_old` variants for testing
- Both old and new endpoints working simultaneously
- Can safely remove old endpoints after full migration

---

## Current File Status

### main.py Line Count
- **Before refactoring**: 1,960 lines
- **Current**: 1,975 lines (temporarily higher due to keeping old endpoints)
- **Expected after cleanup**: ~150 lines

### Files Created
```
auralis-web/backend/
├── routers/
│   ├── __init__.py                 (13 lines - placeholder)
│   └── system.py                   (119 lines - DONE ✅)
├── proactive_buffer.py             (120 lines - DONE ✅)
└── main.py                         (1,975 lines - IN PROGRESS 🟡)
```

---

## Next Steps (In Order of Priority)

### Phase 1: Extract Remaining Routers (~6-8 hours remaining)

#### **Step 1: Extract Files Router** (30 minutes - EASIEST)
**Why next**: Simplest router, only 3 endpoints, good warm-up

**Endpoints to extract** (from main.py):
```python
POST   /api/library/scan           # Line ~859
POST   /api/files/upload           # Line ~902
GET    /api/audio/formats          # Line ~936
```

**Create**: `routers/files.py` (~100 lines)
**Pattern**: Similar to system.py with factory function

#### **Step 2: Extract Enhancement Router** (30 minutes)
**Endpoints to extract**:
```python
POST   /api/player/enhancement/toggle     # Line ~1115
POST   /api/player/enhancement/preset     # Line ~1139
POST   /api/player/enhancement/intensity  # Line ~1171
GET    /api/player/enhancement/status     # Line ~1201
```

**Create**: `routers/enhancement.py` (~150 lines)

#### **Step 3: Extract Artwork Router** (45 minutes)
**Endpoints to extract**:
```python
GET    /api/albums/{album_id}/artwork         # Line ~750
POST   /api/albums/{album_id}/artwork/extract # Line ~789
DELETE /api/albums/{album_id}/artwork         # Line ~826
```

**Create**: `routers/artwork.py` (~150 lines)

#### **Step 4: Extract Playlists Router** (1-1.5 hours)
**Endpoints to extract**:
```python
GET    /api/playlists                      # Line ~503
GET    /api/playlists/{playlist_id}        # Line ~519
POST   /api/playlists                      # Line ~546
PUT    /api/playlists/{playlist_id}        # Line ~585
DELETE /api/playlists/{playlist_id}        # Line ~623
POST   /api/playlists/{playlist_id}/tracks # Line ~653
DELETE /api/playlists/{playlist_id}/tracks/{track_id} # Line ~687
DELETE /api/playlists/{playlist_id}/tracks # Line ~715
```

**Create**: `routers/playlists.py` (~250 lines)

#### **Step 5: Extract Library Router** (1.5-2 hours - LARGEST)
**Endpoints to extract**:
```python
GET    /api/library/stats                  # Line ~256
GET    /api/library/tracks                 # Line ~268
GET    /api/library/tracks/favorites       # Line ~303
POST   /api/library/tracks/{id}/favorite   # Line ~326
DELETE /api/library/tracks/{id}/favorite   # Line ~340
GET    /api/library/tracks/{id}/lyrics     # Line ~354
GET    /api/library/artists                # Line ~431
GET    /api/library/artists/{id}           # Line ~447
GET    /api/library/albums                 # Line ~465
GET    /api/library/albums/{id}            # Line ~481
```

**Create**: `routers/library.py` (~300 lines)

#### **Step 6: Extract Player Router** (2-3 hours - MOST COMPLEX)
**Endpoints to extract**:
```python
GET    /api/player/status                  # Line ~948
GET    /api/player/stream/{track_id}       # Line ~961 (COMPLEX - 150+ lines)
POST   /api/player/load                    # Line ~1210
POST   /api/player/play                    # Line ~1234
POST   /api/player/pause                   # Line ~1252
POST   /api/player/stop                    # Line ~1270
POST   /api/player/seek                    # Line ~1289
POST   /api/player/volume                  # Line ~1309
POST   /api/player/next                    # Line ~1328
POST   /api/player/previous                # Line ~1349
GET    /api/player/queue                   # Line ~1370
POST   /api/player/queue/add               # Line ~1391
POST   /api/player/queue/remove            # Line ~1419
POST   /api/player/queue/clear             # Line ~1446
POST   /api/player/queue/shuffle           # Line ~1466
```

**Create**: `routers/player.py` (~400 lines)
**Note**: Stream endpoint is complex with proactive buffering - needs careful migration

#### **Step 7: Clean Up main.py** (30 minutes)
- Remove all `_old` endpoints
- Remove duplicate code
- Verify only startup, app initialization, and router includes remain
- **Target**: main.py under 200 lines

---

## Migration Pattern (Proven & Working)

### 1. Create Router File
```python
# routers/example.py
from fastapi import APIRouter, HTTPException
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["example"])

def create_example_router(dependency1, dependency2):
    """Factory function for dependency injection"""

    @router.get("/api/example")
    async def example_endpoint():
        # Endpoint logic here
        return {"status": "ok"}

    return router
```

### 2. Integrate into main.py
```python
# In main.py imports:
from routers.example import create_example_router

# After dependencies are created:
example_router = create_example_router(dep1, dep2)
app.include_router(example_router)
```

### 3. Rename Old Endpoint (Keep for Testing)
```python
# Old endpoint in main.py
@app.get("/api/example_old")  # Changed from /api/example
async def example_endpoint_old():
    # Keep original logic
```

### 4. Test Both Endpoints
```bash
# Test new router endpoint
curl http://localhost:8765/api/example

# Test old endpoint still works
curl http://localhost:8765/api/example_old
```

### 5. Remove Old Endpoint After Verification
```python
# Delete the _old endpoint from main.py
```

---

## Testing Checklist

After each router extraction:

```bash
# 1. Restart backend
fuser -k 8765/tcp
cd /mnt/data/src/matchering/auralis-web/backend
python main.py > /tmp/backend_refactor.log 2>&1 &

# 2. Test health check
curl http://localhost:8765/api/health

# 3. Test extracted endpoints
# (Use curl commands for each endpoint)

# 4. Check logs for errors
tail -50 /tmp/backend_refactor.log | grep -E "(ERROR|✅|❌)"

# 5. Run backend tests
cd /mnt/data/src/matchering
python -m pytest tests/backend/ -v
```

---

## Known Dependencies Between Endpoints

### Global State Variables (needed by routers):
```python
library_manager: Optional[LibraryManager]      # Used by: library, player, files
settings_repository: Optional[SettingsRepository] # Used by: enhancement
audio_player: Optional[EnhancedAudioPlayer]    # Used by: player
player_state_manager: Optional[PlayerStateManager] # Used by: player
processing_cache: dict                         # Used by: player (streaming)
processing_engine: Optional[ProcessingEngine]  # Used by: system (WebSocket)
manager: ConnectionManager                     # Used by: system (WebSocket)
HAS_AURALIS: bool                             # Used by: system, library
HAS_PROCESSING: bool                          # Used by: player (enhancement)
```

### Factory Function Parameters:
Each router's `create_*_router()` function should accept the dependencies it needs.

**Example**:
```python
# routers/player.py
def create_player_router(
    library_manager,
    audio_player,
    player_state_manager,
    processing_cache,
    HAS_PROCESSING
):
    # Router logic
```

---

## Backend Currently Running

**PID**: Check with `ps aux | grep "python main.py"`
**Port**: 8765
**Log**: `/tmp/backend_refactor.log`
**Status**: ✅ Running with system router integrated

**To restart**:
```bash
fuser -k 8765/tcp
cd /mnt/data/src/matchering/auralis-web/backend
python main.py > /tmp/backend_refactor.log 2>&1 &
sleep 4
curl http://localhost:8765/api/health
```

---

## Files to Reference

### Documentation
- [BACKEND_REFACTORING_ROADMAP.md](BACKEND_REFACTORING_ROADMAP.md) - Full refactoring plan
- [CLAUDE.md](CLAUDE.md#L897-900) - Project status with refactoring priority
- This file - Session handoff

### Code Files Modified
- [auralis-web/backend/main.py](auralis-web/backend/main.py) - Main application (in progress)
- [auralis-web/backend/routers/system.py](auralis-web/backend/routers/system.py) - System router (complete)
- [auralis-web/backend/routers/__init__.py](auralis-web/backend/routers/__init__.py) - Router package init
- [auralis-web/backend/proactive_buffer.py](auralis-web/backend/proactive_buffer.py) - Proactive buffering (complete)

### Test Files
- [tests/backend/](tests/backend/) - Backend test suite (96 tests, should all pass)
- Run: `python -m pytest tests/backend/ -v`

---

## Quick Start for Next Session

```bash
# 1. Check backend status
curl http://localhost:8765/api/health

# 2. If not running, start it:
cd /mnt/data/src/matchering/auralis-web/backend
fuser -k 8765/tcp
python main.py > /tmp/backend_refactor.log 2>&1 &
sleep 4

# 3. Verify system router works
curl http://localhost:8765/api/health
curl http://localhost:8765/api/version

# 4. Check current line count
wc -l /mnt/data/src/matchering/auralis-web/backend/main.py

# 5. Start with files router (easiest next step)
# Follow pattern in routers/system.py
```

---

## Success Metrics

### Progress Tracking
- ✅ **Completed**: 3 endpoints extracted (system router)
- 🔄 **In Progress**: 56 endpoints remaining
- 📊 **Progress**: 5% complete (3/59 endpoints)

### Target Goals
- ✅ main.py under 200 lines (currently 1,975)
- ✅ All routers under 300 lines each
- ✅ All 96 backend tests passing
- ✅ No functionality regression
- ✅ Clean dependency injection pattern

### Current Status
- ✅ Router pattern proven and working
- ✅ Migration strategy validated
- ✅ No test failures
- ✅ Backend running smoothly

---

## Estimated Time Remaining

- **Files Router**: 30 minutes
- **Enhancement Router**: 30 minutes
- **Artwork Router**: 45 minutes
- **Playlists Router**: 1-1.5 hours
- **Library Router**: 1.5-2 hours
- **Player Router**: 2-3 hours
- **Cleanup**: 30 minutes

**Total**: 6-8 hours remaining

---

## Notes for Next Session

1. **Start with files router** - It's the simplest and will give quick wins
2. **Test after each router** - Don't extract multiple routers without testing
3. **Keep old endpoints** - Only remove after verifying new router works
4. **Run backend tests frequently** - Catch regressions early
5. **Player router is complex** - The streaming endpoint has 150+ lines with proactive buffering, needs careful extraction

6. **Consider creating service layer** - If routers get too complex, extract business logic to services (Phase 2 of roadmap)

---

## Contact Points

If issues arise:
- Check `/tmp/backend_refactor.log` for errors
- Verify all imports are correct
- Ensure factory functions receive all needed dependencies
- Test endpoints individually with curl
- Run pytest to catch regressions

**The pattern is proven - just repeat it for each remaining router! 🚀**
