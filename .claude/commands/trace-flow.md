---
description: "Trace a user action through frontend, backend, and engine layers with file:line references"
argument-hint: "<flow-name | scenario-description>"
---

# Cross-Layer Flow Tracing

Trace a user action through all 3 layers (frontend, backend, engine) with specific file:line references.

**Input**: `$ARGUMENTS` = named flow or custom description

## Named Flows

| Flow Name | Entry Point | Description |
|-----------|-------------|-------------|
| `playback` | Play button click | Track loading, processing, streaming, Web Audio playback |
| `library-scan` | Add folder in settings | Folder scan, metadata extraction, DB insert, progress updates |
| `enhancement` | Adjust enhancement slider | Settings change, config propagation, real-time DSP application |
| `fingerprint` | Similarity search | Fingerprint computation, DB lookup, similarity scoring |
| `seek` | Click progress bar | Position update, chunk selection, stream restart |
| `gapless` | Track ends naturally | Next track prebuffer, advance to the prebuffered track, tiling of emitted chunks (no boundary crossfade — see Retired Architecture in `_audit-common.md`) |
| `queue` | Add/remove/reorder queue | Queue state update, playback engine sync (the live queue is not persisted) |
| `artwork` | Album/artist artwork load | Artwork extraction, caching, image serving, frontend display |
| `websocket` | WebSocket lifecycle | Connection and Origin check (no auth: desktop-only, loopback; the check is `ConnectionManager.connect` in `auralis-web/backend/websocket/connection_manager.py`), message validation, routing, heartbeat, reconnection |

If `$ARGUMENTS` doesn't match a named flow, treat it as a custom description and trace the described action.

## Tracing Methodology

### Layer 1: Frontend (React)

Trace the action through:

1. **Component**: Which component handles the user interaction? Event handler code.
2. **Hook**: Which custom hook processes the action? State updates.
3. **Redux**: Which action/thunk is dispatched? Reducer logic. Selector updates.
4. **Service**: Which API client function is called? Request format.
5. **WebSocket**: Any WebSocket messages sent? Format and handler. Hooks send through `wsContext.send({...})`, whose message type is the `OutgoingCommand` union in `auralis-web/frontend/src/types/ws/commands.ts` (#6050); `buffer_full` / `buffer_ready` go out from `useStreamChunkHandler.ts`; the low-level framing is in `auralis-web/frontend/src/hooks/websocket/` (`useOutgoingChannel.ts` outbound, `socketFrameParser.ts` inbound).

Document each step with `file:line` references.

### Layer 2: Backend (FastAPI)

Trace the request through:

1. **Router**: Which endpoint receives the request? Path, method, handler function. Routes are registered with `router.add_api_route(...)` inside each router's `create_*_router()` factory, not with decorators, and the handler is often in a sibling submodule (`player_queue.py`, `player_playback.py`, ...) — grep the path string, then follow the handler name. A WebSocket command enters at `dispatch_message` in `auralis-web/backend/ws_handlers/connection.py` instead; enhanced and seek streams then run through the shared lifecycle in `auralis-web/backend/core/stream_enhanced_lifecycle.py`, and every stream teardown goes through `detach_stream` in `auralis-web/backend/ws_handlers/stream_cancel.py` (#6214, #6292).
2. **Validation**: How is the request validated? Pydantic model.
3. **Service**: Which service layer processes the request? Business logic.
4. **Engine Call**: How does the backend invoke the audio engine? Parameters.
5. **Response**: What is returned? Schema, status code.
6. **WebSocket Broadcast**: Any real-time updates sent? Message type and data.

Document each step with `file:line` references.

### Layer 3: Engine (Python/Rust)

Trace the processing through:

1. **Service / player**: Which backend service or `auralis/player/` method is called? Parameter validation.
2. **Repository**: Which database queries run? SQL patterns.
3. **Processor**: Which DSP pipeline stages execute? Audio transformations.
4. **I/O**: File reads/writes? Format handling.
5. **Result**: What is returned to the backend? Data format.

Document each step with `file:line` references.

## Boundary Analysis

For EVERY boundary crossing (frontend->backend, backend->engine, etc.), document:

### Boundary Crossing Table

```
| Boundary | Sender | Receiver | Data Format | Transform | Error Handling |
|----------|--------|----------|-------------|-----------|----------------|
| FE -> BE | auralis-web/frontend/src/hooks/player/usePlayTrack.ts::usePlayTrack | auralis-web/backend/routers/player_queue.py::set_queue | POST JSON {tracks, start_index} | none (body already snake_case) | post() throws -> error toast |
| BE -> Service | auralis-web/backend/routers/player_queue.py::set_queue | auralis-web/backend/services/queue_set_mixin.py::set_queue | track ids | ids -> library rows | ServiceError -> raise_for_service_error -> HTTPException |
| Service -> Engine | auralis-web/backend/services/queue_set_mixin.py::set_queue | auralis/player/queue_loading.py::set_queue | list of filepaths + start_index | row -> filepath | engine call off-loop (asyncio.to_thread) |
| BE -> FE | auralis-web/backend/routers/player_queue.py::set_queue | auralis-web/frontend/src/hooks/player/usePlayTrack.ts::usePlayTrack | JSON dict | none | non-2xx -> post() throws |
```

## Risk Identification

For each traced flow, identify:

1. **Concurrency risks**: Can this flow race with another? Shared state? Locks?
2. **Error gaps**: Are there error paths that silently fail or lose context?
3. **Performance bottlenecks**: Blocking calls? N+1 queries? Large payloads?
4. **Contract mismatches**: Do sender and receiver agree on data shape?
5. **State consistency**: Can partial failures leave state inconsistent?

## Output Format

```
# Flow Trace: <flow name>

## Overview
<1-2 sentence description of what this flow does end-to-end>

## Call Chain

### 1. Frontend
- **Component**: `<file>:<line>` — <what happens>
- **Hook**: `<file>:<line>` — <what happens>
- **Redux**: `<file>:<line>` — <action dispatched>
- **Service**: `<file>:<line>` — <API call made>

### 2. Backend
- **Router**: `<file>:<line>` — <endpoint handler>
- **Service**: `<file>:<line>` — <business logic>
- **Engine Call**: `<file>:<line>` — <engine invocation>

### 3. Engine
- **Service / player**: `<file>:<line>` — <orchestration>
- **Repository**: `<file>:<line>` — <database query>
- **Processor**: `<file>:<line>` — <audio processing>

## Boundary Crossings
<table as above>

## Identified Risks
1. <risk description with file:line evidence>
2. ...

## Data Flow Diagram
<ASCII diagram showing the flow>
```

## Rules

- **Read-only**: Do NOT modify any files. Document only.
- **Evidence-based**: Every step must have a `file:line` reference, with the enclosing symbol beside it. If you can't find it, say so. Line numbers belong in the trace you write, which is a point-in-time report; durable text (this skill, issue bodies that outlive the trace) cites `path::Symbol` instead (#6248).
- **Complete**: Trace the ENTIRE flow end-to-end. Don't stop at the first boundary.
- **Practical**: Focus on risks that could actually manifest, not theoretical concerns.
