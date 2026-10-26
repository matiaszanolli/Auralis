---
description: "Deep security audit aligned with OWASP Top 10 (2021) — across backend, library, frontend"
argument-hint: "[--focus <categories>] [--depth shallow|deep] [--limit <N>]"
---

# Security-Focused Audit (OWASP Top 10)

Perform a deep security audit of the Auralis music player aligned with the OWASP Top 10 (2021).

**Architecture**: This is an orchestrator. Each OWASP category runs as an Agent-tool subagent (`subagent_type: general-purpose`, `model: sonnet`). Max 3 run concurrently.

See `.claude/commands/_audit-common.md` for project layout, severity framework, methodology, context management rules, deduplication, and finding format.

## Parameters (from $ARGUMENTS)

- `--focus <categories>`: Comma-separated OWASP categories (e.g., `A01,A03,A07`). Default: all 10.
- `--depth shallow|deep`: `shallow` = check key patterns only; `deep` = trace full data flows. Default: `deep`.
- `--limit <N>`: Stop after N findings. Default: unlimited.

## Severity Examples

| Severity | Security-Specific Examples |
|----------|--------------------------|
| **CRITICAL** | Path traversal to arbitrary files, unvalidated FFmpeg args allowing code execution, exposed debug endpoints |
| **HIGH** | WebSocket connect check bypassable, unvalidated file uploads, CORS `allow_credentials=True` with `["*"]` origins, a file route bypassing `path_security.py` |
| **MEDIUM** | Missing input sanitization, overly broad file access, insufficient rate limiting |
| **LOW** | Missing security headers, undocumented API surface, verbose error messages leaking internals |

## OWASP Top 10 Checklist

For each category, check the specific items listed. Do NOT limit yourself to these — they are starting points.

### A01: Broken Access Control
- [ ] WebSocket connections — the connect-time Origin check is `ConnectionManager.connect()` in `auralis-web/backend/config/globals.py` (`ALLOWED_WS_ORIGINS`, built from `config/origins.py`; an empty Origin is accepted only from a loopback client host, #3845; a denial raises `WebSocketOriginRejected` before `accept()`, #4703). `ws_handlers/connection.py:setup_connection` only delegates to it. Can it be bypassed (missing/spoofed Origin, subprotocol, query param, a proxied non-loopback `client.host`)? `auralis-web/backend/websocket/websocket_security.py` is NOT a connect check: it is the per-message rate limiter and size/JSON-depth validator, called from `routers/system.py` (see A07).
- [ ] All 20 registered routers (list them from `auralis-web/backend/config/routes.py`) — which have NO auth checks?
- [ ] File-reading endpoints — `routers/files.py` is upload + formats only (`files_upload.py`: file-count and byte caps, extension and magic-byte checks, `uuid4` destination). The routes that serve a file back are `routers/artwork.py` (`FileResponse`) and `routers/processing_jobs.py` `download_result` (hand-rolled containment under `tempfile.gettempdir()`, #2561); lyrics/metadata routes (`routers/tracks.py`, `metadata_deps.py`, `metadata_batch.py`) call `validate_file_path`. Can a user request files outside the music library? Does each route use `auralis-web/backend/security/path_security.py`, or hand-roll containment correctly?
- [ ] `path_security.py` itself (the allowlist registry is `path_allowlist.py` and the error types plus `@_logs_rejections` are `path_errors.py`, split out in #6271) — does containment survive symlinks, `..` after normalization, UNC/drive-relative paths, and case-insensitive filesystems? The `validate_file_path` docstring is the canonical list of who validates and who deliberately does not (the playback load path and the streamlined cache worker, #5303 / #5322). Do not re-report a listed non-caller; report a caller missing from both lists.
- [ ] Library scanner (`auralis/library/scanner/`) — it follows symlinked subdirectories with only cycle detection, and that is a decision (#4823 closed as keep-current-behavior), not a finding. Scan roots have no allowlist either: `validate_user_chosen_directory` rejects `..` before `resolve(strict=True)` and refuses OS system trees (87b33dcb). Check that every scan-folder entry point goes through it or `validate_directory_list`: `routers/settings.py` calls them directly, and `routers/library_scan.py` relies on the `LibraryScanRequest` validator in `schemas/library.py`.
- [ ] Artwork endpoints — path traversal via metadata manipulation?
- [ ] Streaming endpoints — can a user stream any file on the filesystem? Stream requests resolve a track and validate its path in `auralis-web/backend/core/stream_track_resolution.py` — is every stream path (enhanced, normal, seek) routed through it?

### A02: Cryptographic Failures
- [ ] Are any API keys, tokens, or secrets hardcoded in the codebase?
- [ ] SQLite database at `~/.auralis/library.db` — is it world-readable?
- [ ] WebSocket traffic — is it encrypted (WSS vs WS)?
- [ ] Any sensitive data stored in localStorage or sessionStorage?
- [ ] `.env` files — excluded from git? Check `.gitignore`.

### A03: Injection
- [ ] SQL injection — all queries via SQLAlchemy ORM, or is there raw SQL?
- [ ] Command injection — FFmpeg invocations in `auralis/io/` — are file paths sanitized?
- [ ] Path traversal — `unified_loader.py` — can a crafted filename escape the library root?
- [ ] Template/XSS — does the frontend render user-supplied metadata (track names, album art URLs) unsafely?
- [ ] Audio metadata — can malicious ID3 tags trigger injection when displayed or processed?

### A04: Insecure Design
- [ ] Player state machine — can invalid transitions cause undefined behavior?
- [ ] Chunked processor — what happens with malformed audio chunks?
- [ ] Queue controller — can queue manipulation cause out-of-bounds access?
- [ ] Fingerprint system — can a specially crafted file cause excessive resource consumption?

### A05: Security Misconfiguration
- [ ] CORS settings in `auralis-web/backend/config/middleware/` (`__init__.py` wires CORSMiddleware, `hosts.py` builds the list; NOT `main.py` — it moved), with the allowed origins built by `auralis-web/backend/config/origins.py` (loopback origin policy) — `allow_credentials=True` with `["*"]` origins? Does the allow-origins builder widen the set more than the localhost/dev-port case requires?
- [ ] `SecurityHeadersMiddleware` — which headers does it actually set, and are any (CSP, X-Frame-Options) missing or permissive?
- [ ] Middleware ordering — `add_middleware` is LIFO. The documented inbound order in `setup_middleware()` is CORS → SecurityHeaders → NoCache → OriginCheck → TrustedHost → RateLimit. Does a security middleware end up running *after* something it should gate, and does a short-circuit 400/403/429 still carry the security headers?
- [ ] Debug/development endpoints accessible in production?
- [ ] `--dev` flag behavior — what security features does it disable? Dev mode is `--dev` or `AURALIS_DEV_MODE` (`is_dev_mode()` in `auralis-web/backend/config/app.py`; it re-enables Swagger/ReDoc/OpenAPI and widens the origin allow-lists, #4802). It also skips the StaticFiles mount: `mount_frontend()` in `auralis-web/backend/config/fallback_routes.py`, moved out of `main.py` in 3d69275a.
- [ ] Catch-all routes (`register_fallback_routes()`, same file) — unmatched `/api` paths and unregistered WebSocket paths must answer before the StaticFiles mount sees them, and the frontend-missing page must not disclose the install path (#4351). Is the registration order in `main.py` (routers → fallbacks → mount) intact?
- [ ] Default configuration values — any that are insecure?
- [ ] Error responses (`auralis-web/backend/routers/errors.py` and the exception handlers in `auralis-web/backend/config/app.py`) — do they leak stack traces, file paths, or internal state?

### A06: Vulnerable and Outdated Components
- [ ] Check `requirements.txt` for known CVEs in dependencies.
- [ ] Check `auralis-web/frontend/package.json` for known CVEs.
- [ ] FFmpeg version — are there known vulnerabilities in the expected version?
- [ ] Rust crate dependencies in `vendor/auralis-dsp/Cargo.toml`.
- [ ] Are dependency versions pinned or floating?

### A07: Identification and Authentication Failures
- [ ] Is there any authentication at all on the backend API? (By design there is none — Auralis is a desktop app bound to `127.0.0.1:8765`. Treat "no auth" as the documented baseline; report only where that baseline is *violated*, e.g. a surface reachable beyond localhost.)
- [ ] WebSocket auth — the Origin check runs at handshake only (`config/globals.py`); `websocket_security.py` (`WebSocketRateLimiter`, `validate_and_parse_message`) runs per message from `routers/system.py`. Is anything trusted after the handshake that should be re-checked per message?
- [ ] Can any *local* process connect to port 8765 and control playback? Is the bind address actually `127.0.0.1` and never `0.0.0.0`? The port is `BACKEND_PORT` from `config/origins.py`, which reads `AURALIS_PORT` (f637c53e, #5796), so the bind port and the allowed origins are one value. Flag any second port literal.
- [ ] Desktop app — does it restrict connections to localhost only?
- [ ] Rate limiting — `RateLimitMiddleware` in `auralis-web/backend/config/middleware/rate_limit.py`: which routes does it cover, what are the limits in `auralis-web/backend/config/limits.py`, and can the window be reset or evaded?

### A08: Software and Data Integrity Failures
- [ ] Database migrations (`migration_manager.py`) — are they validated before applying?
- [ ] Audio file integrity — are checksums validated after loading?
- [ ] Fingerprint data — can it be tampered with to cause incorrect similarity results?
- [ ] Frontend build — is there subresource integrity on loaded scripts?

### A09: Security Logging and Monitoring Failures
- [ ] Are failed operations logged with sufficient detail?
- [ ] File access attempts — are unauthorized accesses logged?
- [ ] WebSocket connections — are connect/disconnect events logged?
- [ ] Sensitive data in logs — are file paths, user data, or system info logged unsafely? `install_log_sanitizer()` in `auralis-web/backend/config/bootstrap.py` re-wraps the root handlers with the sanitizing formatter (#5393). Does a handler or logger created after it bypass that formatter?

### A10: Server-Side Request Forgery (SSRF)
- [ ] Artwork fetching — can user-supplied URLs cause the backend to make arbitrary requests?
- [ ] Any endpoints that accept URLs and fetch them server-side?
- [ ] Metadata lookup services — do they accept user-controlled URLs?

## Key Security Files

| File | Purpose |
|------|---------|
| `auralis-web/backend/config/middleware/` | CORS, rate limiting, security headers, no-cache, origin check — one module each (moved out of `main.py`) |
| `auralis-web/backend/config/routes.py` | Router registration — the authoritative list of exposed surfaces |
| `auralis-web/backend/config/limits.py` | Rate-limit / request-size budgets |
| `auralis-web/backend/config/origins.py` | Loopback origin policy — how the allowed-origin set is built |
| `auralis-web/backend/core/stream_track_resolution.py` | Track lookup + path validation for every WebSocket stream path |
| `auralis-web/backend/main.py` | Composition only: wires the `config/` modules in order and binds uvicorn to `127.0.0.1` |
| `auralis-web/backend/config/app.py` | `create_app()`, exception handlers, `is_dev_mode()` |
| `auralis-web/backend/config/fallback_routes.py` | Catch-all `/api` and WebSocket routes, StaticFiles mount (skipped in dev) |
| `auralis-web/backend/config/bootstrap.py` | Logging bootstrap and log sanitizer, `sys.path` setup |
| `auralis-web/backend/security/path_security.py` | Filesystem path containment (validators); allowlist registry in `path_allowlist.py`, error types in `path_errors.py` |
| `auralis-web/backend/config/globals.py` | `ConnectionManager.connect()`: the WebSocket Origin allowlist and loopback rule |
| `auralis-web/backend/websocket/websocket_security.py` | Per-message WebSocket rate limiter and size/JSON-depth validation |
| `auralis-web/backend/ws_handlers/` | WebSocket message handling (connection, messages, playback commands) |
| `auralis-web/backend/routers/` | All 20 registered route handlers + `errors.py` (error-shape leakage) |
| `auralis-web/backend/core/audio_stream_controller.py` | WebSocket streaming |
| `auralis-web/backend/core/chunked_processor.py` | Audio chunk processing |
| `auralis/io/unified_loader.py` | File loading (FFmpeg, SoundFile) |
| `auralis/library/scanner/` | Filesystem scanning |
| `auralis/library/database.py` | Database access orchestration (`LibraryDatabase`) |
| `auralis-web/backend/core/thumbnail_cache.py` | On-disk cache keyed on a hash of the source path — verify the key cannot be attacker-influenced into a path escape |
| `auralis/library/migration_manager.py` | Schema migrations |
| `auralis-web/frontend/src/services/` | API clients |
| `auralis-web/frontend/src/hooks/` | WebSocket and API hooks |

## Data Flow Security Trace

Trace how user-controlled data flows through the system:

1. **File paths**: Frontend search → Backend router → `security/path_security.py` → `LibraryDatabase` / repositories → unified_loader → FFmpeg — is the path validated at each boundary, and does every route actually go through `path_security`? Include the cache paths: a chunk or thumbnail cache key derived from a user-influenced path must not be able to write outside its cache directory.
2. **Audio metadata**: File on disk → unified_loader → ID3/metadata parser → database → API response → Frontend render — is metadata sanitized?
3. **WebSocket messages**: Frontend → `config/globals.py` (`ConnectionManager.connect`, Origin) → `routers/system.py` (`websocket/websocket_security.py` rate limit and message validation) → `ws_handlers/connection.py` → `ws_handlers/messages.py` → `core/audio_stream_controller.py` → processing_engine → chunked_processor → audio engine — are messages validated at the handler boundary, or trusted after handshake?
4. **Library scan paths**: User adds folder → `routers/library_scan.py` → `scanner/` → filesystem walk → database insert — can symlinks or special paths escape?

## Phase 1: Setup

1. Parse `$ARGUMENTS` for `--focus`, `--depth`, `--limit`
2. `mkdir -p /tmp/audit/auralis/security`
3. Fetch dedup baseline: the canonical dump from `_audit-common.md` Deduplication step 1 (`--limit 100000` + truncation assertion), redirected to `/tmp/audit/auralis/security/issues.json`
4. Scan `docs/audits/` for prior security audit reports

## Phase 2: Launch Category Agents

Launch one Agent-tool subagent per OWASP category (max 3 concurrent). Each agent writes its output to `/tmp/audit/auralis/security/a<NN>.md`.

Every agent prompt MUST include:
- The project root is `/mnt/data/src/matchering`
- The depth parameter value
- The limit parameter value (if set)
- Reference to dedup file: `/tmp/audit/auralis/security/issues.json`
- The key security files table and data flow security traces from this file
- The context management rules from `_audit-common.md`
- The per-finding format below

### Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **OWASP Category**: A01–A10
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Description**: What is wrong and why
- **Evidence**: Code snippet or exact call path
- **Exploit Scenario**: Step-by-step how an attacker could exploit this
- **Impact**: What is compromised (data, access, availability)
- **Suggested Fix**: Brief direction (1-3 sentences)
```

Category → Output mapping:
- A01 (Broken Access Control) → `/tmp/audit/auralis/security/a01.md`
- A02 (Cryptographic Failures) → `/tmp/audit/auralis/security/a02.md`
- A03 (Injection) → `/tmp/audit/auralis/security/a03.md`
- A04 (Insecure Design) → `/tmp/audit/auralis/security/a04.md`
- A05 (Security Misconfiguration) → `/tmp/audit/auralis/security/a05.md`
- A06 (Vulnerable Components) → `/tmp/audit/auralis/security/a06.md`
- A07 (Auth Failures) → `/tmp/audit/auralis/security/a07.md`
- A08 (Data Integrity Failures) → `/tmp/audit/auralis/security/a08.md`
- A09 (Logging Failures) → `/tmp/audit/auralis/security/a09.md`
- A10 (SSRF) → `/tmp/audit/auralis/security/a10.md`

## Phase 3: Merge

1. Read all `/tmp/audit/auralis/security/a*.md` files
2. Combine into `docs/audits/AUDIT_SECURITY_<TODAY>.md` with structure:
   - **Executive Summary** — Total findings by severity, key themes, most exploitable issues
   - **Data Flow Security Matrix** — Which flows are safe, which have gaps
   - **Findings** — Grouped by severity (CRITICAL first), deduplicated across categories
   - **Relationships** — How findings interact (e.g., A01 + A05 chaining)
   - **Prioritized Fix Order** — What to fix first and why
3. Remove cross-category duplicates (same file:line found by multiple categories)

## Phase 4: Cleanup

1. `rm -rf /tmp/audit/auralis/security`
2. Inform user the report is ready
3. Suggest: `/audit-publish docs/audits/AUDIT_SECURITY_<TODAY>.md`

## Labels

Use labels when publishing: severity label + `security` + `bug`
