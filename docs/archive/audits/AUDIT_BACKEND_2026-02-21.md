# Backend Audit Report — 2026-02-21

**Scope**: FastAPI backend (routers, WebSocket, chunked processing, processing engine, schemas, middleware, services, security)
**Auditor**: Claude Opus 4.6
**Prior audits**: 2026-02-12, 2026-02-14, 2026-02-16, 2026-02-20
**Deduplication**: Verified against 42 open GitHub issues and ~51 prior audit findings

---

## Executive Summary

This audit found **9 NEW findings** (1 CRITICAL, 4 HIGH, 3 MEDIUM, 1 LOW) plus confirmed 15+ existing issues still open. The most critical finding is an **unvalidated file path in the processing API** that bypasses all path security controls present in other routers. Additionally, multiple chunk-duration constant mismatches could cause incorrect chunk calculations, and the path security module's allowed directory list is overly permissive.

| Severity | New | Existing (confirmed) |
|----------|-----|---------------------|
| CRITICAL | 1 | 0 |
| HIGH | 4 | 6 |
| MEDIUM | 3 | 12 |
| LOW | 1 | 5 |
| **Total** | **9** | **23** |

---

## NEW Findings

### BE-01: Processing API accepts arbitrary file paths without validation
- **Severity**: CRITICAL
- **Dimension**: Route Handlers / Security
- **Location**: `auralis-web/backend/routers/processing_api.py:83-126`
- **Status**: NEW → #2559
- **Description**: The `process_audio` endpoint accepts `input_path` directly from the request body and passes it to the processing engine without any path validation. Unlike other endpoints (library scan uses `validate_scan_path`, artwork uses `is_relative_to`, files.py validates magic bytes), processing_api.py performs zero path security checks. An attacker can process — and through `download_result`, retrieve — any readable file on the system.
- **Evidence**:
  ```python
  # processing_api.py:93-95 — NO path validation
  if not Path(request.input_path).exists():
      raise HTTPException(status_code=400, detail="Input file not found")
  # input_path could be "/etc/passwd", "~/.ssh/id_rsa", etc.

  # Compare with files.py which validates magic bytes, extension whitelist, size
  # Compare with library.py which uses validate_scan_path()
  # Compare with artwork.py which uses resolved_path.is_relative_to()
  ```
- **Impact**: Local privilege escalation. Any process or malicious webpage capable of sending HTTP requests to localhost:8765 can read arbitrary files by submitting them for "processing" and downloading the result. Even on a localhost-only Electron app, this is exploitable via CSRF or from other local processes.
- **Suggested Fix**: Add `validate_file_path(request.input_path)` from `security.path_security` before processing. Also validate `reference_path` if provided. Consider restricting to audio file extensions.

---

### BE-02: upload_and_process endpoint lacks file type, size, and content validation
- **Severity**: HIGH
- **Dimension**: Route Handlers / Security
- **Location**: `auralis-web/backend/routers/processing_api.py:129-184`
- **Status**: NEW → #2560
- **Description**: The `upload_and_process` endpoint accepts any uploaded file without validating file type, size, or content (magic bytes). By contrast, the `files.py` upload endpoint validates magic bytes against an audio format whitelist, checks extension, and enforces a 500MB size limit. This endpoint saves the file directly to `/tmp/auralis_uploads/` using the client-supplied filename.
- **Evidence**:
  ```python
  # processing_api.py:151-155 — NO validation
  filename = file.filename or "audio_file"
  input_path = temp_dir / filename       # Client-controlled filename
  with open(input_path, "wb") as f:
      content = await file.read()        # No size limit
      f.write(content)                   # No magic byte check

  # Compare with files.py which has:
  # - ALLOWED_AUDIO_EXTENSIONS whitelist
  # - AUDIO_MAGIC_BYTES validation
  # - MAX_UPLOAD_SIZE = 500 * 1024 * 1024
  ```
- **Impact**: (1) Disk exhaustion — unlimited file size upload. (2) Arbitrary file write — client-controlled filename could include path separators on some platforms. (3) Non-audio files processed, causing unpredictable engine behavior.
- **Suggested Fix**: Reuse the validation logic from `files.py` — validate extension, magic bytes, and enforce size limit. Sanitize filename (use `secure_filename` or generate UUID-based names).

---

### BE-03: download_result serves job output path without validation
- **Severity**: HIGH
- **Dimension**: Route Handlers / Security
- **Location**: `auralis-web/backend/routers/processing_api.py:206-238`
- **Status**: NEW → #2561
- **Description**: The `download_result` endpoint serves `job.output_path` as a `FileResponse` without validating the path against allowed directories. If `output_path` is corrupted, manipulated, or if a processing engine bug writes an unexpected path into the job record, arbitrary files could be served.
- **Evidence**:
  ```python
  # processing_api.py:222-234
  output_path = Path(job.output_path)      # No path validation
  if not output_path.exists():
      raise HTTPException(...)
  return FileResponse(path=str(output_path), ...)  # Serves any file
  ```
- **Impact**: Arbitrary file read if `output_path` can be influenced. Even if the processing engine currently writes correct paths, defense-in-depth requires validation at the serving boundary.
- **Suggested Fix**: Validate `output_path` against a known output directory (e.g., the temp processing dir). Reject paths outside expected locations.

---

### BE-04: Path security DEFAULT_ALLOWED_DIRS includes entire home directory
- **Severity**: HIGH
- **Dimension**: Security / Configuration
- **Location**: `auralis-web/backend/security/path_security.py:21-25`
- **Status**: NEW → #2562
- **Description**: `DEFAULT_ALLOWED_DIRS` includes `Path.home()`, making the entire home directory a valid base for `validate_file_path()` and `validate_scan_path()`. This means path validation permits access to `~/.ssh/`, `~/.gnupg/`, `~/.aws/`, `~/.config/`, browser profiles, and any other sensitive files under the home directory.
- **Evidence**:
  ```python
  # path_security.py:21-25
  DEFAULT_ALLOWED_DIRS = [
      Path.home(),           # ← Entire home dir allowed
      Path.home() / "Music",
      Path.home() / "Documents",
  ]
  ```
  Since `Path.home()` is a parent of `Music` and `Documents`, the latter two entries are redundant — everything under home is already allowed.
- **Impact**: The path validation provides a false sense of security. While it blocks access to `/etc/` and other system directories, it permits scanning/reading any file under the user's home directory, including credentials and private keys.
- **Suggested Fix**: Remove `Path.home()` from the defaults. Keep only `Music`, `Documents`, and `XDG_MUSIC_DIR`. Add a user-configurable allowlist for custom music library locations (stored in the app's config DB).

---

### BE-05: webm_streaming.py blocking mutagen.File() call on async event loop
- **Severity**: HIGH
- **Dimension**: Performance / Route Handlers
- **Location**: `auralis-web/backend/routers/webm_streaming.py:340-342`
- **Status**: NEW → #2563
- **Description**: Inside the chunk-serving endpoint, `mutagen.File(track.filepath)` performs synchronous file I/O (reads and parses audio metadata) directly on the async event loop. This blocks all concurrent request handling while the file is being read. The surrounding code already uses `asyncio.to_thread()` for other I/O operations, but this call was missed.
- **Evidence**:
  ```python
  # webm_streaming.py:340-342 — blocking I/O on event loop
  import mutagen
  audio_file = mutagen.File(track.filepath)
  track_duration = audio_file.info.length if audio_file else None

  # Compare with same file, line 330-333 — correctly offloaded:
  wav_bytes = await asyncio.wait_for(
      asyncio.to_thread(Path(chunk_path).read_bytes),
      timeout=10.0
  )
  ```
- **Impact**: Event loop starvation during metadata parsing, especially for large FLAC/WAV files. Other WebSocket connections and HTTP requests are blocked until mutagen completes.
- **Suggested Fix**: Wrap in `asyncio.to_thread()`: `audio_file = await asyncio.to_thread(mutagen.File, track.filepath)`. Add a timeout via `asyncio.wait_for()`.

---

### BE-06: CHUNK_DURATION constant mismatch across modules
- **Severity**: MEDIUM
- **Dimension**: Chunked Processing / Schema Consistency
- **Location**: `auralis-web/backend/routers/enhancement.py:35-37` vs `auralis-web/backend/core/chunked_processor.py:65-66`
- **Status**: NEW → #2564
- **Description**: The `CHUNK_DURATION` constant is defined independently in multiple modules with conflicting values:
  - `enhancement.py:37` → `CHUNK_DURATION = 10` (comment: "must match chunked_processor.py")
  - `chunked_processor.py:65` → `CHUNK_DURATION = 15`
  - `chunk_boundaries.py:17` → `CHUNK_DURATION = 15.0`
  - `cache/manager.py:27` → `CHUNK_DURATION = 15.0`

  The enhancement router's comment explicitly states it must match `chunked_processor.py`, but uses a different value (10 vs 15).
- **Evidence**:
  ```python
  # enhancement.py:35-37
  # Chunk configuration (must match chunked_processor.py)   ← Comment says "must match"
  CHUNK_DURATION = 10  # seconds per chunk                  ← But doesn't match (10 ≠ 15)

  # enhancement.py:107 — calculates WRONG chunk index
  current_chunk_idx = int(current_time / CHUNK_DURATION)  # Uses 10, should be 15

  # enhancement.py:115 — calculates WRONG total chunks
  total_chunks = int(total_duration / CHUNK_DURATION) + 1  # Uses 10, should be 15
  ```
- **Impact**: Enhancement pre-processing calculates wrong chunk indices. For a track at position 25s: enhancement.py computes chunk index 2 (`25/10`), but the actual chunk at that position is index 1 (`25/15` using `CHUNK_INTERVAL=10`). This wastes CPU processing wrong chunks and may miss the chunks actually needed.
- **Suggested Fix**: Import `CHUNK_DURATION` from `core.chunked_processor` or `core.chunk_boundaries` instead of redefining it. Better: create a single `core/constants.py` that all modules import from.

---

### BE-07: proactive_buffer.py dead code, hardcoded /tmp, and stale comments
- **Severity**: MEDIUM
- **Dimension**: Route Handlers / Performance
- **Location**: `auralis-web/backend/core/proactive_buffer.py:19,69,111`
- **Status**: NEW → #2565
- **Description**: Three issues in proactive_buffer.py:
  1. **Dead code** (line 69): String expression `f"{track_id}_{preset}_{intensity}_{chunk_idx}"` is evaluated but never assigned or used — likely a leftover from a removed cache key check.
  2. **Hardcoded /tmp path** (line 111): `get_buffer_status()` uses `Path("/tmp/auralis_chunks")` — this path may not match where `ChunkedAudioProcessor` actually stores chunks, causing the function to always return an empty set.
  3. **Stale comment** (line 19): `PRELOAD_CHUNKS = 3` says "Buffer first 90 seconds (3 x 30s chunks)" but actual chunks are 15s long, so it buffers 45 seconds.
- **Evidence**:
  ```python
  # Line 69 — dead code (string expression with no effect)
  f"{track_id}_{preset}_{intensity}_{chunk_idx}"
  chunk_path = processor._get_chunk_path(chunk_idx)

  # Line 111 — hardcoded /tmp path
  chunk_dir = Path("/tmp/auralis_chunks")

  # Line 19 — stale comment
  PRELOAD_CHUNKS = 3  # Buffer first 90 seconds (3 x 30s chunks)  ← actually 45s
  ```
- **Impact**: `get_buffer_status()` likely always returns empty set (wrong path), making buffer status checks useless. Dead code adds confusion during maintenance.
- **Suggested Fix**: Remove the dead code expression. Use `ChunkedAudioProcessor._get_chunk_path()` or a shared constant for the chunk directory instead of hardcoding `/tmp`. Fix the comment to say "45 seconds (3 x 15s chunks)".

---

### BE-08: Version endpoint fallback still out of sync (regression)
- **Severity**: MEDIUM
- **Dimension**: Schema Consistency / Configuration
- **Location**: `auralis-web/backend/routers/system.py:82-95`
- **Status**: Regression of prior audit B-18 (2026-02-16) → #2566
- **Description**: The version endpoint's fallback value shows `"1.2.1-beta.1"` but the source of truth (`auralis/version.py`) is `"1.2.0-beta.3"`. This was previously flagged as B-18 in the 2026-02-16 audit (which showed `"1.0.0-beta.1"`). The fallback was updated but is still wrong — the comment even says "Keep in sync with auralis/version.py — the single source of truth (fixes #2335)".
- **Evidence**:
  ```python
  # system.py:82-85
  # Keep in sync with auralis/version.py — the single source of truth (fixes #2335).
  return {
      "version": "1.2.1-beta.1",    # ← Wrong: should be 1.2.0-beta.3
      ...
      "display": "Auralis v1.2.1-beta.1"  # ← Also wrong
  }
  ```
- **Impact**: When the fallback path is triggered (broken install, import issue), clients see a wrong version. This could cause version-dependent compatibility checks to fail.
- **Suggested Fix**: Update to `"1.2.0-beta.3"` or — better — read `auralis/version.py` as a text file instead of importing it, so the fallback can never drift.

---

### BE-09: proactive_buffer.py ChunkedAudioProcessor instances never cleaned up
- **Severity**: LOW
- **Dimension**: Performance / Resource Management
- **Location**: `auralis-web/backend/core/proactive_buffer.py:58-63`
- **Status**: NEW → #2567
- **Description**: In `buffer_presets_for_track()`, a `ChunkedAudioProcessor` is created for each of the 5 presets but never explicitly cleaned up. If the processor holds file handles, numpy arrays, or other resources, these accumulate during buffering. The outer `except` at line 89 catches errors but doesn't ensure cleanup.
- **Evidence**:
  ```python
  # proactive_buffer.py:58-63 — processor created, never cleaned up
  for preset in AVAILABLE_PRESETS:          # 5 presets
      try:
          processor = ChunkedAudioProcessor(  # Resources allocated
              track_id=track_id,
              filepath=filepath,
              preset=preset,
              intensity=intensity
          )
          # ... use processor ...
          # No cleanup: processor goes out of scope with resources
  ```
- **Impact**: Potential memory pressure during proactive buffering (5 processors × audio metadata/arrays). Garbage collection will eventually reclaim, but explicit cleanup would be more predictable.
- **Suggested Fix**: Add a `close()` or `cleanup()` method to `ChunkedAudioProcessor` and call it in a `finally` block. Alternatively, implement `__enter__`/`__exit__` for context manager support.

---

## Confirmed Existing Issues (Still Open)

The following previously-reported issues were verified as still present:

| Issue | Title | Severity | Status |
|-------|-------|----------|--------|
| #2169 | Information disclosure via `str(e)` in error responses | MEDIUM | Open — confirmed in processing_api.py:126, webm_streaming.py:365 |
| #2129 | sys.path manipulation inside request handlers | LOW | Open — confirmed in enhancement.py:101-102, recommendation_service.py:72 |
| #2142 | Pydantic V1 `class Config` pattern in metadata router | MEDIUM | Open |
| #2224 | CORS allows all headers/methods with `allow_credentials=True` | MEDIUM | Open |
| #2126 | No global exception handler for unhandled errors | MEDIUM | Open |
| #2218 | Processor cache key ignores settings | MEDIUM | Open |
| #2186 | RepositoryFactory missing database connection pooling config | HIGH | Open |
| #2170 | Temp file TOCTOU in file upload handler | MEDIUM | Open |
| #2206 | WebSocket endpoint has no authentication | HIGH | Open |
| #2188 | Double crossfade (server + frontend) | HIGH | Open |
| #2106 | Backend pause destroys streaming task with no resume | HIGH | Open |
| #2334 | No concurrent WebSocket streaming stress tests | MEDIUM | Open |
| #2333 | Streaming timeout scenarios untested | MEDIUM | Open |
| #2281 | WebSocket correlation_id stripped by validation | MEDIUM | Open |
| #2256 | Backend play_enhanced ignores frontend-sent preset/intensity | MEDIUM | Open |
| #2257 | _send_pcm_chunk stereo framing produces oversized frames | MEDIUM | Open |
| #2171 | Backend position update loop drifts from actual playback | MEDIUM | Open |
| #2127 | Startup event blocks event loop with synchronous auto-scan | MEDIUM | Open |
| #2145 | asyncio.get_event_loop() deprecated in fingerprint generator | MEDIUM | Open |
| #2124 | stream_normal_audio pads last chunk with silence | MEDIUM | Open |
| #2092 | Error response format inconsistency across routers | LOW | Open |
| #2093 | FingerprintGenerator initialization failure silent | LOW | Open |
| #2172 | Bare except clause in lyrics extraction | LOW | Open |

---

## Dimension Coverage Summary

| Dimension | Findings | Key Observations |
|-----------|----------|-----------------|
| Route Handlers | BE-01, BE-02, BE-03 | processing_api.py is the only router without path validation |
| WebSocket Streaming | — | No new issues; existing #2206, #2188, #2106 still open |
| Chunked Processing | BE-06, BE-07 | Constant mismatch across modules; proactive buffer has dead code |
| Processing Engine | — | Existing issues (#2218 cache key, blocking calls) still open |
| Schema Consistency | BE-06, BE-08 | CHUNK_DURATION mismatch; version fallback drift |
| Middleware & Config | — | CORS issue (#2224) still open; no new middleware issues |
| Error Handling | — | str(e) disclosure (#2169) still pervasive; no global handler (#2126) |
| Performance | BE-05, BE-09 | Blocking mutagen call in webm_streaming; processor resource leak |
| Security | BE-01, BE-04 | Path traversal in processing API; overly broad allowed dirs |
| Test Coverage | — | Gaps from prior audits (#2333, #2334) still open |

---

## Methodology

1. Read all backend source files systematically (main.py, config/, routers/, core/, services/, security/, schemas.py)
2. Cross-referenced every finding against 42 open GitHub issues and 51 findings from 4 prior audit reports
3. Verified code evidence directly via file reads (not from memory/assumptions)
4. Severity assigned per the common audit protocol severity framework
5. Focused on genuinely NEW findings only — existing confirmed issues listed for tracking but not re-filed
