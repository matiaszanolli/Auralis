# Backend Environment-Variable Configuration

Tuning constants that can be overridden per deployment through environment
variables, without a code edit. Auralis is a single-user desktop app, so every
default is tuned for one client on loopback; override only when that changes.

Integer overrides are read once, at import time, by
`auralis-web/backend/core/env_config.py::get_int_env`. A value that is unset,
not an integer, or below 1 falls back to the default with a logged warning, so a
malformed override never crashes startup. The few variables that parse
themselves (marked below) have their own fallback rule.

## Process and launch

| Variable | Default | Read in | Purpose |
|---|---|---|---|
| `AURALIS_PORT` | `8765` | `config/origins.py::BACKEND_PORT` (bind: `main.py`) | Port the backend binds on `127.0.0.1` and always allows as an origin. `launch-auralis-web.py --port` and the Electron dev launcher set it. |
| `AURALIS_FRONTEND_PORT` | `3000` | `config/origins.py` | Vite dev-server port added to the origin allowlists (dev mode only). |
| `AURALIS_DEV_MODE` | unset | `config/app.py::is_dev_mode` | `1`/`true`/`yes` (or the `--dev` argument) enables Swagger/ReDoc/OpenAPI, the Vite dev ports in the CORS and WebSocket origin allowlists, and skips the static frontend mount. Logs a warning when set. The packaged Electron spawn forces it to `0` (and `AURALIS_PORT` to 8765) so an ambient shell value cannot widen a production launch. |
| `AURALIS_LOG_LEVEL` | `info` (`debug` in dev mode) | `config/bootstrap.py::resolve_log_level` | One of `critical`, `error`, `warning`, `info`, `debug`, `trace` (case-insensitive). An unrecognised value logs a warning and uses the default. Independent of `AURALIS_DEV_MODE`. |
| `AURALIS_LAUNCH_ID` | unset | `routers/health.py` | Opaque id a supervisor hands its child; `GET /api/ready` echoes it as `X-Auralis-Launch-Id` so a server that won a port-bind race cannot pass the supervisor's probe. |
| `AURALIS_STDIN_LIFELINE` | unset | `config/parent_lifeline.py` | Set to `1` by the Electron wrapper only. The backend watches its stdin pipe and shuts down gracefully at end-of-file, which the OS produces when the parent exits by any means. A hard `os._exit(1)` follows after `SHUTDOWN_TOTAL_TIMEOUT_S + 2 x SHUTDOWN_STEP_TIMEOUT_S`. Never set it for a backend whose stdin is a terminal. |
| `ELECTRON_MODE` | unset | `config/bootstrap.py`, `config/fallback_routes.py` | `1` selects the Electron resource layout when resolving `sys.path` and the built frontend directory. Set by the Electron wrapper. |
| `AURALIS_DATA_DIR` | `~/.auralis` | `auralis/library/data_dir.py` | Root for the library database, caches and uploads directory. |

## Shutdown budget

All three read through `get_int_env` and are held as whole seconds in
`config/limits.py`.

| Variable | Default | Purpose |
|---|---|---|
| `AURALIS_SHUTDOWN_STEP_TIMEOUT_SECONDS` | `10` | Per-step budget for the lifespan teardown waits (scanner task cancel, watchdog teardown, fingerprint executor drain) and uvicorn's `timeout_graceful_shutdown`. |
| `AURALIS_OBSERVER_JOIN_TIMEOUT_SECONDS` | `5` | How long the watchdog observer's `join()` may block before it is abandoned. |
| `AURALIS_SHUTDOWN_TOTAL_TIMEOUT_SECONDS` | `30` | One deadline over all of the lifespan's stop steps. When it passes, the remaining steps are abandoned with an ERROR log; the library WAL checkpoint and thread-pool shutdown still run. |

Worst-case teardown is `OBSERVER_JOIN_TIMEOUT_S + 3 x SHUTDOWN_STEP_TIMEOUT_S`
(35 s at the defaults). The Electron wrapper's `BACKEND_KILL_GRACE_MS`
(`desktop/main.js`) must stay above that sum.

## Streaming and concurrency

| Variable | Default | Read in | Purpose |
|---|---|---|---|
| `AURALIS_MAX_CONCURRENT_STREAMS` | `10` | `core/audio_stream_controller.py` | Global cap on concurrent audio streams (enhanced, normal, seek). Each holds a `ChunkedAudioProcessor`; raising it without RAM risks OOM. It also sizes the streaming thread pool (`max(4, 2 x this)`). |
| `AURALIS_SEND_QUEUE_MAXSIZE` | `4` | `core/stream_protocol.py` | Encoded PCM frames queued ahead of the WebSocket sender per stream. Bounds memory when a client is slower than the encoder. |
| `AURALIS_PROCESSOR_CACHE_MAX` | `32` | `core/processor_factory.py` | LRU bound on cached `HybridProcessor` instances (filter banks, compressor state, mastering targets; roughly 1-200 MB each). |
| `AURALIS_IO_POOL_WORKERS` | `8` | `core/executors.py` | Default executor (repository and file I/O). Clamped to 10, the SQLAlchemy pool ceiling, with a warning. |
| `AURALIS_JOB_POOL_WORKERS` | `2` | `core/executors.py` | Mastering-job DSP pool; matches `ProcessingEngine(max_concurrent_jobs=2)`. |
| `AURALIS_TRANSPORT_POOL_WORKERS` | `2` | `core/executors.py` | Player transport engine calls, already serialised by the playback lock. |

## Library scan and fingerprinting

| Variable | Default | Read in | Purpose |
|---|---|---|---|
| `AURALIS_SCAN_TIMEOUT` | `3600` s | `config/limits.py::SCAN_TIMEOUT_S` | Bound on one manual scan request (`POST /api/library/scan`). |
| `AURALIS_SCAN_STOP_GRACE_SECONDS` | `5` s | `services/scanner_stop.py` | How long a cancelled, timed-out or abandoned scan (manual and auto-scanner) waits for the scanner thread to exit after `stop_scan()` before warning and leaving it to stop at its next checkpoint. |
| `AURALIS_FINGERPRINT_WORKERS` | `max(1, min(2, cpu_count // 2))` | `analysis/fingerprint_executor.py` | Thread-pool size for fingerprint extraction (the Rust extractor releases the GIL). |
| `AURALIS_FINGERPRINT_TRACK_TIMEOUT` | `600` s | `auralis/services/fingerprint_worker.py` | Per-track wall-clock bound in the fingerprint queue worker. Float; non-numeric or non-positive values fall back to the default (a self-parsing variable). |

## Audio loading

Read by `auralis/io/loader.py`, which parses them itself: a non-integer value
falls back to the default.

| Variable | Default | Purpose |
|---|---|---|
| `AURALIS_MAX_DURATION_SECONDS` | `7200` | Longest file the loader will decode into RAM. |
| `AURALIS_MAX_DECODED_BYTES` | `6 GiB` (`6442450944`) | Ceiling on the estimated decoded size (duration x sample rate x channels x float32). Raise it together with the duration cap. |

## HTTP rate limits

`config/middleware/rate_limit.py::RateLimitMiddleware` applies a sliding window
per client IP, HTTP method and path prefix; the longest matching prefix wins.
Every limit is `AURALIS_RATE_LIMIT_<NAME>_MAX` (requests) and
`AURALIS_RATE_LIMIT_<NAME>_WINDOW` (seconds), defined in `config/limits.py`.

| `<NAME>` | Path prefix | Max | Window |
|---|---|---|---|
| `UPLOAD` | `/api/files/upload` | 5 | 60 |
| `PROCESSING` | `/api/processing` | 10 | 60 |
| `RESET` | `/api/library/reset` | 1 | 60 |
| `SCAN` | `/api/library/scan` | 2 | 60 |
| `SCAN_STATUS` | `/api/library/scan/status` | 30 | 60 |
| `SIMILARITY` | `/api/similarity` | 20 | 60 |
| `RECOMMENDATION` | `/api/player/mastering/recommendation` | 20 | 60 |

## Fixed limits (not env-tunable)

Constants in `config/limits.py`: upload caps (`MAX_UPLOAD_BYTES` 500 MiB per
file, `MAX_UPLOAD_FILES` 200, `MAX_UPLOAD_REQUEST_BYTES` 2 GiB,
`MAX_UPLOAD_DIR_BYTES` 20 GiB) and the WebSocket limits documented in
[WEBSOCKET_API.md](WEBSOCKET_API.md).

## Artwork CLI keys

`auralis/cli/fetch_artwork.py` (an offline script, not the server) prefers
`AURALIS_DISCOGS_TOKEN` and `AURALIS_LASTFM_KEY` over the equivalent command-line
flags, which would land in shell history.
