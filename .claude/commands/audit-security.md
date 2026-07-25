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
- [ ] WebSocket connections (`auralis-web/backend/ws_handlers/connection.py`, `auralis-web/backend/core/audio_stream_controller.py`) — is `auralis-web/backend/websocket/websocket_security.py` invoked on connect, and can its check be bypassed (missing/spoofed Origin, subprotocol, query param)?
- [ ] All 20 registered routers (list them from `auralis-web/backend/config/routes.py`) — which have NO auth checks?
- [ ] File serving endpoints (`auralis-web/backend/routers/files.py`) — can a user request files outside the music library? Do they route through `auralis-web/backend/security/path_security.py`, or hand-roll containment?
- [ ] `path_security.py` itself — does containment survive symlinks, `..` after normalization, UNC/drive-relative paths, and case-insensitive filesystems?
- [ ] Library scanner (`auralis/library/scanner/`) — does it follow symlinks outside allowed directories?
- [ ] Artwork endpoints — path traversal via metadata manipulation?
- [ ] Streaming endpoints — can a user stream any file on the filesystem?

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
- [ ] CORS settings in `auralis-web/backend/config/middleware.py` (NOT `main.py` — it moved) — `allow_credentials=True` with `["*"]` origins? Does the allow-origins builder widen the set more than the localhost/dev-port case requires?
- [ ] `SecurityHeadersMiddleware` — which headers does it actually set, and are any (CSP, X-Frame-Options) missing or permissive?
- [ ] Middleware ordering — `add_middleware` is LIFO. Does a security middleware end up running *after* something it should gate?
- [ ] Debug/development endpoints accessible in production?
- [ ] `--dev` flag behavior — what security features does it disable? (It also skips the StaticFiles mount in `main.py`.)
- [ ] Default configuration values — any that are insecure?
- [ ] Error responses (`auralis-web/backend/routers/errors.py`) — do they leak stack traces, file paths, or internal state?

### A06: Vulnerable and Outdated Components
- [ ] Check `requirements.txt` for known CVEs in dependencies.
- [ ] Check `auralis-web/frontend/package.json` for known CVEs.
- [ ] FFmpeg version — are there known vulnerabilities in the expected version?
- [ ] Rust crate dependencies in `vendor/auralis-dsp/Cargo.toml`.
- [ ] Are dependency versions pinned or floating?

### A07: Identification and Authentication Failures
- [ ] Is there any authentication at all on the backend API? (By design there is none — Auralis is a desktop app bound to `127.0.0.1:8765`. Treat "no auth" as the documented baseline; report only where that baseline is *violated*, e.g. a surface reachable beyond localhost.)
- [ ] WebSocket auth — `auralis-web/backend/websocket/websocket_security.py` exists: is it validated on connect AND on each message, or only at handshake?
- [ ] Can any *local* process connect to port 8765 and control playback? Is the bind address actually `127.0.0.1` and never `0.0.0.0`?
- [ ] Desktop app — does it restrict connections to localhost only?
- [ ] Rate limiting — `RateLimitMiddleware` in `auralis-web/backend/config/middleware.py`: which routes does it cover, what are the limits in `auralis-web/backend/config/limits.py`, and can the window be reset or evaded?

### A08: Software and Data Integrity Failures
- [ ] Database migrations (`migration_manager.py`) — are they validated before applying?
- [ ] Audio file integrity — are checksums validated after loading?
- [ ] Fingerprint data — can it be tampered with to cause incorrect similarity results?
- [ ] Frontend build — is there subresource integrity on loaded scripts?

### A09: Security Logging and Monitoring Failures
- [ ] Are failed operations logged with sufficient detail?
- [ ] File access attempts — are unauthorized accesses logged?
- [ ] WebSocket connections — are connect/disconnect events logged?
- [ ] Sensitive data in logs — are file paths, user data, or system info logged unsafely?

### A10: Server-Side Request Forgery (SSRF)
- [ ] Artwork fetching — can user-supplied URLs cause the backend to make arbitrary requests?
- [ ] Any endpoints that accept URLs and fetch them server-side?
- [ ] Metadata lookup services — do they accept user-controlled URLs?

## Key Security Files

| File | Purpose |
|------|---------|
| `auralis-web/backend/config/middleware.py` | CORS, rate limiting, security headers, no-cache (moved out of `main.py`) |
| `auralis-web/backend/config/routes.py` | Router registration — the authoritative list of exposed surfaces |
| `auralis-web/backend/config/limits.py` | Rate-limit / request-size budgets |
| `auralis-web/backend/main.py` | Lifespan wiring, StaticFiles mount, `--dev` switch |
| `auralis-web/backend/security/path_security.py` | Filesystem path containment |
| `auralis-web/backend/websocket/websocket_security.py` | WebSocket connect-time checks |
| `auralis-web/backend/ws_handlers/` | WebSocket message handling (connection, messages, playback commands) |
| `auralis-web/backend/routers/` | All 20 registered route handlers + `errors.py` (error-shape leakage) |
| `auralis-web/backend/core/audio_stream_controller.py` | WebSocket streaming |
| `auralis-web/backend/core/chunked_processor.py` | Audio chunk processing |
| `auralis/io/unified_loader.py` | File loading (FFmpeg, SoundFile) |
| `auralis/library/scanner/` | Filesystem scanning |
| `auralis/library/manager.py` | Database access orchestration |
| `auralis/library/migration_manager.py` | Schema migrations |
| `auralis-web/frontend/src/services/` | API clients |
| `auralis-web/frontend/src/hooks/` | WebSocket and API hooks |

## Data Flow Security Trace

Trace how user-controlled data flows through the system:

1. **File paths**: Frontend search → Backend router → `security/path_security.py` → LibraryManager → unified_loader → FFmpeg — is the path validated at each boundary, and does every route actually go through `path_security`?
2. **Audio metadata**: File on disk → unified_loader → ID3/metadata parser → database → API response → Frontend render — is metadata sanitized?
3. **WebSocket messages**: Frontend → `websocket/websocket_security.py` → `ws_handlers/connection.py` → `ws_handlers/messages.py` → `core/audio_stream_controller.py` → processing_engine → chunked_processor → audio engine — are messages validated at the handler boundary, or trusted after handshake?
4. **Library scan paths**: User adds folder → `routers/library_scan.py` → `scanner/` → filesystem walk → database insert — can symlinks or special paths escape?

## Phase 1: Setup

1. Parse `$ARGUMENTS` for `--focus`, `--depth`, `--limit`
2. `mkdir -p /tmp/audit/security`
3. Fetch dedup baseline: `gh issue list --limit 200 --json number,title,state,labels > /tmp/audit/security/issues.json`
4. Scan `docs/audits/` for prior security audit reports

## Phase 2: Launch Category Agents

Launch one Agent-tool subagent per OWASP category (max 3 concurrent). Each agent writes its output to `/tmp/audit/security/a<NN>.md`.

Every agent prompt MUST include:
- The project root is `/mnt/data/src/matchering`
- The depth parameter value
- The limit parameter value (if set)
- Reference to dedup file: `/tmp/audit/security/issues.json`
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
- A01 (Broken Access Control) → `/tmp/audit/security/a01.md`
- A02 (Cryptographic Failures) → `/tmp/audit/security/a02.md`
- A03 (Injection) → `/tmp/audit/security/a03.md`
- A04 (Insecure Design) → `/tmp/audit/security/a04.md`
- A05 (Security Misconfiguration) → `/tmp/audit/security/a05.md`
- A06 (Vulnerable Components) → `/tmp/audit/security/a06.md`
- A07 (Auth Failures) → `/tmp/audit/security/a07.md`
- A08 (Data Integrity Failures) → `/tmp/audit/security/a08.md`
- A09 (Logging Failures) → `/tmp/audit/security/a09.md`
- A10 (SSRF) → `/tmp/audit/security/a10.md`

## Phase 3: Merge

1. Read all `/tmp/audit/security/a*.md` files
2. Combine into `docs/audits/AUDIT_SECURITY_<TODAY>.md` with structure:
   - **Executive Summary** — Total findings by severity, key themes, most exploitable issues
   - **Data Flow Security Matrix** — Which flows are safe, which have gaps
   - **Findings** — Grouped by severity (CRITICAL first), deduplicated across categories
   - **Relationships** — How findings interact (e.g., A01 + A05 chaining)
   - **Prioritized Fix Order** — What to fix first and why
3. Remove cross-category duplicates (same file:line found by multiple categories)

## Phase 4: Cleanup

1. `rm -rf /tmp/audit/security`
2. Inform user the report is ready
3. Suggest: `/audit-publish docs/audits/AUDIT_SECURITY_<TODAY>.md`

## Labels

Use labels when publishing: severity label + `security` + `bug`
