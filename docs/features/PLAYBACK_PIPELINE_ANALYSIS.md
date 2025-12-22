# Playback Pipeline Analysis - Issues Found

## Flow Trace: Button Press → Audio Output

### ✅ Step 1: Frontend - Play Button Click

**File**: [auralis-web/frontend/src/hooks/player/usePlaybackControl.ts](auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:100)

```typescript
const play = useCallback(async (): Promise<void> => {
  await api.post('/api/player/play');  // Line 106
  // Expects: Server broadcasts 'playback_started' message
}, [api]);
```

**Status**: ✅ **Working** - Correctly sends POST to `/api/player/play`

---

### ✅ Step 2: Backend - Player Router Endpoint

**File**: [auralis-web/backend/routers/player.py](auralis-web/backend/routers/player.py:213)

```python
@router.post("/api/player/play", response_model=None)
async def play_audio() -> Dict[str, Any]:
    service = get_playback_service()
    return await service.play()  # Line 218
```

**Status**: ✅ **Working** - Routes to PlaybackService

---

### ✅ Step 3: Backend - PlaybackService

**File**: [auralis-web/backend/services/playback_service.py](auralis-web/backend/services/playback_service.py:114)

```python
async def play(self) -> Dict[str, Any]:
    self.audio_player.play()  # Line 130

    await self.player_state_manager.set_playing(True)

    await self.connection_manager.broadcast({
        "type": "playback_started",
        "data": {"state": "playing"}
    })  # Line 136-139

    return {"message": "Playback started", "state": "playing"}
```

**Status**: ✅ **Working** - Calls audio player and broadcasts state change

---

### ⚠️ **ISSUE #1**: Python Audio Player - No Actual Audio Output

**File**: [auralis/player/enhanced_audio_player.py](auralis/player/enhanced_audio_player.py:109)

```python
def play(self) -> bool:
    if not self.file_manager.is_loaded():
        warning("No audio file loaded")
        return False
    return self.playback.play()  # Line 114
```

**File**: [auralis/player/playback_controller.py](auralis/player/playback_controller.py:52)

```python
def play(self) -> bool:
    if self.state == PlaybackState.PAUSED:
        self.state = PlaybackState.PLAYING  # Line 60
        info("Playback resumed")
    elif self.state == PlaybackState.STOPPED:
        self.state = PlaybackState.PLAYING  # Line 63
        info("Playback started")
    else:
        return False

    self._notify_callbacks({"state": self.state.value, "action": "play"})
    return True  # Line 69
```

**Problem**: ❌ **The `play()` method only changes state - it doesn't start any audio streaming!**

**What's Missing**:
1. No audio output device initialization
2. No audio buffer streaming to output
3. No call to start audio thread/process
4. No WebSocket audio streaming initiation

**Expected Behavior**:
- Should trigger audio streaming via WebSocket to frontend
- Should start audio output thread/process
- Should begin processing audio chunks

---

### ❓ **ISSUE #2**: WebSocket Audio Streaming - Where is it?

Looking at the code comments:
- **player.py:7-8**: "Audio streaming is now handled exclusively via WebSocket using the WebSocket controller."
- **playback_service.py:136-139**: Broadcasts `playback_started` event

**Question**: Where is the WebSocket audio streaming triggered?

**Expected Flow**:
1. Frontend receives `playback_started` WebSocket message
2. Frontend should then request audio stream via WebSocket
3. Backend should start streaming PCM audio chunks
4. Frontend should decode and play chunks via HTML5 Audio

**Current Status**: ❓ **Unclear - need to trace WebSocket streaming setup**

---

### 🔍 Step 4: Frontend - What Happens After `playback_started`?

**Expected**:
- Frontend WebSocket listener receives `playback_started` message
- Frontend initiates audio stream request
- Frontend sets up HTML5 Audio API to play incoming chunks

**To Investigate**:
1. Where is the WebSocket `playback_started` listener?
2. What triggers the audio stream request?
3. Is there an HTML5 Audio element being used?
4. How are PCM chunks being decoded and played?

---

## Critical Issues Found

### 🚨 Issue #1: No Audio Output in Python Player

**Location**: `auralis/player/playback_controller.py:52`

**Problem**: The `play()` method only updates state - no actual audio playback happens.

**Expected Fix**:
```python
def play(self) -> bool:
    if self.state in [PlaybackState.PAUSED, PlaybackState.STOPPED]:
        self.state = PlaybackState.PLAYING

        # ❌ MISSING: Start audio output here
        # Should either:
        # A) Start audio streaming via WebSocket to frontend
        # B) Start local audio output thread/process
        # C) Trigger audio chunk generation and transmission

        self._notify_callbacks({"state": self.state.value, "action": "play"})
        return True
    return False
```

---

### ❓ Issue #2: WebSocket Streaming Mechanism Unknown

**Problem**: Code comments say "Audio streaming is now handled exclusively via WebSocket" but I can't find where this is triggered.

**Need to Find**:
1. Where is the WebSocket `/ws` endpoint handler?
2. What message type triggers audio streaming?
3. Is there a `play_enhanced` or `stream_audio` message handler?
4. How does the backend know to start streaming audio when playback starts?

---

### ❓ Issue #3: Frontend Audio Playback Unknown

**Problem**: Even if backend streams audio, frontend needs to:
1. Listen for WebSocket messages
2. Decode PCM audio chunks
3. Feed chunks to HTML5 Audio API or Web Audio API
4. Handle buffering and synchronization

**Need to Find**:
1. Frontend WebSocket audio chunk handler
2. HTML5 Audio element or Web Audio API setup
3. Audio decoding and playback logic

---

## Next Steps for Investigation

1. **Find WebSocket streaming trigger**:
   - Search for WebSocket message handlers
   - Look for `play_enhanced` or `stream_audio` message types
   - Find `audio_stream_controller.py` usage

2. **Find frontend audio playback**:
   - Search for `usePlayEnhanced` hook usage
   - Look for HTML5 `<audio>` element
   - Find Web Audio API setup
   - Check for PCM decoding logic

3. **Trace complete WebSocket flow**:
   - Frontend sends `play_enhanced` message?
   - Backend receives and starts streaming?
   - Frontend receives chunks and plays?

---

## Architecture Notes

From code comments and structure, the intended architecture is:

```
Frontend (React)
    ↓ (WebSocket)
Backend REST API (FastAPI)
    ↓
PlaybackService
    ↓
EnhancedAudioPlayer (Python)
    ↓
PlaybackController (State Machine)
    ↓
❌ MISSING: Audio Output Mechanism
```

**Expected**:
```
Frontend (React)
    ↓ (POST /api/player/play)
Backend REST API
    ↓
PlaybackService.play()
    ↓
✅ Trigger WebSocket Streaming
    ↓ (WebSocket audio_chunk messages)
Frontend Audio Playback
    ↓
HTML5 Audio / Web Audio API
    ↓
Speaker Output
```

---

## Status Summary

| Step | Component | Status | Issue |
|------|-----------|--------|-------|
| 1 | Frontend play button | ✅ Working | None |
| 2 | Backend REST endpoint | ✅ Working | None |
| 3 | PlaybackService | ✅ Working | None |
| 4 | EnhancedAudioPlayer | ⚠️ Partial | No audio output triggered |
| 5 | PlaybackController | ❌ **Broken** | Only changes state, no audio |
| 6 | WebSocket streaming | ❓ Unknown | Need to find trigger |
| 7 | Frontend audio decode | ❓ Unknown | Need to find handler |
| 8 | HTML5 Audio playback | ❓ Unknown | Need to find element |

**Conclusion**: Playback state changes correctly, but **no audio actually plays** because the audio output mechanism is disconnected.
