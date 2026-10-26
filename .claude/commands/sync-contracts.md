---
description: "Cross-reference REST endpoints, Pydantic/TS schemas, and WS message types; reports mismatches (no fixes)"
argument-hint: "[rest|websocket|all]"
---

# Backend-Frontend API Contract Sync

Cross-reference all REST endpoints, Pydantic/TypeScript schemas, and WebSocket message types between the FastAPI backend and React frontend. Reports mismatches — does NOT fix them.

**Input**: `$ARGUMENTS` = `rest`, `websocket`, or `all` (default: `all`)

## Step 1: Extract Backend Contracts

### REST Endpoints

Routers are registered in `auralis-web/backend/config/routes.py`. Each router module's `create_*_router()` factory registers its routes with `router.add_api_route(path, handler, methods=[...], response_model=...)` — there are no `@router.get(...)` decorators to grep for. The handlers are module-level functions (#5832) in the router module or its sibling submodules (`player_playback.py`, `player_queue.py`, `<router>_models.py`, `<router>_deps.py`, ... — the ten-router split of #5831), so read the factory for the path and method, then follow the handler reference. The SPA/unregistered catch-all routes live in `auralis-web/backend/config/fallback_routes.py`. For each endpoint, extract:
- HTTP method (GET, POST, PUT, DELETE, PATCH)
- URL path (including path parameters)
- Request body schema (Pydantic model or raw types)
- Response schema (return type annotation or Pydantic model)
- Query parameters and their types/defaults

### Pydantic Schemas

Read the `auralis-web/backend/schemas/` package (shared contracts: `enhancement.py` holds `VALID_PRESETS` / `DEFAULT_PRESET`; `websocket.py` holds the inbound `WebSocketMessageType` enum and error envelope) and the per-router request/response bodies in `auralis-web/backend/routers/*_models.py` (a few routers — `tracks.py`, `cache_streamlined.py`, `similarity_graph.py`, `library_scan.py`, `fingerprint_status.py` — still define theirs inline):
- Model names, field names, types, and defaults
- Nested model references
- `model_config = ConfigDict(...)` settings. No backend model sets an `alias_generator`, so the wire is snake_case throughout — there is no automatic camelCase conversion on the backend side

### WebSocket Messages (Backend sends)

The typed contract lives in `auralis-web/backend/websocket/outbound_messages.py` (the `broadcast_typed` overloads, one Literal discriminator per outbound message type) and its payload TypedDicts in `auralis-web/backend/websocket/outbound/` (`player.py`, `queue.py`, `library.py`, `enhancement.py`; split out in #6269). Start there, then scan the places that build frames outside it:
- `auralis-web/backend/core/stream_protocol.py` and `auralis-web/backend/core/stream_lifecycle.py` / `stream_notifications.py` (the `audio_stream_*` JSON control messages)
- `auralis-web/backend/ws_handlers/` (inbound command handlers and their replies — `playback_commands.py`, `seek_command.py`, `playback_control.py`, `messages.py`; `connection.py` `dispatch_message` is the inbound type switch), `auralis-web/backend/routers/system.py` (the module-level `websocket_endpoint` connection loop) and `auralis-web/backend/routers/system_streams.py` (the stream tasks it launches, split out in #5832)
- Any remaining direct `send_text(json.dumps({...}))` / `send_json({...})` call: `grep -rn "send_text\|send_json" auralis-web/backend --include='*.py'`

For each message, extract the `type` field value and `data` field structure.

### WebSocket Messages (Frontend sends)

Two send paths: the raw `manager.send(JSON.stringify(...))` calls in `auralis-web/frontend/src/hooks/websocket/` (`websocketConnectionCore.ts`, `useOutgoingChannel.ts`, and the heartbeat `pong` in `socketFrameParser.ts` — split out of the connection core in #5840), and `wsContext.send({...})` from hooks, chiefly `auralis-web/frontend/src/hooks/enhancement/` (`play_enhanced` / `play_normal` in `useEnhancedPlayCommand.ts`, `seek` in `useEnhancedSeek.ts`, `buffer_full` / `buffer_ready` in `useStreamMessageHandlers.ts`, and the drain-triggered `buffer_ready` in `flowDrainWatch.ts`): `grep -rn "\.send(" auralis-web/frontend/src --include='*.ts' --include='*.tsx'`. Check each sent `type` against the backend's `dispatch_message` switch and the inbound `WebSocketMessageType` enum. The frontend's message types are in `auralis-web/frontend/src/types/ws/`.

## Step 2: Extract Frontend Contracts

### API Client Calls

Most calls go through `auralis-web/frontend/src/utils/apiRequest.ts` (`get` / `post` / `put` / `patch` / `del`; options and timeouts in `apiRequestTypes.ts`, retry policy in `queryRetry.ts`) with paths from `ENDPOINTS` in `auralis-web/frontend/src/config/api.ts`. Scan all service files in `auralis-web/frontend/src/services/`, plus `useRestAPI` (`auralis-web/frontend/src/hooks/api/useRestAPI.ts`, a React wrapper over the shared `fetchWithTimeout` / `buildUrl` exported by `apiRequest.ts` since #6216 — there is no second transport) and the direct `fetch(` calls still scattered across `src/hooks/` and `src/components/`. For each API call, extract:
- HTTP method, URL path
- Request body shape (TypeScript interface or inline object)
- Expected response shape

Also check `auralis-web/frontend/src/hooks/api/` and `auralis-web/frontend/src/store/` for thunks making API calls.

### TypeScript Types

Read:
- `auralis-web/frontend/src/types/` — all type definition files
- `auralis-web/frontend/src/services/` — inline type definitions
- `auralis-web/frontend/src/hooks/` — hook parameter/return types

### WebSocket Message Types

Read:
- `auralis-web/frontend/src/types/websocket.ts` — a barrel re-exporting the per-domain modules in `auralis-web/frontend/src/types/ws/`
- `auralis-web/frontend/src/hooks/websocket/` — message handlers

For each handler, extract which `type` values it listens for and what `data` fields it accesses.

## Step 3: Cross-Reference REST

For each backend endpoint, verify:

1. **Frontend caller exists**: Is there a service/hook that calls this endpoint?
2. **Method matches**: GET on backend, GET on frontend?
3. **URL matches**: Including path parameter naming
4. **Request body**: All required fields sent by frontend? Extra fields that backend ignores?
5. **Response shape**: Does the frontend type match the backend Pydantic model?
6. **Field naming**: The wire is `snake_case`. Conversion to the camelCase domain types is explicit, at ingress: `auralis-web/frontend/src/api/transformers/` (`transformTrack` etc.) and `auralis-web/frontend/src/hooks/player/trackInfoMapper.ts`. Many wire types stay snake_case on purpose (`has_more`, `current_index` — the camelCase fallbacks were removed in #5823). Is a raw payload dispatched into a camelCase slice without a transformer (the #5606 class)?
7. **Optional fields**: Are fields optional on both sides consistently?

## Step 4: Cross-Reference Schemas

For each Pydantic model / TypeScript interface pair:

1. **Field names**: After case conversion, do all fields match?
2. **Field types**: `int` = `number`, `str` = `string`, `bool` = `boolean`, `list[T]` = `T[]`
3. **Nested objects**: Are nested schemas consistent at all levels?
4. **Enums**: Do enum values match exactly?
5. **Defaults**: Are default values consistent?

## Step 5: Cross-Reference WebSocket (if scope includes `websocket` or `all`)

1. **Backend sends -> Frontend handles**: For every message type the backend sends, is there a frontend handler?
2. **Frontend expects -> Backend sends**: For every message type the frontend listens for, does the backend send it?
3. **Data shape match**: For each message type, do the `data` fields match between sender and receiver?
4. **Documentation**: Cross-check against `auralis-web/backend/WEBSOCKET_API.md`
5. **Envelope format**: All messages use `{type, data}` structure consistently?

## Output Format

### Table 1: REST Endpoint Sync

```
| Method | Backend Path | Frontend Caller | Status | Notes |
|--------|-------------|-----------------|--------|-------|
| GET | /api/tracks | trackService.list() | OK | |
| POST | /api/library/scan | settingsService.triggerScan() | MISMATCH | Request body differs |
| GET | /api/player/position | — | ORPHAN | No frontend caller |
```

Statuses: `OK`, `MISMATCH` (details in Notes), `ORPHAN` (one side only)

### Table 2: Schema Mismatches

```
| Backend Model | Frontend Type | Field | Backend Type | Frontend Type | Issue |
|--------------|---------------|-------|-------------|---------------|-------|
| TrackResponse | Track | duration | float (seconds) | number (ms) | Unit mismatch |
```

### Table 3: WebSocket Message Sync (if applicable)

```
| Message Type | Backend Sends | Frontend Handles | Data Shape Match | Notes |
|-------------|--------------|-----------------|-----------------|-------|
| player_state | system.py:L45 | usePlayerState | OK | |
```

### Summary

```
## Contract Sync Summary
- REST endpoints: X total, Y matched, Z mismatches, W orphans
- Schema pairs: X total, Y matched, Z mismatches
- WebSocket types: X total, Y matched, Z mismatches, W orphans
- Overall: SYNCED / HAS MISMATCHES
```

## Rules

- **Read-only**: Do NOT modify any files. Report only.
- **Be precise**: Include file:line references for every mismatch.
- **Case conversion awareness**: `snake_case` to `camelCase` conversion happens only where a transformer is applied (see Step 3 item 6); a snake_case wire type read as snake_case is correct. Only flag mismatches where the conversion is WRONG or MISSING, or where a frontend reads a spelling no backend emitter sends.
- **Deduplication**: Check `gh issue list --state all` before reporting (open-only hides closed regressions). Note existing issues.
- **Scope respect**: If `$ARGUMENTS` is `rest`, skip WebSocket checks. If `websocket`, skip REST checks.
