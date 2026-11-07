---
description: "Trace 9 critical data flows across audio engine, FastAPI backend, and React frontend"
argument-hint: "[--flows <numbers>] [--depth shallow|deep] [--limit <N>]"
---

# Backend-Frontend-Engine Integration Audit

Trace the 9 critical data flows between the Auralis audio engine, FastAPI backend, and React frontend.

**Architecture**: This is an orchestrator. Each flow runs as an Agent-tool subagent (`subagent_type: general-purpose`, `model: sonnet`). Max 3 run concurrently.

See `.claude/commands/_audit-common.md` for project layout, severity framework, methodology, context management rules, deduplication, and finding format.

## Parameters (from $ARGUMENTS)

- `--flows <numbers>`: Comma-separated flow numbers (e.g., `1,3,5`). Default: all 9.
- `--depth shallow|deep`: `shallow` = check key patterns only; `deep` = trace full data paths. Default: `deep`.
- `--limit <N>`: Stop after N findings. Default: unlimited.

## Severity Examples

| Severity | Integration-Specific Examples |
|----------|------------------------------|
| **CRITICAL** | Dropped audio chunks across boundary, sample rate mismatch between engine and streaming, truncated playback |
| **HIGH** | WebSocket message schema mismatch, timeout causing playback stutter, unhandled error propagation across layers |
| **MEDIUM** | Different field names for same concept, inconsistent error codes, stale frontend state after backend update |
| **LOW** | Missing API schema docs, undocumented WebSocket message types, unused response fields |

## Flows to Trace

### Flow 1: Track Playback (Full Pipeline)

| Step | Layer | File |
|------|-------|------|
| User clicks play | Frontend | `src/hooks/player/` hooks (`usePlayTrack.ts` sets the queue over REST), `src/store/` player slice |
| Play command | Frontend | `auralis-web/frontend/src/hooks/enhancement/useEnhancedPlayCommand.ts` — fetches the track over REST, then sends the WS `play_enhanced` / `play_normal` command (audio streaming is WebSocket-only; no REST streaming endpoint) |
| Command handler | Backend | `auralis-web/backend/ws_handlers/connection.py` (`dispatch_message`) → `auralis-web/backend/ws_handlers/playback_commands.py` (play) / `auralis-web/backend/ws_handlers/seek_command.py` (seek, #6269) → stream tasks in `auralis-web/backend/routers/system_streams.py` |
| Audio loading | Engine | `auralis/io/unified_loader.py` |
| Processing | Engine | `auralis/core/hybrid_processor.py` → `simple_mastering.py` |
| Chunking | Backend | `chunked_processor.py` (15s render windows with context, emitted as 10s non-overlapping segments — no crossfade, #4642) |
| WebSocket stream | Backend | `audio_stream_controller.py` |
| Audio playback | Frontend | `auralis-web/frontend/src/hooks/websocket/socketFrameParser.ts` → `auralis-web/frontend/src/services/audio/` (`PCMStreamBuffer.ts` + `pcmRingOps.ts`, `BufferScheduler.ts`, `WorkletOutput.ts`) |

**Check**: Sample rate consistency from file to playback. Chunk boundaries — do the emitted segments tile exactly, with no gap, overlap or repeated samples at the seams, both in the backend stream and in the frontend PCM buffer? WebSocket binary frame format — does the frontend decode it correctly? What happens when processing is slower than playback? Flow control: after `buffer_full` the server parks on its gate and sends nothing, so resume cannot wait for the next chunk — `auralis-web/frontend/src/hooks/enhancement/flowDrainWatch.ts` polls the ring and sends `buffer_ready`, bounded server-side in `auralis-web/backend/core/stream_gates.py` (regression guard: fixed in `3a1ab313`, #5863, pinned by `tests/backend/test_flow_gate_bound_5863.py`). Is the frontend start gate expressed in seconds, with the watchdog derived from `BACKEND_STREAM_TIMING` in `auralis-web/frontend/src/services/audio/audioConstants.ts` (#6232, `a3488cff`)? Failure paths (regression guards): a chunk the pump skips sends `audio_stream_error` with `continues: true` and the frontend keeps its engine and buffer instead of ending playback (`0121aaca`, #5867, pinned by `auralis-web/frontend/src/hooks/enhancement/__tests__/useAudioStreamingCore.chunkError.5867.test.tsx`); a stream that ended below the start threshold still plays what it delivered (`4b261747`, #5900, `useAudioStreamingCore.shortStreamStart.5900.test.tsx`); a late end/error from a superseded track no longer tears down the new stream (`cde03344`, #6017, `useAudioStreamingCore.supersededTrack.6017.test.tsx`); a finished, stopped or failed stream is not re-issued by a toggle or reconnect (`b65f5759`, #5876, `activeStreamSession.5876.test.tsx`).

### Flow 2: Library Browsing

| Step | Layer | File |
|------|-------|------|
| User navigates | Frontend | `src/hooks/library/`, `src/store/` library slice |
| REST requests | Frontend | `src/services/` API client |
| Library endpoints | Backend | `routers/` (albums, artists, playlists, tracks) |
| Database queries | Engine | `auralis/library/database.py` (`LibraryDatabase`) → `repositories/` |
| Response format | Backend | `schemas/` (package) |

**Check**: Pagination — the list responses share one `PaginatedResponse` envelope (`total`/`limit`/`offset`/`has_more`, #5499, pinned by `tests/backend/test_paginated_envelope_shared_5499.py`) and the frontend reads only the snake_case `has_more` (#5823); is every new list route on the envelope? Sorting is server-side, either direction, NULLs last (#5868, `tests/auralis/library/test_list_ordering_5868_5869.py`) — does the album grid re-sort loaded pages anyway? Field naming — camelCase (frontend) vs snake_case (backend)? Null handling — an absent album or artist is `null` on the wire (#5905, `tests/backend/test_absent_album_artist_sentinels_5905.py`), and the wire types now admit `| null` for album year/genre, similar-track fields, `TrackInfo.artwork_url`/`format` and scan `current_file` (#6049, still open after `8dc831b3`, #5985 `16ac993f`): is any other nullable backend field typed as non-null? Large libraries — does the frontend handle 100k+ tracks?

### Flow 3: Audio Enhancement

| Step | Layer | File |
|------|-------|------|
| User adjusts settings | Frontend | `useEnhancementControl()` local state — the live source of truth (`playerSlice.preset` is dead state; the slice has no intensity). Commands live in `auralis-web/frontend/src/hooks/enhancement/useEnhancementCommands.ts`, backend status sync in `useEnhancementStatusSync.ts` |
| Settings API call | Frontend | `useEnhancementCommands.ts`, `src/services/` |
| Preset contract | Backend ↔ Frontend | `auralis-web/backend/schemas/enhancement.py` `VALID_PRESETS` ↔ `auralis-web/frontend/src/types/domain.ts` `EnhancementPreset` — `'adaptive'` only since 2026-09-13; the default is the one `DEFAULT_PRESET` in `schemas/enhancement.py` (#5794) |
| Enhancement endpoint | Backend | `auralis-web/backend/routers/enhancement.py` (factory) + `enhancement_controls.py` / `enhancement_recommendation.py` |
| Runtime settings | Backend | shared `enhancement_settings` dict (mutated in place, seeded at startup from UserSettings) |
| Processing config | Engine | `auralis/core/config/unified_config.py` (UnifiedConfig) — the only config layer since #4918 |
| DSP pipeline | Engine | `auralis/core/hybrid_processor.py` → DSP modules |
| Real-time application | Engine | `auralis/player/realtime/` |

**Check**: Config format — do frontend slider values map correctly to engine parameters? Does the transport actually pass the *current* preset/intensity through to playback, or re-read stale Redux state? Range validation — can the frontend send out-of-range values? Preset validation — the v23 migration rewrote every stored `default_preset` to `'adaptive'` and the off-list read-side degrade branches were deleted (`90245885`, #5824), so `SettingsResponse.default_preset` is non-nullable and the frontend types it without `| null`; any path that can still write an off-list preset (bypassing the `EnhancementPresetLiteral` request validation) would now reach the UI and the engine unfiltered. `PUT /api/settings` rejects an explicit null for every field (`33eee167`, #5875), and the one remaining read-side degrade for `default_preset` maps a stored NULL (pre-#5875 rows) to `DEFAULT_PRESET`. `enhancement_intensity` still degrades to null on read, and callers must fall back (#5517). Live re-issue: a Settings-dialog intensity/preset save re-issues the playing stream so later seeks use the new values (`be39043b`, #5874), and enhancement setting changes no longer feed look-ahead from REST player state (`29c5816e`, #5908, pinned by `tests/backend/test_enhancement_controls_no_rest_state_feed_5908.py`). Real-time vs offline — is the same config used for both paths? Do the enhancement settings participate in the chunk cache key, or can a settings change serve cached audio mastered with the *previous* settings? Latency — does enhancement cause audible gaps?

### Flow 4: Library Scanning

| Step | Layer | File |
|------|-------|------|
| User adds folder | Frontend | Library management hooks |
| Scan request | Backend | `auralis-web/backend/routers/library_scan.py` (browse endpoints live in `auralis-web/backend/routers/library.py`) |
| Auto-scan | Backend | `auralis-web/backend/services/library_auto_scanner.py` (background folder watcher) |
| Filesystem scan | Engine | `auralis/library/scanner/` |
| Metadata extraction | Engine | `auralis/io/unified_loader.py` |
| Database insert | Engine | `auralis/library/database.py` → repositories |
| Progress updates | Backend | WebSocket `library_scan_started` / `scan_progress` / `scan_complete` / `library_scan_error` frames. `auralis-web/backend/services/scan_events.py` is the one progress bridge, fingerprint enqueue and `scan_complete_payload` for both paths (#5912); `auralis-web/backend/routers/library_scan_events.py` keeps only the manual route's terminal frames |
| UI update | Frontend | `auralis-web/frontend/src/hooks/library/useScanProgress.ts` — a module-level store fed by one refcounted WS subscription, read via `useSyncExternalStore` (#5622), not Redux |

**Check**: Progress reporting — does the frontend receive scan progress? Error handling — what happens when a file can't be read? Unreadable folders and aborted scans must reach the UI as failures, not a normal "+0 added" completion, and an incomplete walk must not prune tracks (`acc651b3`, #5877, pinned by `tests/backend/test_scan_failures_reach_ui_5877.py`); do both paths report the scanner's own `files_processed` (#5912, `tests/backend/test_scan_complete_payload_5912.py`)? Duplicate detection — does rescan handle already-imported tracks? Streaming allowlist — a manual scan of a folder outside the default roots must also register it via `/api/settings/scan-folders` (`useLibraryScan.ts`, fixed in `4cbd2e4c`, #5865), or its tracks list fine and then stream as "Audio file not found"? Large folders — timeout or chunking?

### Flow 5: WebSocket Lifecycle

| Step | Layer | File |
|------|-------|------|
| Connection init | Frontend | `src/hooks/websocket/`, `src/contexts/WebSocketContext.tsx`, `src/contexts/PlaybackSessionContext.tsx` (shared streaming session) |
| WS endpoint | Backend | `auralis-web/backend/routers/system.py` (module-level `websocket_endpoint`, registered with `add_api_websocket_route`, #5832); the per-connection stream task registries live in `auralis-web/backend/routers/system_streams.py` |
| WS accept + checks | Backend | `auralis-web/backend/ws_handlers/connection.py`, `auralis-web/backend/websocket/websocket_security.py` (a rejected Origin is accepted then closed with 1008 so the browser sees 1008, not 1006, `91137517`, #5883; invalid and binary frames are metered against the sender's budget and inbound size is bounded at the transport, #5915) |
| Message routing | Backend | `auralis-web/backend/ws_handlers/messages.py`, `playback_commands.py`, `seek_command.py`, `playback_control.py` (shared bundles in `context.py`; preset/intensity resolution in `enhancement_params.py`) |
| Protocol contract | Backend | `auralis-web/backend/websocket/websocket_protocol.py`, `auralis-web/backend/websocket/outbound_messages.py` (`broadcast_typed` overloads) with its payload TypedDicts in `auralis-web/backend/websocket/outbound/` (player, queue, library, enhancement; split out in #6269), `auralis-web/backend/core/stream_protocol.py`, `auralis-web/backend/core/stream_lifecycle.py` / `stream_notifications.py` |
| Binary audio frames | Backend | `auralis-web/backend/core/encoding/wav_encoder.py`, `auralis-web/backend/core/audio_stream_controller.py` |
| Frame decode | Frontend | `auralis-web/frontend/src/hooks/websocket/socketFrameParser.ts` (binary PCM pairing, heartbeat reply, `audio_chunk_meta.seq` desync check) → `auralis-web/frontend/src/services/audio/` |
| Timing policy | Both | heartbeat `WS_HEARTBEAT_INTERVAL_SECONDS` / `WS_HEARTBEAT_TIMEOUT_SECONDS` in `auralis-web/backend/config/limits.py`; reconnect backoff in `WebSocketManager` (`auralis-web/frontend/src/utils/errorHandling.ts`) — one definition each since #5800; the reconnect budget is `DEFAULT_MAX_RECONNECT_ATTEMPTS` / `DEV_MAX_RECONNECT_ATTEMPTS` in `auralis-web/frontend/src/config/timing.ts`, shared by the manager, `useWebSocketConnection.ts` and the connection slice's `canReconnect` (#6220) |

**Check**: Connection establishment — handshake protocol? Message types — are all types documented and handled on both sides? Binary vs text frames — consistent usage? Reconnection — does the frontend re-establish state after disconnect? The shared subscription lifecycle is `useMessageSubscriptions` in `auralis-web/frontend/src/hooks/websocket/useWebSocketMessages.ts` (#5789) — does any hook still hand-roll a subscribe effect that resubscribes on a status flicker (#4668)? Backpressure — what happens when the frontend can't consume frames fast enough? Malformed play/seek commands get typed errors, not `internal_error` (#5973, `tests/backend/test_ws_malformed_play_commands_5973.py`); `ping` has its own rate-limit budget (#5079). After a backend restart the first `player_state` is applied and the seq watermarks reset on a changed `server_instance_id` (`4e17e402`, #5882); a stream re-issue queued while the socket is down restarts from the live position, not the stale one (`12057779`, #6044, pinned by `auralis-web/frontend/src/hooks/websocket/__tests__/websocketConnectionCore.queuedReissue.6044.test.ts`). Is the WebSocket base URL derived from an absolute `VITE_API_URL` when `VITE_WS_URL` is unset (`5c7da778`, #5654, `wsBaseFromApiBase` in `auralis-web/frontend/src/config/api.ts`)?

### Flow 6: Fingerprint & Similarity

| Step | Layer | File |
|------|-------|------|
| Similarity request | Frontend | Fingerprint/similarity hooks |
| Similarity endpoints | Backend | `auralis-web/backend/routers/similarity.py` (factory; handlers in `similarity_query.py` / `similarity_explain.py`), `auralis-web/backend/routers/similarity_graph.py` (shared helpers in `auralis-web/backend/routers/similarity_common.py`) |
| Fingerprint queue/status | Backend | `auralis-web/backend/routers/fingerprint_queue.py`, `auralis-web/backend/routers/fingerprint_status.py`, `auralis-web/backend/analysis/fingerprint_generator.py` |
| Fingerprint engine | Engine | `auralis/analysis/fingerprint/` |
| Database lookup | Engine | `auralis/library/repositories/` (fingerprint, similarity repos) |
| Results format | Backend | `schemas/` (package) |

**Check**: Fingerprint format — is it consistent between compute and lookup? Similarity scores — range and precision? Missing fingerprints — graceful fallback? Batch vs single — consistent API (the album grid reads fingerprints one request per page through a batch endpoint, #5873)? `POST /api/similarity/fit` forwards `min_samples` and reports a failed fit as a failure (#5889); graph builds are single-flight (#5945) and a locked database is a retryable 503 on the similarity-family routes (#5381).

### Flow 7: Artwork

| Step | Layer | File |
|------|-------|------|
| Artwork request | Frontend | Image components, hooks |
| Artwork endpoint | Backend | `auralis-web/backend/routers/artwork.py` (factory; handlers in `artwork_thumbnails.py` / `artwork_manage.py`) |
| Artwork extraction | Engine | `auralis/services/artwork_service.py`, `auralis/library/artwork.py` |
| Thumbnail cache | Backend | `auralis-web/backend/core/thumbnail_cache.py` — on-disk, content-addressed on source mtime/size (#4447) |
| Image serving | Backend | Static file or stream response |

**Check**: Image formats — are all common formats handled? Cache headers — are they set correctly, and do they agree with the on-disk thumbnail cache's own invalidation? Does the thumbnail key's size bucket match the sizes the frontend actually requests, or does every request miss? Missing artwork — fallback behavior? Large images — resizing on backend or frontend? Decompression-bomb artwork is rejected before it is stored or served (#6153), and re-encoded artwork keeps its orientation and ICC profile (#5927). The artist view's albums say whether they have artwork so cards stop probing for it (#5925).

### Flow 8: Seek & Rebuffer

| Step | Layer | File |
|------|-------|------|
| User drags the scrubber | Frontend | `auralis-web/frontend/src/hooks/player/`, player slice in `auralis-web/frontend/src/store/` |
| Seek command | Frontend → Backend | `auralis-web/frontend/src/hooks/enhancement/useEnhancedSeek.ts` sends WS `seek` with `track_id` + `position` only; preset/intensity are resolved server-side from the connection's active stream settings (#5604) → `auralis-web/backend/ws_handlers/seek_command.py` (`handle_seek`) |
| Seek stream path | Backend | `auralis-web/backend/core/stream_seek.py`, `auralis-web/backend/core/stream_chunk_ops.py` |
| Chunk index math | Backend | `auralis-web/backend/core/chunk_boundaries.py` (`content_chunk_count()`, overlap-aware) |
| Source seek | Backend | `auralis-web/backend/core/seekable_source.py` (converts non-seekable sources once, #4737) |
| Cache lookup | Backend | `auralis-web/backend/core/chunk_path_cache.py` + `chunk_cache_manager.py` + `file_signature.py` |
| Chunk pump / look-ahead | Backend | `auralis-web/backend/core/stream_enhanced_chunks.py` (the one pump shared by the enhanced and seek streams since #5761, plus the look-ahead task), `auralis-web/backend/core/proactive_buffer.py` |
| Level continuity | Backend | `auralis-web/backend/core/level_manager.py` |
| Resume playback | Frontend | WebSocket hook → Web Audio API |

**Check**: Position units — does the frontend send seconds where the backend expects samples (or ms)? Does the reported position after seek match what was requested, or drift by an overlap width? Are stale pre-seek chunks drained from both the backend buffer and the frontend audio queue, or does the user hear pre-seek audio after the jump? Rapid consecutive seeks — does the last one win, or do two streams interleave? Seek past end / to 0 — clamped consistently on both sides (huge positions clamp, #6130)? Held arrow keys commit coalesced seeks, and a rejected seek clears `seeking` and is retried instead of leaving the bar stuck (`bf922521`, #5885); a seek stream's chunk progress counts from its `start_chunk` (#5931). Does the first post-seek chunk arrive at the right level, given it has no predecessor context? Regression guards on the resume path: the frontend applies the backend `seek_position` to the playback clock (`e562e0d1`, #5860), discards buffer content superseded by the new stream's `audio_stream_start` epoch (`0fa8abbe`, #5861) and tears down the worklet queue and `streamEnded` latch when a new epoch replaces the buffer (`eb7f6e0c`, #5862).

### Flow 9: Queue & Playback State

| Step | Layer | File |
|------|-------|------|
| User reorders / adds / removes | Frontend | Queue components, `auralis-web/frontend/src/store/` |
| Queue request | Frontend → Backend | `auralis-web/frontend/src/hooks/player/useQueueMutations.ts` → `auralis-web/backend/routers/player_queue.py` (registered by the `routers/player.py` factory) |
| Queue service | Backend | `auralis-web/backend/services/queue_service.py` over `queue_service_base.py` (`_queue_mutation`, #5790) and the `queue_set_mixin.py` / `queue_edit_mixin.py` / `queue_order_mixin.py` mixins; `queue_enrichment.py`, `queue_protocols.py` |
| Engine queue | Engine | `auralis/player/queue_controller.py` (authoritative order) |
| State broadcast | Backend | `auralis-web/backend/core/state_manager.py` → WebSocket |
| UI update | Frontend | `auralis-web/frontend/src/hooks/player/useQueueSubscription.ts` → Redux queue slice |

**Check**: The engine queue and the backend state manager hold *different shapes* of the same queue — the engine's is filepath-only and authoritative on order, the state manager's carries rich track info and goes stale after add/remove/move (#4374 bridged them via enrichment in `queue_service.py`, which pops the engine's internal `repeat_enabled` so only `repeat_mode` reaches clients, #5983). Does every mutation path re-enrich, or do some return the stale copy? Is `filepath` ever leaked to the client (it must not be — #3205; clients get `format`)? After a reorder, does the frontend's optimistic order match what the engine actually plays next? The live queue is not persisted (queue history/undo was retired in `7088915d`, #5526), so after a backend restart is the frontend's queue reconciled against the empty engine queue rather than shown as if still playable? The frontend reads only the snake_case `current_index` from `queue_changed` (#5823) — does every emitter send that spelling? Drag-reorder of the queue or a playlist moves the track rather than duplicating it (#5189), and enqueue-all reports the tracks a full queue dropped rather than calling them already queued (#5920).

## Per-Flow Verification Checklist

For EVERY flow, systematically check:
- [ ] **Schema match**: Request fields sent == fields expected. Response fields returned == fields consumed.
- [ ] **Error handling**: Does the frontend handle 4xx and 5xx responses gracefully?
- [ ] **Timeouts**: Frontend timeout vs backend processing time — compatible?
- [ ] **Data types**: Sample rates, bit depths, timestamps, durations — consistent units and precision?
- [ ] **Null handling**: What happens when optional fields are missing on either side?
- [ ] **Case conversion**: camelCase ↔ snake_case at the API boundary?

## Phase 1: Setup

1. Parse `$ARGUMENTS` for `--flows`, `--depth`, `--limit`
2. `mkdir -p /tmp/audit/auralis/integration`
3. Fetch dedup baseline: the canonical dump from `_audit-common.md` Deduplication step 1 (`--limit 100000` + truncation assertion), redirected to `/tmp/audit/auralis/integration/issues.json`
4. Scan `docs/audits/` for prior integration audit reports

## Phase 2: Launch Flow Agents

Launch one Agent-tool subagent per flow (max 3 concurrent). Each agent writes its output to `/tmp/audit/auralis/integration/flow_<N>.md`.

Every agent prompt MUST include:
- The project root is `/mnt/data/src/matchering`
- The depth parameter value
- The limit parameter value (if set)
- The per-flow verification checklist from this file
- Reference to dedup file: `/tmp/audit/auralis/integration/issues.json`
- The context management rules from `_audit-common.md`
- The per-finding format below

### Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Flow**: <which of the 9 flows>
- **Boundary**: <sender layer> → <receiver layer>
- **Location**: `<sender-file>:<line>` → `<receiver-file>:<line>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Description**: What is wrong at this boundary
- **Evidence**: Code from both sides showing the mismatch
- **Impact**: What breaks and when
- **Suggested Fix**: Which side should change and how
```

Flow → Output mapping:
- Flow 1 (Track Playback) → `/tmp/audit/auralis/integration/flow_1.md`
- Flow 2 (Library Browsing) → `/tmp/audit/auralis/integration/flow_2.md`
- Flow 3 (Audio Enhancement) → `/tmp/audit/auralis/integration/flow_3.md`
- Flow 4 (Library Scanning) → `/tmp/audit/auralis/integration/flow_4.md`
- Flow 5 (WebSocket Lifecycle) → `/tmp/audit/auralis/integration/flow_5.md`
- Flow 6 (Fingerprint & Similarity) → `/tmp/audit/auralis/integration/flow_6.md`
- Flow 7 (Artwork) → `/tmp/audit/auralis/integration/flow_7.md`
- Flow 8 (Seek & Rebuffer) → `/tmp/audit/auralis/integration/flow_8.md`
- Flow 9 (Queue & Playback State) → `/tmp/audit/auralis/integration/flow_9.md`

## Phase 3: Merge

1. Read all `/tmp/audit/auralis/integration/flow_*.md` files
2. Combine into `docs/audits/AUDIT_INTEGRATION_<TODAY>.md` with structure:
   - **Executive Summary** — Total findings by severity, key themes, most impactful boundary mismatches
   - **Flow Coverage Matrix** — Table of all 9 flows with boundary-check status
   - **Findings** — Grouped by severity (CRITICAL first), deduplicated across flows
   - **Relationships** — Shared root causes, cross-flow boundary issues
   - **Prioritized Fix Order** — What to fix first and why
3. Remove cross-flow duplicates (same boundary issue found by multiple flows)

## Phase 4: Cleanup

1. `rm -rf /tmp/audit/auralis/integration`
2. Inform user the report is ready
3. Suggest: `/audit-publish docs/audits/AUDIT_INTEGRATION_<TODAY>.md`

## Labels

Use labels when publishing: severity label + domain labels (`backend`, `frontend`, `audio-integrity`, `websocket`, `streaming`, `library`, `fingerprint`) + `bug`
