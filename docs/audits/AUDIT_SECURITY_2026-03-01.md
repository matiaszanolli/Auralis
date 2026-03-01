# Security Audit — OWASP Top 10 — 2026-03-01

**Scope**: Full OWASP Top 10 (2021) security audit of the Auralis music player (FastAPI backend, React frontend, Rust DSP, audio engine).
**Auditor**: Claude Sonnet 4.6
**Prior audits**: AUDIT_SECURITY_2026-02-22 (5 findings: SEC-01 through SEC-05), AUDIT_SECURITY_2026-02-17 (10 findings).
**Deduplication**: All findings cross-referenced against 13 existing security-labeled issues from prior audits plus all prior audit reports.

**Architectural context**: Auralis is an Electron desktop app — frontend + FastAPI backend + Rust DSP bundled together, always running on localhost:8765. No multi-user, no remote deployment. This context mitigates findings that would be CRITICAL in server-deployed applications, but does NOT mitigate path traversal, SSRF, or command injection since malicious websites can reach localhost services via CORS or pre-flight bypass.

---

## Executive Summary

This audit found **4 NEW findings** (1 HIGH, 2 MEDIUM, 1 LOW) and verified the status of all prior open findings.

**Significant fixes since 2026-02-22 audit**:
- SEC-02/#2574 (missing browser security headers) — **FIXED**: `SecurityHeadersMiddleware` now added in `middleware.py`
- SEC-03/#2575 (no REST rate limiting) — **FIXED**: `RateLimitMiddleware` added covering upload, processing, scan, similarity
- SEC-04/#2576 (MusicBrainz SSRF redirect + no size limit) — **FIXED**: redirect URL validated against `_TRUSTED_ARTWORK_DOMAINS`, 5MB cap enforced

| Severity | New | Existing (Open) | Fixed since last audit |
|----------|-----|-----------------|------------------------|
| CRITICAL | 0   | 0               | 0                      |
| HIGH     | 1   | 1 (#2206)       | 3 (#2574, #2575, #2576) |
| MEDIUM   | 2   | 2 (#2573, #2126)| 0                      |
| LOW      | 1   | 5 (#2206-adjacent, #2079, #2083, #2419, #2422) | 0 |
| **Total**| **4**| **8**          | **3**                  |

---

## NEW Findings

### SEC-01: Missing Content-Security-Policy Header Allows Script/Style Injection
- **Severity**: HIGH
- **OWASP Category**: A05 — Security Misconfiguration
- **Location**: `auralis-web/backend/config/middleware.py:47-63`
- **Status**: NEW
- **Description**: The `SecurityHeadersMiddleware` added since the prior audit sets `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and the deprecated `X-XSS-Protection`. However, it does NOT set `Content-Security-Policy` (CSP). CSP is the primary browser defense against cross-site scripting (XSS) and related injection attacks. Without CSP, the Electron-hosted frontend has no server-enforced restriction on which scripts, styles, or resources can execute. Additionally, `X-XSS-Protection: 1; mode=block` was deprecated by all major browsers (Chromium 78+, Firefox 83+) and actively removed — setting it provides no protection and can cause compatibility issues.

- **Evidence**:

  `middleware.py:55-62` — CSP absent, deprecated header set:
  ```python
  class SecurityHeadersMiddleware(BaseHTTPMiddleware):
      async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
          response = await call_next(request)
          response.headers["X-Content-Type-Options"] = "nosniff"
          response.headers["X-Frame-Options"] = "DENY"
          response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
          response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
          response.headers["X-XSS-Protection"] = "1; mode=block"   # ← deprecated, no effect
          # Missing: Content-Security-Policy
  ```

  Additionally, `frontend/index.html` loads external Google Fonts without SRI (existing #2419):
  ```html
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Asap..." />
  ```
  Without CSP, injected CSS from a compromised CDN has no browser-level barrier.

- **Exploit Scenario**: A malicious audio metadata tag (e.g., an ID3 `COMM` frame injected with `<script>` tags) that reaches the frontend via a metadata response could execute JavaScript if the component renders it with `dangerouslySetInnerHTML`. Without CSP, there is no fallback restriction. Even in Electron's sandboxed Chromium context, inline scripts and eval() are permitted without CSP.
- **Impact**: No browser-level defense against script injection. `X-XSS-Protection` header provides false sense of security while doing nothing on modern browsers.
- **Suggested Fix**: Add a strict CSP appropriate for the Electron context:
  ```python
  response.headers["Content-Security-Policy"] = (
      "default-src 'self'; "
      "script-src 'self'; "
      "style-src 'self' https://fonts.googleapis.com; "
      "font-src 'self' https://fonts.gstatic.com; "
      "img-src 'self' data: blob:; "
      "connect-src 'self' ws://localhost:8765 http://localhost:8765; "
      "media-src 'self' blob:; "
  )
  ```
  And remove the deprecated `X-XSS-Protection` header.

---

### SEC-02: Filesystem Path Enumeration via Error Messages in Processing API
- **Severity**: MEDIUM
- **OWASP Category**: A03 — Injection / A05 — Security Misconfiguration
- **Location**: `auralis-web/backend/routers/processing_api.py:122-125`, `auralis-web/backend/security/path_security.py:200-204`
- **Status**: NEW
- **Description**: `POST /api/processing/process` accepts a raw `input_path` string from the client (not a database-backed track ID). The path is validated by `validate_file_path()` which checks whether the resolved path is within `~/Music` or `~/Documents`. However, `validate_file_path()` raises different `PathValidationError` messages depending on the failure mode:
  - If the path is outside allowed dirs: `"Path '/home/user/Music/secret.mp3' is outside allowed directories. Allowed directories: /home/user/Music, /home/user/Documents"`
  - If the path is inside allowed dirs but doesn't exist: `"File does not exist: /home/user/Music/nonexistent.mp3"`

  These distinct error messages are propagated verbatim to the HTTP 400 response via `detail=f"Invalid input path: {e}"`. A client can therefore determine whether a given file path exists anywhere within `~/Music` or `~/Documents` by sending crafted requests and interpreting the error response — a filesystem enumeration attack.

- **Evidence**:

  `processing_api.py:122-125`:
  ```python
  try:
      validated_input = validate_file_path(request.input_path)
  except PathValidationError as e:
      raise HTTPException(status_code=400, detail=f"Invalid input path: {e}")  # ← str(e) leaks path info
  ```

  `path_security.py:196-204`:
  ```python
  if not is_allowed:
      raise PathValidationError(
          f"Path '{resolved_path}' is outside allowed directories. "  # ← distinct from...
          f"Allowed directories: {allowed_dirs_str}"
      )
  if not resolved_path.exists():
      raise PathValidationError(f"File does not exist: {resolved_path}")  # ← ...this error
  ```

  Client test:
  - `POST /api/processing/process {"input_path": "/home/user/Music/private/journal.txt"}` → `400 "File does not exist: ..."` (file doesn't exist — path IS in allowed dir)
  - `POST /api/processing/process {"input_path": "/home/user/.ssh/id_rsa"}` → `400 "Path ... is outside allowed directories"` (path rejected outright)
  - `POST /api/processing/process {"input_path": "/home/user/Music/private/photo.jpg"}` → `400 "File does not exist: ..."` (non-audio extension would still reach the exists check after path validation)

- **Exploit Scenario**: A malicious web page (using CORS — `localhost:3000` is allowed) sends `POST /api/processing/process` requests with crafted paths. By systematically probing paths and distinguishing "outside allowed" from "does not exist" responses, the attacker can enumerate the existence of files within the user's `~/Music` and `~/Documents` directories, building a map of the filesystem without reading file content.
- **Impact**: Filesystem enumeration within `~/Music` and `~/Documents`. Reveals directory structure and file names, potentially exposing sensitive documents stored in `~/Documents`.
- **Suggested Fix**: Collapse all `PathValidationError` messages into a single generic response that does not distinguish between "outside allowed" and "file not found":
  ```python
  except PathValidationError:
      raise HTTPException(status_code=400, detail="Invalid or inaccessible input path")
  ```
  Apply the same treatment to `reference_path` validation.

---

### SEC-03: RateLimitMiddleware _windows Dict Grows Without Bound — Memory Exhaustion DoS
- **Severity**: MEDIUM
- **OWASP Category**: A04 — Insecure Design
- **Location**: `auralis-web/backend/config/middleware.py:83-119`
- **Status**: NEW
- **Description**: `RateLimitMiddleware` maintains a `_windows` dict keyed by `{client_ip}:{path}`. Timestamps are pruned from each list when that specific key is accessed again. However, the dict itself is never evicted — entries accumulate for every unique `(client_ip, path)` combination that matches a rate-limited endpoint. In a normal single-user Electron app this is negligible. However, if the CORS origin whitelist ever allows a client that sends many rapid requests with varying paths, or if `client_ip` is spoofed (via `X-Forwarded-For` if a proxy is ever added), the dict can grow without bound. Additionally, `request.client.host` is used directly which trusts the TCP connection source — no proxy awareness.

- **Evidence**:

  `middleware.py:83-119`:
  ```python
  class RateLimitMiddleware(BaseHTTPMiddleware):
      def __init__(self, app: Any) -> None:
          super().__init__(app)
          self._windows: dict[str, list[float]] = {}  # ← never evicted, only pruned per-key

      async def dispatch(self, request: Request, call_next: ...) -> Response:
          ...
          client_ip = request.client.host if request.client else "unknown"
          key = f"{client_ip}:{path}"

          timestamps = self._windows.get(key, [])
          timestamps = [t for t in timestamps if now - t < window_sec]  # ← per-key pruning only

          timestamps.append(now)
          self._windows[key] = timestamps  # ← entry never removed, only pruned
  ```

  Over time with varied keys:
  - `_windows["127.0.0.1:/api/files/upload"] = []` (after window expires, entry stays with empty list)
  - Repeated new keys accumulate memory without GC

- **Exploit Scenario**: A runaway frontend bug rapidly cycles through different parameter-varied paths (e.g., query strings that affect routing, or a bug creating many unique request paths). Each creates a permanent entry in `_windows`. Over a long-running session, memory pressure grows unboundedly. In a production Electron app running 24/7, this could contribute to process memory bloat.
- **Impact**: Slow memory leak in the rate limiter. In extreme scenarios, contributes to process memory exhaustion. LOW practical risk in single-user desktop context.
- **Suggested Fix**: Add periodic eviction of stale entries. The simplest approach is to evict empty timestamp lists when the outer dict size exceeds a threshold:
  ```python
  # After pruning, evict empty entries
  if not timestamps:
      self._windows.pop(key, None)
  else:
      self._windows[key] = timestamps
  # Periodic full GC (every N requests)
  if len(self._windows) > 10_000:
      self._windows = {k: v for k, v in self._windows.items() if v}
  ```

---

### SEC-04: Rust Fingerprint Server Binary Accepts Arbitrary File Paths Without Auth or Path Validation
- **Severity**: LOW
- **OWASP Category**: A01 — Broken Access Control
- **Location**: `vendor/auralis-dsp/src/bin/fingerprint_server.rs:1-90`
- **Status**: NEW
- **Description**: The `fingerprint-server` Rust binary (compiled from `vendor/auralis-dsp/`) starts an HTTP server on `127.0.0.1:8766` with a `POST /fingerprint` endpoint that accepts `{"track_id": N, "filepath": "/arbitrary/path"}` in JSON. The only validation is `fs::metadata(&req.filepath).is_ok()` — a file existence check, not a path restriction. No CORS, no authentication, no allowed-directories check. If this binary is compiled and run (which is possible during development, and may be part of future production architecture), any browser tab can `fetch("http://127.0.0.1:8766/fingerprint", {method: "POST", body: JSON.stringify({track_id: 1, filepath: "/home/user/.ssh/id_rsa"})})` and trigger DSP processing on any readable file.

  The binary is NOT currently referenced in the FastAPI backend or Electron startup scripts, so it appears to be a development artifact. However, it IS compiled as part of `cargo build` in `vendor/auralis-dsp/` due to the `[[bin]]` directive in `Cargo.toml`.

- **Evidence**:

  `Cargo.toml`:
  ```toml
  [[bin]]
  name = "fingerprint-server"
  path = "src/bin/fingerprint_server.rs"
  ```

  `fingerprint_server.rs:36-50`:
  ```rust
  async fn fingerprint_handler(req: web::Json<FingerprintRequest>) -> impl Responder {
      // Only checks file existence — no path validation, no auth
      if !fs::metadata(&req.filepath).is_ok() {
          return HttpResponse::NotFound().json(serde_json::json!({
              "error": "File not found",
              "filepath": req.filepath  // ← also leaks the attempted path in response
          }));
      }
      // Calls DSP processing on the filepath
  ```

  Binding comment acknowledges the risk:
  ```rust
  // Bind to loopback only — this service has no authentication and accepts
  // arbitrary file paths in POST requests, so network-accessible binding
  // would be a significant security risk (fixes #2243).
  ```

- **Exploit Scenario**: Developer runs `cargo build && ./target/debug/fingerprint-server` during development. A malicious browser tab sends `POST http://127.0.0.1:8766/fingerprint` with `filepath: "/home/user/.gnupg/secring.gpg"`. The server attempts DSP processing on the file, potentially crashing, consuming CPU, or (in a parser vulnerability scenario) triggering unsafe Rust code on attacker-controlled data.
- **Impact**: Arbitrary file processing via unauthenticated HTTP endpoint if binary is running. Path enumeration via error responses. Future risk if binary is integrated into production deployment.
- **Suggested Fix**: (1) Add `path_security.rs` equivalent with allowed-directories validation before processing any filepath. (2) Add a `Authorization: Bearer <token>` header requirement using a shared secret. (3) Add an `Origin` header check identical to the FastAPI WebSocket check. (4) If the binary is not intended for production, document this clearly and exclude it from release builds using Cargo features.

---

## OWASP Category Coverage

### A01: Broken Access Control
- **No auth on REST or WebSocket** — Existing: #2206 (HIGH). All 18+ REST routers and WebSocket have no authentication. Mitigated by `host="127.0.0.1"` binding. WebSocket origin check added (fixes prior SEC-01).
- **WebSocket origin check** — FIXED (was SEC-01 in prior audit). `system.py:116-123` now checks that origin starts with `http://localhost`, `http://127.0.0.1`, or `file://`. Empty origins accepted for non-browser clients (acceptable).
- **Artwork path validation** — SAFE. `artwork.py:84-103` resolves path and calls `is_relative_to(allowed_dir)` where `allowed_dir = ~/.auralis/artwork`. Validated BEFORE file existence check.
- **Scanner symlink following** — LOW risk. `file_discovery.py:109,130` follows symlinks but uses inode tracking (`visited_inodes`) to prevent cycles and re-traversal. Audio extension filter prevents indexing non-audio files reached via symlinks. Scan path restricted to `~/Music` and `~/Documents` by `validate_scan_path()` in `LibraryScanRequest`.
- **Rust fingerprint server** — NEW: SEC-04 (LOW). See above.

### A02: Cryptographic Failures
- **Secret key in .env** — Existing: #2079. `.env` is in `.gitignore` (line 125). Appears to be legacy Matchering keys, not used by current Auralis backend.
- **SQLite database permissions** — Existing: SEC-05/#2577 from prior audit. Database created at `~/.auralis/library.db` with default umask permissions (likely 0644). No explicit `chmod(0o600)` applied. Still open.
- **WebSocket WS vs WSS** — Uses unencrypted WS on localhost. Acceptable for same-machine IPC; would require WSS if ever network-exposed.
- **MD5 for artwork deduplication** — `artwork_downloader.py:287`: `hashlib.md5(data).hexdigest()[:8]` used for unique filename generation. MD5 is broken for security purposes but safe for non-cryptographic file naming. No impact.

### A03: Injection
- **SQL injection** — SAFE. All repositories use SQLAlchemy ORM with parameterized queries. The `order_by` parameter in `/api/library/tracks` is validated against a `VALID_ORDER_COLUMNS` whitelist at `track_repository.py:505-506` before use.
- **Command injection (FFmpeg)** — SAFE. All FFmpeg invocations verified to use list-based `subprocess.run()` (not `shell=True`). File paths passed as separate list elements.
- **Path traversal in file serving** — SAFE. All file-serving endpoints (artwork, streaming) validate paths against allowed directories before serving. Metadata router validates via `validate_file_path()`.
- **Path enumeration via error messages** — NEW: SEC-02 (MEDIUM). See above.
- **XSS via metadata** — SAFE. React renders metadata via text interpolation, not `dangerouslySetInnerHTML`. Lyrics displayed as text. `main.py:191` uses `html_module.escape()` for the fallback root page path.

### A04: Insecure Design
- **RateLimitMiddleware memory leak** — NEW: SEC-03 (MEDIUM). See above.
- **Chunk cache unbounded (memory)** — Existing: #2084 (MEDIUM). `SimpleChunkCache` bounded to 50 entries by count but no memory-based limit. Still open.
- **Migration scripts unvalidated before execution** — Existing: #2083 (MEDIUM). Migration SQL validated against `_DANGEROUS_KEYWORDS` denylist (DROP TABLE, TRUNCATE, etc.) but no SHA-256 integrity check on migration files. Still open.
- **Enhancement preprocess: filepath from player state, not DB** — `enhancement.py:184`: `filepath=state.current_track.file_path` — uses `file_path` from player state, which was originally populated from DB. Not a direct injection risk.

### A05: Security Misconfiguration
- **CORS** — SAFE. Explicit localhost origins enumerated (not wildcard) with `allow_credentials=True`. Matches #2224 fix. Origin list: localhost:3000-3006, localhost:8765, 127.0.0.1:3000, 127.0.0.1:8765.
- **Swagger UI / ReDoc** — SAFE. `config/app.py:40-41`: `docs_url="/api/docs" if is_dev else None` — disabled in production.
- **Missing CSP** — NEW: SEC-01 (HIGH). See above.
- **Deprecated X-XSS-Protection** — Included in SEC-01.
- **Error detail leakage (str(e) in 500 responses)** — Existing: #2573 (HIGH). Still present across 30+ endpoints. The global `Exception` handler added in `config/app.py:70-76` now returns generic `"Internal server error"` for truly unhandled exceptions, but most routers still directly call `raise HTTPException(status_code=500, detail=f"... {e}")` with raw exception text. Examples: `cache_streamlined.py:71,105,127,162`, `artwork.py:144,195`, `metadata.py:138,183,277,372`, `enhancement.py:212,272,339`.
- **HTML path disclosure in fallback root** — Existing: #2094 (LOW). `main.py:191`: `html_module.escape(str(frontend_path))` — now properly HTML-escaped. Risk is reduced to path disclosure in HTML, not XSS.
- **Processing API logs unvalidated path** — `processing_api.py:151`: `logger.info(f"Processing job {job_id} submitted for {request.input_path}")` — logs the client-supplied path before validation. Logs the raw input, not the validated path. Low impact but incorrect ordering.

### A06: Vulnerable and Outdated Components
- **Python dependencies** — Pinned to exact versions in `requirements.txt` (fixed since SEC-02 in 2026-02-17 audit): `fastapi==0.122.0`, `uvicorn==0.38.0`, `pydantic==2.12.4`, `numpy==2.3.5`, `mutagen==1.47.0`. All major packages now have exact pins. No known CVEs for these pinned versions at audit time.
- **Frontend dependencies** — `package.json` uses floating `^` constraints (common for frontend). Specific versions at install time would be in `package-lock.json`. No obviously outdated packages. `axios ^1.5.0` and `react-router-dom ^6.15.0` are recent stable versions.
- **Rust crates** — `Cargo.toml` uses floating version constraints (e.g., `pyo3 = { version = "0.21" }`). `actix-web = "4"` and `tonic = "0.12"` are dependency-major versions. No pinned exact versions. Cargo.lock is in `.gitignore` (`vendor/**/Cargo.lock`) — this means reproducible builds are not guaranteed for the Rust DSP module.
- **Cargo.lock excluded from version control** — `.gitignore:179`: `vendor/**/Cargo.lock`. Without Cargo.lock, different build environments may compile different minor/patch versions of Rust dependencies, defeating reproducibility.

### A07: Identification and Authentication Failures
- **No authentication** — Existing: #2206 (HIGH). No auth on any endpoint. Mitigated by localhost binding.
- **WebSocket auth** — No token/session auth on WebSocket, but origin check prevents cross-origin connections. Acceptable for local Electron app.
- **Rate limiting** — FIXED (was SEC-03/#2575). `RateLimitMiddleware` now covers upload (5/60s), processing (10/60s), scan (2/60s), similarity (20/60s).

### A08: Software and Data Integrity Failures
- **DB migration validation** — Existing: #2083 (MEDIUM). `apply_migration()` validates SQL against `_DANGEROUS_KEYWORDS` denylist but no SHA-256 integrity check on migration script files.
- **SRI on Google Fonts** — Existing: #2419 (LOW). Google Fonts loaded without `integrity` attribute.
- **Fingerprint integrity** — Existing: #2422 (LOW). Fingerprint data stored without checksum.
- **Cargo.lock excluded** — Related to A06. Build artifacts may differ across environments.

### A09: Security Logging and Monitoring Failures
- **Unhandled exception handler** — FIXED (was #2126). `config/app.py:70-76` now logs unhandled exceptions at ERROR level and returns generic 500.
- **Error detail leakage** — Existing: #2573. Still open — 30+ endpoints return raw `str(e)` in HTTP responses.
- **WebSocket audit logging** — Existing: #2206-adjacent. Connections logged with `id(websocket)` (memory address) but not with client IP:port for correlation. The rate limiter uses `request.client.host` but WebSocket connect/disconnect logs use `id(websocket)`.
- **Processing API logs unvalidated input** — `processing_api.py:151` logs `request.input_path` BEFORE validation, meaning invalid/malicious paths appear in logs verbatim. LOW risk but incorrect log hygiene.

### A10: Server-Side Request Forgery
- **Artwork download — MusicBrainz SSRF** — FIXED (was SEC-04/#2576). `artwork_downloader.py:184-196` now validates redirect URL against `_TRUSTED_ARTWORK_DOMAINS` using `_validate_artwork_url(str(resp.url))` after MusicBrainz redirect, with 5MB cap.
- **Artwork download — iTunes SSRF** — FIXED (was SEC-04/#2416). `artwork_downloader.py:249-251` validates `artwork_url` against `_TRUSTED_ARTWORK_DOMAINS` before fetching.
- **No other SSRF vectors** — No endpoints accept user-supplied URLs for server-side fetch beyond artwork download.

---

## Prior Findings Status Summary

| Issue | Severity | Title | Status in This Audit |
|-------|----------|-------|----------------------|
| #2573 | HIGH | Error detail leakage (str(e) in HTTP responses) | Still open — 30+ instances |
| #2206 | HIGH | No authentication on any endpoint | Still open — mitigated by localhost |
| #2574 | HIGH | Missing browser security headers | **FIXED** — SecurityHeadersMiddleware added |
| #2575 | MEDIUM | No rate limiting on REST endpoints | **FIXED** — RateLimitMiddleware added |
| #2576 | MEDIUM | MusicBrainz SSRF + no size limit | **FIXED** — domain validation + 5MB cap |
| #2126 | MEDIUM | No global exception handler | **FIXED** — `config/app.py` global handler |
| #2083 | MEDIUM | Migration scripts no integrity check | Still open |
| #2079 | MEDIUM | Secret key in .env | Still open (legacy, appears unused) |
| #2577 | LOW | SQLite database world-readable permissions | Still open |
| #2419 | LOW | No SRI on Google Fonts CDN | Still open |
| #2422 | LOW | Fingerprint stored without integrity hash | Still open |
| #2094 | LOW | HTML path disclosure in fallback root | Partially mitigated — `html.escape()` added |

---

## Prioritized Fix Order

1. **SEC-01** (HIGH): Add `Content-Security-Policy` header and remove deprecated `X-XSS-Protection` — `middleware.py`
2. **#2573** (HIGH, existing): Remove `str(e)` from all 500 response `detail` fields — 30+ router endpoints
3. **SEC-02** (MEDIUM): Collapse `PathValidationError` messages to prevent filesystem enumeration — `processing_api.py` + `path_security.py`
4. **SEC-03** (MEDIUM): Fix `RateLimitMiddleware._windows` unbounded growth — `middleware.py`
5. **SEC-04** (LOW): Add path validation and auth to Rust fingerprint server binary — `vendor/auralis-dsp/src/bin/fingerprint_server.rs`

---

## Methodology

1. Read all key security files: `main.py`, all 18 router files, `audio_stream_controller.py`, `chunked_processor.py`, `processing_engine.py`, `unified_loader.py`, scanner files, `migration_manager.py`, `schemas.py`, all config files, all backend services, `requirements.txt`, `package.json`, `Cargo.toml`, `.gitignore`, `path_security.py`, `websocket_security.py`.
2. Reviewed prior audit reports (2026-02-17 and 2026-02-22) to identify fixed and still-open findings.
3. Performed OWASP A01–A10 analysis for each category with direct code tracing.
4. Confirmed all SEC-01 through SEC-05 findings from prior audit against current code.
5. Identified 4 new findings, confirmed 3 prior findings fixed, and confirmed 8 prior findings still open.
