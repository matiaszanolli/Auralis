# Backend-Frontend API Contract Sync

Cross-reference all REST endpoints, Pydantic/TypeScript schemas, and WebSocket message types between the FastAPI backend and React frontend. Reports mismatches — does NOT fix them.

**Input**: `$ARGUMENTS` = `rest`, `websocket`, or `all` (default: `all`)

## Step 1: Extract Backend Contracts

### REST Endpoints

Scan all router files in `auralis-web/backend/routers/`. For each endpoint, extract:
- HTTP method (GET, POST, PUT, DELETE, PATCH)
- URL path (including path parameters)
- Request body schema (Pydantic model or raw types)
- Response schema (return type annotation or Pydantic model)
- Query parameters and their types/defaults

### Pydantic Schemas

Read `auralis-web/backend/schemas.py` and any schema files in `auralis-web/backend/core/`:
- Model names, field names, types, and defaults
- Nested model references
- `Config` settings (especially `alias_generator`, `populate_by_name`)

### WebSocket Messages (Backend sends)

Scan these files for all `send_text(json.dumps({...}))` and `send_json({...})` calls:
- `auralis-web/backend/audio_stream_controller.py`
- `auralis-web/backend/routers/system.py`
- `auralis-web/backend/services/library_auto_scanner.py`
- Any other file that sends WebSocket messages

For each message, extract the `type` field value and `data` field structure.

### WebSocket Messages (Frontend sends)

Scan `auralis-web/frontend/src/hooks/websocket/` and `auralis-web/frontend/src/services/` for `send()`, `ws.send()`, or `sendMessage()` calls.

## Step 2: Extract Frontend Contracts

### API Client Calls

Scan all service files in `auralis-web/frontend/src/services/`. For each API call, extract:
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
- `auralis-web/frontend/src/types/websocket.ts` — message type definitions
- `auralis-web/frontend/src/hooks/websocket/` — message handlers

For each handler, extract which `type` values it listens for and what `data` fields it accesses.

## Step 3: Cross-Reference REST

For each backend endpoint, verify:

1. **Frontend caller exists**: Is there a service/hook that calls this endpoint?
2. **Method matches**: GET on backend, GET on frontend?
3. **URL matches**: Including path parameter naming
4. **Request body**: All required fields sent by frontend? Extra fields that backend ignores?
5. **Response shape**: Does the frontend type match the backend Pydantic model?
6. **Field naming**: Backend `snake_case`, frontend `camelCase` — is conversion handled?
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
- **Case conversion awareness**: `snake_case` to `camelCase` conversion is expected at the API boundary. Only flag mismatches where the conversion is WRONG or MISSING.
- **Deduplication**: Check `gh issue list` before reporting. Note existing issues.
- **Scope respect**: If `$ARGUMENTS` is `rest`, skip WebSocket checks. If `websocket`, skip REST checks.
