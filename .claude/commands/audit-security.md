# Security-Focused Audit (OWASP Top 10)

Perform a security audit of the Auralis music player aligned with the OWASP Top 10 (2021), then create GitHub issues for every new confirmed finding.

## Project Layout

All code lives in a single repo at `/mnt/data/src/matchering`:

- **Audio Engine**: `auralis/` — Core Python audio engine
- **Backend**: `auralis-web/backend/` — FastAPI REST + WebSocket (:8765)
- **Frontend**: `auralis-web/frontend/` — React 18, TypeScript, Vite
- **Rust DSP**: `vendor/auralis-dsp/` — PyO3 module
- **Tests**: `tests/` — 850+ tests across 21 directories

## Severity Definitions

| Severity | Definition | Examples |
|----------|-----------|---------|
| **CRITICAL** | Exploitable NOW. File system access, code execution, or data exfiltration with no workaround. | Path traversal to arbitrary files, unvalidated FFmpeg args, exposed debug endpoints |
| **HIGH** | Exploitable under realistic conditions or requires minor prerequisites. | Missing auth on WebSocket, unvalidated file uploads, CORS misconfiguration |
| **MEDIUM** | Defense-in-depth gap or requires chained exploitation. | Missing input sanitization, overly broad file access, insufficient rate limiting |
| **LOW** | Informational, hardening opportunity, or requires local access. | Missing security headers, undocumented API surface, verbose error messages |

## OWASP Top 10 Checklist

For each category, check the specific items listed. Do NOT limit yourself to these — they are starting points.

### A01: Broken Access Control
- [ ] WebSocket connections in `audio_stream_controller.py` — is there auth on connect?
- [ ] All 18 routers in `auralis-web/backend/routers/` — which have NO auth checks?
- [ ] File serving endpoints — can a user request files outside the music library?
- [ ] Library scanner (`auralis/library/scanner.py`) — does it follow symlinks outside allowed directories?
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
- [ ] CORS settings in `main.py` — `allow_credentials=True` with `["*"]` origins?
- [ ] Debug/development endpoints accessible in production?
- [ ] `--dev` flag behavior — what security features does it disable?
- [ ] Default configuration values — any that are insecure?
- [ ] Error responses — do they leak stack traces, file paths, or internal state?

### A06: Vulnerable and Outdated Components
- [ ] Check `requirements.txt` for known CVEs in dependencies.
- [ ] Check `auralis-web/frontend/package.json` for known CVEs.
- [ ] FFmpeg version — are there known vulnerabilities in the expected version?
- [ ] Rust crate dependencies in `vendor/auralis-dsp/Cargo.toml`.
- [ ] Are dependency versions pinned or floating?

### A07: Identification and Authentication Failures
- [ ] Is there any authentication at all on the backend API?
- [ ] WebSocket auth — is it validated on connect AND on each message?
- [ ] Can any client connect to port 8765 and control playback?
- [ ] Desktop app — does it restrict connections to localhost only?
- [ ] Rate limiting on any endpoints?

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
| `auralis-web/backend/main.py` | FastAPI app, CORS, middleware config |
| `auralis-web/backend/routers/` | All 18 route handlers |
| `auralis-web/backend/audio_stream_controller.py` | WebSocket streaming |
| `auralis-web/backend/chunked_processor.py` | Audio chunk processing |
| `auralis/io/unified_loader.py` | File loading (FFmpeg, SoundFile) |
| `auralis/library/scanner.py` | Filesystem scanning |
| `auralis/library/manager.py` | Database access orchestration |
| `auralis/library/migration_manager.py` | Schema migrations |
| `auralis-web/frontend/src/services/` | API clients |
| `auralis-web/frontend/src/hooks/` | WebSocket and API hooks |

## Data Flow Security Trace

Trace how user-controlled data flows through the system:

1. **File paths**: Frontend search → Backend router → LibraryManager → unified_loader → FFmpeg — is the path validated at each boundary?
2. **Audio metadata**: File on disk → unified_loader → ID3/metadata parser → database → API response → Frontend render — is metadata sanitized?
3. **WebSocket messages**: Frontend → WebSocket → audio_stream_controller → processing_engine → chunked_processor → audio engine — are messages validated?
4. **Library scan paths**: User adds folder → scanner.py → filesystem walk → database insert — can symlinks or special paths escape?

## Deduplication (MANDATORY)

Before reporting ANY finding:

1. Run: `gh issue list --limit 200 --json number,title,state,labels`
2. Search for keywords from your finding in existing issue titles
3. If a matching issue exists:
   - **OPEN**: Note as "Existing: #NNN" and skip
   - **CLOSED**: Verify fix is in place. If regressed, report as "Regression of #NNN"
4. If no match: Report as NEW

## Phase 1: Audit

Write your report to: **`docs/audits/AUDIT_SECURITY_<TODAY>.md`** (use today's date, format YYYY-MM-DD).

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

## Phase 2: Publish to GitHub

After completing the audit report, for every finding with **Status: NEW** or **Regression**:

1. **Create a GitHub issue** with:
   - **Title**: `[<TODAY>] <SEVERITY> - <Short Title>`
   - **Labels**: severity label (`critical`, `high`, `medium`, `low`) + `security` + `bug`
   - **Body**: Summary, Evidence/Code Paths, Exploit Scenario, Impact, Related Issues, Proposed Fix, Acceptance Criteria, Test Plan

2. **Cross-reference**: For each new issue that relates to an existing issue:
   ```
   gh issue comment <EXISTING_ISSUE> --body "Related: #<NEW_ISSUE> — <brief description>"
   ```

3. **Print a summary table** at the end with finding, severity, action taken, and issue number.
