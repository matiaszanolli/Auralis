# Playback Pipeline Complete Analysis - Issues Found

**Date**: December 16, 2025
**Status**: ❌ CRITICAL PLAYBACK ISSUES IDENTIFIED
**Scope**: Full pipeline trace from UI button click to audio output

---

## Executive Summary

**CRITICAL FINDING**: The main play button in the Player component does NOT trigger actual audio playback. Pressing play only changes backend state to "PLAYING" but initiates no audio streaming or output.

**Root Cause**: Two separate, disconnected playback systems exist:
1. **REST API playback** (main play button) - State management only, **NO AUDIO OUTPUT**
2. **WebSocket streaming** (enhanced playback) - Actual PCM audio streaming, **WORKS CORRECTLY**

**User Impact**: Users must click "Play Enhanced" button (separate from main play button) to hear audio. Main play button is non-functional.

---

## Complete Playback Flow Trace

### ✅ WORKING FLOW: Enhanced Audio Playback (WebSocket)

This is the **correct implementation** but it's only accessible via the separate "Play Enhanced" button, not the main play button.

#### Frontend Flow

1. **User Action**: Clicks "Play Enhanced" button in `PlayerEnhancementPanel` component
   - File: [auralis-web/frontend/src/components/enhancement/EnhancedPlaybackControls.tsx:113-121](auralis-web/frontend/src/components/enhancement/EnhancedPlaybackControls.tsx#L113-L121)

2. **Hook Invocation**: Calls `usePlayEnhanced.playEnhanced(trackId, preset, intensity)`
   - File: [auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:345-392](auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts#L345-L392)
   - Action: Subscribes to WebSocket messages (`audio_stream_start`, `audio_chunk`, `audio_stream_end`, `audio_stream_error`)

3. **WebSocket Message**: Sends `play_enhanced` message
   ```typescript
   wsContext.send({
     type: 'play_enhanced',
     data: { track_id: trackId, preset, intensity }
   });
   ```
   - File: [usePlayEnhanced.ts:370-377](auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts#L370-L377)

#### Backend Flow

4. **WebSocket Handler**: Receives `play_enhanced` message at `/ws` endpoint
   - File: [auralis-web/backend/routers/system.py:80-207](auralis-web/backend/routers/system.py#L80-L207)
   - Handler: `websocket_endpoint()` at line 124-185

5. **AudioStreamController Initialization**
   ```python
   controller = AudioStreamController(
       chunked_processor_class=ChunkedAudioProcessor,
       get_repository_factory=get_repository_factory,
   )
   ```
   - File: [system.py:142-145](auralis-web/backend/routers/system.py#L142-L145)

6. **Stream Processing**: Calls `stream_enhanced_audio()`
   ```python
   await controller.stream_enhanced_audio(
       track_id=track_id,
       preset=preset,
       intensity=intensity,
       websocket=websocket,
   )
   ```
   - File: [system.py:156-161](auralis-web/backend/routers/system.py#L156-L161)
   - Implementation: [audio_stream_controller.py:200-333](auralis-web/backend/audio_stream_controller.py#L200-L333)

7. **Audio Processing**:
   - Loads track from library (lines 229-244)
   - Creates `ChunkedAudioProcessor` (lines 248-253)
   - Ensures fingerprint available for adaptive mastering (lines 264-271)
   - Sends `audio_stream_start` message with metadata (lines 278-289)
   - Processes chunks in loop (lines 292-319):
     - Processes chunk with fast-start for first chunk
     - Checks chunk cache (SimpleChunkCache)
     - If cache miss, processes chunk via `ChunkedAudioProcessor`
     - Sends `audio_chunk` message with base64-encoded PCM samples
   - Sends `audio_stream_end` when complete (lines 324-329)

#### Frontend Playback

8. **Message Handlers**: Frontend receives streaming messages
   - `audio_stream_start`: Initializes `PCMStreamBuffer` and `AudioPlaybackEngine` (lines 193-261)
   - `audio_chunk`: Decodes PCM samples, appends to circular buffer, starts playback when buffered (lines 266-316)
   - `audio_stream_end`: Marks streaming complete (lines 321-330)
   - File: [usePlayEnhanced.ts:191-340](auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts#L191-L340)

9. **Audio Output**: Web Audio API via `AudioPlaybackEngine`
   - Reads from `PCMStreamBuffer`
   - Outputs to browser speakers/headphones
   - ✅ **AUDIO ACTUALLY PLAYS**

---

### ❌ BROKEN FLOW: Regular Playback (REST API)

This is what the **main play button** does - it's completely disconnected from audio streaming.

#### Frontend Flow

1. **User Action**: Clicks main play button in Player component
   - File: [auralis-web/frontend/src/components/player/Player.tsx:225](auralis-web/frontend/src/components/player/Player.tsx#L225)
   - Button: `<PlaybackControls onPlay={async () => { await controls.play(); }} />`

2. **Control Hook**: Calls `usePlayerControls.play()`
   - File: [Player.tsx:138-143](auralis-web/frontend/src/components/player/Player.tsx#L138-L143)
   - Delegate: Calls `apiPlay()` function

3. **REST API Call**: Sends POST to `/api/player/play`
   ```typescript
   const apiPlay = async () => {
     try {
       await fetch('/api/player/play', { method: 'POST' });
     } catch (err) {
       console.error('[Player] Play command error:', err);
     }
   };
   ```
   - File: [Player.tsx:78-84](auralis-web/frontend/src/components/player/Player.tsx#L78-L84)

#### Backend Flow

4. **REST Endpoint**: Routes to `PlaybackService.play()`
   ```python
   @router.post("/api/player/play", response_model=None)
   async def play_audio() -> Dict[str, Any]:
       try:
           service = get_playback_service()
           return await service.play()  # ❌ NO AUDIO STREAMING TRIGGERED
       except ValueError as e:
           raise HTTPException(status_code=503, detail=str(e))
   ```
   - File: [auralis-web/backend/routers/player.py:213-220](auralis-web/backend/routers/player.py#L213-L220)

5. **PlaybackService**: Calls `audio_player.play()`
   ```python
   async def play(self) -> Dict[str, Any]:
       if not self.audio_player:
           raise ValueError("Audio player not available")

       self.audio_player.play()  # ❌ ONLY CHANGES STATE

       await self.player_state_manager.set_playing(True)
       await self.connection_manager.broadcast({
           "type": "playback_started",
           "data": {"state": "playing"}
       })

       return {"message": "Playback started", "state": "playing"}
   ```
   - File: [auralis-web/backend/services/playback_service.py:124-145](auralis-web/backend/services/playback_service.py#L124-L145)

6. **EnhancedAudioPlayer**: Calls `playback.play()`
   ```python
   def play(self) -> bool:
       if not self.file_manager.is_loaded():
           warning("No audio file loaded")
           return False
       return self.playback.play()  # ❌ ONLY STATE CHANGE
   ```
   - File: [auralis/player/enhanced_audio_player.py:110-114](auralis/player/enhanced_audio_player.py#L110-L114)

7. **PlaybackController**: **❌ CRITICAL ISSUE - ONLY CHANGES STATE, NO AUDIO OUTPUT**
   ```python
   def play(self) -> bool:
       """
       Start playback.

       Returns:
           bool: True if state changed, False if already playing
       """
       if self.state == PlaybackState.PAUSED:
           self.state = PlaybackState.PLAYING  # ❌ ONLY STATE
           info("Playback resumed")
       elif self.state == PlaybackState.STOPPED:
           self.state = PlaybackState.PLAYING  # ❌ ONLY STATE
           info("Playback started")
       else:
           return False

       self._notify_callbacks({"state": self.state.value, "action": "play"})
       return True  # ❌ RETURNS WITHOUT STARTING AUDIO OUTPUT
   ```
   - File: [auralis/player/playback_controller.py:52-66](auralis/player/playback_controller.py#L52-L66)

8. **Result**: ❌ **NO AUDIO STREAMING, NO AUDIO OUTPUT, NO PLAYBACK**
   - State changes to PLAYING
   - WebSocket broadcasts "playback_started" message
   - **BUT NO ACTUAL AUDIO IS PLAYED**

---

## Issues Summary

### Issue #1: Main Play Button is Non-Functional ⭐ CRITICAL

**Problem**: The main play button in the Player component sends a REST API request that only changes backend state to PLAYING but does not trigger any audio streaming or output.

**Root Cause**: `playback_controller.py:52` - The `play()` method only updates the state machine and notifies callbacks. It does not initiate any audio output mechanism.

**Expected Behavior**: Clicking play should start audio streaming via WebSocket and produce audible output.

**Actual Behavior**: Clicking play changes state to PLAYING but produces no audio.

**Files Involved**:
- [auralis/player/playback_controller.py:52-66](auralis/player/playback_controller.py#L52-L66) - Missing audio output trigger
- [auralis-web/frontend/src/components/player/Player.tsx:78-84](auralis-web/frontend/src/components/player/Player.tsx#L78-L84) - Calls wrong endpoint
- [auralis-web/backend/routers/player.py:213-220](auralis-web/backend/routers/player.py#L213-L220) - Only updates state

**User Workaround**: Must click separate "Play Enhanced" button to hear audio.

---

### Issue #2: Two Separate Playback Systems

**Problem**: The application has two independent playback systems that don't communicate:

1. **REST API Playback** (main play button)
   - Endpoint: `/api/player/play`
   - Purpose: State management only
   - Output: **None** (broken)

2. **WebSocket Streaming** (enhanced playback button)
   - Message: `play_enhanced`
   - Purpose: Actual audio streaming
   - Output: **PCM audio via Web Audio API** (works correctly)

**Expected Behavior**: There should be one unified playback system where the main play button triggers actual audio streaming.

**Actual Behavior**: Two completely separate systems with different APIs, buttons, and behaviors.

**Impact**: Confusing UX - users don't know which button actually plays audio.

---

### Issue #3: Missing Audio Output Mechanism in playback_controller.py

**Problem**: The `PlaybackController.play()` method is a state machine only. It has no mechanism to trigger audio output.

**Missing Components**:
- No WebSocket message emission to trigger streaming
- No audio device initialization
- No PCM chunk generation
- No audio output pipeline connection

**Expected Implementation**: The `play()` method should either:
1. Send a WebSocket `play_enhanced` message to initiate streaming, OR
2. Call into the audio streaming controller directly, OR
3. Initialize an audio output device and start playback

**Actual Implementation**: Only changes state and notifies callbacks.

**File**: [auralis/player/playback_controller.py:52-66](auralis/player/playback_controller.py#L52-L66)

---

### Issue #4: REST Endpoint `/api/player/play` is Incomplete

**Problem**: The REST endpoint only updates state but doesn't trigger the actual playback mechanism (WebSocket streaming).

**Expected Behavior**: When the REST endpoint is called, it should:
1. Update state to PLAYING
2. Trigger WebSocket audio streaming via `AudioStreamController`
3. Start sending PCM chunks to connected clients

**Actual Behavior**: Only steps 1 is performed. No audio streaming is initiated.

**File**: [auralis-web/backend/routers/player.py:213-220](auralis-web/backend/routers/player.py#L213-L220)

---

## Architectural Questions

Based on this analysis, the following questions arise:

1. **Is the REST API playback system legacy code?**
   - The WebSocket streaming system appears to be newer (Phase 2-3 work)
   - The REST API system might be from an older architecture

2. **Should the main play button use WebSocket streaming?**
   - Currently, only the "Play Enhanced" button uses WebSocket
   - Should the main play button also trigger `usePlayEnhanced.playEnhanced()`?

3. **What is the Python audio player supposed to do?**
   - `playback_controller.py` doesn't actually play audio
   - Is it supposed to integrate with the WebSocket streaming?
   - Or is it a legacy component that's no longer needed?

4. **Should there be one unified playback system?**
   - Currently, two separate systems with different APIs
   - Recommendation: Merge into single WebSocket-based streaming system

---

## Recommended Fixes

### Option A: Main Play Button → Enhanced Playback (Quick Fix)

**Change**: Make the main play button call `usePlayEnhanced.playEnhanced()` instead of REST API

**Steps**:
1. Modify `Player.tsx` to import and use `usePlayEnhanced` hook
2. Update `onPlay` callback to call `playEnhanced(currentTrack.id, 'adaptive', 1.0)`
3. Remove REST API call to `/api/player/play`

**Pros**:
- Quick fix (< 50 lines changed)
- Uses existing working WebSocket streaming
- Main play button will actually play audio

**Cons**:
- REST API endpoints become unused (technical debt)
- Doesn't address architectural duplication

---

### Option B: Integrate WebSocket Streaming into REST Endpoint (Architectural Fix)

**Change**: Make `/api/player/play` REST endpoint trigger WebSocket streaming

**Steps**:
1. Add `AudioStreamController` to `PlaybackService`
2. When `play()` is called, initiate WebSocket streaming:
   ```python
   # In PlaybackService.play()
   await self.audio_stream_controller.stream_enhanced_audio(
       track_id=current_track_id,
       preset='adaptive',
       intensity=1.0,
       websocket=active_websocket_connection
   )
   ```
3. Broadcast streaming status via WebSocket

**Pros**:
- Fixes REST API to actually play audio
- Maintains backward compatibility with existing REST clients
- Unified architecture

**Cons**:
- More complex implementation (~200 lines)
- Need to manage WebSocket connections in REST context
- Requires tracking active WebSocket for each client

---

### Option C: Remove REST Playback System (Clean Slate)

**Change**: Deprecate REST API playback, migrate everything to WebSocket streaming

**Steps**:
1. Remove `/api/player/play`, `/api/player/pause`, etc. REST endpoints
2. Update all frontend components to use `usePlayEnhanced` hook
3. Remove `playback_controller.py`, `enhanced_audio_player.py` (legacy)
4. Consolidate to single WebSocket-based playback system

**Pros**:
- Clean architecture (single source of truth)
- Removes ~500 lines of unused code
- Future-proof (WebSocket is correct approach)

**Cons**:
- Breaking change (requires frontend updates)
- More work (~500 lines affected)
- Potential disruption to other features

---

## Next Steps

1. **Immediate**: Implement Option A (quick fix) to restore main play button functionality
2. **Short-term**: Evaluate Option B or C for long-term architectural cleanup
3. **Investigation**: Determine if REST API system is legacy or still needed
4. **Testing**: Verify WebSocket streaming works across all browsers/platforms

---

## Files Reference

### Frontend
- [auralis-web/frontend/src/components/player/Player.tsx](auralis-web/frontend/src/components/player/Player.tsx) - Main player component (uses REST API)
- [auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts](auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts) - WebSocket streaming hook (works correctly)
- [auralis-web/frontend/src/components/enhancement/EnhancedPlaybackControls.tsx](auralis-web/frontend/src/components/enhancement/EnhancedPlaybackControls.tsx) - Enhanced playback button

### Backend
- [auralis-web/backend/routers/system.py](auralis-web/backend/routers/system.py) - WebSocket endpoint (handles `play_enhanced`)
- [auralis-web/backend/routers/player.py](auralis-web/backend/routers/player.py) - REST API endpoints (broken)
- [auralis-web/backend/audio_stream_controller.py](auralis-web/backend/audio_stream_controller.py) - WebSocket streaming controller (works correctly)
- [auralis-web/backend/services/playback_service.py](auralis-web/backend/services/playback_service.py) - REST playback service

### Python Audio Engine
- [auralis/player/playback_controller.py](auralis/player/playback_controller.py) - State machine only (no audio output)
- [auralis/player/enhanced_audio_player.py](auralis/player/enhanced_audio_player.py) - Player facade (delegates to broken controller)

---

## Conclusion

The playback pipeline investigation has revealed **critical architectural issues**. The main play button is non-functional because it uses a legacy REST API that only manages state without triggering actual audio streaming.

The WebSocket-based streaming system (`usePlayEnhanced` hook + `AudioStreamController`) works correctly but is only accessible via a separate "Play Enhanced" button, not the main play button.

**Recommendation**: Implement Option A (quick fix) immediately to restore basic functionality, then plan Option C (architectural cleanup) for long-term maintainability.
