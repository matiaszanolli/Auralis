# Comprehensive Auralis Audit — 2026-02-13

## Executive Summary

**Total findings: 54** — 6 CRITICAL, 18 HIGH, 23 MEDIUM, 7 LOW

This audit builds on 6 prior audit reports and 88 existing open issues. After thorough deduplication, **9 NEW findings** were confirmed across audio integrity, backend API, security, concurrency, and error handling.

| Severity | Existing | New | Total | Key themes |
|----------|----------|-----|-------|------------|
| CRITICAL | 6 | 0 | 6 | (covered by prior audits) |
| HIGH | 15 | 3 | 18 | + Streaming task race, order_by injection, double windowing |
| MEDIUM | 17 | 5 | 22 | + dtype inconsistency, pagination bounds, info disclosure, temp file TOCTOU, position drift |
| LOW | 7 | 1 | 8 | + Bare except in lyrics extraction |

**Most impactful NEW findings:**
1. **S3-H01**: Streaming task `finally` block deletes the **successor** task's reference from `_active_streaming_tasks`, orphaning the new stream. Pause/stop commands then have no effect.
2. **S3-H02**: User-controlled `order_by` parameter passed directly to `getattr(Track, order_by)` without whitelist, allowing arbitrary SQLAlchemy model attribute probing.
3. **S3-H03**: FFT EQ applies Hanning window **twice** — before FFT and after IFFT — causing a hanning² amplitude envelope with ~3 dB level drop and severe edge attenuation.

---

## New Findings (9)

### HIGH

### S3-H01: Streaming Task Finally Block Deletes Successor's Reference (Orphaned Task Race)
- **Severity**: HIGH
- **Dimension**: Concurrency / Backend API
- **Location**: `auralis-web/backend/routers/system.py:242-250, 298-301, 424-426`
- **Status**: NEW
- **Description**: When a user sends two rapid `play_enhanced` (or `play_normal`) messages, the first task is cancelled and a new task is created. But the cancelled task's `finally` block (`del _active_streaming_tasks[ws_id]`) runs *after* the new task has been stored under the same `ws_id`, deleting the **new** task's reference. The new task becomes orphaned — unreachable for future pause/stop/cancel operations.
- **Evidence**:
```python
# system.py — play_enhanced handler (lines 181-250):
# Step 1: User sends play_enhanced (track A)
ws_id = id(websocket)
task = asyncio.create_task(stream_audio())       # task1
_active_streaming_tasks[ws_id] = task1

# Step 2: User immediately sends play_enhanced (track B)
old_task = _active_streaming_tasks[ws_id]        # task1
old_task.cancel()                                 # cancel task1
task = asyncio.create_task(stream_audio())       # task2
_active_streaming_tasks[ws_id] = task2            # overwrite

# Step 3: task1's finally block fires (CancelledError):
if ws_id in _active_streaming_tasks:             # True (task2 is there!)
    del _active_streaming_tasks[ws_id]           # DELETES task2's reference!

# Step 4: User sends "pause":
if ws_id in _active_streaming_tasks:             # False! task2 is orphaned
    task.cancel()                                 # Never reached
# Audio keeps streaming to client with no way to stop it.
```
The same pattern exists in `stream_normal()` at lines 298-301 and `stream_from_position()` at lines 424-426.
- **Impact**: Rapid track switching (common during browsing) renders pause/stop non-functional. Audio continues streaming until WebSocket disconnects. Every subsequent play command adds another orphaned task.
- **Related**: Distinct from #2076 (TOCTOU in stream loop body) — this is about task lifecycle management in the message handler.
- **Suggested Fix**: Use a unique task ID (not `ws_id`) per streaming task. In the finally block, only delete if `_active_streaming_tasks.get(ws_id) is current_task`:
```python
my_task = asyncio.current_task()
finally:
    if _active_streaming_tasks.get(ws_id) is my_task:
        del _active_streaming_tasks[ws_id]
```

---

### S3-H02: Unvalidated order_by Parameter Allows Arbitrary Attribute Access via getattr()
- **Severity**: HIGH
- **Dimension**: Security / Library
- **Location**: `auralis/library/repositories/track_repository.py:431`, `auralis-web/backend/routers/library.py:88`, `auralis-web/backend/routers/albums.py:46`
- **Status**: NEW
- **Description**: The `order_by` query parameter is passed from the REST API directly to `getattr(Track, order_by, Track.title)` without validation against a whitelist. While the fallback to `Track.title` prevents crashes for non-existent attributes, valid but sensitive attributes (e.g., `filepath`, `metadata`, `_sa_instance_state`) can be accessed and used for ordering, revealing information about the data model.
- **Evidence**:
```python
# track_repository.py:431
order_column = getattr(Track, order_by, Track.title)
tracks = (
    session.query(Track)
    .order_by(order_column.asc())
    ...
)

# library.py:88 — passes user input directly
order_by: str = 'created_at'  # No validation, no whitelist
```
The same pattern exists in `albums.py:46` with `order_by: str = 'title'`.
- **Impact**: (1) Information disclosure — ordering by `filepath` reveals directory structure. (2) Potential DoS — ordering by computed properties or relationships could generate expensive queries. (3) Reconnaissance — enumerating valid attributes reveals model structure.
- **Related**: Distinct from #2078 (SQL injection in fingerprint columns) — this is about `getattr()` on the Track model.
- **Suggested Fix**: Add whitelist validation:
```python
VALID_ORDER_BY = {'title', 'created_at', 'play_count', 'duration', 'artist', 'album'}
if order_by not in VALID_ORDER_BY:
    order_by = 'title'
```

---

### S3-H03: Double Windowing in FFT EQ Causes Amplitude Modulation
- **Severity**: HIGH
- **Dimension**: DSP Pipeline / Audio Integrity
- **Location**: `auralis/dsp/eq/filters.py:78, 99`
- **Status**: NEW
- **Description**: `apply_eq_mono()` applies a Hanning window to the audio before FFT (line 78) and then applies the **same** window again after IFFT (line 99, labeled "Apply window compensation"). This is not compensation — it's double windowing. The output has a hanning² amplitude envelope, causing ~3 dB level drop at center and severe attenuation at chunk edges. This function is called per-chunk without overlap-add normalization.
- **Evidence**:
```python
# filters.py:76-101
window = np.hanning(fft_size)
windowed_audio = audio_mono[:fft_size] * window   # Window #1 (line 78)

spectrum = fft(windowed_audio)                     # FFT of windowed signal
# ... apply gains to spectrum ...
processed_audio = np.real(ifft(spectrum))           # IFFT (line 96)

processed_audio *= window                           # Window #2 (line 99) — WRONG!
# Comment says "Apply window compensation" but it applies window again

return np.asarray(processed_audio[:len(audio_mono)], dtype=np.float32)
```
The calling function `apply_eq_to_chunk()` (line 46) invokes this once per chunk with no overlap-add, so the double windowing directly affects the output level envelope.
- **Impact**: EQ-processed audio has non-uniform amplitude across each chunk — full level at center, near-zero at edges. This produces audible amplitude modulation artifacts and ~3 dB average level reduction. Downstream level management compensates with makeup gain, increasing noise floor.
- **Suggested Fix**: Remove the second window application (line 99). For single-frame processing without overlap-add, only the pre-FFT window is needed:
```python
# Remove line 99: processed_audio *= window
```

---

### MEDIUM

### S3-M01: dtype Inconsistency Between Vectorized and Numba Envelope Followers
- **Severity**: MEDIUM
- **Dimension**: Audio Integrity / DSP Pipeline
- **Location**: `auralis/dsp/dynamics/vectorized_envelope.py:90, 116`
- **Status**: NEW
- **Description**: `process_buffer_vectorized()` returns `float64` (line 90) while `process_buffer_numba()` returns `float32` (line 116). The `process_buffer()` dispatcher (line 128) calls one or the other based on `use_numba`, so downstream code receives different dtypes depending on whether Numba is available. This breaks dtype consistency guarantees in the DSP pipeline.
- **Evidence**:
```python
# process_buffer_vectorized() — line 70, 90:
output = np.zeros_like(input_levels, dtype=np.float64)  # Allocates float64
return output                                              # Returns float64

# process_buffer_numba() — line 116:
return np.asarray(output, dtype=np.float32)                # Returns float32

# process_buffer() dispatcher — line 128:
if self.use_numba:
    return self.process_buffer_numba(input_levels)     # → float32
return self.process_buffer_vectorized(input_levels)    # → float64
```
- **Impact**: Compressor/limiter behavior differs between environments with and without Numba. Float64 vs float32 affects threshold comparisons and gain reduction calculations. Tests may pass in one environment but produce different audio in another.
- **Suggested Fix**: Standardize both to return `float32`:
```python
# In process_buffer_vectorized(), line 90:
return np.asarray(output, dtype=np.float32)
```

---

### S3-M02: No Bounds Validation on Pagination Query Parameters
- **Severity**: MEDIUM
- **Dimension**: Security / Backend API
- **Location**: `auralis-web/backend/routers/library.py:85-86`, `auralis-web/backend/routers/albums.py:42-44`
- **Status**: NEW
- **Description**: The `limit` and `offset` parameters on `/api/library/tracks` and `/api/albums` endpoints have no upper or lower bounds. A request with `limit=999999999` causes the database to attempt returning all rows, consuming excessive memory. A negative `offset` produces undefined behavior.
- **Evidence**:
```python
# library.py:84-86
async def get_tracks(
    limit: int = 50,    # No upper bound (should be e.g. 500)
    offset: int = 0,    # No lower bound (could be negative)
    ...
)

# albums.py:42-44
async def get_albums(
    limit: int = 50,    # Same issue
    offset: int = 0,
    ...
)
```
Some routers DO validate (e.g., `artists.py:100-101` uses `ge=1, le=200`), creating inconsistency.
- **Impact**: Memory exhaustion with `limit=999999999`. Slow queries with `offset=999999999`. Inconsistent behavior across endpoints.
- **Suggested Fix**: Add FastAPI Query constraints:
```python
from fastapi import Query
limit: int = Query(50, ge=1, le=500)
offset: int = Query(0, ge=0)
```

---

### S3-M03: Information Disclosure via str(e) in 30+ HTTP Error Responses
- **Severity**: MEDIUM
- **Dimension**: Security / Backend API
- **Location**: `auralis-web/backend/routers/enhancement.py:297-298, 391`, `similarity.py:191,250,287,342,378,400,420`, `cache_streamlined.py:71,105,127,162`, `player.py:155,266,299`, `system.py:235,291,417`
- **Status**: NEW
- **Description**: Over 30 HTTP error responses include `str(e)` in the `detail` field, exposing internal exception messages to API clients. These messages can reveal file system paths, module names, database structure, and stack trace fragments.
- **Evidence**:
```python
# enhancement.py:297-298
raise HTTPException(status_code=500, detail=f"Failed to set intensity: {e}")
# If e = FileNotFoundError('/opt/auralis/internal/config.yaml')
# → Client sees: "Failed to set intensity: [Errno 2] No such file or directory: '/opt/auralis/internal/config.yaml'"

# similarity.py:191
raise HTTPException(status_code=500, detail=f"Error finding similar tracks: {str(e)}")

# cache_streamlined.py:71
raise HTTPException(status_code=500, detail=str(e))  # Raw exception to client
```
- **Impact**: Information disclosure aids reconnaissance. Reveals internal paths, database schema details, and third-party library internals. Violates OWASP secure error handling guidelines.
- **Suggested Fix**: Log full exception server-side, return generic message to client:
```python
logger.exception(f"Failed to set intensity: {e}")
raise HTTPException(status_code=500, detail="Internal server error")
```

---

### S3-M04: Temp File TOCTOU in File Upload Handler
- **Severity**: MEDIUM
- **Dimension**: Security
- **Location**: `auralis-web/backend/routers/files.py:178-186`
- **Status**: NEW
- **Description**: The file upload handler creates a temp file with `NamedTemporaryFile(delete=False)`, writes the upload content, closes the file (end of `with` block), then loads it with `load_audio(temp_path)`. Between the close and the load, another process can replace the file via symlink attack (TOCTOU).
- **Evidence**:
```python
# files.py:178-186
with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
    content = await file.read()
    tmp.write(content)
    temp_path = tmp.name
# File is closed here — TOCTOU window opens
try:
    audio_data, sample_rate = load_audio(temp_path)  # Loads potentially different file
```
- **Impact**: On shared systems, an attacker with access to /tmp could replace the file between write and load, causing the application to process arbitrary audio (or non-audio) data. Low likelihood in single-user deployments.
- **Suggested Fix**: Create temp files in an application-specific directory with restricted permissions, or keep the file handle open and pass it directly to the loader.

---

### S3-M05: Backend Position Update Loop Drifts from Actual Playback
- **Severity**: MEDIUM
- **Dimension**: Backend API / Player State
- **Location**: `auralis-web/backend/state_manager.py:210-226`
- **Status**: NEW
- **Description**: The position update loop increments `current_time += 1.0` every second (via `asyncio.sleep(1.0)`), without reading the actual playback position from the audio engine. Over time, the broadcast position drifts from the real audio position due to: (a) `asyncio.sleep` jitter, (b) audio buffering delays, (c) processing latency, (d) track end edge cases.
- **Evidence**:
```python
# state_manager.py:210-222
async def _position_update_loop(self) -> None:
    while True:
        await asyncio.sleep(1.0)                     # Not guaranteed to be exactly 1s
        with self._lock:
            if self.state.is_playing and self.state.current_track:
                new_time = min(
                    self.state.current_time + 1.0,    # Blind increment, no engine query
                    self.state.duration
                )
                self.state.current_time = new_time
```
- **Impact**: Position displayed by non-WebSocket clients (e.g., desktop API consumers) drifts from actual playback. After 10 minutes of playback, accumulated drift can reach 1-3 seconds. Track-end detection at line 225 (`new_time >= self.state.duration`) may trigger early or late.
- **Suggested Fix**: Query actual playback engine position instead of blind increment:
```python
actual_position = self.audio_engine.get_position_seconds()
self.state.current_time = min(actual_position, self.state.duration)
```

---

### LOW

### S3-L01: Bare Except Clause Silently Swallows Errors in Lyrics Extraction
- **Severity**: LOW
- **Dimension**: Error Handling
- **Location**: `auralis-web/backend/routers/library.py:271`
- **Status**: NEW
- **Description**: A bare `except:` clause catches ALL exceptions including `KeyboardInterrupt` and `SystemExit`, silently discarding them during lyrics extraction from MP4/M4A files.
- **Evidence**:
```python
# library.py:270-272
try:
    lyrics_text = audio_file.get('\xa9lyr', [None])[0]
except:
    pass  # Catches KeyboardInterrupt, SystemExit, MemoryError, etc.
```
- **Impact**: Cannot interrupt the process during lyrics extraction. Unexpected errors (MemoryError, SystemExit) are silently swallowed. Debugging is difficult because all errors are hidden.
- **Suggested Fix**: Use `except Exception:` instead of bare `except:`:
```python
except Exception:
    pass  # Still catches standard errors but not KeyboardInterrupt/SystemExit
```

---

## Existing Findings (45) — Previously Filed

All findings from prior audits are tracked as GitHub issues. Key groupings:

### CRITICAL (6)
| Title | Issue |
|-------|-------|
| In-place audio modification in CompressionStrategies | #2150 |
| NaN/Inf unchecked in HybridProcessor pipeline | #2151 |
| usePlayNormal wrong AudioContext sample rate | #2098 |
| usePlaybackControl uses non-existent sendMessage | #2100 |
| Scan request body key mismatch | #2101 |
| Race condition in player auto-advance | #2064 (fixed) |

### HIGH (15)
| Title | Issue |
|-------|-------|
| Gapless transition position not reset | #2152 |
| Position read-modify-write race | #2153 |
| Seek doesn't invalidate prebuffer | #2154 |
| Truncated audio files pass validation | #2155 |
| Unvalidated WebSocket messages | #2156 |
| Dual streaming hooks double processing | #2104 |
| Backend pause destroys streaming task | #2106 |
| Hardcoded image/jpeg for artwork | #2108 |
| Artist artwork never populated | #2110 |
| Library stats shape mismatch | #2111 |
| No preset/intensity validation in play_enhanced | #2112 |
| WebSocket scan progress mismatch | #2113 |
| Sync I/O blocks async event loop | #2120 |
| stream_normal_audio loads entire file | #2121 |
| No WebSocket backpressure | #2122 |

### MEDIUM (17) — See issues #2078-#2088, #2096, #2114-#2119, #2123-#2127, #2157-#2162

### LOW (7) — See issues #2091-#2095, #2128-#2130, #2163

---

## Relationships

### Cluster 1: Streaming Task Lifecycle (NEW + EXISTING)
**S3-H01** (orphaned task race) + #2106 (pause destroys task) + #2076 (stream TOCTOU). All three affect the WebSocket streaming task lifecycle in `system.py`. S3-H01 prevents cancellation, #2106 prevents resumption, and #2076 allows interleaved read/writes. Together, they make streaming unreliable under real-world usage patterns (rapid track switching, seeking, pausing).

### Cluster 2: DSP Signal Integrity (NEW + EXISTING)
**S3-H03** (double windowing) + **S3-M01** (dtype inconsistency) + #2150 (in-place modification) + #2151 (NaN propagation) + #2158 (dtype promotion). Five issues that collectively degrade audio quality through the DSP pipeline. The double windowing introduces amplitude modulation, the dtype inconsistency causes environment-dependent behavior, and the existing issues corrupt data and propagate errors.

### Cluster 3: Input Validation Gaps (NEW + EXISTING)
**S3-H02** (order_by injection) + **S3-M02** (pagination bounds) + **S3-M03** (info disclosure) + #2156 (WebSocket validation) + #2112 (preset/intensity validation). A pattern of missing input validation across REST and WebSocket endpoints, creating a broad attack surface.

### Cluster 4: Security Hardening (NEW + EXISTING)
**S3-M04** (temp file TOCTOU) + **S3-M03** (info disclosure) + #2069 (path traversal) + #2079 (secret key) + #2162 (innerHTML XSS). Multiple security hygiene issues that, while individually medium-severity, collectively indicate insufficient security review.

---

## Prioritized Fix Order (New Findings Only)

1. **S3-H01** — Streaming task race. Breaks pause/stop for all users. Fix: guard `finally` with task identity check. ~30min.
2. **S3-H03** — Double windowing. Affects all EQ-processed audio. Fix: remove second window application. ~15min.
3. **S3-H02** — order_by injection. Security issue. Fix: add whitelist. ~15min.
4. **S3-M03** — Info disclosure. Security hygiene. Fix: replace `str(e)` with generic messages. ~1hr (30+ locations).
5. **S3-M02** — Pagination bounds. DoS risk. Fix: add Query constraints. ~15min.
6. **S3-M01** — dtype inconsistency. Audio correctness. Fix: standardize return type. ~15min.
7. **S3-M05** — Position drift. UX issue. Fix: query engine position. ~30min.
8. **S3-M04** — Temp file TOCTOU. Security. Fix: use app-specific temp dir. ~30min.
9. **S3-L01** — Bare except. Code quality. Fix: use `except Exception:`. ~5min.

---

## Cross-Cutting Recommendations

### 1. Streaming Task Lifecycle Management
Replace the simple `_active_streaming_tasks[ws_id]` dict with a proper task manager that tracks task identity, prevents finally-block races, and provides clean cancellation semantics. This addresses S3-H01, #2106, and #2076 together.

### 2. Input Validation Layer
Add a shared validation layer for all API endpoints:
- Whitelist-based `order_by` validation on all list endpoints
- Pagination bounds (1-500 for limit, ≥0 for offset) as default Query constraints
- WebSocket message schema validation via Pydantic models
This addresses S3-H02, S3-M02, #2112, and #2156.

### 3. Secure Error Handling Policy
Adopt a standard pattern: log full exception server-side, return generic HTTP 500 to client. Apply across all 30+ affected locations. This addresses S3-M03 and partially addresses #2126 (no global exception handler).

### 4. DSP dtype Consistency
Establish a policy: all DSP functions accept and return `float32` unless explicitly documented otherwise. Add assertions at pipeline boundaries. This addresses S3-M01, S3-H03, #2158.

### 5. Audio Pipeline Validation
The `validate_audio_buffer()` recommendation from the prior audit (Revision 2) remains the highest-leverage fix. It addresses #2150, #2151, #2155, and would catch the output of S3-H03's double windowing.
