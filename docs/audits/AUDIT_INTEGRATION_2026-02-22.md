# Integration Audit — 2026-02-22

**Scope**: Cross-layer integration between React frontend, FastAPI backend, and audio engine.
**Auditor**: Claude Opus 4.6
**Prior audits**: AUDIT_INTEGRATION_2026-02-21 (13 findings: INT-01 through INT-13)
**Deduplication**: Verified against 42+ open GitHub issues, prior integration/backend audits, and all INT-01..13 findings.

---

## Executive Summary

This audit found **5 NEW findings** (4 HIGH, 1 MEDIUM) focused on the playback position pipeline and processing engine boundary. The most impactful is a **complete breakdown of backend→frontend position synchronization**: the backend sends `current_time` but the frontend reads `position`, and the `position_changed` WebSocket events the frontend subscribes to are never emitted by the backend. Additionally, the seek REST endpoint has the same query-param-vs-body mismatch that was fixed for volume (#2498) but was missed for seek.

Two findings from the prior integration audit have been **fixed** since yesterday:
- INT-01 (volume endpoint mismatch) → Fixed via #2498
- INT-03 (scan_progress no subscriber) → Fixed: `useScanProgress.ts` now exists

| Severity | New | Fixed Since Prior | Still Open |
|----------|-----|-------------------|-----------|
| HIGH | 4 | 1 (INT-01) | 1 (INT-02) |
| MEDIUM | 1 | 1 (INT-03) | 6 (INT-04..09) |
| LOW | 0 | 0 | 2 (INT-12..13) |
| **Total** | **5** | **2** | **9** |

---

## NEW Findings

### INT-14: player_state broadcasts `current_time` but frontend reads `position` — always 0
- **Severity**: HIGH
- **Flow**: 1 — Track Playback
- **Boundary**: Backend → Frontend (WebSocket)
- **Location**: `auralis-web/backend/player_state.py:50` → `auralis-web/frontend/src/hooks/player/usePlaybackState.ts:86`
- **Status**: NEW → #2568
- **Description**: The backend `PlayerState` Pydantic model defines the playback position field as `current_time: float = 0.0`. When broadcasted via `state.model_dump()`, the field is serialized as `current_time`. Both `usePlaybackState` (line 86) and `usePlaybackPosition` (line 178) read `data.position` from the `player_state` message — a field that does not exist in the broadcast. The nullish coalescing `data.position ?? 0` always evaluates to `0`.
- **Evidence**:

  Backend (`player_state.py:49-50`, `state_manager.py:192-194`):
  ```python
  class PlayerState(BaseModel):
      current_time: float = 0.0  # ← field name is "current_time"

  # Broadcast:
  await self.ws_manager.broadcast({
      "type": "player_state",
      "data": state.model_dump()  # ← serializes as "current_time"
  })
  ```

  Frontend (`usePlaybackState.ts:81-86`):
  ```typescript
  const data = msg.data as any;
  return {
      position: data.position ?? 0,  // ← reads "position" — DOESN'T EXIST
      // Should be: data.current_time ?? 0
  ```

  Frontend (`usePlaybackPosition`, same file line 176-178):
  ```typescript
  if (message.type === 'player_state') {
      setPosition(msg.data.position);  // ← undefined, sets position to undefined
  ```

- **Impact**: On every `player_state` broadcast (sent every 1 second during playback), the frontend's position state is reset to `0`. During WebSocket streaming, position is tracked locally by the Web Audio API, masking this issue. But on reconnect or in non-streaming mode, the seek bar snaps to 0. The `usePlaybackPosition` hook always returns position 0.
- **Suggested Fix**: Either (a) rename `current_time` to `position` in `PlayerState` model, or (b) change frontend to read `data.current_time`. Option (a) is cleaner since `position` is the frontend's convention.

---

### INT-15: Seek REST endpoint sends position as query param — backend expects JSON body
- **Severity**: HIGH
- **Flow**: 1 — Track Playback
- **Boundary**: Frontend → Backend (REST)
- **Location**: `auralis-web/frontend/src/hooks/player/usePlaybackControl.ts:223` → `auralis-web/backend/routers/player.py:288-289`
- **Status**: NEW → #2569
- **Description**: The frontend sends the seek position as a URL query parameter via `api.post('/api/player/seek', undefined, { position: validPosition })`. The `useRestAPI.post()` function signature is `post(endpoint, body, queryParams)` — so `position` becomes a query param. The backend declares `seek_position(request: SeekRequest)` where `SeekRequest` is a Pydantic `BaseModel` — FastAPI reads this from the request body, not query params. The body is empty (arg2 = `undefined`), so FastAPI returns 422 Unprocessable Entity. This is the exact same pattern as INT-01 (volume endpoint), which was fixed in #2498 for volume but NOT for seek.
- **Evidence**:

  Frontend (`usePlaybackControl.ts:223`):
  ```typescript
  // position sent as query param (3rd arg), body is undefined (2nd arg)
  await api.post('/api/player/seek', undefined, { position: validPosition });
  ```

  `useRestAPI.ts:145`:
  ```typescript
  const post = async (endpoint, payload?, queryParams?) => {
      const url = buildUrl(endpoint, queryParams);  // ← position goes in URL
      body: payload ? JSON.stringify(payload) : undefined,  // ← body is undefined
  ```

  Backend (`player.py:288-289`):
  ```python
  @router.post("/api/player/seek", response_model=None)
  async def seek_position(request: SeekRequest):  # ← Pydantic model = reads from body
  ```

  Volume fix (`usePlaybackControl.ts:292-293`):
  ```typescript
  // Backend reads volume from JSON body (SetVolumeRequest, 0-100) (fixes #2498)
  await api.post('/api/player/volume', { volume: Math.round(validVolume) });
  // ← Volume correctly sends body, but seek still sends query param
  ```

- **Impact**: REST-based seek always fails with 422. During WebSocket streaming, seeking works via WebSocket `seek` messages in the stream controller, masking this bug. But any component using REST seek (e.g., non-streaming playback) will fail silently.
- **Suggested Fix**: Change seek call to send body: `await api.post('/api/player/seek', { position: validPosition })`. Update the `useRestAPI.ts` doc comment example which shows seek as a query-param example.

---

### INT-16: Backend never emits `position_changed` WebSocket messages
- **Severity**: HIGH
- **Flow**: 1 — Track Playback / 5 — WebSocket Lifecycle
- **Boundary**: Backend → Frontend (WebSocket)
- **Location**: Backend `state_manager.py` (missing) → Frontend `usePlaybackState.ts:174,180`, `usePlayerStreaming.ts:262`
- **Status**: NEW → #2570
- **Description**: Multiple frontend hooks subscribe to `position_changed` WebSocket messages for position updates and drift correction. However, the backend **never emits** `position_changed` messages — grep across all backend Python files returns zero matches. The backend state manager (`state_manager.py`) only broadcasts full `player_state` messages via `_broadcast_state()`. The `WEBSOCKET_API.md` documentation describes `position_changed` as a valid message type, but no code implements it.
- **Evidence**:

  Frontend subscriptions:
  ```typescript
  // usePlaybackPosition (usePlaybackState.ts:174)
  useWebSocketSubscription(
      ['player_state', 'position_changed', ...],  // ← subscribes to position_changed
  // usePlayerStreaming.ts:262
  const unsubscribePosition = wsContext.subscribe('position_changed', (msg) => {
      serverTimeRef.current = msg.data.position;  // ← used for drift correction
  ```

  Backend: Zero matches for `position_changed` in Python files.

  Documentation (`WEBSOCKET_API.md:134-142`):
  ```
  #### `position_changed`
  {
    "type": "position_changed",
    "data": { "position": 120.5 }
  }
  ```

- **Impact**: (1) `usePlaybackPosition` hook only receives position from `player_state` (which has the INT-14 field name mismatch), so it never works correctly. (2) `usePlayerStreaming` drift correction never triggers because the `position_changed` event that would update `serverTimeRef` never arrives. Without drift correction, the frontend audio position can silently drift from the backend's expected position.
- **Suggested Fix**: Add `position_changed` broadcasting in `_position_update_loop()`: broadcast a lightweight `{"type": "position_changed", "data": {"position": new_time}}` message each second alongside (or instead of) the full `player_state` message. This avoids sending the entire state on every tick.

---

### INT-17: ProcessingEngine cache key accesses nonexistent `config.sample_rate` attribute
- **Severity**: HIGH
- **Flow**: 1 — Track Playback (batch processing path)
- **Boundary**: Backend → Engine (config interface)
- **Location**: `auralis-web/backend/core/processing_engine.py:220` → `auralis/core/config/unified_config.py:66`
- **Status**: NEW → #2571
- **Description**: The `_get_processor_cache_key()` method accesses `config.sample_rate` to build the processor cache key. `UnifiedConfig` defines `self.internal_sample_rate` (line 66) and `self.processing_sample_rate` (line 76), but has no `sample_rate` attribute, property, or `__getattr__` fallback. The developer added `# type: ignore[attr-defined]` to suppress the mypy error, but the attribute genuinely does not exist. At runtime, this raises `AttributeError`.
- **Evidence**:

  Backend (`processing_engine.py:218-222`):
  ```python
  key_parts: list[str] = [
      mode,
      str(config.sample_rate),  # type: ignore[attr-defined]  ← DOES NOT EXIST
      config.processing_mode if hasattr(config, 'processing_mode') else 'unknown',
  ]
  ```

  Engine (`unified_config.py:66,76`):
  ```python
  self.internal_sample_rate = internal_sample_rate   # ← correct attribute name
  self.processing_sample_rate = processing_sample_rate
  # No "sample_rate" attribute exists
  ```

  Full grep of `unified_config.py` for `sample_rate`: only `internal_sample_rate` and `processing_sample_rate` found. No `@property` for `sample_rate`.

- **Impact**: Any batch processing job (via `POST /api/processing/process`) that reaches the processor cache key generation will crash with `AttributeError: 'UnifiedConfig' object has no attribute 'sample_rate'`. The real-time streaming path (which uses `ChunkedAudioProcessor` directly) is unaffected.
- **Suggested Fix**: Change `config.sample_rate` to `config.internal_sample_rate` on line 220. Remove the `# type: ignore[attr-defined]` comment.

---

### INT-18: VolumeChangedMessage TypeScript type declares 0.0-1.0 but backend sends 0-100
- **Severity**: MEDIUM
- **Flow**: 1 — Track Playback / 5 — WebSocket Lifecycle
- **Boundary**: Backend → Frontend (WebSocket schema definition)
- **Location**: `auralis-web/frontend/src/types/websocket.ts:140` → `auralis-web/backend/player_state.py:54`
- **Status**: NEW → #2572
- **Description**: The `VolumeChangedMessage` TypeScript interface declares `volume: number; // 0.0 - 1.0`, but the backend `PlayerState` model defines `volume: int = 80` (0-100 scale). The runtime code in `usePlaybackState.ts:85` correctly handles this as 0-100 (`volume: data.volume ?? 80, // 0-100 scale`), but the type definition is wrong. Similarly, `PlayerStateMessage` at line 79 declares `volume: number; // 0.0 - 1.0` which is also incorrect.
- **Evidence**:

  Frontend type (`websocket.ts:137-141`):
  ```typescript
  export interface VolumeChangedMessage extends WebSocketMessage {
    type: 'volume_changed';
    data: {
      volume: number; // 0.0 - 1.0  ← WRONG: backend sends 0-100
    };
  }
  ```

  Backend model (`player_state.py:54`):
  ```python
  volume: int = 80  # 0-100 scale
  ```

  Frontend runtime (correctly handles 0-100, `usePlaybackState.ts:85`):
  ```typescript
  volume: data.volume ?? 80,  // 0-100 scale, matches backend default (issue #2251)
  ```

- **Impact**: Type documentation misleads developers. Any new code that trusts the type definition and passes `volume * 100` will double-scale the value. The `as any` cast at line 81 currently bypasses type checking, preventing compile-time detection.
- **Suggested Fix**: Update the comment in `VolumeChangedMessage` to `// 0-100 integer scale`. Update `PlayerStateMessage.volume` similarly.

---

## Fixed Since Prior Audit

| Prior ID | Title | Status |
|----------|-------|--------|
| INT-01 | Volume endpoint: frontend sends query param, backend requires JSON body | **FIXED** — Frontend now sends JSON body (fixes #2498). Code at `usePlaybackControl.ts:292-293`. |
| INT-03 | scan_progress WebSocket broadcasts have no frontend subscriber | **FIXED** — `useScanProgress.ts` now exists with subscription to `['scan_progress', 'scan_complete']`. |

---

## Confirmed Still Open (Prior Audit Findings)

| Prior ID | Severity | Title | Status |
|----------|----------|-------|--------|
| INT-02 | HIGH | useLibraryWithStats falls back to mock data on API failure | Open |
| INT-04 | MEDIUM | `audio_chunk` TypeScript interface field name wrong | Open |
| INT-05 | MEDIUM | `fingerprint_progress` TypeScript interface wrong fields | Open |
| INT-06 | MEDIUM | `audio_stream_start` TypeScript interface missing fields | Open |
| INT-07 | MEDIUM | set_enhancement_intensity missing buffer manager update | Open |
| INT-08 | MEDIUM | `Playlist` domain interface uses snake_case | Open |
| INT-09 | MEDIUM | Fingerprint stats inflated by placeholder rows | Open |
| INT-10 | MEDIUM | Enhancement settings not rebroadcast on reconnect | Open |
| INT-11 | MEDIUM | Album artwork response returns filesystem path | Open |
| INT-12 | LOW | `/api/library/albums` duplicates `/api/albums` | Open |
| INT-13 | LOW | Artwork MIME type defaults to image/jpeg | Open |

---

## Flow Coverage

| Flow | New Findings | Key Observations |
|------|-------------|-----------------|
| 1 — Track Playback | INT-14, INT-15, INT-16, INT-17 | Position pipeline completely broken at integration boundary |
| 2 — Library Browsing | — | No new issues. Mock data fallback (INT-02) still open. |
| 3 — Audio Enhancement | — | Enhancement settings correctly synced via WS. INT-07 still open. |
| 4 — Library Scanning | — | INT-03 fixed. `useScanProgress` now exists. |
| 5 — WebSocket Lifecycle | INT-16, INT-18 | `position_changed` never emitted; volume type annotation wrong |
| 6 — Fingerprint | — | INT-09 (stats inflation) still open. No new issues. |
| 7 — Artwork | — | INT-11 (filesystem path leak) still open. No new issues. |

---

## Methodology

1. Traced all 7 integration flows using parallel subagent analysis of frontend hooks, backend routers, and engine modules.
2. Verified every finding against actual source code via direct file reads (not from agent reports alone).
3. Cross-referenced against 42+ open GitHub issues and 13 findings from prior integration audit.
4. Specifically disproved several agent-reported findings before excluding them (audio_stream_error subscription, track_id vs path, stats auto-refresh).
5. Confirmed 2 prior findings as fixed and updated status.
