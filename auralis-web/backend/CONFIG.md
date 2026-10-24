# Backend Environment-Variable Configuration

Tuning constants that can be overridden per-deployment via environment
variables, without a code edit + rebuild. All of these default to values
tuned for the single-user desktop deployment (see
[project_desktop_only.md] context) and only need overriding if that scope
changes (e.g. a LAN-shared backend serving multiple concurrent clients).

Invalid or out-of-range values fall back to the default with a logged
warning — a malformed override never crashes startup (see
`core/env_config.py`).

| Variable | Default | Where | Purpose |
|---|---|---|---|
| `AURALIS_MAX_CONCURRENT_STREAMS` | `10` | `core/audio_stream_controller.py` | Hard cap on concurrent audio streams (enhanced/normal/seek). Each stream holds a `ChunkedProcessor` in memory; raising this without more RAM risks OOM under load (#2185). |
| `AURALIS_SEND_QUEUE_MAXSIZE` | `4` | `core/stream_protocol.py` | Max encoded PCM frames queued ahead of the WebSocket sender per stream. Bounds Python-heap memory when a client is slower than the encoder. |
| `AURALIS_PROCESSOR_CACHE_MAX` | `32` | `core/processor_factory.py` | LRU bound on cached `HybridProcessor` instances (EQ filter banks, compressor state, mastering targets — roughly 1-200 MB each). Amortises creation cost across rapid track switches and A/B preset comparisons (#3515). |
| `AURALIS_FINGERPRINT_WORKERS` | `max(1, min(2, cpu_count // 2))` | `analysis/fingerprint_generator.py` | Thread pool size for fingerprint extraction (PyO3 Rust releases the GIL, so threads give true parallelism). |
| `AURALIS_SCAN_TIMEOUT` | `3600` (seconds) | `routers/library_scan.py` | Timeout for a full library scan. |
| `AURALIS_SCAN_STOP_GRACE_SECONDS` | `5` (whole seconds) | `services/scanner_stop.py` | How long a cancelled, timed-out or abandoned scan (manual endpoint and auto-scanner alike) waits for the scanner thread to exit after `stop_scan()` before logging a warning and leaving it to finish at its next checkpoint (#5196). |
| `AURALIS_SHUTDOWN_STEP_TIMEOUT_SECONDS` | `10` (whole seconds) | `config/limits.py` | Per-step budget for the lifespan's teardown waits (scanner task cancel, watchdog teardown await, fingerprint executor drain). Worst case the backend's teardown spends `OBSERVER_JOIN_TIMEOUT_S + 3 x` this value (35 s today); the Electron wrapper's `BACKEND_KILL_GRACE_MS` (`desktop/main.js`) must be read against that sum (#6233). |
| `AURALIS_OBSERVER_JOIN_TIMEOUT_SECONDS` | `5` (whole seconds) | `config/limits.py` | How long the watchdog observer's `join()` may block during teardown before it is abandoned (#4368, #4775). Part of the shutdown budget sum above. |
