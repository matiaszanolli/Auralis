# REST/WebSocket Architecture Analysis

## Executive Summary

The Auralis web application uses a **hybrid REST + WebSocket architecture** for communication between frontend and backend. While this approach works for most features, there are several **critical mismatches** where the frontend expects WebSocket messages that the backend never sends, causing the application to rely on inefficient REST polling as a fallback.

**Key Findings:**
- ✅ Enhancement system: Working correctly
- ✅ Library scanning: Working correctly
- ❌ Player state updates: **Frontend expects WebSocket, backend doesn't send, falls back to 1-second polling**
- ⚠️ Multiple WebSocket connections: Inefficient, should consolidate to one

---

## Backend WebSocket Messages

Based on analysis of `auralis-web/backend/main.py`:

### Player-Related Messages
- `track_changed` - Sent when next/previous track is loaded
- `track_loaded` - Sent when a track is loaded
- `playback_stopped` - Sent when playback stops
- `position_changed` - Sent when seek position changes
- `volume_changed` - Sent when volume changes

### Enhancement Messages
- `enhancement_toggled` - Sent when enhancement is enabled/disabled ✅
- `enhancement_preset_changed` - Sent when preset changes ✅
- `enhancement_intensity_changed` - Sent when intensity changes ✅

### Library Messages
- `scan_complete` - Sent when library scan finishes ✅
- `scan_error` - Sent when library scan errors ✅
- `scan_folder_added` - Sent when folder is added to scan list
- `scan_folder_removed` - Sent when folder is removed
- `playlist_created` - Sent when playlist is created
- `playlist_updated` - Sent when playlist is updated
- `playlist_deleted` - Sent when playlist is deleted
- `playlist_tracks_added` - Sent when tracks are added to playlist
- `playlist_track_removed` - Sent when track is removed from playlist
- `playlist_cleared` - Sent when playlist is cleared
- `queue_updated` - Sent when playback queue changes

### Processing Messages
- `processing_changed` - Sent when processing state changes
- `processing_settings_applied` - Sent when settings are applied
- `preset_applied` - Sent when preset is applied
- `reference_loaded` - Sent when reference track is loaded
- `comparison_tracks_loaded` - Sent for A/B comparison
- `ab_track_ready` - Sent when A/B track is ready

### Settings Messages
- `settings_changed` - Sent when settings change
- `settings_reset` - Sent when settings are reset
- `artwork_extracted` - Sent when artwork is extracted
- `artwork_deleted` - Sent when artwork is deleted

---

## Frontend WebSocket Consumers

### usePlayerAPI.ts (Critical Issue)
**Location:** `auralis-web/frontend/src/hooks/usePlayerAPI.ts:313-336`

**Expected messages:**
- `player_state` - ❌ **NOT SENT BY BACKEND**
- `player_update` - ❌ **NOT SENT BY BACKEND**

**Missing handlers for messages that ARE sent:**
- `track_changed` (sent by backend, not handled)
- `track_loaded` (sent by backend, not handled)
- `playback_stopped` (sent by backend, not handled)
- `position_changed` (sent by backend, not handled)
- `volume_changed` (sent by backend, not handled)
- `queue_updated` (sent by backend, not handled)

**Current workaround:**
```typescript
// Line 255-260: Polls every 1 second as fallback
useEffect(() => {
  const interval = setInterval(() => {
    if (playerState.isPlaying) {
      fetchPlayerStatus(); // REST call to /api/player/status
    }
  }, 1000);
}, [playerState.isPlaying]);
```

**Impact:**
- WebSocket is ineffective for player state
- Application makes 60+ HTTP requests per minute during playback
- Increased latency (up to 1 second) for state updates

---

### EnhancementContext.tsx ✅ Working Correctly
**Location:** `auralis-web/frontend/src/contexts/EnhancementContext.tsx:58-83`

**Expected messages:**
- `enhancement_toggled` - ✅ SENT
- `enhancement_preset_changed` - ✅ SENT
- `enhancement_intensity_changed` - ✅ SENT

**Status:** ✅ **WORKING CORRECTLY** - All expected messages are sent by backend

---

### EnhancedAudioPlayer.tsx (Partial Issue)
**Location:** `auralis-web/frontend/src/components/EnhancedAudioPlayer.tsx:111-118`

**Expected messages:**
- `playback_started` - ❌ **NOT SENT BY BACKEND**
- `playback_paused` - ❌ **NOT SENT BY BACKEND**
- `playback_stopped` - ✅ SENT
- `track_loaded` - ✅ SENT
- `volume_changed` - ✅ SENT
- `position_changed` - ✅ SENT
- `track_changed` - ✅ SENT

**Impact:** Component may not update correctly on play/pause events

---

### MagicalApp.tsx ✅ Working Correctly
**Location:** `auralis-web/frontend/src/MagicalApp.tsx:80-87`

**Expected messages:**
- `scan_complete` - ✅ SENT
- `scan_error` - ✅ SENT

**Status:** ✅ **WORKING CORRECTLY**

---

### processingService.ts (Needs Verification)
**Location:** `auralis-web/frontend/src/services/processingService.ts:142`

**Expected messages:**
- `job_progress` - ⚠️ **NEED TO VERIFY**

---

### RealtimeAudioVisualizer.tsx (Needs Verification)
**Location:** `auralis-web/frontend/src/components/RealtimeAudioVisualizer.tsx:48`

**Expected messages:**
- `audio_analysis` - ⚠️ **NEED TO VERIFY**

---

## Issues Identified

### Critical Issues

#### 1. usePlayerAPI expects non-existent WebSocket messages
**Problem:**
- Frontend expects `player_state` and `player_update` messages
- Backend never sends these messages
- Frontend falls back to REST polling every 1 second

**Evidence:**
```typescript
// Frontend (usePlayerAPI.ts:313-325)
if (message.type === 'player_state') {
  // This never executes because backend doesn't send it
  setPlayerState(message.data);
}
```

```python
# Backend: No code sends 'player_state' message
# (grep confirms this)
```

**Impact:**
- 60+ unnecessary HTTP requests per minute during playback
- WebSocket connection is wasted (connected but unused)
- Increased server load
- Increased latency for state updates (up to 1 second delay)

**Recommendation:**
Add backend support for `player_state` broadcasts, or update frontend to handle existing messages (`track_changed`, `volume_changed`, etc.)

---

#### 2. EnhancedAudioPlayer expects non-existent messages
**Problem:**
- Frontend expects `playback_started` and `playback_paused`
- Backend only sends `playback_stopped`, never `started` or `paused`

**Impact:**
Component may not update UI correctly when playback starts or pauses

**Recommendation:**
Add backend broadcasts for `playback_started` and `playback_paused` events

---

### Design Inconsistencies

#### 1. Hybrid REST + WebSocket pattern lacks clear rules
**Problem:**
- Some operations use REST API + WebSocket broadcast (e.g., enhancement toggle)
- Some operations use REST only
- Some state updates rely on polling instead of WebSocket
- No documented pattern for when to use which approach

**Examples:**
```typescript
// Enhancement: REST + WebSocket ✅
await fetch('/api/player/enhancement/toggle?enabled=true', { method: 'POST' });
// Backend also broadcasts: { type: 'enhancement_toggled', data: {...} }

// Player state: REST polling only ❌
setInterval(() => fetch('/api/player/status'), 1000);
// Backend doesn't broadcast player_state
```

**Recommendation:**
Establish clear architectural pattern:
- **Command operations** (play, pause, seek): REST request → Backend broadcasts state change
- **State queries**: REST endpoint for initial load, WebSocket for updates
- **Long-running operations**: WebSocket progress updates

---

#### 2. WebSocket message structure inconsistency
**Problem:**
Messages don't follow consistent structure

**Examples:**
```javascript
// Most messages (correct pattern):
{ type: "enhancement_toggled", data: { enabled: true, preset: "adaptive" } }

// Some messages (inconsistent):
{ type: "track_changed", action: "next" }  // Missing 'data' wrapper
```

**Recommendation:**
Standardize all messages:
```typescript
interface WebSocketMessage {
  type: string;
  data: any;
  timestamp?: number;
}
```

---

#### 3. Multiple WebSocket connections
**Problem:**
Different parts of the app create their own WebSocket connections:

```typescript
// usePlayerAPI.ts:302
const ws = new WebSocket('ws://localhost:8765/ws');

// EnhancementContext.tsx:48 (via useWebSocket hook)
const wsUrl = `ws://${window.location.hostname}:8765/ws`;
const { lastMessage } = useWebSocket(wsUrl);
```

**Impact:**
- Multiple connections to same endpoint (inefficient)
- Duplicate message processing
- Higher memory usage
- Harder to debug

**Recommendation:**
Create single `WebSocketContext` provider at app root, shared by all components

---

## Recommendations

### High Priority (Fix Now)

#### 1. Add missing player WebSocket messages
**Backend changes needed:**

```python
# In play() endpoint
await manager.broadcast({
    "type": "playback_started",
    "data": {
        "track": current_track,
        "position": 0
    }
})

# In pause() endpoint
await manager.broadcast({
    "type": "playback_paused",
    "data": {
        "position": current_position
    }
})

# After any player state change
await manager.broadcast({
    "type": "player_state",
    "data": player_state_manager.get_state().model_dump()
})
```

**OR** update frontend to handle existing messages:

```typescript
// In usePlayerAPI.ts, handle existing messages instead of expecting new ones
switch (message.type) {
  case 'track_changed':
    // Update current track
    break;
  case 'volume_changed':
    setPlayerState(prev => ({ ...prev, volume: message.data.volume }));
    break;
  case 'position_changed':
    setPlayerState(prev => ({ ...prev, currentTime: message.data.position }));
    break;
  // etc.
}
```

---

#### 2. Consolidate to single WebSocket connection
**Create WebSocketContext:**

```typescript
// src/contexts/WebSocketContext.tsx
export const WebSocketProvider: React.FC = ({ children }) => {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [listeners, setListeners] = useState<Map<string, Set<Function>>>(new Map());

  // Single connection
  useEffect(() => {
    const websocket = new WebSocket(`ws://${window.location.hostname}:8765/ws`);

    websocket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      const typeListeners = listeners.get(message.type);
      if (typeListeners) {
        typeListeners.forEach(listener => listener(message.data));
      }
    };

    setWs(websocket);
  }, []);

  const subscribe = (messageType: string, callback: Function) => {
    // Add listener for specific message type
  };

  return (
    <WebSocketContext.Provider value={{ subscribe, ws }}>
      {children}
    </WebSocketContext.Provider>
  );
};
```

**Update App.tsx:**
```typescript
<WebSocketProvider>
  <EnhancementProvider>
    <ComfortableApp />
  </EnhancementProvider>
</WebSocketProvider>
```

---

#### 3. Standardize message structure
**Backend:**
```python
# Enforce consistent structure in all broadcasts
await manager.broadcast({
    "type": event_name,
    "data": event_data,
    "timestamp": time.time()
})
```

**Frontend:**
```typescript
interface WebSocketMessage {
  type: string;
  data: any;
  timestamp?: number;
}
```

---

### Medium Priority (Plan for Next Sprint)

#### 4. Document WebSocket API
Create `WEBSOCKET_API.md`:

```markdown
# WebSocket API Reference

## Connection
- **Endpoint:** `ws://<host>:8765/ws`
- **Protocol:** JSON messages

## Message Types

### Player Events
- `player_state` - Full player state update
  ```json
  {
    "type": "player_state",
    "data": {
      "is_playing": true,
      "current_track": {...},
      "current_time": 123.45,
      "volume": 80
    }
  }
  ```
...
```

---

#### 5. Replace polling with WebSocket
**Remove polling in usePlayerAPI:**
```typescript
// DELETE THIS:
useEffect(() => {
  const interval = setInterval(() => {
    if (playerState.isPlaying) {
      fetchPlayerStatus(); // ❌ Unnecessary if WebSocket works
    }
  }, 1000);
}, [playerState.isPlaying]);
```

**Backend sends periodic updates:**
```python
# During playback, send position updates every second
asyncio.create_task(send_position_updates())
```

---

### Low Priority (Nice to Have)

#### 6. Add reconnection logic
Standardize reconnection across all WebSocket usage:

```typescript
const connect = () => {
  const ws = new WebSocket(url);

  ws.onclose = () => {
    setTimeout(() => connect(), 3000); // Reconnect after 3s
  };
};
```

---

#### 7. Add message queueing
Queue outgoing messages when WebSocket is disconnected:

```typescript
const sendMessage = (message: any) => {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
  } else {
    messageQueue.push(message); // Send when reconnected
  }
};
```

---

## Current Status Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Enhancement system | ✅ Working | All messages sent/received correctly |
| Library scanning | ✅ Working | All messages sent/received correctly |
| Player state (WebSocket) | ❌ Broken | Frontend expects messages backend doesn't send |
| Player state (REST polling) | ✅ Working | Inefficient but functional fallback |
| EnhancedAudioPlayer | ⚠️ Partial | Missing play/pause messages |

---

## Testing Plan

After implementing fixes:

1. **Test player state updates via WebSocket:**
   ```bash
   # Start backend
   cd auralis-web/backend && python main.py

   # In browser console:
   ws = new WebSocket('ws://localhost:8765/ws');
   ws.onmessage = (e) => console.log(JSON.parse(e.data));

   # Click play/pause/seek and verify messages appear
   ```

2. **Test enhancement system:**
   ```bash
   # Toggle enhancement, verify WebSocket messages
   # Expected: enhancement_toggled message
   ```

3. **Monitor WebSocket connections:**
   ```bash
   # In browser DevTools → Network → WS
   # Should see only ONE WebSocket connection
   ```

4. **Measure performance improvement:**
   ```bash
   # Before: ~60 HTTP requests/minute during playback
   # After: 0-5 HTTP requests/minute
   ```

---

## Migration Path

**Phase 1: Fix Critical Issues (1-2 days)**
1. Add `playback_started` and `playback_paused` backend messages
2. Add `player_state` backend broadcast after state changes
3. Update `usePlayerAPI` to handle actual backend messages
4. Remove REST polling fallback

**Phase 2: Consolidation (2-3 days)**
1. Create `WebSocketContext` provider
2. Migrate `usePlayerAPI` to use context
3. Migrate `EnhancementContext` to use context
4. Test all WebSocket-dependent features

**Phase 3: Polish (1-2 days)**
1. Standardize all message structures
2. Add TypeScript types for all messages
3. Create `WEBSOCKET_API.md` documentation
4. Add reconnection and queueing logic

**Total estimated time: 4-7 days**

---

## Conclusion

The current architecture works but is inefficient due to **REST polling compensating for missing WebSocket messages**. By implementing the recommendations above, we can:

- ✅ Eliminate 60+ HTTP requests per minute
- ✅ Reduce latency from 1 second to <50ms
- ✅ Reduce server CPU/bandwidth usage
- ✅ Improve real-time user experience
- ✅ Establish clear architectural patterns for future development

The enhancement system demonstrates the correct pattern - it should be replicated for player state management.
