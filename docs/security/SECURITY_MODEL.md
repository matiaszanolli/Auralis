# Auralis Security Model

Threat model for the local REST and WebSocket API of `auralis-web/backend/`
(FastAPI on `127.0.0.1:8765`). Each defense below names the code that enforces
it; cite symbols, not line numbers.

## Summary

Auralis is a single-user desktop application: an Electron shell, a FastAPI
backend and a Rust DSP module, all on one machine. The backend binds to the
loopback interface only and ships no caller authentication. That is a deliberate
decision. The boundaries below bound who can reach the API, and the residual
risk sections state what they do not cover.

## Deployment shape

- One user, one machine. There is no server deployment, no multi-tenant mode and
  no LAN or remote scenario. A machine where other people hold their own OS
  accounts and can run programs while Auralis is open (a shared workstation, a
  terminal server) is not a supported deployment; see "Out of scope" below.
- The backend binds `127.0.0.1` only (`auralis-web/backend/main.py`,
  `uvicorn.run(host="127.0.0.1", ...)`), so no other host on the network can
  connect.
- The packaged renderer loads from the backend's own origin,
  `http://127.0.0.1:8765` (`APP_ORIGIN` in `desktop/url-safety.js`). No
  file-scheme origin is involved. In development the renderer is served by Vite
  on port 3000 and the backend admits that origin in dev mode only.

## Authentication posture

There is no authentication on REST or WebSocket. Any process on the local
machine, and any browser page whose `Origin` is in the loopback allowlist, can
call every endpoint (control playback, scan the library, edit metadata, run
processing jobs). Nothing under `auralis-web/backend/routers/` uses an HTTP
bearer, OAuth2 or `Security(...)` dependency.

## Boundaries that bound the risk

### Network and origin

| Boundary | Enforced by |
|---|---|
| Loopback bind | `main.py` (`host="127.0.0.1"`) |
| No proxy headers: `X-Forwarded-For` never rewrites the client address that the loopback checks read | `uvicorn.run(proxy_headers=False)` in `main.py` |
| Host header allowlist (`localhost`, `127.0.0.1`): a page on another domain rebound to 127.0.0.1 is refused before any handler runs | `config/middleware/logged_rejections.py::LoggingTrustedHostMiddleware` with `config/middleware/hosts.py::trusted_hosts` |
| WebSocket `Origin` matrix: a browser upgrade must present an origin from `http`/`https`/`ws`/`wss` x `localhost`/`127.0.0.1` x allowed ports (the backend port; Vite dev ports 3000-3006 in dev mode only). Refused with close code 1008. No `file://` entry | `websocket/connection_manager.py::build_ws_origins` over `config/origins.py::origin_matrix` |
| Empty-`Origin` loopback gate: a non-browser client sends no `Origin`; it is accepted only from a loopback peer (`127.0.0.1`, `::1`, `localhost`) | `websocket/connection_manager.py::ConnectionManager.connect`, `LOOPBACK_HOSTS` |
| REST origin check: `POST`/`PUT`/`DELETE`/`PATCH` under `/api` need an `Origin` from the CORS allowlist, or no `Origin` from a loopback peer. A `GET`/`HEAD` under `/api` is refused when the browser marks it `Sec-Fetch-Site: cross-site` or `same-site` and neither its `Origin` nor `Referer` is trusted | `config/middleware/origin_check.py::OriginCheckMiddleware` |
| CORS: explicit origin, method and header lists; never a wildcard with credentials | `config/middleware/__init__.py::setup_middleware`, `hosts.py::cors_allowed_origins` |
| Dev mode widens origins and enables Swagger/ReDoc/OpenAPI only when explicitly requested (`--dev` or `AURALIS_DEV_MODE`). The packaged Electron spawn sets `AURALIS_DEV_MODE=0` and pins `AURALIS_PORT` so an ambient shell variable cannot widen a production launch | `config/app.py::is_dev_mode`, `desktop/backend-env.js::buildBackendEnv` |

All three origin allowlists (CORS, WebSocket handshake, CSP `connect-src`) derive
from `config/origins.py`; add a host or port there once.

### Request budgets

| Budget | Value | Enforced by |
|---|---|---|
| WebSocket frame and message size | 64 KiB, at the transport (`ws_max_size`) and again after decode; nesting depth 32; text frames only | `config/limits.py::WS_MAX_MESSAGE_SIZE`, `websocket/message_validation.py` |
| WebSocket message rate | 10 per second per connection, 30 per second per client IP (survives reconnects); `ping` has its own 5 per second budget | `websocket/rate_limiter.py::WebSocketRateLimiter`, `routers/system.py` |
| WebSocket connections | 16 concurrent | `config/limits.py::WS_MAX_CONNECTIONS` |
| Concurrent audio streams | 10 | `core/audio_stream_controller.py::MAX_CONCURRENT_STREAMS` |
| HTTP rate limits on expensive routes (upload, processing, library reset, scan, similarity, mastering recommendation), keyed on client IP, method and path prefix | see [CONFIG.md](../../auralis-web/backend/CONFIG.md) | `config/middleware/rate_limit.py::RateLimitMiddleware` |
| Uploads: 200 files per request, 500 MiB per file, 2 GiB per request, 20 GiB in the uploads directory | | `config/limits.py`, `routers/files_upload.py`, `routers/files_upload_budget.py` |

Frames that fail validation are charged to the same rate limiter and, once it is
exhausted, are dropped with no reply, so a bad-frame flood cannot become a free
request/response loop. Rejections that a remote page can trigger are logged once
per reason per window (`config/log_throttle.py::warn_throttled`) so a flood
cannot evict earlier security log entries.

### Paths and files

Path inputs are validated independently of the caller, in
`auralis-web/backend/security/`:

- **Scan folders** (`POST /api/library/scan`, `POST /api/settings/scan-folders`,
  `PUT /api/settings`): `path_security.py::validate_user_chosen_directory` and
  `validate_directory_list`. The directory must exist, be readable and contain no
  `..`; operating-system trees and the app's own scratch roots (system temp, the
  Auralis data directory) are refused. The user's choice is otherwise trusted.
  There is deliberately no allowlist-enforcing directory validator: it would
  imply a containment guarantee the app does not enforce. Do not add one.
  Persisted folders are re-checked at every startup and auto-scan cycle
  (`trusted_scan_folders`), so a stale entry such as `/` is never scanned.
- **File reads from request-scoped features** (lyrics, metadata edit and batch,
  mastering recommendation, processing input paths, the streaming entry points
  `stream_normal`, `stream_enhanced`, `stream_seek`):
  `path_security.py::validate_file_path`. The path must resolve inside an allowed
  directory (`path_allowlist.py::get_allowed_directories`: `~/Music`,
  `~/Documents`, `XDG_MUSIC_DIR`, the uploads directory and the registered scan
  folders; never bare `$HOME`), exist and be readable. Rejections carry fixed,
  path-free messages.
- **Accepted asymmetry:** the player's load path (queue operations) and the
  streamlined cache worker do not call `validate_file_path` on database-sourced
  paths. A library follows symlinked subdirectories, so a stored path can
  legitimately resolve outside the allowlist, and those tracks must play.
- **Artwork** (`routers/artwork.py::_contained_artwork_path`): the stored
  artwork path is resolved and must lie under the artwork directory before the
  existence check; a traversal is a 403, not a probe. Remote artwork fetches
  follow redirects only across a provider's trusted hosts and read bodies with a
  hard byte bound (`services/artwork_providers/trust.py`, `bounded_read.py`).
- **Job downloads** (`routers/processing_jobs.py::_contained_output_path`): the
  output path must lie under the temp directory.
- **Uploads** (`routers/files_upload.py`, `files_validation.py`): the extension
  must be a supported audio format, the content must start with a known audio
  container signature, and the file is stored under a random name
  (`uuid4().hex` plus the suffix), never the client filename.
- **Temp directories**: the chunk, upload and processing directories under the
  system temp root are created owner-only (`0o700`), refuse to follow a symlink or
  adopt a directory owned by another user
  (`config/limits.py::create_secure_temp_dir`). The data directory and database
  are owner-only (`auralis/library/database_engine.py`).

### Browser-facing headers

`config/middleware/security_headers.py::SecurityHeadersMiddleware` sets
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`,
`Permissions-Policy` (camera, microphone, geolocation off) and a CSP:
`default-src 'self'`, loopback-only `connect-src`, `form-action 'self'`,
`base-uri 'self'`, and an `img-src` allowlist for artwork hosts. The middleware
wraps rate limiting, so 403 and 429 responses carry the headers too.

### Error and log hygiene

- Error bodies never include server paths or raw exception text: handlers return
  fixed messages (`routers/errors.py`) and `core/job_error_mapping.py::_safe_error_message`
  maps exception types to categories. Details are logged server-side.
- Untrusted values (tag text, client filenames, tracebacks) are escaped before they
  reach a log line, so they cannot forge entries
  (`auralis/utils/logging.py::sanitize_log_value`,
  `auralis/utils/log_formatter.py`).
- INFO-level logs omit absolute paths (they embed the OS username); paths appear
  at DEBUG only.

### Electron shell

`desktop/main.js` runs the renderer with `contextIsolation`, `sandbox` and no
`nodeIntegration`. Every IPC handler refuses a sender that is not the app's own
top-level document (`isTrustedIpcSender`); in-window navigation is limited to the
app origin (`isAllowedAppNavigation`); external links pass `isSafeExternalUrl`;
web permission requests are denied (`setPermissionRequestHandler`). Electron
fuses (`electronFuses` in `desktop/package.json`) disable `runAsNode` and the
Node inspector options and require the app to load from the asar. The packaged
backend binary is checked against a SHA-256 recorded at build time before it is
spawned (`desktop/backend-integrity.js`); on Linux that is tamper evidence
against a swapped binary, not against a swapped asar. The backend exits with its
parent through the stdin lifeline (`config/parent_lifeline.py`).

## Residual risk

### Accepted: a process running as the same user

These boundaries do not stop a co-resident local process running under the
user's own account. It can open `ws://127.0.0.1:8765/ws` with no `Origin` (allowed
as loopback) and issue commands, or call REST directly. This is accepted because
such a process already holds the user's filesystem privileges: it can read and
write the music library, the SQLite database (`~/.auralis/library.db`) and the
user's files directly. Driving the API grants it nothing new.

### Out of scope: another OS account on the same machine

Loopback is shared by every account on the machine, so a process run by another
local user passes the same boundaries (loopback peer, no `Origin`). The
same-user argument does not cover it: that user cannot read `~/.auralis`
(owner-only) or, typically, this user's music, yet while Auralis runs it could,
through the API, list the library, read metadata, artwork and the audio of
allowlisted folders, edit tags, change the persisted scan folders, reset the
library and control playback.

Decision (closed issue #6520): shared multi-user hosts are not a supported
deployment, and Auralis does not defend against this actor. The fix that would
close it is the capability token below, which must be threaded through Electron,
the renderer's REST and WebSocket clients, both backend gates, the development
launcher and every test client. That cost is not taken for a deployment the app
does not target. Do not run Auralis where untrusted people have their own accounts
and can run programs at the same time. Revisit this if Auralis is ever packaged
for shared machines (labs, terminal servers, kiosks) or gains a headless or server
mode.

### Not exposed off the machine

- No LAN peer can reach the API (loopback bind).
- No remote or cross-origin web page can drive the WebSocket or REST API (origin
  matrix, REST origin check, Host allowlist).

## Optional hardening (not implemented)

If defense against co-resident processes or other local accounts is ever wanted,
the Electron main process could mint a per-launch loopback capability token, pass
it to the renderer at startup, and require it on WebSocket connect and REST
mutations. This is a design decision with a usability and complexity cost and is
not adopted.

## History

Write-ups of the original fixes are archived and describe the code as it was when
they were written: [WebSocket input validation](../archive/fixes/WEBSOCKET_SECURITY_FIX_2156.md),
[path traversal in scanning](../archive/fixes/PATH_TRAVERSAL_FIX_2069.md),
[path traversal, second pass](../archive/fixes/SECURITY_FIX_2236_PATH_TRAVERSAL.md),
[artwork path validation](../archive/fixes/SECURITY_FIX_2237_ARTWORK_PATH_VALIDATION.md).
