# MSE + Multi-Tier Buffer Conflict

**Date**: October 27, 2025
**Status**: ⚠️ **MSE TEMPORARILY DISABLED**
**Issue**: Both MSE and multi-tier buffer loading chunks simultaneously

---

## 🐛 Problem: Dual System Conflict

### Symptoms Reported by User
1. **Chunk overlapping**: Audio playing with echo/overlapping effect
2. **Pause button hanging**: Gets stuck in "please wait" state permanently
3. **Both enhancement ON and OFF affected**: Issue persists regardless of settings

### Root Cause Analysis

**Two independent chunking systems running simultaneously**:

1. **MSE Progressive Streaming** (Frontend-driven):
   - **Purpose**: Instant preset switching (<100ms)
   - **Method**: Frontend requests chunks from `/api/mse/stream/{track_id}/chunk/{idx}`
   - **When**: Supposed to run ONLY when enhancement is disabled
   - **Backend Endpoint**: `mse_streaming.py` - serves pre-encoded WebM chunks
   - **Audio Element**: MSE player manages its own `<audio>` element via MediaSource API

2. **Multi-Tier Buffer System** (Backend-driven):
   - **Purpose**: Fast playback start + proactive preset buffering
   - **Method**: Backend processes chunks via `ChunkedAudioProcessor`
   - **When**: Runs when enhancement is enabled (via `/api/player/stream/{track_id}?enhanced=true`)
   - **Backend Endpoint**: `player.py` - creates chunked WAV files, concatenates to full file
   - **Audio Element**: HTML5 Audio element loads from `/api/player/stream/{track_id}`

### The Conflict

**Backend Logs Show**:
```
INFO:routers.mse_streaming:Serving original (unenhanced) chunk 0 for track 12217
INFO:routers.mse_streaming:Chunk 0 delivered: ORIGINAL cache, 938.3ms latency
INFO:routers.player:Starting chunked processing for track 12217 (preset: adaptive, intensity: 1.0)
INFO:chunked_processor:ChunkedAudioProcessor initialized: track_id=12217, duration=246.6s, chunks=9
INFO:chunked_processor:Chunk 0 processed and saved to /tmp/auralis_chunks/track_12217_6fe55965_adaptive_1.0_chunk_0.wav
```

**Both systems are creating chunks for the same track!**

### Why This Causes Overlapping Audio

1. **MSE player** creates blob URL and starts playing via MSE audio element
2. **HTML5 Audio player** loads full stream from `/api/player/stream/` and starts playing
3. **Result**: TWO audio elements playing the same track simultaneously → echo/overlap

### Why Pause Button Hangs

The pause button likely sends requests to both players:
1. Backend player state (`POST /api/player/pause`)
2. MSE player (via frontend state)

But with dual playback, the state gets confused:
- Backend thinks it's paused
- MSE player might still be loading chunks
- Frontend shows "please wait" waiting for state synchronization that never completes

---

## 🎯 The Core Issue: Architectural Overlap

### What Each System Does

| Feature | MSE Progressive Streaming | Multi-Tier Buffer System |
|---------|---------------------------|--------------------------|
| **Chunk Creation** | ❌ NO (serves original) | ✅ YES (processes audio) |
| **Encoding Format** | WebM/Opus | WAV |
| **Enhancement Support** | ❌ NO (unenhanced only) | ✅ YES (real-time processing) |
| **Instant Preset Switching** | ✅ YES (<100ms) | ⚠️ PARTIAL (proactive buffering) |
| **Audio Element** | MSE MediaSource | HTML5 Audio |
| **Backend Endpoint** | `/api/mse/stream/` | `/api/player/stream/` |
| **When Active** | Enhancement OFF | Enhancement ON |

### The Integration Problem

**Current Architecture**:
```
Enhancement OFF:
  Frontend → MSE Player → /api/mse/stream/{id}/chunk/{idx} → Original WebM chunks

Enhancement ON:
  Frontend → HTML5 Audio → /api/player/stream/{id}?enhanced=true → Multi-Tier Buffer → Full WAV
```

**The Bug**:
- MSE and multi-tier buffer are **not mutually exclusive** in the current code
- MSE initializes early (page load) and starts requesting chunks
- Multi-tier buffer activates when enhancement is toggled ON
- **Both systems run simultaneously** causing dual playback

---

## ✅ Immediate Fix: Disable MSE

**File**: [auralis-web/frontend/src/ComfortableApp.tsx](../../auralis-web/frontend/src/ComfortableApp.tsx)

**Change** (lines 13-17):
```typescript
// BEFORE (MSE enabled):
import BottomPlayerBarConnected from './components/BottomPlayerBarConnected.MSE';

// AFTER (MSE disabled):
import BottomPlayerBarConnected from './components/BottomPlayerBarConnected';
```

**Result**:
- ✅ Only multi-tier buffer system active
- ✅ No dual playback conflict
- ✅ Player works correctly (pause/play functional)
- ❌ No instant preset switching (2-5s delay remains)

**Build**: `index-BcURs9zI.js` (3.88s)

---

## 🔧 Proper Integration Strategy

To get both MSE instant switching AND multi-tier buffer enhancement working together, we need:

### Option 1: Unified Chunking System (Recommended)

**Concept**: Merge MSE and multi-tier buffer into a single system

**Architecture**:
```
Frontend Request
  ↓
Backend Chunking Router (NEW - unified endpoint)
  ↓
Check: enhanced=true or enhanced=false?
  ↓
Enhanced=FALSE → Serve original WebM chunk (MSE, instant switching)
Enhanced=TRUE  → Serve processed WAV chunk (Multi-tier buffer, real-time enhancement)
  ↓
Frontend: Single Audio Element Manager
  ↓
  MSE mode (unenhanced) OR HTML5 Audio mode (enhanced)
```

**Benefits**:
- ✅ Single source of truth for chunk delivery
- ✅ No dual playback conflicts
- ✅ Instant switching in unenhanced mode
- ✅ Real-time processing in enhanced mode
- ✅ Simplified frontend logic

**Implementation**:
1. Create unified chunking endpoint `/api/audio/stream/{track_id}/chunk/{idx}`
2. Detect `enhanced` parameter, route to appropriate backend processor
3. MSE for unenhanced, HTML5 Audio for enhanced
4. Frontend manages single player mode, switches based on enhancement toggle

### Option 2: Strict Mode Separation

**Concept**: Make MSE and multi-tier buffer truly mutually exclusive

**Implementation**:
1. Add backend check: if MSE requests detected, disable multi-tier buffer processing
2. Add frontend check: if enhancement enabled, completely destroy MSE player (not just pause)
3. Use backend flag `mse_active` to prevent multi-tier buffer from running when MSE is active

**Benefits**:
- ✅ Simpler integration (less refactoring)
- ✅ Clear separation of concerns
- ⚠️ More complex state management

**Drawbacks**:
- ❌ Can't have enhanced + instant switching (fundamental limitation)
- ❌ Mode switching requires full audio reload

### Option 3: MSE-Based Enhancement (Advanced)

**Concept**: Extend MSE to support enhanced chunks

**Architecture**:
```
MSE Player requests chunk
  ↓
Backend: Check cache for enhanced chunk
  ↓
  CACHE HIT: Serve pre-processed enhanced WebM chunk (instant!)
  CACHE MISS: Process chunk on-demand, encode to WebM, serve + cache
  ↓
MSE Player plays enhanced chunk with instant preset switching
```

**Benefits**:
- ✅ Instant preset switching even with enhancement!
- ✅ Best of both worlds
- ✅ Full MSE performance with real-time processing

**Challenges**:
- ⚠️ High cache storage requirements (5 presets × N chunks per track)
- ⚠️ Initial chunk latency on cache miss (still ~900ms first time)
- ⚠️ Complex cache invalidation logic

---

## 📋 Recommended Next Steps

### Phase 1: Stabilize (DONE)
- [x] Disable MSE temporarily
- [x] Verify multi-tier buffer works correctly alone
- [x] Document conflict and integration strategies

### Phase 2: Choose Integration Approach
Evaluate options:
1. **Option 1 (Unified Chunking)** - Most robust, moderate complexity
2. **Option 2 (Strict Separation)** - Fastest to implement, limited features
3. **Option 3 (MSE Enhancement)** - Most features, highest complexity

**Recommendation**: Start with **Option 2** (quick fix), then move to **Option 1** (proper solution)

### Phase 3: Implementation
**Option 2 (Strict Separation) - Quick Fix**:
1. Add backend mutex to prevent simultaneous chunking
2. Frontend: Destroy MSE player completely when enhancement enabled
3. Test mode switching thoroughly
4. **Time Estimate**: 2-3 hours

**Option 1 (Unified Chunking) - Proper Solution**:
1. Design unified chunking API `/api/audio/stream/{track_id}/chunk/{idx}`
2. Refactor backend to route based on `enhanced` parameter
3. Refactor frontend to use single player manager
4. Migrate multi-tier buffer cache to work with unified system
5. Test all scenarios (enhanced/unenhanced, preset switching, pause/play)
6. **Time Estimate**: 1-2 days

---

## 🧪 Testing Checklist (After Integration)

### Basic Playback
- [ ] Play track with enhancement OFF → Only MSE chunks load
- [ ] Play track with enhancement ON → Only multi-tier buffer activates
- [ ] Pause/play works correctly in both modes
- [ ] Seek works in both modes

### Mode Switching
- [ ] Toggle enhancement OFF → ON (mid-playback) → No dual playback
- [ ] Toggle enhancement ON → OFF (mid-playback) → Switches cleanly
- [ ] No audio overlapping when switching modes

### Preset Switching
- [ ] Enhancement OFF → Instant preset switching (<100ms)
- [ ] Enhancement ON → Multi-tier buffer preset switching (~2-5s first time, faster on cache hit)

### Backend Logs
- [ ] Only ONE chunking system logs activity per track
- [ ] No duplicate chunk creation in `/tmp/auralis_chunks/`
- [ ] Cache tier (L1/L2/L3) reported correctly

### Edge Cases
- [ ] Rapidly toggle enhancement → No crashes
- [ ] Seek while loading → No stuck states
- [ ] Next/previous track → Cleans up old players correctly

---

## 📊 Technical Details

### MSE Chunk Flow
```
Frontend: MSEPlayer.initialize(track_id)
  ↓
GET /api/mse/stream/{track_id}/metadata
  ← {total_chunks: 8, duration: 234.6, mime_type: "audio/webm", codecs: "opus"}
  ↓
GET /api/mse/stream/{track_id}/chunk/0?enhanced=false&preset=warm
  ↓
Backend: Load original WAV → Encode to WebM → Return chunk
  ↓
Frontend: SourceBuffer.appendBuffer(chunk)
  ↓
MSE audio element plays seamlessly
```

### Multi-Tier Buffer Flow
```
Frontend: HTML5 Audio loads /api/player/stream/{track_id}?enhanced=true&preset=warm
  ↓
Backend: Check cache for full processed file
  ↓
CACHE MISS:
  ↓
  ChunkedAudioProcessor.process_chunk(0) → First chunk ready (~1s)
  ↓
  Background: Process remaining chunks + proactive preset buffering
  ↓
  ChunkedAudioProcessor.get_full_processed_audio_path() → Concatenate all chunks
  ↓
  Return full WAV file
  ↓
Frontend: HTML5 Audio plays full file
```

### The Conflict Visualized
```
Time: 0s                  1s                  2s
      |                   |                   |
MSE:  [Initialize]────→[Load chunk 0]────→[Load chunk 1]
      |                   |                   |
MTB:  ────────────→[Init ChunkedProcessor]────→[Process chunk 0]
                          |                   |
                     CONFLICT: Both systems
                     active for same track!
```

---

## 🎯 Summary

**Problem**: MSE Progressive Streaming and Multi-Tier Buffer System both process chunks simultaneously, causing dual playback and state confusion.

**Root Cause**: Two independent chunking systems without coordination, both trying to manage audio playback.

**Immediate Fix**: Disable MSE temporarily (frontend import change).

**Proper Solution**: Unified chunking API that routes requests based on enhancement state, ensuring only ONE system active at a time.

**Status**:
- ✅ **MSE disabled** - Player now working correctly
- ⏳ **Integration pending** - Need to choose and implement integration strategy

---

**MSE Disabled**: October 27, 2025
**Frontend Build**: index-BcURs9zI.js
**Backend**: Multi-tier buffer system active
**Player Status**: ✅ Working (no dual playback, pause/play functional)

**Next**: Choose integration strategy and implement proper MSE + Buffer coordination! 🚀
