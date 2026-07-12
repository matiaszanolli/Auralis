# Backend / Frontend / Engine Integration Audit — 2026-05-27

**Scope**: Flows 1 (Track Playback) and 3 (Audio Enhancement) only. `--flows 1,3`, `--depth deep`.
**Auditor**: `audit-integration` orchestrator (sonnet).
**Audit baseline**: 29 open GitHub issues snapshotted to `/tmp/audit/integration/issues.json`.
**Methodology**: traced each flow end-to-end through frontend hooks → REST/WS boundary → backend routers/streaming → engine; re-read every code path before reporting a finding; attempted to disprove each finding before including it.

## Executive Summary

10 findings, 9 unique after dedup (1 cross-flow boundary issue counted once).

| Severity | Count |
|---|---|
| HIGH     | 3 |
| MEDIUM   | 2 |
| LOW      | 5 |

### Key themes

1. **Mid-stream configuration changes do not affect the running stream.** Both `enabled → false` (INT-1-3 / INT-3-2) and `preset` / `intensity` changes (INT-3-1) modify the global settings dict and broadcast `enhancement_settings_changed`, but the active `ChunkedAudioProcessor` keeps using whatever values were baked in at instantiation. In one case (enable→disable) the stream is even terminated with a success-shaped `audio_stream_end`, leaving the user silent.
2. **Symmetry gap between `stream_normal_audio` and `stream_enhanced_audio`.** The enhanced path got `is_seek=true` / `seek_position` semantics, dedicated `_send_stream_start_with_seek`, and a documented `chunk_duration`; the normal path was updated to support `start_position` but never received the corresponding metadata changes (INT-1-1) and reports `total_chunks` with different semantics (INT-1-2).
3. **Documented protections that are not wired up.** `audio_chunk_meta.seq` was added "to detect dropped or reordered frames" (#3189) but no frontend consumer checks it (INT-1-4). `RawPlayerStateData.gapless_enabled`/`crossfade_*` fields exist in TS types but are never emitted by the backend (INT-1-8). The dead code in `usePlayerStreaming` (475 lines, 6 fix-PR references in comments) is not consumed by any production component (INT-1-6). The REST seek broadcast is consumed by nobody (INT-1-7).

### Most-impactful boundary mismatches

- **INT-3-1** (HIGH) — Live preset/intensity changes have no audible effect. Affects a core marketed feature.
- **INT-1-3 / INT-3-2** (HIGH) — Disabling enhancement mid-stream silences the user.
- **INT-1-1** (HIGH) — Every WS reconnect during normal playback produces an audible click.

## Flow Coverage Matrix

| Flow | Schema match | Error handling | Timeouts | Data types | Null handling | Case conversion | Findings |
|---|---|---|---|---|---|---|---|
| 1 — Track Playback | ✓ | ✓ | ⚠ (no frontend timeout on `audio_stream_start`) | ⚠ (chunk_duration constant duplicated) | ✓ | ✓ | INT-1-1 ··· INT-1-8 |
| 2 — Library Browsing | not in scope (--flows 1,3) | | | | | | |
| 3 — Audio Enhancement | ✓ | ✓ | ✓ | ⚠ (preset/intensity bound at init) | ✓ | ✓ | INT-3-1 ··· INT-3-5 |
| 4 — Library Scanning | not in scope | | | | | | |
| 5 — WebSocket Lifecycle | not in scope | | | | | | |
| 6 — Fingerprint & Similarity | not in scope | | | | | | |
| 7 — Artwork | not in scope | | | | | | |

## Findings

### HIGH

#### INT-1-1: `stream_normal_audio` omits `is_seek=true` on seek / reconnect resume
- **Severity**: HIGH
- **Flow**: 1 (Track Playback)
- **Boundary**: Backend `stream_normal_audio` → Frontend `usePlayNormal.handleStreamStart`
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:927-939` → `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts:220-244`
- **Status**: NEW (partial regression scope of #3185, but that issue's fix only covered the enhanced path)
- **Description**: On WS reconnect, `WebSocketContext.tsx:343-353` re-issues the saved stream command with `start_position: resumePos`. The backend's `stream_normal_audio` handles `start_position > 0` (`start_chunk` is computed on lines 909-914) but calls plain `_send_stream_start()` — no `is_seek` / `seek_position` fields. The enhanced path correctly uses `_send_stream_start_with_seek()` (line 1697) for the same scenario. The frontend's `usePlayNormal.handleStreamStart` reads `message.data.is_seek` (line 220) to decide whether to preserve the existing `AudioContext` and `PCMStreamBuffer` or tear them down and recreate. Without the flag the resume always falls through to "tear down + recreate".
- **Evidence**: see flow_1.md §INT-1-1.
- **Impact**: On every WS reconnect during normal (unprocessed) playback the frontend recreates the AudioContext, producing an audible click/glitch and resetting the engine's playback clock so the UI position jumps to 0:00 momentarily before re-syncing.
- **Suggested Fix**: Generalise `_send_stream_start_with_seek` (or add a normal-path variant) and use it from `stream_normal_audio` when `start_position > 0`. No frontend change required — the consumer already handles `is_seek=true`.

#### INT-1-3 (= INT-3-2): Toggling enhancement off mid-stream silences the user
- **Severity**: HIGH
- **Flows**: 1 + 3 — cross-flow boundary issue
- **Boundary**: Backend `stream_enhanced_audio` → Frontend `usePlayEnhanced.handleStreamEnd`
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:657-665, 766-774` → `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:534-546`
- **Status**: NEW
- **Description**: The streaming loop polls `_get_enhancement_enabled()` at the top of every chunk iteration. When the user toggles enhancement OFF mid-stream (via `useEnhancementControl.toggleEnabled()` → REST `POST /api/player/enhancement/toggle`), `break` exits the loop and control falls through to `# Stream complete` which emits `audio_stream_end` with `total_samples = full duration * sample_rate` — i.e. shaped as a clean completion. Frontend's `handleStreamEnd` dispatches `completeStreaming('enhanced')` and the engine stops. No `play_normal` is auto-issued from the frontend.
- **Evidence**: see flow_1.md §INT-1-3 (full code snippets).
- **Impact**: User toggles enhancement off and within ~10s the audio cuts; UI shows stream-complete; no further audio plays. The product expectation ("switch to original") is not met. (The `PlayerEnhancementPanel` mode-toggle does restart playback, but the global enhancement toggle does not.)
- **Suggested Fix**: Frontend-side fix is cleanest. In `useEnhancementControl.setEnabled(false)` (or in an effect that listens for self-originated `enhancement_settings_changed { enabled: false }`), capture the current playback position via the resume-position getter and immediately send `play_normal` with `start_position`. The backend should NOT learn about a fallback policy.

#### INT-3-1: Live preset / intensity changes silently do nothing for the current stream
- **Severity**: HIGH
- **Flow**: 3 (Audio Enhancement)
- **Boundary**: Frontend `useEnhancementControl.setPreset` / `setIntensity` → Backend stream
- **Location**: `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts:238-303` → `auralis-web/backend/core/chunked_processor.py:84-105` and `auralis-web/backend/core/audio_stream_controller.py:657-714`
- **Status**: NEW
- **Description**: A `POST /api/player/enhancement/preset` or `/intensity` updates the global `enhancement_settings` dict and broadcasts `enhancement_settings_changed`. The backend stream loop only re-reads enablement, never preset/intensity — those are bound to `ChunkedAudioProcessor` at construction. The frontend updates Redux + UI but never re-issues `play_enhanced` with the new values. The slider/preset selector changes, the audio does not.
- **Evidence**: see flow_3.md §INT-3-1.
- **Impact**: A core feature (change preset/intensity while listening) is non-functional. The `enhancement.py:270-273` log line "⚡ Preset switched instantly: ... (cache preserved)" is misleading — instant switch does not happen on the audio path.
- **Suggested Fix**: Frontend re-issues `play_enhanced` with the new preset/intensity using the resume-position getter as `start_position`. Same plumbing as the seek-on-reconnect path. Alternative: backend polls `get_enhancement_settings()` per chunk and restarts at the next chunk boundary when preset/intensity has changed — heavier but doesn't depend on the client.

### MEDIUM

#### INT-1-2: Enhanced-seek reports `total_chunks` = full track; normal-seek reports remaining chunks
- **Severity**: MEDIUM
- **Flow**: 1 (Track Playback)
- **Boundary**: Backend `_send_stream_start_with_seek` vs `_send_stream_start` → Frontend progress accounting
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1697-1712` (enhanced) and `:927-936` (normal) → `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:300-311`
- **Status**: NEW
- **Description**: Two paths use inconsistent semantics for the same field. After a seek from 50%, enhanced-progress can only ever reach 50% before `audio_stream_end` arrives; normal-progress always reaches 100%.
- **Evidence**: see flow_1.md §INT-1-2.
- **Impact**: Progress UI never hits 100 % after a seek in enhanced mode; any future code that uses `progress >= 100` as a completion signal is broken in that path.
- **Suggested Fix**: Both paths should agree. Prefer emitting `total_chunks = full` plus an explicit `start_chunk` so the client can subtract, since that matches the resume-mid-track use case.

#### INT-3-3: WS-path `play_enhanced` mixes client intent with stored settings, then rejects on `enabled=false`
- **Severity**: MEDIUM
- **Flow**: 3 (Audio Enhancement)
- **Boundary**: Frontend `usePlayEnhanced.playEnhanced` → Backend `routers/system.py` WS handler
- **Location**: `auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts:649-664` → `auralis-web/backend/routers/system.py:253-326`
- **Status**: NEW
- **Description**: The backend uses the frontend's `preset`/`intensity` if present and valid, else fills from stored settings, but then unconditionally checks the **stored** `enabled` flag and rejects the request if disabled — overriding explicit client intent.
- **Evidence**: see flow_3.md §INT-3-3.
- **Impact**: Confusing precedence. Programmatic / A-B / future flows that send `play_enhanced` will fail silently when global enhancement is off, with no `force` opt-out.
- **Suggested Fix**: Either require the frontend to consult `enabled` before sending `play_enhanced` (and send `play_normal` otherwise), or document a `force: true` field that bypasses the global flag.

### LOW

#### INT-1-4: `audio_chunk_meta.seq` is emitted but never validated by the frontend
- **Severity**: LOW
- **Location**: `auralis-web/backend/core/audio_stream_controller.py:1378-1406` → `auralis-web/frontend/src/contexts/WebSocketContext.tsx:300-310`
- **Status**: NEW
- **Description**: Backend emits a monotonic `seq` field with a comment "clients can detect dropped or reordered frames (fixes #3189)" — but no frontend code reads it. The protection advertised by #3189 is not in place.
- **Suggested Fix**: In `WebSocketContext.tsx` track a per-stream-type seq counter; on a gap, surface a `desync` event and use the existing `recovery_position` from `audio_stream_error` to restart from the failed chunk.

#### INT-1-5: `chunk_duration` constant duplicated across enhanced and normal paths
- **Severity**: LOW
- **Location**: `auralis-web/backend/core/chunked_processor.py:66` and `auralis-web/backend/core/audio_stream_controller.py:899`
- **Status**: NEW
- **Description**: `stream_normal_audio` hard-codes `chunk_duration = 15.0` while `stream_enhanced_audio` reads `processor.chunk_duration` (which derives from `CHUNK_DURATION = 15` in `chunked_processor.py`). A single-source-of-truth module already exists for `CHUNK_INTERVAL` (`core/chunk_boundaries.py`) — `CHUNK_DURATION` should live there too.
- **Suggested Fix**: Move `CHUNK_DURATION` into `core/chunk_boundaries.py` and import from both call sites.

#### INT-1-6: `usePlayerStreaming` (475 lines) is dead code — drives an HTML5 audio element with no production consumer
- **Severity**: LOW
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayerStreaming.ts:1-475`
- **Status**: NEW (related but distinct from open #3261 and #2816 which describe specific bugs *inside* this dead hook)
- **Description**: The hook is exported from `hooks/player/index.ts:22` but consumed only by its own test file. Auralis migrated to PCM streaming via `AudioPlaybackEngine`; the `<audio>`-element drift correction code is not exercised in production. Multiple bug-fix PRs (#2543, #2784, #3591, #3605, #3612, #3626) have churned this file for no behavioural benefit.
- **Suggested Fix**: Delete the hook + its tests; resolve the two related open issues (#3261, #2816) by closing them as no-longer-applicable.

#### INT-1-7: REST `/api/player/seek` exists, but its `'seek'` broadcast has no frontend subscriber
- **Severity**: LOW
- **Location**: `auralis-web/backend/services/playback_service.py:234-274`
- **Status**: NEW
- **Description**: `PlaybackService.seek()` calls `audio_player.seek()` (the legacy `EnhancedAudioPlayer`) and broadcasts `{type: 'seek', ...}`. No frontend code subscribes. The production seek path is `usePlayEnhanced.seekTo()` over WS; `PlayerControls` (which calls REST seek via `usePlaybackControl`) is rendered only in tests.
- **Suggested Fix**: Delete the REST endpoint and `usePlaybackControl.seek()`. Desktop-only deployment makes the cleanup safe.

#### INT-1-8: Frontend's `RawPlayerStateData` declares `gapless_enabled` / `crossfade_*`, but backend `PlayerState` never sets them
- **Severity**: LOW
- **Location**: `auralis-web/backend/player_state.py:47-83` → `auralis-web/frontend/src/types/websocket.ts:81-140`
- **Status**: NEW
- **Description**: Frontend's `transformPlayerState()` defaults `gapless_enabled ?? true`, `crossfade_enabled ?? true`, `crossfade_duration ?? 3.0`. None of these are present on the backend's Pydantic model — so the Redux store always shows the hardcoded defaults.
- **Suggested Fix**: Either add the fields to the backend `PlayerState` and wire them through the gapless playback engine, or remove them from the frontend type and `transformPlayerState`. The contract must be aligned.

#### INT-3-4: `get_processing_parameters` returns defaults when no profile is cached — no `is_default` flag
- **Severity**: LOW
- **Location**: `auralis-web/backend/routers/enhancement.py:445-500`
- **Status**: NEW
- **Description**: When no track has been processed, the endpoint returns the same-shaped dict with hard-coded defaults. The client cannot distinguish "engine processed this audio" from "no data yet".
- **Suggested Fix**: Add `is_default: bool` (or `source: 'profile' | 'default'`) to the response and have the visualiser fade/grey-out when default.

#### INT-3-5: Two different sequence-field naming conventions across streams (`seq` vs `sequence`)
- **Severity**: LOW
- **Location**: `auralis-web/frontend/src/services/RealTimeAnalysisStream.ts:262-267` vs `auralis-web/frontend/src/types/websocket.ts:480` (`seq`)
- **Status**: NEW
- **Description**: Audio chunks use `seq` (singular abbreviation); the real-time analysis stream uses `sequence`. Naming inconsistency invites bugs when the two systems are wired together.
- **Suggested Fix**: Unify on one field name across all sequenced WS messages, document in `WEBSOCKET_API.md`.

## Relationships

- **INT-1-1 + INT-1-2**: Both stem from the normal-path streaming code not receiving the same protocol upgrades as the enhanced path. Fix together by promoting `_send_stream_start_with_seek` to a shared helper that both call.
- **INT-1-3 + INT-3-1**: Both manifest the same root cause — *mid-stream config changes do not affect the active stream*. The cleanest single fix is to teach the frontend to re-issue `play_enhanced` / `play_normal` with `start_position` when the user changes `enabled`, `preset`, or `intensity`, reusing the resume-position getter that already exists for WS reconnect (#3185).
- **INT-1-4 + INT-3-5**: Both about sequence-number contracts that exist nominally but aren't enforced. Worth doing one round of "implement and document the contract" across all WS message types.
- **INT-1-6 + INT-1-7**: Both are "dead code that has accumulated maintenance"; the existence of #3261 and #2816 (touching the dead `usePlayerStreaming`) is direct evidence of the cost. Closing both with a single removal PR.
- **INT-1-8**: Standalone schema-drift; ties into Flow 5 (WebSocket Lifecycle) at a contract level but doesn't share a fix with the others.

## Prioritized Fix Order

1. **INT-3-1** + **INT-1-3** — restore "live preset/intensity/enabled changes" via a single frontend fix that re-issues `play_enhanced` / `play_normal` with `start_position`. One PR fixes a core feature gap.
2. **INT-1-1** — normal-path `is_seek` flag. Small backend change, removes an audible click on every reconnect.
3. **INT-1-2** — align `total_chunks` semantics across enhanced and normal seek; depends partially on the fix in #2.
4. **INT-3-3** — clarify precedence (client intent vs stored `enabled`) so future programmatic flows aren't surprised.
5. **INT-1-4** — wire up the existing `seq` field for desync detection. Cheap once #1-3 are in.
6. **INT-1-8** — decide direction (backend adds fields, or frontend drops them) and align.
7. **INT-1-7** + **INT-1-6** — delete dead code. Best paired with #2816 / #3261 / #3085 cleanup.
8. **INT-1-5** + **INT-3-4** + **INT-3-5** — bundle into a "WS protocol hygiene" PR.

## Suggested Publish Command

```
/audit-publish docs/audits/AUDIT_INTEGRATION_2026-05-27.md
```
