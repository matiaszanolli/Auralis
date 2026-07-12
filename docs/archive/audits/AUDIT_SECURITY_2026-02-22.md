# Security Audit — OWASP Top 10 — 2026-02-22

**Scope**: Security posture of the Auralis music player (FastAPI backend, React frontend, audio engine) against OWASP Top 10 (2021).
**Auditor**: Claude Opus 4.6
**Prior audits**: AUDIT_BACKEND_2026-02-21 (9 findings), AUDIT_INTEGRATION_2026-02-22 (5 findings), plus 4 prior audit reports.
**Deduplication**: Verified against 60+ open GitHub issues, all prior audit findings, and existing security-labeled issues (#2206, #2079, #2078, #2094, #2126, #2419, #2422).

**Architectural context**: Auralis is an Electron desktop app — frontend + FastAPI backend + Rust DSP bundled together, always running on localhost:8765. No multi-user, no remote deployment. This context mitigates some findings that would be CRITICAL in a server-deployed application.

---

## Executive Summary

This audit found **5 NEW findings** (2 HIGH, 2 MEDIUM, 1 LOW) across OWASP categories A04, A05, and A10. The most impactful is **InternalServerError leaking raw exception messages** (including file paths, database errors, and FFmpeg output) to HTTP clients via 38+ router endpoints, and **missing browser security headers** on all responses.

Several prior security issues have been **fixed** since earlier audits:
- BE-01/#2559 (processing API path traversal) → FIXED: `validate_file_path()` now called
- BE-02/#2560 (upload validation) → FIXED: magic bytes + size limit + UUID filename
- BE-03/#2561 (download path traversal) → FIXED: validates output within tempdir
- BE-04/#2562 (DEFAULT_ALLOWED_DIRS too broad) → FIXED: restricted to ~/Music and ~/Documents

| Severity | New | Existing (Open) | Fixed |
|----------|-----|-----------------|-------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 2 | 2 (#2206, #2126) | 4 (#2559–2562) |
| MEDIUM | 2 | 2 (#2078, #2079) | 0 |
| LOW | 1 | 3 (#2094, #2419, #2422) | 0 |
| **Total** | **5** | **7** | **4** |

---

## NEW Findings

### SEC-01: InternalServerError leaks raw exception messages to HTTP clients
- **Severity**: HIGH
- **OWASP Category**: A05 — Security Misconfiguration
- **Location**: `auralis-web/backend/routers/errors.py:44-45`, plus 38+ call sites across 10 routers
- **Status**: NEW → #2573
- **Description**: The centralized `InternalServerError` class includes `str(error)` in the HTTP 500 response `detail` field. This is distinct from #2126 (no global exception handler) — this IS an error handler, and it deliberately exposes raw exception messages to clients. Additionally, 38+ endpoints across 10 routers directly use `str(e)` in `HTTPException(status_code=500, detail=...)` responses, bypassing even this centralized handler.
- **Evidence**:

  Centralized handler (`errors.py:43-50`):
  ```python
  class InternalServerError(HTTPException):
      def __init__(self, operation: str, error: Exception | None = None) -> None:
          if error:
              detail = f"Failed to {operation}: {str(error)}"  # ← LEAKS exception details
              logger.error(f"Internal error during {operation}: {error}", exc_info=True)
  ```

  Direct leakage across routers (38+ instances, sampled):
  ```python
  # similarity.py:191
  raise HTTPException(status_code=500, detail=f"Error finding similar tracks: {str(e)}")
  # enhancement.py:425
  raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
  # cache_streamlined.py:71
  raise HTTPException(status_code=500, detail=str(e))
  # processing_api.py:163
  raise HTTPException(status_code=500, detail=str(e))
  # webm_streaming.py:365
  detail=f"Chunk processing failed: {str(e)}"
  ```

- **Exploit Scenario**: An attacker sends malformed requests to trigger exceptions. The 500 responses reveal internal file paths (`/home/user/.auralis/library.db`), database schema details (`no such column: ...`), FFmpeg error output (revealing installed version and codecs), and Python traceback details.
- **Impact**: Information disclosure — internal architecture, file paths, library versions, and database schema exposed to any HTTP client.
- **Suggested Fix**: Replace `str(error)` in all HTTPException details with generic messages. Keep detailed logging server-side. Example: `detail = f"Failed to {operation}"` (omit `str(error)`).

---

### SEC-02: No browser security headers on HTTP responses
- **Severity**: HIGH
- **OWASP Category**: A05 — Security Misconfiguration
- **Location**: `auralis-web/backend/config/middleware.py` (entire file — headers absent)
- **Status**: NEW → #2574
- **Description**: The middleware configures only CORS and no-cache headers. It does not set any browser security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`, or `Permissions-Policy`. Even for a localhost Electron app, the frontend runs in a Chromium browser context that respects these headers for defense-in-depth.
- **Evidence**:

  Current middleware (`middleware.py:46-83`):
  ```python
  def setup_middleware(app: FastAPI) -> None:
      app.add_middleware(NoCacheMiddleware)  # Only sets Cache-Control on .html/.js
      app.add_middleware(
          CORSMiddleware,
          allow_origins=[...],
          allow_credentials=True,
          allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
          allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "X-Session-Id"],
      )
      # ← No SecurityHeadersMiddleware
  ```

  Missing headers:
  - `X-Content-Type-Options: nosniff` — prevents MIME sniffing attacks
  - `X-Frame-Options: DENY` — prevents clickjacking via iframe embedding
  - `Content-Security-Policy` — restricts script/style sources
  - `Referrer-Policy: strict-origin-when-cross-origin` — prevents referrer leakage
  - `Permissions-Policy` — restricts browser feature access

- **Exploit Scenario**: A malicious page opened in a browser tab alongside the Electron app could attempt to iframe the Auralis backend at localhost:8765 (clickjacking). MIME sniffing could misinterpret audio responses as executable content.
- **Impact**: Browser-level security mitigations are disabled. Clickjacking, MIME confusion, and script injection attacks are not mitigated by server headers.
- **Suggested Fix**: Add a `SecurityHeadersMiddleware` that sets all standard security headers on every response. Example:
  ```python
  class SecurityHeadersMiddleware(BaseHTTPMiddleware):
      async def dispatch(self, request, call_next):
          response = await call_next(request)
          response.headers["X-Content-Type-Options"] = "nosniff"
          response.headers["X-Frame-Options"] = "DENY"
          response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
          return response
  ```

---

### SEC-03: No rate limiting on REST endpoints — file upload, scan, and processing unprotected
- **Severity**: MEDIUM
- **OWASP Category**: A05 — Security Misconfiguration
- **Location**: All routers in `auralis-web/backend/routers/` (18 routers, 0 with rate limiting); contrast with `auralis-web/backend/websocket/websocket_security.py` (WebSocket IS rate-limited)
- **Status**: NEW → #2575
- **Description**: WebSocket messages are rate-limited to 10/second via `WebSocketRateLimiter` (fixes #2156), but ALL REST endpoints are completely unprotected. This includes expensive operations like file upload (`POST /api/files/upload`), library scanning (`POST /api/library/scan`), audio processing (`POST /api/processing/process`), and similarity computation (`POST /api/similarity/find`). Even on localhost, a runaway frontend bug or browser extension could flood these endpoints.
- **Evidence**:

  WebSocket — protected (`system.py:28`):
  ```python
  _rate_limiter = WebSocketRateLimiter(max_messages_per_second=10)
  ```

  REST — unprotected (no rate limiting in any router):
  ```python
  # files.py - No rate limiting on upload
  @router.post("/api/files/upload")
  async def upload_files(files: list[UploadFile] = File(...)) -> dict[str, Any]:
      # No rate limit check

  # processing_api.py - No rate limiting on processing
  @router.post("/process", response_model=ProcessResponse)
  async def process_audio(request: ProcessRequest) -> ProcessResponse:
      # No rate limit check

  # library.py - No rate limiting on scan
  @router.post("/api/library/scan")
  async def scan_library(request: LibraryScanRequest) -> dict[str, Any]:
      # No rate limit check
  ```

- **Exploit Scenario**: A compromised browser extension or malicious script on a page with CORS access sends hundreds of concurrent `POST /api/processing/process` requests. Each spawns CPU-intensive audio processing, exhausting system resources.
- **Impact**: Denial of service via resource exhaustion (CPU, memory, disk I/O). File upload endpoint allows rapid disk consumption up to 500MB per request with no per-client throttling.
- **Suggested Fix**: Add rate limiting middleware (e.g., `slowapi`) for expensive endpoints. At minimum, rate-limit `POST /api/files/upload` (1 req/s), `POST /api/library/scan` (1 req/10s), and `POST /api/processing/process` (2 req/s).

---

### SEC-04: MusicBrainz artwork download follows HTTP redirects without domain validation and has no response size limit
- **Severity**: MEDIUM
- **OWASP Category**: A10 — Server-Side Request Forgery (SSRF) / A04 — Insecure Design
- **Location**: `auralis-web/backend/services/artwork_downloader.py:166-174`
- **Status**: NEW → #2576
- **Description**: The artwork downloader correctly validates iTunes artwork URLs against `_TRUSTED_ARTWORK_DOMAINS` (fixes #2416). However, MusicBrainz Cover Art Archive downloads at line 166-174 are NOT validated: the code fetches from `coverartarchive.org` which redirects (HTTP 307) to Internet Archive (`archive.org`) or potentially other hosts. `aiohttp.ClientSession` follows redirects by default, and the redirect target is never validated against a domain whitelist. Additionally, neither source has a response size limit — `await resp.read()` at lines 173 and 235 reads the entire response into memory with no cap.
- **Evidence**:

  iTunes — validated (`artwork_downloader.py:225-228`):
  ```python
  # Validate artwork URL against trusted domains (fixes #2416: SSRF mitigation)
  if not _validate_artwork_url(artwork_url):
      logger.warning(f"Rejecting untrusted artwork URL: {artwork_url!r}")
      return None
  ```

  MusicBrainz — NOT validated (`artwork_downloader.py:166-174`):
  ```python
  coverart_url = f"{self.coverart_api}/release/{release_id}/front"
  async with session.get(coverart_url, headers=headers) as resp:  # ← Follows redirects to ANY domain
      if resp.status != 200:
          return None
      artwork_data = await resp.read()  # ← No size limit
      return self._save_artwork(artwork_data, album_id, "jpg")
  ```

  No size limit on either path (`lines 173, 235`):
  ```python
  artwork_data = await resp.read()  # Could be gigabytes
  ```

- **Exploit Scenario**: (1) An attacker manipulates MusicBrainz data to set a release's cover art to point to an attacker-controlled redirect. The backend follows the redirect, making a request that reveals the user's IP and User-Agent to the attacker. (2) A malicious server returns a multi-GB response, exhausting disk space when saved via `_save_artwork()`.
- **Impact**: SSRF via open redirect — the backend can be made to contact arbitrary servers. Disk exhaustion via unbounded download size.
- **Suggested Fix**: (1) Validate redirect targets: use `aiohttp.ClientSession(trust_env=False)` and check `resp.url.host` against a whitelist after the request completes (or set `max_redirects=0` and handle redirects manually). (2) Add a size limit: `artwork_data = await resp.content.read(5 * 1024 * 1024)` (5MB cap) and reject if content-length exceeds the limit.

---

### SEC-05: SQLite database created with default file permissions — world-readable on multi-user systems
- **Severity**: LOW
- **OWASP Category**: A02 — Cryptographic Failures / A05 — Security Misconfiguration
- **Location**: `auralis/library/manager.py:114-121`
- **Status**: NEW → #2577
- **Description**: The SQLite database at `~/.auralis/library.db` is created by SQLAlchemy's `create_engine()` with the default umask, typically resulting in `0644` permissions on Linux. No explicit `os.chmod(db_path, 0o600)` is set. The database contains library metadata, play counts, user preferences, playlists, and fingerprint data. On a multi-user system, other users could read this data.
- **Evidence**:

  Database creation (`manager.py:114-121`):
  ```python
  self.engine = create_engine(
      f"sqlite:///{database_path}",
      echo=False,
      connect_args=connect_args,
      pool_pre_ping=True,
      pool_size=5,
      max_overflow=5,
  )
  # ← No os.chmod(database_path, 0o600) after creation
  ```

  Database directory creation (`manager.py:85-87`, approximate):
  ```python
  db_dir = Path.home() / ".auralis"
  db_dir.mkdir(parents=True, exist_ok=True)
  # ← No os.chmod(db_dir, 0o700) after creation
  ```

- **Exploit Scenario**: On a shared workstation, another user runs `sqlite3 /home/victim/.auralis/library.db "SELECT filepath, title FROM tracks"` to enumerate the victim's music library, playlists, and listening habits.
- **Impact**: Information disclosure of music library metadata, play history, and user preferences to other local users. LOW severity because Auralis is a single-user desktop app and this requires local access.
- **Suggested Fix**: After database creation, set restrictive permissions: `os.chmod(database_path, 0o600)` and `os.chmod(db_dir, 0o700)`.

---

## OWASP Category Coverage

### A01: Broken Access Control
- **No authentication on any endpoint** — Existing: #2206 (HIGH). All 18 REST routers and the WebSocket endpoint lack user authentication. Mitigated by localhost-only binding (`host="127.0.0.1"`, `main.py:203`).
- **WebSocket origin checking only** — Existing: #2206. `ConnectionManager.connect()` validates Origin header against `ALLOWED_WS_ORIGINS` but allows empty origins (for non-browser clients). No session/token auth.
- **Scanner symlink following** — The scanner follows symlinks (`follow_symlinks=True` at `file_discovery.py:109,130`) but has cycle detection via inode tracking and audio extension filtering. On multi-user systems, symlinks inside ~/Music → another user's directory would be indexed. LOW risk given desktop-app context.
- **Path security** — FIXED: `validate_scan_path()` and `validate_file_path()` restrict access to ~/Music and ~/Documents. Processing API now validates paths (#2559 fixed). Artwork path validated against `~/.auralis/artwork/`.

### A02: Cryptographic Failures
- **Secret key in .env** — Existing: #2079. Hardcoded `MATCHERING_SECRET_KEY` in `.env` file. File is in `.gitignore` (line 125) but exists in working directory. These are legacy Matchering settings and appear unused by the current Auralis backend.
- **Database permissions** — NEW: SEC-05 (LOW). See above.
- **WebSocket traffic** — Uses WS (not WSS) on localhost. Acceptable for same-machine communication; would need WSS if ever exposed to network.

### A03: Injection
- **SQL injection** — Existing: #2078 (mitigated). Fingerprint repository uses f-string column interpolation BUT validates against a frozenset whitelist (`_FINGERPRINT_WRITABLE_COLS`) before use. Values are parameterized. All other repositories use SQLAlchemy ORM.
- **Command injection (FFmpeg)** — SAFE. All FFmpeg invocations use list-based `subprocess.run()` without `shell=True`. File paths passed as separate arguments. Verified in `ffmpeg_loader.py:133-149`, `webm_encoder.py:161-184`, `unified_loader.py:187-200`.
- **Path traversal** — FIXED. All path-accepting endpoints now validate via `validate_file_path()` or `validate_scan_path()`. Processing API (#2559), upload (#2560), download (#2561), scan paths (Pydantic validator in `LibraryScanRequest`).
- **XSS via metadata** — SAFE. Frontend renders metadata via React text interpolation (not `dangerouslySetInnerHTML`). Error handler in `index.tsx` properly HTML-escapes messages.

### A04: Insecure Design
- **Artwork download no size limit** — NEW: SEC-04 (MEDIUM). See above.
- **Chunk cache unbounded** — Existing: #2084 (MEDIUM). `SimpleChunkCache` has a max of 50 entries but no memory-based bound.
- **Migration scripts unvalidated** — Existing: #2083 (MEDIUM). Migrations executed without integrity check.

### A05: Security Misconfiguration
- **CORS** — SAFE. Explicit localhost origins with `allow_credentials=True`. Not wildcard. Fixes #2224.
- **Swagger UI** — SAFE. Disabled in production (`docs_url=None` when not `--dev`). Fixes #2418.
- **Error detail leakage** — NEW: SEC-01 (HIGH). See above.
- **Security headers** — NEW: SEC-02 (HIGH). See above.
- **Rate limiting** — NEW: SEC-03 (MEDIUM). See above.
- **HTML path disclosure** — Existing: #2094 (LOW). Fallback root page at `main.py:184` interpolates `frontend_path` into HTML response.

### A06: Vulnerable and Outdated Components
- **Python dependencies** — Mostly well-pinned in root `requirements.txt` (`fastapi==0.122.0`, `uvicorn==0.38.0`, `pydantic==2.12.4`). Backend-specific `requirements.txt` uses floating constraints (`fastapi>=0.104.0`) but is likely not the primary install target.
- **Frontend dependencies** — Would need `npm audit` to check. No floating version patterns observed in `package.json`.
- **Rust dependencies** — `vendor/auralis-dsp/Cargo.toml` pins specific versions.

### A07: Identification and Authentication Failures
- **No authentication** — Existing: #2206 (HIGH). No auth on any endpoint. Mitigated by localhost-only binding.
- **No rate limiting on REST** — NEW: SEC-03 (MEDIUM). WebSocket is rate-limited, REST is not.

### A08: Software and Data Integrity Failures
- **Fingerprint integrity** — Existing: #2422 (LOW). Fingerprint data stored without integrity hash.
- **SRI** — Existing: #2419 (LOW). No Subresource Integrity on Google Fonts CDN links.
- **Migration integrity** — Existing: #2083 (MEDIUM). Migration scripts executed without validation.

### A09: Security Logging and Monitoring Failures
- **No global exception handler** — Existing: #2126 (MEDIUM). Unhandled exceptions return raw 500s.
- **Verbose path logging** — `main.py:33,41,46,153,161,180` logs filesystem paths at INFO level. Acceptable for desktop app; would need redaction for server deployment.
- **WebSocket connect/disconnect logged** — `globals.py:74,87` logs client IPs on connect/disconnect. Good practice.

### A10: Server-Side Request Forgery
- **Artwork SSRF** — Partially fixed via #2416 (iTunes domain whitelist). NEW: SEC-04 (MEDIUM) — MusicBrainz redirects not validated.
- **No other SSRF vectors found** — No endpoints accept arbitrary URLs for server-side fetch.

---

## Fixed Since Prior Audits

| Prior ID | Title | Status |
|----------|-------|--------|
| BE-01/#2559 | Processing API accepts arbitrary file paths | **FIXED** — `validate_file_path()` now called at `processing_api.py:123` |
| BE-02/#2560 | upload_and_process lacks file validation | **FIXED** — Magic bytes, size limit, UUID filename, exclusive-create at `processing_api.py:189-211` |
| BE-03/#2561 | download_result serves unvalidated output_path | **FIXED** — Validates output within tempdir at `processing_api.py:282-287` |
| BE-04/#2562 | DEFAULT_ALLOWED_DIRS includes Path.home() | **FIXED** — Restricted to `~/Music` and `~/Documents` at `path_security.py:22-25` |

---

## Confirmed Still Open (Prior Security Findings)

| Prior ID | Severity | Title | Status |
|----------|----------|-------|--------|
| #2206 | HIGH | WebSocket endpoint has no authentication | Open |
| #2126 | MEDIUM | No global exception handler for unhandled errors | Open |
| #2079 | MEDIUM | Secret key committed to git in .env | Open |
| #2078 | MEDIUM | SQL injection risk in fingerprint column names (mitigated) | Open |
| #2094 | LOW | Unsafe HTML interpolation in fallback page | Open |
| #2419 | LOW | No Subresource Integrity on Google Fonts CDN | Open |
| #2422 | LOW | Fingerprint data stored without integrity hash | Open |

---

## Methodology

1. Read all security-critical files: middleware, path security, globals, routers, scanner, loaders, artwork downloader, WebSocket security.
2. Launched 3 parallel explore agents for OWASP A01-A03 (injection), A01/A07 (auth/access control), and A02/A05/A06/A09 (secrets/config/logging).
3. Verified all agent findings against actual source code via direct file reads.
4. Cross-referenced against 60+ open GitHub issues and 13 existing security-labeled issues.
5. Verified 4 prior backend audit findings as FIXED in current code.
6. Confirmed 7 prior security findings as still open.
