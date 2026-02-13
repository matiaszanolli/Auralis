# Backend Audit Report — 2026-02-12

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: `auralis-web/backend/` — FastAPI REST + WebSocket backend
**Existing issues checked**: 50+ open issues from `gh issue list --limit 200`

---

## Executive Summary

The Auralis FastAPI backend is a well-structured audio processing server with 16+ routers, WebSocket streaming, chunked processing with crossfade, and a sophisticated caching layer. The codebase follows good patterns (factory-based DI, async handlers, repository pattern).

However, this audit identified **11 new findings** across route handlers, WebSocket streaming, processing engine, middleware, error handling, performance, and test coverage:

| Severity | Count | Key Themes |
|----------|-------|------------|
| HIGH | 3 | Event loop blocking, memory exhaustion, missing backpressure |
| MEDIUM | 5 | Dead routes, audio padding, missing timeouts, missing error handlers, startup blocking |
| LOW | 3 | Duplicate modules, unsafe sys.path, missing tests |

The most critical pattern is **pervasive synchronous I/O in async handlers** (B-01), which can block the entire event loop and freeze all concurrent requests including WebSocket heartbeats.

---

## Findings

### B-01: Pervasive sync I/O in async handlers blocks event loop
- **Severity**: HIGH
- **Dimension**: Performance & Resource Management / Route Handler Correctness
- **Location**: `auralis-web/backend/routers/files.py:105`, `routers/library.py:244-264,497`, `routers/metadata.py:114-237`, `routers/enhancement.py:74-95`, `routers/webm_streaming.py:387-419`, `audio_stream_controller.py:557`
- **Status**: NEW
- **Description**: Multiple async route handlers perform synchronous file I/O, audio decoding, and CPU-bound processing directly on the event loop without `asyncio.to_thread()` or `run_in_executor()`. This starves the event loop, blocking all concurrent requests (including WebSocket heartbeats and ping/pong) during these operations.
- **Evidence**:
  ```python
  # files.py:103-105 — sync scanner in async background task
  async def scan_worker() -> None:
      result = scanner.scan_single_directory(directory, recursive=True)  # BLOCKS event loop

  # library.py:244-245 — sync mutagen parsing in async handler
  async def get_track_lyrics(track_id: int) -> Dict[str, Any]:
      audio_file = mutagen.File(track.filepath)  # BLOCKS event loop

  # library.py:497 — sync directory scan in async handler
  result = scanner.scan_directories(directories=directories, ...)  # BLOCKS event loop

  # metadata.py:114,117 — sync file metadata reads
  editable_fields = metadata_editor.get_editable_fields(str(track.filepath))  # BLOCKS
  current_metadata = metadata_editor.read_metadata(str(track.filepath))  # BLOCKS

  # enhancement.py:74-95 — sync soundfile + processor creation in async task
  async def _preprocess_upcoming_chunks(...):
      info = sf.info(filepath)  # BLOCKS event loop
      processor = ChunkedAudioProcessor(...)  # CPU-bound, BLOCKS

  # webm_streaming.py:387-419 — loads ENTIRE audio file synchronously
  async def _get_original_wav_chunk(...):
      audio, sr = load_audio(filepath)  # Loads entire file, BLOCKS
      wav_bytes = encode_to_wav(chunk_audio, sr)  # CPU-bound encoding, BLOCKS

  # audio_stream_controller.py:557 — loads entire audio file for normal streaming
  audio_data, sample_rate = sf.read(str(track.filepath), dtype=np.float32)  # BLOCKS
  ```
- **Impact**: During any of these operations (which can take 100ms-30s+), the entire backend is frozen. No other HTTP requests or WebSocket messages are processed. WebSocket clients may time out and disconnect. Concurrent users experience complete unresponsiveness.
- **Suggested Fix**: Wrap all sync I/O calls in `asyncio.to_thread()` (Python 3.9+) or `loop.run_in_executor(None, ...)`. For CPU-bound work like audio processing, use a dedicated `ProcessPoolExecutor`. Example:
  ```python
  result = await asyncio.to_thread(scanner.scan_single_directory, directory, recursive=True)
  ```

---

### B-02: stream_normal_audio loads entire audio file into memory
- **Severity**: HIGH
- **Dimension**: Performance & Resource Management / WebSocket Streaming
- **Location**: `auralis-web/backend/audio_stream_controller.py:557`
- **Status**: NEW
- **Description**: The `stream_normal_audio` method calls `sf.read()` to load the entire audio file into memory before chunking. For a 10-minute song at 44.1kHz stereo float32, this allocates ~200MB per stream. Multiple concurrent normal-mode streams can rapidly exhaust server memory.
- **Evidence**:
  ```python
  # audio_stream_controller.py:557
  async def stream_normal_audio(self, track_id, websocket, ...):
      audio_data, sample_rate = sf.read(str(track.filepath), dtype=np.float32)
      # ^^ For a 10-min stereo track: 10*60*44100*2*4 = ~211 MB

      # Then iterates through chunks:
      for chunk_idx in range(total_chunks):
          start_sample = chunk_idx * interval_samples
          end_sample = min(start_sample + chunk_samples, len(audio_data))
          chunk_audio = audio_data[start_sample:end_sample]  # Slice from full array
  ```
  Compare with `stream_enhanced_audio` which uses `ChunkedAudioProcessor` to load chunks on-demand — much more memory efficient.
- **Impact**: 3 concurrent normal streams of 10-minute tracks = ~630MB RAM. With longer tracks (1-hour podcasts), a single stream could use over 1GB. Server may OOM-kill or swap thrash.
- **Suggested Fix**: Use `sf.read()` with `start` and `stop` parameters to load only the needed chunk, or use `soundfile.SoundFile` in streaming mode with `sf.blocks()`. This mirrors how `ChunkedAudioProcessor` already handles enhanced audio.

---

### B-03: No backpressure on WebSocket audio streaming
- **Severity**: HIGH
- **Dimension**: WebSocket Streaming
- **Location**: `auralis-web/backend/audio_stream_controller.py:797-826`
- **Status**: NEW
- **Description**: The `_send_pcm_chunk` method sends base64-encoded audio frames in a tight loop via `await websocket.send_text()`. While each send is awaited, there is no mechanism to detect or respond to the client falling behind. If audio processing is faster than network delivery (likely on LAN or fast processing), WebSocket send buffers grow unboundedly.
- **Evidence**:
  ```python
  # audio_stream_controller.py:797-826
  async def _send_pcm_chunk(self, websocket, pcm_samples, ...):
      for frame_idx in range(num_frames):
          frame_samples = pcm_samples[start_idx:end_idx]
          pcm_bytes = frame_samples.tobytes()
          pcm_base64 = base64.b64encode(pcm_bytes).decode("ascii")
          message = {"type": "audio_chunk", "data": {...}}
          await websocket.send_text(json.dumps(message))
          # ^^ No flow control, no check if client is keeping up
  ```
  Also in the outer loop (`stream_enhanced_audio`, line 462-489), chunks are processed and sent sequentially with no pacing.
- **Impact**: On slow networks or with a client that pauses processing (e.g., tab backgrounded), the server-side send buffer grows. This can cause high memory usage on the server and eventual WebSocket disconnection when the buffer exceeds limits.
- **Suggested Fix**: Add a simple flow control mechanism: either (1) send chunk metadata first and wait for client acknowledgment before sending the next chunk, (2) use a bounded asyncio.Queue between the producer and sender, or (3) periodically check `websocket.client_state` and add small delays between frames.

---

### B-04: Duplicate POST /api/library/scan route with conflicting signatures
- **Severity**: MEDIUM
- **Dimension**: Route Handler Correctness
- **Location**: `auralis-web/backend/routers/files.py:74` and `auralis-web/backend/routers/library.py:433`
- **Status**: NEW
- **Description**: Two routers register `POST /api/library/scan` with incompatible request models. `files.py` expects `ScanRequest(directory: str)` (single directory). `library.py` expects query parameters `directories: List[str]` (multiple directories). Since `files_router` is registered first in `config/routes.py:94` (before `library_router` at line 131), the library router's scan endpoint is unreachable dead code.
- **Evidence**:
  ```python
  # files.py:74 — registered FIRST (wins)
  @router.post("/api/library/scan")
  async def scan_directory(request: ScanRequest) -> Dict[str, Any]:
      # Expects: {"directory": "/path/to/music"}

  # library.py:433 — registered SECOND (dead code, never reached)
  @router.post("/api/library/scan")
  async def scan_library(
      directories: List[str],
      recursive: bool = True,
      skip_existing: bool = True
  ) -> Dict[str, Any]:
      # Expects: directories as query params — NEVER CALLED
  ```
  Router registration order in `config/routes.py`:
  ```python
  app.include_router(files_router)     # Line 94 — registers POST /api/library/scan first
  # ...
  app.include_router(library_router)   # Line 131 — duplicate route is shadowed
  ```
- **Impact**: The library router's richer scan endpoint (supporting multiple directories, recursive flag, skip_existing, progress callbacks) is completely unreachable. Any frontend code calling the multi-directory scan API gets a validation error. This is related to but distinct from #2101 (which covers the frontend/backend key mismatch).
- **Suggested Fix**: Remove the duplicate route from `files.py` and keep only the `library.py` version which has richer functionality. Or rename one to a different path (e.g., `/api/library/scan-directory` vs `/api/library/scan`).

---

### B-05: stream_normal_audio pads last chunk with silence
- **Severity**: MEDIUM
- **Dimension**: WebSocket Streaming / Chunked Processing
- **Location**: `auralis-web/backend/audio_stream_controller.py:612-615`
- **Status**: NEW
- **Description**: When the last chunk of a normal audio stream is shorter than `chunk_samples`, it is padded with zeros to the full chunk length. This adds audible silence at the end of every track, breaking gapless playback and causing a perceptible gap between tracks.
- **Evidence**:
  ```python
  # audio_stream_controller.py:612-615
  # Pad if last chunk is shorter
  if len(chunk_audio) < chunk_samples:
      padding = np.zeros((chunk_samples - len(chunk_audio), channels), dtype=np.float32)
      chunk_audio = np.vstack([chunk_audio, padding])
  ```
  For a 3:27 track with 15s chunks: 207s / 15s = 13 full chunks + 12s remainder. The remainder gets padded with 3 seconds of silence.
- **Impact**: Every track played in normal mode ends with audible silence (up to 15 seconds). This disrupts gapless playback and makes the player feel broken for users who notice the gap.
- **Suggested Fix**: Send the last chunk at its actual length without padding. Include the actual sample count in the message metadata so the frontend knows the true length. The enhanced streaming path (via `ChunkedAudioProcessor`) already handles variable-length last chunks correctly.

---

### B-06: No timeout on ChunkedAudioProcessor instantiation
- **Severity**: MEDIUM
- **Dimension**: Error Handling & Resilience
- **Location**: `auralis-web/backend/routers/webm_streaming.py:279-284`, `routers/enhancement.py:89-95`, `routers/system.py:179`
- **Status**: NEW
- **Description**: `ChunkedAudioProcessor()` instantiation loads audio metadata, creates a processor factory, and potentially extracts fingerprints from the audio file. None of the call sites wrap this in a timeout. A corrupt, very large, or network-mounted audio file could cause the constructor to hang indefinitely.
- **Evidence**:
  ```python
  # webm_streaming.py:279-284 — No timeout protection
  processor = chunked_audio_processor_class(
      track_id=track_id,
      filepath=track.filepath,
      preset=preset,
      intensity=intensity
  )
  # If filepath points to a corrupt file or slow NFS mount, this hangs forever

  # system.py:179 — Same issue in WebSocket handler
  from chunked_processor import ChunkedAudioProcessor
  controller = AudioStreamController(
      chunked_processor_class=ChunkedAudioProcessor,
      ...
  )
  ```
- **Impact**: A single request for a corrupt file can consume a thread/task indefinitely. If this happens in the WebSocket handler, the connection hangs and the client sees no error. If it happens in the REST endpoint, the HTTP request times out with no useful error message.
- **Suggested Fix**: Wrap processor creation in `asyncio.wait_for()` with a reasonable timeout (e.g., 30 seconds):
  ```python
  processor = await asyncio.wait_for(
      asyncio.to_thread(ChunkedAudioProcessor, track_id=track_id, ...),
      timeout=30.0
  )
  ```

---

### B-07: No global exception handler for unhandled errors
- **Severity**: MEDIUM
- **Dimension**: Error Handling & Resilience / Middleware & Configuration
- **Location**: `auralis-web/backend/main.py` (missing), `auralis-web/backend/config/app.py` (missing)
- **Status**: NEW
- **Description**: The FastAPI application has no global exception handler (`@app.exception_handler(Exception)`) or `RequestValidationError` handler. When an unhandled exception occurs in any route, FastAPI returns a raw 500 response that may include stack trace details. There is also no structured error response format enforced globally.
- **Evidence**:
  ```python
  # config/app.py:8-12 — No exception handlers registered
  def create_app() -> FastAPI:
      return FastAPI(
          title="Auralis Web API",
          docs_url="/api/docs",
          redoc_url="/api/redoc"
      )
  # No @app.exception_handler(Exception) anywhere in main.py or config/

  # Example: routers/enhancement.py:476-492 — catches Exception and returns default values
  # But not all routers do this — some let exceptions propagate to FastAPI's default handler
  ```
  Several routers use `handle_query_error()` from `routers/errors.py`, but this isn't applied universally. Any route that misses a try/except leaks stack traces.
- **Impact**: Unhandled exceptions in routes expose internal implementation details (file paths, library versions, stack traces) in the HTTP response. This is both a security concern (information disclosure) and a user experience issue (cryptic error messages). Related to but distinct from #2092 (error format inconsistency).
- **Suggested Fix**: Add a global exception handler in `config/app.py`:
  ```python
  @app.exception_handler(Exception)
  async def global_exception_handler(request, exc):
      logger.error(f"Unhandled exception: {exc}", exc_info=True)
      return JSONResponse(status_code=500, content={"status": "error", "message": "Internal server error"})
  ```

---

### B-08: Startup event blocks event loop with synchronous auto-scan
- **Severity**: MEDIUM
- **Dimension**: Middleware & Configuration / Performance
- **Location**: `auralis-web/backend/config/startup.py:148-152`
- **Status**: NEW
- **Description**: During the `startup_event`, `scanner.scan_directories()` is called synchronously. This is a blocking operation that walks the filesystem, reads metadata from audio files, and inserts records into the database. For a large music library (10K+ files), this can take 30+ seconds, during which the server cannot accept any requests.
- **Evidence**:
  ```python
  # config/startup.py:148-152
  scan_result = scanner.scan_directories(
      [str(music_source_dir)],
      recursive=True,
      skip_existing=True
  )
  # ^^ Synchronous call during async startup — blocks all request handling
  ```
  This runs on every server start, scanning `~/Music` recursively.
- **Impact**: Server startup is delayed by the scan duration. During startup, the frontend shows "connecting..." with no feedback. If the scan encounters errors (e.g., permission denied on subdirectories), startup may hang or fail silently.
- **Suggested Fix**: Move auto-scan to a background task that runs after startup completes:
  ```python
  @app.on_event("startup")
  async def startup_event():
      # ... initialize components ...
      asyncio.create_task(_background_auto_scan())  # Non-blocking
  ```
  Or use `asyncio.to_thread(scanner.scan_directories, ...)` to avoid blocking the event loop.

---

### B-09: Duplicate WAV encoder module paths
- **Severity**: LOW
- **Dimension**: Middleware & Configuration
- **Location**: `auralis-web/backend/encoding/wav_encoder.py` and `auralis-web/backend/core/encoding/wav_encoder.py`
- **Status**: NEW
- **Description**: Two WAV encoder modules exist at different paths. The `webm_streaming.py` router imports from `encoding.wav_encoder` while `chunked_processor.py` imports from `core.encoding.wav_encoder`. Having two modules with the same purpose creates confusion about which is canonical and risks divergent implementations.
- **Evidence**:
  ```python
  # webm_streaming.py:35
  from encoding.wav_encoder import WAVEncoderError, encode_to_wav

  # chunked_processor.py (via core/)
  # Uses core.encoding.wav_encoder
  ```
- **Impact**: If one encoder is updated but not the other, audio encoding behavior diverges between REST and WebSocket streaming paths. Developers may edit the wrong file.
- **Suggested Fix**: Consolidate to a single WAV encoder module and update all imports.

---

### B-10: sys.path manipulation inside request handlers
- **Severity**: LOW
- **Dimension**: Route Handler Correctness
- **Location**: `auralis-web/backend/routers/enhancement.py:72-73,362-364,406-407`
- **Status**: NEW
- **Description**: Several handlers insert directories into `sys.path` at the start of each request. This is not thread-safe (mutates global state), accumulates duplicate entries over time, and is fragile (depends on `__file__` resolution at runtime).
- **Evidence**:
  ```python
  # enhancement.py:72-73 (inside _preprocess_upcoming_chunks)
  import sys
  sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

  # enhancement.py:362-364 (inside get_mastering_recommendation)
  import sys
  sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

  # enhancement.py:406-407 (inside get_processing_parameters)
  import sys
  sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
  ```
  Each request adds a new duplicate entry to `sys.path`.
- **Impact**: `sys.path` grows indefinitely with duplicate entries. While not a crash risk, it slows import resolution and indicates fragile module layout. If the backend directory structure changes, these hardcoded paths break silently.
- **Suggested Fix**: Fix the module import structure so `chunked_processor` and other backend modules are importable without path manipulation. The `main.py` already adds the correct paths at startup — these handler-level insertions should be unnecessary.

---

### B-11: Zero test coverage for webm_streaming and cache_streamlined routers
- **Severity**: LOW
- **Dimension**: Test Coverage
- **Location**: `tests/backend/` (missing files)
- **Status**: NEW
- **Description**: The `webm_streaming.py` router (2 endpoints: metadata and chunk streaming) and `cache_streamlined.py` router (4 endpoints: stats, track status, clear, health) have zero test coverage. These are production endpoints that handle audio chunk delivery and cache management.
- **Evidence**: Search of `tests/backend/` found 54 test files covering other routers but none for:
  - `GET /api/stream/{track_id}/metadata`
  - `GET /api/stream/{track_id}/chunk/{chunk_idx}`
  - `GET /api/cache/stats`
  - `GET /api/cache/track/{track_id}/status`
  - `POST /api/cache/clear`
  - `GET /api/cache/health`
- **Impact**: Regressions in chunk streaming or cache management go undetected. The webm_streaming router has particularly complex logic (multi-tier cache lookup, on-demand processing, WAV encoding) that is error-prone without tests.
- **Suggested Fix**: Add test files `test_webm_streaming.py` and `test_cache_streamlined.py` covering at minimum: happy path metadata retrieval, chunk delivery (cache hit and miss), invalid track IDs, cache stats format, and cache clear behavior.

---

## Deduplication Summary

The following existing issues overlap with findings in this audit and were NOT re-reported:

| Existing Issue | Related Finding | Relationship |
|---------------|-----------------|--------------|
| #2114 | schemas.py dead code | Covers schema inconsistency dimension |
| #2112 | WebSocket preset/intensity validation | Covers WebSocket input validation |
| #2108 | Hardcoded Content-Type in artwork | Relates to artwork router issues |
| #2106 | Pause destroys streaming task | Relates to streaming lifecycle |
| #2103 | Decoupled enhancement configs | Relates to enhancement settings |
| #2101 | Scan request body mismatch | Related to B-04 (different angle) |
| #2094 | Unsafe HTML interpolation | Covers main.py fallback page |
| #2093 | FingerprintGenerator init failure silent | Covers fingerprint init |
| #2092 | Error response format inconsistency | Related to B-07 (different scope) |
| #2085 | WebSocket error recovery on chunk failure | Relates to streaming error handling |
| #2084 | Chunk cache not bounded by memory | Relates to B-02 (different mechanism) |
| #2080 | process_chunk_synchronized bypasses lock | Different from B-01 (sync vs async lock issue) |
| #2076 | WebSocket stream loop TOCTOU race | Relates to streaming task management |

---

## Audit Checklist Summary

### Dimension 1: Route Handler Correctness
- [x] All handlers are `async def` — **YES**, no sync handlers found
- [x] Input validation — **PARTIAL**: Request bodies validated with Pydantic where used, but ~60% of endpoints lack `response_model`
- [x] Error responses — **PARTIAL**: inconsistent format (existing #2092)
- [x] Route conflicts — **FOUND**: duplicate `/api/library/scan` (B-04)
- [x] Dependency injection — **GOOD**: factory pattern with closures works correctly

### Dimension 2: WebSocket Streaming
- [x] Connection lifecycle — **GOOD**: accept/close handled, resources cleaned in finally block
- [x] Backpressure — **MISSING** (B-03)
- [x] Multiple clients — **SUPPORTED**: per-connection task tracking via `_active_streaming_tasks`
- [x] Error during streaming — **PARTIAL**: errors sent to client but existing issues with recovery (#2085)
- [x] Heartbeat — **PRESENT**: ping/pong handled in message loop

### Dimension 3: Chunked Processing
- [x] Chunk boundaries — **GOOD**: tested extensively (80+ tests)
- [x] Crossfade — **GOOD**: server-side crossfade in enhanced path
- [x] Normal path padding — **FOUND**: silence padding breaks gapless (B-05)
- [x] Memory management — **ISSUE**: entire file loaded for normal streams (B-02)

### Dimension 4: Processing Engine
- [x] Engine lifecycle — **GOOD**: singleton per config, cached with LRU eviction
- [x] Async/sync boundary — **ISSUE**: multiple sync calls on event loop (B-01)
- [x] Timeouts — **MISSING** (B-06)

### Dimension 5: Schema Consistency
- [x] ~40% of routers use `response_model` declarations
- [x] schemas.py contains 569 lines of unused models (existing #2114)

### Dimension 6: Middleware & Configuration
- [x] CORS — **PROPERLY RESTRICTED**: explicit origin list, no wildcard
- [x] Router registration — **16 routers registered**: 1 duplicate route found (B-04)
- [x] Startup — **BLOCKING**: sync auto-scan delays startup (B-08)

### Dimension 7: Error Handling & Resilience
- [x] Global exception handler — **MISSING** (B-07)
- [x] Per-router error handling — **PARTIAL**: some use `handle_query_error()`, others use raw try/except

### Dimension 8: Performance & Resource Management
- [x] Event loop blocking — **PERVASIVE** (B-01)
- [x] Connection pooling — configured with `pool_pre_ping=True` (existing issues)
- [x] Memory — file loading is the main concern (B-02)

### Dimension 9: Test Coverage
- [x] 54 test files, 1033 tests, 25788 LOC
- [x] 2 routers with zero coverage (B-11)
- [x] WebSocket protocol well-tested (30+ tests)
- [x] Chunked processing well-tested (80+ tests)
- [x] 5 test files completely skipped (playlists, similarity, error handling, migrations, full stack)
