# Security Audit (OWASP Top 10) — 2026-02-17

## Executive Summary

**10 new findings** across 6 OWASP categories. No findings regressed existing security fixes.

| Severity | Count |
|----------|-------|
| HIGH | 1 |
| MEDIUM | 4 |
| LOW | 5 |

**Key themes:**
1. **Cross-origin WebSocket hijacking** — the WebSocket endpoint accepts connections from any origin, allowing a malicious webpage visited in the same browser to control the player without consent.
2. **Unpinned dependencies** — `librosa` and multiple other packages have no version pin, creating supply chain exposure.
3. **File upload content validation gap** — extension-only checks; a crafted or malformed audio file could attack the parser (soundfile/libav).
4. **SSRF via iTunes artwork URL** — the artwork service fetches a URL sourced from the iTunes API JSON response without validating the domain.

**Skipped (extend or match existing open issues):**
- Unknown message type CPU spin → extends #2185 (no concurrent stream limits)
- WebSocket `track_id` not validated → Existing: #2393
- Secrets in `.env` committed → Existing: #2079
- Migration scripts no integrity check → Existing: #2083
- `str(e)` in HTTP error responses → Existing: #2169
- Discogs API token in URL query string → Existing: #2244

---

## Findings

### SEC-01: Cross-Origin WebSocket Hijacking — No Origin Header Validation
- **Severity**: HIGH
- **OWASP Category**: A07 (Identification and Authentication Failures)
- **Location**: `auralis-web/backend/config/globals.py:38-39`, `auralis-web/backend/routers/system.py:107`
- **Status**: NEW
- **Description**: `ConnectionManager.connect()` calls `await websocket.accept()` without checking the `Origin` header of the WebSocket upgrade request. FastAPI's `CORSMiddleware` does not protect WebSocket upgrade requests — it only enforces CORS for standard HTTP requests. Any web page served from any domain that a user visits in the same browser can silently open a WebSocket to `ws://localhost:8765/ws`, issue `play_enhanced`, `play_normal`, and `seek` messages, and receive the PCM audio stream and `broadcast` metadata for all connected clients.
- **Evidence**:
  ```python
  # globals.py:31-39
  async def connect(self, websocket: WebSocket) -> None:
      await websocket.accept()   # No Origin check — accepts any origin
      self.active_connections.append(websocket)

  # system.py:107
  await manager.connect(websocket)  # Called unconditionally
  ```
  The CORS config in `middleware.py:64-75` whitelists specific `allow_origins`, but this is enforced only for HTTP requests, not WebSocket upgrades.
- **Exploit Scenario**:
  1. User opens Auralis in the browser (or Electron) — `ws://localhost:8765/ws` is live.
  2. User visits a malicious webpage at `https://evil.com`.
  3. Malicious page executes: `new WebSocket("ws://localhost:8765/ws")`.
  4. The handshake succeeds because no Origin check is performed.
  5. Attacker page sends `{"type": "play_enhanced", "data": {"track_id": 1}}`.
  6. Server starts streaming PCM audio to the attacker's WebSocket connection.
  7. The `broadcast()` in `ConnectionManager` sends track metadata to ALL active connections, including the attacker's.
- **Impact**: Any webpage the user visits can control the music player, receive PCM audio data, and capture track metadata — without any user interaction or consent. Privacy violation and player hijacking.
- **Suggested Fix**: Check the `Origin` header in `ConnectionManager.connect()` before calling `websocket.accept()`. Only accept connections from the CORS whitelist (`localhost:3000`, `localhost:8765`, etc.):
  ```python
  async def connect(self, websocket: WebSocket) -> None:
      origin = websocket.headers.get("origin", "")
      if not any(origin.startswith(allowed) for allowed in ALLOWED_ORIGINS):
          await websocket.close(code=4003, reason="Forbidden origin")
          return
      await websocket.accept()
  ```

---

### SEC-02: Unpinned Dependency Versions — Supply Chain Exposure
- **Severity**: MEDIUM
- **OWASP Category**: A06 (Vulnerable and Outdated Components)
- **Location**: `requirements.txt:1-27`
- **Status**: NEW
- **Description**: All Python dependencies use floating lower-bound versions (`>=`) with no upper bound. Critically, `librosa` and `mutagen` have no version constraint at all. On a fresh install, `pip` will install the latest available version of each package — including versions with known CVEs that were published after the last tested version. Supply chain attacks that compromise PyPI packages would automatically install malicious versions.
- **Evidence**:
  ```
  librosa           # NO VERSION AT ALL — any version accepted
  mutagen           # NO VERSION AT ALL
  numpy>=1.23.4     # No upper bound — latest numpy installed
  scipy>=1.9.2      # No upper bound
  fastapi>=0.104.0  # No upper bound
  aiohttp>=3.9.0    # No upper bound — CVEs in older aiohttp versions
  SQLAlchemy>=2.0.22 # No upper bound
  ```
- **Exploit Scenario**:
  1. Attacker publishes a malicious version of `librosa` to PyPI (or a legitimate vulnerability is published in a new `librosa` release).
  2. User runs `pip install -r requirements.txt` on fresh install.
  3. The malicious/vulnerable version is installed silently.
  4. Audio processing code executes attacker-controlled code.
- **Impact**: Supply chain compromise, arbitrary code execution during audio processing, silent installation of vulnerable library versions.
- **Suggested Fix**: Pin all dependencies to exact versions (`==`) and use `pip-audit` in CI to scan for CVEs. Generate a pinned `requirements.lock` file. At minimum, add `mutagen==<version>` and `librosa==<version>` with exact version strings.

---

### SEC-03: File Upload Validates Extension Only — No Magic Byte / MIME Type Verification
- **Severity**: MEDIUM
- **OWASP Category**: A08 (Software and Data Integrity Failures)
- **Location**: `auralis-web/backend/routers/files.py:104-121`
- **Status**: NEW
- **Description**: The file upload handler accepts files solely based on their extension (`.mp3`, `.wav`, `.flac`, `.ogg`, `.m4a`, `.aac`). File content is not validated against magic bytes or MIME type headers before the file is passed to `librosa`/`soundfile`/`ffmpeg` for parsing. A file that is not actually audio (e.g., a malformed binary disguised as `.mp3`, a ZIP archive, or a file crafted to exploit a known CVE in libav/libsndfile) will be passed directly to the parser.
- **Evidence**:
  ```python
  # files.py:104-110 — extension-only validation
  if not file.filename or not file.filename.lower().endswith(supported_extensions):
      results.append({"filename": ..., "status": "error", "message": "Unsupported file type"})
      continue

  # files.py:119-122 — parser invoked without content validation
  try:
      audio_data, sample_rate = load_audio(temp_path)  # FFmpeg/soundfile called on unchecked bytes
  ```
- **Exploit Scenario**:
  1. Attacker crafts a binary file exploiting CVE-XXXX-XXXX in libsndfile (several parser CVEs exist in libsndfile pre-1.1.0).
  2. Attacker names the file `exploit.flac` and uploads it via `POST /api/files/upload`.
  3. File passes extension check (`.flac` is allowed).
  4. `soundfile.read(temp_path)` is called, triggering the heap overflow in the vulnerable libsndfile.
  5. Depending on the exploit, this can lead to crash (DoS) or code execution.
- **Impact**: DoS or remote code execution via crafted audio file if a parser vulnerability exists in the installed libsndfile/libav version.
- **Suggested Fix**: Read the first 12 bytes of each uploaded file and validate against known audio magic bytes before calling any parser:
  ```python
  MAGIC_BYTES = {
      b'ID3': '.mp3', b'\xff\xfb': '.mp3',
      b'RIFF': '.wav', b'fLaC': '.flac',
      b'OggS': '.ogg',
  }
  with open(temp_path, 'rb') as f:
      header = f.read(12)
  if not any(header.startswith(magic) for magic in MAGIC_BYTES):
      raise ValueError("File content does not match declared audio format")
  ```

---

### SEC-04: SSRF via Unvalidated Artwork URL Fetched From iTunes API Response
- **Severity**: MEDIUM
- **OWASP Category**: A10 (Server-Side Request Forgery)
- **Location**: `auralis-web/backend/services/artwork_downloader.py:163-191`
- **Status**: NEW
- **Description**: The artwork downloader queries the iTunes Search API and then fetches the `artworkUrl100` value from the API JSON response using `aiohttp`. The URL is taken from the external API response and passed directly to `session.get(artwork_url)` without validating that the URL points to a trusted CDN domain. If the iTunes API response is manipulated (e.g., via a TLS-stripping proxy, a compromised DNS entry, or a future iTunes API compromise), the server will make an HTTP request to an attacker-controlled URL.
- **Evidence**:
  ```python
  # artwork_downloader.py:163-191
  async with session.get(self.itunes_api, params=params) as resp:
      data = await resp.json()
      results = data.get("results", [])
      if results:
          artwork_url = results[0].get("artworkUrl100", "")      # URL from external API
          artwork_url = artwork_url.replace("100x100", "600x600")  # Modified but not validated

  async with session.get(artwork_url) as resp:    # SSRF: unvalidated URL fetched
      artwork_data = await resp.read()
  ```
- **Exploit Scenario**:
  1. Attacker performs DNS spoofing for `itunes.apple.com` or a MITM attack on the network.
  2. Forged iTunes API response sets `artworkUrl100` to `http://169.254.169.254/latest/meta-data/` (cloud IMDS) or `http://192.168.1.1/admin`.
  3. Server fetches the internal URL and stores the response bytes as the album artwork.
  4. Attacker retrieves the "artwork" to read the internal network response.
- **Impact**: Internal network reconnaissance, potential access to cloud metadata services (IMDS), requests to internal admin interfaces.
- **Suggested Fix**: Whitelist allowed artwork URL domains before fetching:
  ```python
  ALLOWED_ARTWORK_DOMAINS = {"is1-ssl.mzstatic.com", "a5.mzstatic.com", "coverartarchive.org"}
  parsed = urlparse(artwork_url)
  if parsed.netloc not in ALLOWED_ARTWORK_DOMAINS or parsed.scheme != "https":
      logger.warning(f"Blocked unsafe artwork URL: {artwork_url}")
      return None
  ```

---

### SEC-05: WebSocket Handler Silently Drops Unknown Message Types — Rate-Limited but Noisy
- **Severity**: MEDIUM
- **OWASP Category**: A04 (Insecure Design)
- **Location**: `auralis-web/backend/routers/system.py:127-510`
- **Status**: NEW
- **Description**: The WebSocket message loop has `if/elif` branches for known message types (`ping`, `processing_settings_update`, `ab_track_loaded`, `play_enhanced`, `play_normal`, `seek`, `subscribe_job_progress`) but NO `else` clause. An unrecognized message type passes validation, finds no matching branch, and silently causes the loop to continue. While the 10 msg/sec rate limiter caps throughput, each unknown message still runs through the full `validate_and_parse_message()` pipeline (JSON parse + Pydantic validation) before being silently discarded. One hundred concurrent connections each sending 10 unknown-type messages per second produces 1,000 validation calls/second on the event loop — all returning silently with no log.
- **Evidence**:
  ```python
  # system.py — the message dispatch chain ends without else:
  elif message.get("type") == "subscribe_job_progress":
      ...
  # NO else clause:
  # - Unknown type passes rate limit + validation
  # - Falls through all elif branches
  # - Loop continues with no error sent to client and no log
  except WebSocketDisconnect:
      ...
  ```
- **Impact**: Silent DoS amplification via validation overhead per connection; diagnostic blind spot — clients sending wrong message types receive no feedback and developers see no log.
- **Suggested Fix**: Add an `else` clause that logs and responds to unrecognized types:
  ```python
  else:
      msg_type = message.get("type", "<none>")
      logger.warning(f"Unknown WebSocket message type: {msg_type!r}")
      await send_error_response(websocket, "unknown_message_type", f"Unknown type: {msg_type}")
  ```

---

### SEC-06: API Documentation (Swagger UI / ReDoc) Always Accessible — No Production Guard
- **Severity**: LOW
- **OWASP Category**: A05 (Security Misconfiguration)
- **Location**: `auralis-web/backend/config/app.py:26-33`
- **Status**: NEW
- **Description**: The FastAPI application is created with `docs_url="/api/docs"` and `redoc_url="/api/redoc"` unconditionally — no check for `DEV_MODE` or `--dev` flag. Both Swagger UI and ReDoc are accessible in production builds, exposing the full API surface (all routes, request/response schemas, WebSocket message format) to any connected client. This is significant if the backend is ever exposed beyond localhost (e.g., containerized deployments, LAN sharing).
- **Evidence**:
  ```python
  # config/app.py:26-33
  app = FastAPI(
      title="Auralis Web API",
      docs_url="/api/docs",    # Always enabled, no environment check
      redoc_url="/api/redoc",  # Always enabled
      lifespan=lifespan,
  )
  ```
- **Impact**: Exposes complete API documentation including schema details that assist attackers in crafting attacks. Informational in local-only deployment; becomes HIGH if backend is network-accessible.
- **Suggested Fix**: Disable docs in non-development mode:
  ```python
  import os
  is_dev = os.environ.get("DEV_MODE") or "--dev" in sys.argv
  app = FastAPI(
      docs_url="/api/docs" if is_dev else None,
      redoc_url="/api/redoc" if is_dev else None,
  )
  ```

---

### SEC-07: No Subresource Integrity (SRI) on Google Fonts CDN Links
- **Severity**: LOW
- **OWASP Category**: A08 (Software and Data Integrity Failures)
- **Location**: `auralis-web/frontend/index.html:22-32`
- **Status**: NEW
- **Description**: Two external stylesheets are loaded from `fonts.googleapis.com` without `integrity` attributes. If the Google Fonts CDN is compromised or a MITM attack strips HTTPS, malicious CSS could be injected into the frontend. While HTTPS provides significant protection, SRI provides defense-in-depth by verifying content hash independently of TLS.
- **Evidence**:
  ```html
  <!-- index.html:22-27 — no integrity attribute -->
  <link rel="stylesheet"
    href="https://fonts.googleapis.com/css2?family=Asap:ital,wght@0,100..900;1,100..900&display=swap" />
  <!-- index.html:29-32 — no integrity attribute -->
  <link rel="stylesheet"
    href="https://fonts.googleapis.com/icon?family=Material+Icons" />
  ```
- **Impact**: CSS injection via CDN compromise or MITM; potential UI spoofing or input capture via CSS-based attacks.
- **Suggested Fix**: Compute SHA-384 hash of the loaded CSS and add `integrity` + `crossorigin` attributes. Alternatively, self-host the fonts to eliminate the CDN dependency entirely.

---

### SEC-08: WebSocket Connect/Disconnect Not Logged With Client Identifier
- **Severity**: LOW
- **OWASP Category**: A09 (Security Logging and Monitoring Failures)
- **Location**: `auralis-web/backend/config/globals.py:40,51`
- **Status**: NEW
- **Description**: WebSocket connection and disconnection events are logged but without the client's IP address or port. While the server binds to `127.0.0.1`, the connection identifier in logs is only `len(self.active_connections)` — a count, not a client identifier. This makes it impossible to correlate log entries with specific connections during incident investigation (e.g., debugging cross-origin attacks identified in SEC-01).
- **Evidence**:
  ```python
  # globals.py:40 — no client IP logged
  logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
  # globals.py:51 — no client IP logged
  logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
  ```
- **Impact**: Loss of audit trail for WebSocket sessions. Cannot identify source of misbehaving connections.
- **Suggested Fix**: Log `websocket.client.host` and `websocket.client.port` on connect and disconnect.

---

### SEC-09: File Upload Handler Silently Discards Unsupported Files — No Audit Log
- **Severity**: LOW
- **OWASP Category**: A09 (Security Logging and Monitoring Failures)
- **Location**: `auralis-web/backend/routers/files.py:104-110`
- **Status**: NEW
- **Description**: When a file is rejected due to an unsupported extension, the handler appends an error to the result list but does NOT write a log entry. Repeated uploads of rejected files (e.g., scanning for accepted types, probe attacks) are invisible in server logs.
- **Evidence**:
  ```python
  if not file.filename or not file.filename.lower().endswith(supported_extensions):
      results.append({"filename": ..., "status": "error", "message": "Unsupported file type"})
      continue   # No logger call — silent drop
  ```
- **Impact**: No audit trail for rejected uploads; cannot detect probing attempts or automated file type scanning.
- **Suggested Fix**: Add `logger.warning(f"Rejected upload of unsupported file type: {file.filename!r}")` before `continue`.

---

### SEC-10: Fingerprint Data Stored Without Integrity Hash — Tampering Undetectable
- **Severity**: LOW
- **OWASP Category**: A08 (Software and Data Integrity Failures)
- **Location**: `auralis/library/repositories/fingerprint_repository.py`
- **Status**: NEW
- **Description**: The 25-dimensional fingerprint vectors (spectral, harmonic, temporal metrics) are stored in the database without any checksum or signature. If the SQLite database file is directly modified (e.g., by another process or via SQL injection), the fingerprint values can be altered silently. The similarity engine would then return incorrect track matches with no indication of tampering.
- **Evidence**: `TrackFingerprint` is created and committed with raw `fingerprint_data` dict. No `fingerprint_hash` column exists in the schema.
- **Impact**: Integrity of similarity results compromised; incorrect mastering recommendations based on tampered fingerprints. Low exploitability since it requires DB-level access.
- **Suggested Fix**: Compute and store a SHA-256 hash of the fingerprint data at insert time. Verify the hash at read time and flag mismatches.

---

## Relationships

- **SEC-01 + SEC-05**: Cross-origin WebSocket attack (SEC-01) relies on the lack of `else` handling (SEC-05) — an attacker can probe valid message types silently with no feedback. Fixing SEC-01 (Origin check) is the primary control; SEC-05 ensures errors are surfaced during normal debugging.
- **SEC-02 + SEC-03**: Unpinned `librosa`/`soundfile` versions (SEC-02) compound the parser attack risk (SEC-03) — a vulnerable library version might be installed, and then exploited via the missing magic byte check.

## Prioritized Fix Order

1. **SEC-01** (HIGH): WebSocket Origin check — prevents cross-origin player hijacking
2. **SEC-04** (MEDIUM): Artwork SSRF — add domain whitelist for fetched URLs
3. **SEC-03** (MEDIUM): Magic byte validation on file uploads
4. **SEC-02** (MEDIUM): Pin dependency versions in `requirements.txt`
5. **SEC-05** (MEDIUM): Add `else` clause to WebSocket message dispatch

## Cross-References to Existing Issues

| Skipped Finding | Status | Existing Issue |
|----------------|--------|----------------|
| WebSocket track_id not validated | Existing | #2393 |
| Secrets committed to .env | Existing | #2079 |
| Migration scripts no integrity check | Existing | #2083 |
| str(e) in HTTP error responses | Existing | #2169 |
| Discogs API token in URL query string | Existing | #2244 |
| No concurrent stream limits (unknown msg CPU overhead) | Extends | #2185 |
