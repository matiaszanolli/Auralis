# Backend Refactoring Roadmap

**Priority**: MEDIUM-HIGH
**Current Status**: 🔴 Critical - main.py has grown to **1,960 lines** with **59 endpoints**
**Target**: Modular architecture with files under 300 lines each
**Estimated Effort**: 8-12 hours

---

## Current Problems

### 1. **Monolithic main.py** (1,960 lines)
- ❌ 59 API endpoints in a single file
- ❌ Hard to navigate and understand
- ❌ Merge conflicts in team development
- ❌ Difficult to test individual components
- ❌ Violates Single Responsibility Principle

### 2. **Endpoint Categories Mixed Together**
```
Library endpoints (tracks, albums, artists, playlists)  → ~800 lines
Player endpoints (play, pause, seek, volume)           → ~400 lines
Enhancement endpoints (presets, intensity, toggle)     → ~200 lines
File/upload endpoints (scan, upload, formats)          → ~150 lines
Artwork endpoints (get, extract, delete)               → ~200 lines
Infrastructure (WebSocket, health, version)            → ~150 lines
```

### 3. **Poor Separation of Concerns**
- Business logic mixed with HTTP handling
- State management scattered across endpoints
- Duplicate error handling patterns
- No clear dependency injection

---

## Refactoring Strategy

### Phase 1: Extract API Routers (4-6 hours)
**Goal**: Split 59 endpoints into focused router modules

#### 1.1 Create Router Structure
```
auralis-web/backend/
├── main.py                    # 100-150 lines (FastAPI app + startup only)
├── routers/
│   ├── __init__.py
│   ├── library.py             # Library endpoints (~300 lines)
│   ├── player.py              # Player control endpoints (~200 lines)
│   ├── enhancement.py         # Enhancement settings (~150 lines)
│   ├── playlists.py           # Playlist management (~250 lines)
│   ├── artwork.py             # Album artwork (~150 lines)
│   ├── files.py               # File upload/scan (~100 lines)
│   └── system.py              # Health, version, WebSocket (~100 lines)
```

#### 1.2 Router Responsibilities

**routers/library.py** - Music library operations
```python
# Endpoints:
GET    /api/library/stats
GET    /api/library/tracks
GET    /api/library/tracks/favorites
POST   /api/library/tracks/{id}/favorite
DELETE /api/library/tracks/{id}/favorite
GET    /api/library/tracks/{id}/lyrics
GET    /api/library/artists
GET    /api/library/artists/{id}
GET    /api/library/albums
GET    /api/library/albums/{id}
```

**routers/player.py** - Playback control
```python
# Endpoints:
GET    /api/player/status
GET    /api/player/stream/{track_id}
POST   /api/player/load
POST   /api/player/play
POST   /api/player/pause
POST   /api/player/stop
POST   /api/player/seek
POST   /api/player/volume
POST   /api/player/next
POST   /api/player/previous
GET    /api/player/queue
POST   /api/player/queue/add
POST   /api/player/queue/remove
POST   /api/player/queue/clear
POST   /api/player/queue/shuffle
```

**routers/enhancement.py** - Real-time enhancement settings
```python
# Endpoints:
POST   /api/player/enhancement/toggle
POST   /api/player/enhancement/preset
POST   /api/player/enhancement/intensity
GET    /api/player/enhancement/status
```

**routers/playlists.py** - Playlist management
```python
# Endpoints:
GET    /api/playlists
GET    /api/playlists/{id}
POST   /api/playlists
PUT    /api/playlists/{id}
DELETE /api/playlists/{id}
POST   /api/playlists/{id}/tracks
DELETE /api/playlists/{id}/tracks/{track_id}
DELETE /api/playlists/{id}/tracks
```

**routers/artwork.py** - Album artwork handling
```python
# Endpoints:
GET    /api/albums/{id}/artwork
POST   /api/albums/{id}/artwork/extract
DELETE /api/albums/{id}/artwork
```

**routers/files.py** - File operations
```python
# Endpoints:
POST   /api/library/scan
POST   /api/files/upload
GET    /api/audio/formats
```

**routers/system.py** - System/infrastructure
```python
# Endpoints:
GET    /api/health
GET    /api/version
WebSocket /ws
```

---

### Phase 2: Extract Service Layer (3-4 hours)
**Goal**: Separate business logic from HTTP handling

#### 2.1 Create Service Structure
```
auralis-web/backend/
├── services/
│   ├── __init__.py
│   ├── library_service.py     # Library business logic
│   ├── player_service.py      # Player state management
│   ├── enhancement_service.py # Enhancement logic
│   ├── playlist_service.py    # Playlist operations
│   └── artwork_service.py     # Artwork extraction/management
```

#### 2.2 Service Responsibilities

**services/library_service.py**
```python
class LibraryService:
    def __init__(self, library_manager: LibraryManager):
        self.library = library_manager

    def get_tracks(self, limit: int, offset: int, search: str = None):
        """Business logic for retrieving tracks"""
        # Validation, filtering, pagination logic here

    def get_track_lyrics(self, track_id: int):
        """Extract and format lyrics from audio file"""
        # Complex lyrics extraction logic here

    # ... other library methods
```

**services/player_service.py**
```python
class PlayerService:
    def __init__(self, player: EnhancedAudioPlayer, state_manager: PlayerStateManager):
        self.player = player
        self.state = state_manager

    async def play_track(self, track_id: int):
        """Load and play a track"""
        # Complex playback logic here

    async def stream_with_enhancement(self, track_id: int, preset: str, intensity: float):
        """Stream audio with real-time enhancement"""
        # Proactive buffering, chunked processing logic here

    # ... other player methods
```

#### 2.3 Benefits of Service Layer
- ✅ Routers become thin HTTP handlers (5-10 lines per endpoint)
- ✅ Business logic testable without HTTP layer
- ✅ Easy to reuse logic across multiple endpoints
- ✅ Clear dependency injection patterns

---

### Phase 3: Dependency Injection (1-2 hours)
**Goal**: Clean initialization and dependency management

#### 3.1 Create Dependency Container
```python
# dependencies.py
from functools import lru_cache

@lru_cache()
def get_library_service() -> LibraryService:
    return LibraryService(library_manager)

@lru_cache()
def get_player_service() -> PlayerService:
    return PlayerService(audio_player, player_state_manager)

# ... other service factories
```

#### 3.2 Use in Routers
```python
# routers/library.py
from fastapi import APIRouter, Depends
from services.library_service import LibraryService
from dependencies import get_library_service

router = APIRouter(prefix="/api/library", tags=["library"])

@router.get("/tracks")
async def get_tracks(
    limit: int = 50,
    offset: int = 0,
    search: str = None,
    library: LibraryService = Depends(get_library_service)
):
    return library.get_tracks(limit, offset, search)
```

---

## Implementation Plan

### Step 1: Create Router Structure (1-2 hours)
```bash
# Create directories
mkdir -p auralis-web/backend/routers
mkdir -p auralis-web/backend/services

# Create empty files
touch auralis-web/backend/routers/__init__.py
touch auralis-web/backend/routers/{library,player,enhancement,playlists,artwork,files,system}.py
touch auralis-web/backend/services/__init__.py
touch auralis-web/backend/services/{library_service,player_service,enhancement_service}.py
```

### Step 2: Extract System Router First (30 minutes)
**Why start here**: Simple, self-contained, good template for others

```python
# routers/system.py
from fastapi import APIRouter, WebSocket

router = APIRouter()

@router.get("/api/health")
async def health_check():
    # Move from main.py lines 231-238

@router.get("/api/version")
async def get_version():
    # Move from main.py lines 240-253

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Move from main.py lines 175-229
```

### Step 3: Extract Library Router (1-2 hours)
**Most endpoints**, needs careful migration

```python
# routers/library.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from dependencies import get_library_manager

router = APIRouter(prefix="/api/library", tags=["library"])

# Migrate all library endpoints (~10 endpoints)
```

### Step 4: Extract Remaining Routers (2-3 hours)
- `routers/player.py` (~15 endpoints)
- `routers/enhancement.py` (~4 endpoints)
- `routers/playlists.py` (~7 endpoints)
- `routers/artwork.py` (~3 endpoints)
- `routers/files.py` (~3 endpoints)

### Step 5: Update main.py (30 minutes)
```python
# main.py (final ~150 lines)
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routers import system, library, player, enhancement, playlists, artwork, files

app = FastAPI(title="Auralis Web API")

# Include routers
app.include_router(system.router)
app.include_router(library.router)
app.include_router(player.router)
app.include_router(enhancement.router)
app.include_router(playlists.router)
app.include_router(artwork.router)
app.include_router(files.router)

# Startup event
@app.on_event("startup")
async def startup_event():
    # Initialize global components
    # (Keep this in main.py for now)

# Serve static files
app.mount("/", StaticFiles(directory="frontend/build", html=True), name="frontend")
```

### Step 6: Extract Service Layer (2-3 hours)
Move business logic from routers to services

### Step 7: Add Dependency Injection (1 hour)
Create `dependencies.py` and update routers

### Step 8: Testing (1-2 hours)
- ✅ All 96 backend tests still pass
- ✅ No regressions in API behavior
- ✅ Frontend still works correctly

---

## Expected Results

### Before Refactoring
```
main.py                          1,960 lines  (59 endpoints)
```

### After Refactoring
```
main.py                            150 lines  (startup + FastAPI app)
routers/system.py                  100 lines  (3 endpoints)
routers/library.py                 300 lines  (10 endpoints)
routers/player.py                  200 lines  (15 endpoints)
routers/enhancement.py             150 lines  (4 endpoints)
routers/playlists.py               250 lines  (7 endpoints)
routers/artwork.py                 150 lines  (3 endpoints)
routers/files.py                   100 lines  (3 endpoints)
services/library_service.py        200 lines
services/player_service.py         250 lines
services/enhancement_service.py    100 lines
dependencies.py                     50 lines
-------------------------------------------------------
Total:                           2,000 lines  (similar total, but modular!)
```

### Benefits
- ✅ **No file over 300 lines** (down from 1,960!)
- ✅ **Clear separation of concerns** (HTTP vs business logic)
- ✅ **Easy to navigate** (find endpoints by category)
- ✅ **Better testability** (test services independently)
- ✅ **Team-friendly** (fewer merge conflicts)
- ✅ **Follows FastAPI best practices**

---

## Migration Strategy

### Option A: Incremental (Safer)
1. Create new router files
2. Copy endpoints to routers (keep in main.py)
3. Test both old and new endpoints work
4. Remove from main.py once verified
5. Repeat for each router

**Pros**: Zero downtime, can test incrementally
**Cons**: Temporary duplication
**Timeline**: 2-3 days with testing between steps

### Option B: Big Bang (Faster)
1. Create all router files
2. Move all endpoints in one session
3. Update imports in main.py
4. Test everything at once

**Pros**: Faster, cleaner commit history
**Cons**: Higher risk, needs extensive testing after
**Timeline**: 1 day intensive work + 1 day testing

---

## Recommended Approach

**Hybrid Strategy**: Start incremental, finish big bang

1. **Day 1 Morning**: Extract system router (low risk, template for others)
2. **Day 1 Afternoon**: Extract library router (most endpoints, test thoroughly)
3. **Day 2 Morning**: Extract remaining routers (player, enhancement, etc.)
4. **Day 2 Afternoon**: Service layer extraction
5. **Day 3**: Dependency injection + comprehensive testing

---

## Success Metrics

- ✅ main.py under 200 lines
- ✅ No router file over 300 lines
- ✅ All 96 backend tests pass
- ✅ Frontend works without changes
- ✅ No performance degradation
- ✅ Improved code maintainability score

---

## Next Steps

When you're ready to tackle this:

1. **Create feature branch**: `git checkout -b refactor/backend-routers`
2. **Start with Phase 1**: Extract routers (low risk)
3. **Test incrementally**: Run tests after each router extraction
4. **Phase 2 optional**: Service layer can be separate PR if Phase 1 takes longer

**Ready to start?** I can begin with extracting the system router as a proof of concept!
