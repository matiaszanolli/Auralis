# Backend Audit

Audit the Auralis FastAPI backend for route handler correctness, WebSocket streaming reliability, chunked processing integrity, schema consistency, middleware configuration, async/sync boundary safety, error handling, and test coverage. Then create GitHub issues for every new confirmed finding.

## Scope

This audit covers ONLY the backend code:

- **App Entry**: `auralis-web/backend/main.py` (FastAPI app, CORS, middleware)
- **Routers**: `auralis-web/backend/routers/` (18 route handlers: player, library, albums, artists, playlists, enhancement, metadata, artwork, system, similarity, streaming, etc.)
- **WebSocket Streaming**: `auralis-web/backend/audio_stream_controller.py`
- **Chunked Processor**: `auralis-web/backend/chunked_processor.py` (30s chunks, 3s crossfade)
- **Processing Engine**: `auralis-web/backend/processing_engine.py`
- **Schemas**: `auralis-web/backend/schemas.py`
- **Services**: `auralis-web/backend/services/`
- **Core/Config**: `auralis-web/backend/core/`, `auralis-web/backend/config/`
- **Tests**: Backend-related tests under `tests/`

Out of scope: React frontend, audio engine internals (`auralis/`), Rust DSP. However, DO verify that the backend correctly calls engine APIs and returns responses matching frontend expectations.

## Severity Definitions

| Severity | Definition | Examples |
|----------|-----------|---------|
| **CRITICAL** | Audio streaming corruption, data loss, or exploitable vulnerability in production NOW. | Dropped audio chunks in WebSocket stream, database corruption from concurrent writes, path traversal via router |
| **HIGH** | Failures under realistic conditions. Fix before next release. | Blocking sync call starving event loop, WebSocket disconnect leaking resources, unhandled exception returning 500 |
| **MEDIUM** | Incorrect behavior with workarounds, or affects non-critical paths. | Schema mismatch with frontend, missing input validation, inconsistent error response format |
| **LOW** | Code quality, maintainability, or minor inconsistencies. | Unused imports, missing type hints, undocumented endpoints, inconsistent naming |

## Audit Dimensions

### Dimension 1: Route Handler Correctness

**Key locations**: `auralis-web/backend/routers/`

**Check**:
- [ ] All handlers are `async def` — are there any sync handlers that block the event loop?
- [ ] Input validation — are path parameters, query parameters, and request bodies validated with Pydantic models?
- [ ] Error responses — do all error paths return proper `HTTPException` with appropriate status codes?
- [ ] Response schemas — do actual return values match declared response models?
- [ ] Idempotency — are PUT/DELETE operations safe to retry?
- [ ] Route conflicts — are there overlapping path patterns that could match incorrectly?
- [ ] Dependency injection — are shared resources (LibraryManager, ProcessingEngine) injected correctly?
- [ ] Missing endpoints — are there frontend API calls that have no corresponding backend route?

### Dimension 2: WebSocket Streaming

**Key locations**: `auralis-web/backend/audio_stream_controller.py`, WebSocket-related code in `main.py`

**Check**:
- [ ] Connection lifecycle — is accept/close handled correctly? Are resources cleaned up on disconnect?
- [ ] Binary frame format — is the audio frame encoding consistent with what the frontend expects?
- [ ] Backpressure — what happens when the client can't consume frames fast enough? Does the server buffer unboundedly?
- [ ] Multiple clients — can multiple WebSocket connections coexist? Is state per-connection or shared?
- [ ] Error during streaming — does a processing error gracefully close the stream or leave it hanging?
- [ ] Message type consistency — are all message types (text control + binary audio) correctly discriminated?
- [ ] Heartbeat / keepalive — is there a mechanism to detect stale connections?
- [ ] Reconnection state — when a client reconnects, can it resume or must it restart?

### Dimension 3: Chunked Processing

**Key locations**: `auralis-web/backend/chunked_processor.py`

**Check**:
- [ ] Chunk boundaries — do 30s chunks align to audio frame boundaries (not mid-sample)?
- [ ] Crossfade correctness — is the 3s crossfade using equal-power curves? Is `len(output) == len(input)` maintained?
- [ ] First/last chunk — are the first and last chunks handled correctly (no crossfade at start/end of track)?
- [ ] Sample rate consistency — is the sample rate preserved across chunk boundaries?
- [ ] Processing failure — if one chunk fails, does it corrupt subsequent chunks or gracefully degrade?
- [ ] Memory management — are completed chunks released promptly, or do they accumulate?
- [ ] Concurrent chunk requests — can a new track request arrive while chunks are still being processed for the previous track?

### Dimension 4: Processing Engine

**Key locations**: `auralis-web/backend/processing_engine.py`

**Check**:
- [ ] Engine lifecycle — is the processing engine a singleton, per-request, or per-connection? Is this appropriate?
- [ ] Audio engine integration — are calls to `auralis/` engine APIs correct (parameters, return types, error handling)?
- [ ] Async/sync boundary — are sync audio processing calls wrapped in `run_in_executor`? Can they starve the event loop?
- [ ] State management — does the engine maintain mutable state between requests? Is this thread-safe?
- [ ] Configuration propagation — do enhancement settings from the frontend correctly reach the DSP pipeline?
- [ ] Resource cleanup — are audio buffers, temporary files, and engine state cleaned up after processing?

### Dimension 5: Schema Consistency

**Key locations**: `auralis-web/backend/schemas.py`, router response declarations

**Check**:
- [ ] Request/Response models — are all endpoints using Pydantic models for both input and output?
- [ ] Field naming — consistent snake_case throughout? Proper `alias` config for camelCase JSON responses?
- [ ] Optional fields — are fields marked Optional only when truly optional? Default values sensible?
- [ ] Type accuracy — do numeric fields use the correct type (int vs float, seconds vs milliseconds)?
- [ ] Nested schemas — are related objects properly nested, not flattened inconsistently?
- [ ] Enum values — are string enums used for fixed sets of values (player state, enhancement mode)?
- [ ] Schema reuse — are common patterns (track info, pagination) shared, not duplicated?

### Dimension 6: Middleware & Configuration

**Key locations**: `auralis-web/backend/main.py`, `auralis-web/backend/config/`

**Check**:
- [ ] CORS — is `allow_origins` properly restricted? Is `allow_credentials=True` combined with wildcard `["*"]` origins (insecure)?
- [ ] Router inclusion — are all 18 routers properly registered with correct prefixes and tags?
- [ ] Middleware ordering — are middleware applied in the correct order (CORS before auth, etc.)?
- [ ] Static file serving — is there proper path restriction for served files?
- [ ] Startup/shutdown events — are background tasks, database connections, and engine resources properly initialized and cleaned up?
- [ ] `--dev` flag — what security or performance features does it change?
- [ ] Logging configuration — appropriate log levels? Sensitive data (file paths, user data) redacted?

### Dimension 7: Error Handling & Resilience

**Key locations**: All routers, `processing_engine.py`, `audio_stream_controller.py`

**Check**:
- [ ] Global exception handler — is there a catch-all that prevents 500 errors from leaking stack traces?
- [ ] FFmpeg failures — does the backend gracefully handle corrupt or unsupported audio files?
- [ ] Database errors — are SQLAlchemy errors caught and translated to meaningful HTTP responses?
- [ ] File not found — does the backend handle missing audio files, artwork, or library paths?
- [ ] Timeout handling — are there timeouts on audio processing? What happens when processing takes too long?
- [ ] WebSocket error propagation — are processing errors sent to the client as error messages before closing?
- [ ] Recovery — can the backend recover from a crash (process restart) without losing critical state?

### Dimension 8: Performance & Resource Management

**Key locations**: All backend files

**Check**:
- [ ] Event loop blocking — are there sync I/O calls (file reads, subprocess, CPU-bound work) on the async event loop?
- [ ] Connection pooling — is SQLAlchemy connection pooling configured (`pool_pre_ping=True`, appropriate pool size)?
- [ ] Memory usage — are large audio buffers (30s chunks at 44.1kHz stereo = ~10MB each) managed carefully?
- [ ] Concurrent request handling — can the backend handle multiple simultaneous track requests?
- [ ] Streaming efficiency — is audio data streamed chunk-by-chunk, or loaded entirely into memory?
- [ ] Caching — are expensive operations (fingerprinting, analysis) cached to avoid redundant computation?
- [ ] N+1 queries — do list endpoints use `selectinload()` to avoid N+1 database queries?

### Dimension 9: Test Coverage

**Key locations**: Backend-related tests under `tests/`

**Check**:
- [ ] Router coverage — is each of the 18 routers tested with happy path and error cases?
- [ ] WebSocket testing — are WebSocket connections tested (connect, send, receive, disconnect)?
- [ ] Chunked processing tests — are chunk boundaries, crossfades, and edge cases tested?
- [ ] Schema validation tests — are invalid request payloads tested for proper rejection?
- [ ] Integration tests — are end-to-end flows (REST → engine → response) tested?
- [ ] Error scenario tests — are corrupt files, missing resources, and timeouts tested?
- [ ] Concurrency tests — are concurrent request scenarios tested?

## Deduplication (MANDATORY)

Before reporting ANY finding:

1. Run: `gh issue list --limit 200 --json number,title,state,labels`
2. Search for keywords from your finding in existing issue titles
3. If a matching issue exists:
   - **OPEN**: Note as "Existing: #NNN" and skip
   - **CLOSED**: Verify fix is in place. If regressed, report as "Regression of #NNN"
4. If no match: Report as NEW

## Phase 1: Audit

Write your report to: **`docs/audits/AUDIT_BACKEND_<TODAY>.md`** (use today's date, format YYYY-MM-DD).

### Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Dimension**: Route Handlers | WebSocket Streaming | Chunked Processing | Processing Engine | Schema Consistency | Middleware & Config | Error Handling | Performance | Test Coverage
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Description**: What is wrong and why
- **Evidence**: Code snippet demonstrating the issue
- **Impact**: What breaks, when, user-visible effect
- **Suggested Fix**: Brief direction (1-3 sentences)
```

## Phase 2: Publish to GitHub

After completing the audit report, for every finding with **Status: NEW** or **Regression**:

1. **Create a GitHub issue** with:
   - **Title**: `[<TODAY>] <SEVERITY> - <Short Title>`
   - **Labels**: severity label (`critical`, `high`, `medium`, `low`) + `backend` + `bug`
   - **Body**:
     ```
     ## Summary
     <description>

     ## Evidence / Code Paths
     - **File**: `<path>:<line-range>`
     - **Code**: <relevant snippet>
     - **Call path**: <how execution reaches the problem>

     ## Impact
     - **Severity**: <SEVERITY>
     - **What breaks**: <failure mode>
     - **When**: <trigger conditions>

     ## Related Issues
     - #NNN — <relationship>

     ## Proposed Fix
     <recommended approach>

     ## Acceptance Criteria
     - [ ] <criterion>

     ## Test Plan
     - <test description> — assert <expected>
     ```

2. **Cross-reference**: For each new issue that relates to an existing issue:
   ```
   gh issue comment <EXISTING_ISSUE> --body "Related: #<NEW_ISSUE> — <brief description>"
   ```

3. **Print a summary table** at the end:
   ```
   | Finding | Severity | Dimension | Action | Issue |
   |---------|----------|-----------|--------|-------|
   | <title> | HIGH | WebSocket Streaming | CREATED | #NNN |
   | <title> | MEDIUM | Schema Consistency | DUPLICATE of #NNN | — |
   ```
