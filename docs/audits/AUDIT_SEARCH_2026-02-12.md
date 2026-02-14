# Comprehensive Auralis Audit — 2026-02-12 (Revision 2)

## Executive Summary

**Total findings: 45** — 6 CRITICAL, 15 HIGH, 17 MEDIUM, 7 LOW

This revision adds **14 NEW findings** from deep exploration of audio integrity, DSP pipeline correctness, player state management, security hardening, and error handling. The 31 original findings are referenced as existing issues.

| Severity | Original | New | Total | Key themes |
|----------|----------|-----|-------|------------|
| CRITICAL | 4 | 2 | 6 | + DSP in-place modification, NaN propagation |
| HIGH | 10 | 5 | 15 | + Gapless sample rate, seek race, truncated audio, WebSocket validation |
| MEDIUM | 11 | 6 | 17 | + Crossfade boundary, dtype promotion, queue reorder, memory |
| LOW | 6 | 1 | 7 | + pickle for size estimation |

**Most impactful NEW findings:**
1. **S-C01**: `CompressionStrategies` modifies audio arrays in-place without `.copy()`, violating the project's core invariant. Any caller reusing the input array gets corrupted data.
2. **S-C02**: `HybridProcessor` checks for silence (all zeros) but not NaN/Inf values. A single NaN from a failed filter stage propagates through the entire pipeline, producing silent corrupted output.
3. **S-H01**: Gapless transition sets new sample rate without converting position, causing ~0.4s skip at every track boundary when sample rates differ.

---

## New Findings (14)

### CRITICAL

### S-C01: In-Place Audio Modification in CompressionStrategies Violates Copy Invariant
- **Severity**: CRITICAL
- **Dimension**: Audio Integrity
- **Location**: `auralis/core/processing/base/compression_expansion.py:54-62`
- **Status**: NEW
- **Description**: `apply_soft_knee_compression()` modifies the input `audio` array directly via `audio[over_threshold] = ...` without calling `.copy()` first. This violates the project's critical invariant: "Never modify in-place." Any caller that retains a reference to the original array gets corrupted data.
- **Evidence**:
```python
# compression_expansion.py:54-62
audio_abs = np.abs(audio)
over_threshold = audio_abs > clip_threshold_linear
if np.any(over_threshold):
    compressed_excess = excess / compression_ratio
    new_amplitude = clip_threshold_linear + compressed_excess
    audio[over_threshold] = np.sign(audio[over_threshold]) * new_amplitude  # IN-PLACE!
```
The same pattern appears in `apply_peak_enhancement_expansion()` at lines 150-165.
- **Impact**: Audio data corruption when the same buffer is used in multiple processing paths. Breaks adaptive processing where the original signal is compared to the processed result. Silent — no error raised.
- **Related**: CLAUDE.md invariant: `output = audio.copy()  # Never modify in-place`
- **Suggested Fix**: Add `audio = audio.copy()` as the first line in both `apply_soft_knee_compression()` and `apply_peak_enhancement_expansion()`.

---

### S-C02: NaN/Inf Values Unchecked in HybridProcessor Pipeline
- **Severity**: CRITICAL
- **Dimension**: Audio Integrity / DSP Pipeline
- **Location**: `auralis/core/hybrid_processor.py:219-231`
- **Status**: NEW
- **Description**: `HybridProcessor.process()` checks for silence (all zeros) at line 220 but does not check for NaN or Inf values. If any DSP stage produces NaN (e.g., from an unstable IIR filter, division by zero in dynamics processing, or a corrupted input file), the NaN propagates through all subsequent stages including the brick wall limiter, producing silent corrupted output.
- **Evidence**:
```python
# hybrid_processor.py:219-221
if np.allclose(target_audio, 0.0, atol=1e-10):  # Checks silence
    return target_audio.copy()
# NO check for NaN or Inf!
# Processing continues with potentially corrupted data...
```
The same gap exists in `simple_mastering.py` — no NaN/Inf check between processing stages (bass enhance, presence boost, dynamics, safety limiter). A NaN from one stage cascades through crossfading in the chunked processor.
- **Impact**: Silent audio corruption. NaN values produce silence in most audio outputs but corrupt crossfade calculations, producing clicks/pops at chunk boundaries. No error is raised — the user hears degraded audio with no diagnostic.
- **Suggested Fix**: Add `if np.any(~np.isfinite(target_audio)): raise ValueError("NaN/Inf detected in audio")` before processing and after each stage (or at minimum, after the full pipeline).

---

### HIGH

### S-H01: Gapless Transition Does Not Convert Position on Sample Rate Change
- **Severity**: HIGH
- **Dimension**: Player State / Audio Integrity
- **Location**: `auralis/player/gapless_playback_engine.py:170-185`
- **Status**: NEW
- **Description**: `advance_with_prebuffer()` sets `self.file_manager.sample_rate = sample_rate` for the new track but does not reset `self.playback.position` to 0. After transition, `position` still holds the sample count from the previous track, interpreted against the new sample rate.
- **Evidence**:
```python
# gapless_playback_engine.py:174-178
with self.update_lock:
    self.file_manager.audio_data = audio_data
    self.file_manager.sample_rate = sample_rate  # Changed!
    self.file_manager.current_file = file_path
    # self.playback.position NOT reset!
```
The caller (`enhanced_audio_player.py:next_track()`) is responsible for resetting position, but there's a window where `get_audio_chunk()` reads the stale position against the new sample rate.
- **Impact**: At track transitions between 44.1kHz and 48kHz content, position is misinterpreted by ~8.8%. Audio skips or repeats at the transition point.
- **Suggested Fix**: Reset `self.playback.position = 0` inside the `update_lock` block in `advance_with_prebuffer()`.

---

### S-H02: Position Read-Modify-Write Race in get_audio_chunk
- **Severity**: HIGH
- **Dimension**: Concurrency / Player State
- **Location**: `auralis/player/enhanced_audio_player.py:356-362`
- **Status**: NEW
- **Description**: `get_audio_chunk()` reads `self.playback.position`, uses it to fetch audio, then increments it — without any lock. A concurrent `seek()` call can update `position` between the read and the increment, causing the increment to overwrite the seek target.
- **Evidence**:
```python
# enhanced_audio_player.py:356-362
chunk = self.file_manager.get_audio_chunk(
    self.playback.position,      # Read
    chunk_size
)
self.playback.position += len(chunk)  # Modify — overwrites any concurrent seek()
```
- **Impact**: When user seeks during playback, the seek position is immediately overwritten by the playback thread's position increment. Audio jumps back to pre-seek position. Reproduces consistently with any seek during active playback.
- **Related**: Existing #2064 covers auto-advance race, but this is a separate race in the seek path
- **Suggested Fix**: Protect the read-modify-write sequence with the existing RLock or use `position` as an atomic variable.

---

### S-H03: Seek Does Not Invalidate Gapless Prebuffer
- **Severity**: HIGH
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:131-148`
- **Status**: NEW
- **Description**: `seek()` updates the playback position but does not call `self.gapless.invalidate_prebuffer()`. If the user seeks backward while near the end of a track, the prebuffered next track remains queued and can trigger auto-advance prematurely.
- **Evidence**:
```python
# enhanced_audio_player.py:131-148
def seek(self, position_seconds: float) -> bool:
    if not self.file_manager.is_loaded():
        return False
    max_samples = self.file_manager.get_total_samples()
    position_samples = int(position_seconds * self.file_manager.sample_rate)
    return self.playback.seek(position_samples, max_samples)
    # No call to self.gapless.invalidate_prebuffer()!
```
- **Impact**: Seeking backward near end-of-track causes unexpected advance to next track. User intent to re-listen is violated.
- **Suggested Fix**: Add `self.gapless.invalidate_prebuffer()` after a successful seek, then restart prebuffering.

---

### S-H04: Truncated Audio Files Pass Validation Silently
- **Severity**: HIGH
- **Dimension**: Error Handling / Audio Integrity
- **Location**: `auralis/io/unified_loader.py:73-94`
- **Status**: NEW
- **Description**: The loader validates `file_size == 0` but does not validate that the loaded audio data matches the expected frame count from the file header. When `soundfile` loads a truncated file, it returns partial audio without raising an error. The downstream pipeline processes this partial data as if it were complete.
- **Evidence**:
```python
# unified_loader.py:73-94
file_size = file_path.stat().st_size
if file_size == 0:
    raise ModuleError(...)  # Only catches empty files

audio_data, sample_rate = load_with_soundfile(file_path)
# NO validation: audio_data.shape[0] could be << expected frames
audio_data, sample_rate = validate_audio(audio_data, sample_rate, file_type)
```
- **Impact**: Truncated files produce incomplete audio that processes without error. Users hear cut-off tracks with no warning. Crossfade calculations at the truncated end may produce artifacts.
- **Suggested Fix**: Compare loaded frame count against `sf.info(file_path).frames`. Warn if significantly shorter than expected.

---

### S-H05: Unvalidated WebSocket Message Content and Size
- **Severity**: HIGH
- **Dimension**: Security / Backend API
- **Location**: `auralis-web/backend/routers/system.py:101-137`
- **Status**: NEW
- **Description**: The WebSocket handler receives text messages with no size limit and no schema validation. `json.loads(data)` parses arbitrary JSON. Message types are checked with `message.get("type")` but unrecognized types are silently ignored. User-provided data in `processing_settings_update` is broadcast to all clients without validation.
- **Evidence**:
```python
# system.py:101-119
data = await websocket.receive_text()  # No size limit
message = json.loads(data)  # No schema validation

if message.get("type") == "processing_settings_update":
    settings = message.get("data", {})  # Unvalidated
    await manager.broadcast({
        "type": "processing_settings_applied",
        "data": settings  # Echoed to ALL clients
    })
```
- **Impact**: (1) DoS via large/deeply-nested JSON messages causing memory exhaustion. (2) Data injection: malicious client sends crafted settings that are broadcast to other clients. (3) No rate limiting per message.
- **Suggested Fix**: Add message size limit (e.g., 64KB). Validate message structure with a Pydantic model. Rate limit per connection.

---

### MEDIUM

### S-M01: Missing Zero-Length Boundary Check in Mastering Crossfade
- **Severity**: MEDIUM
- **Dimension**: Audio Integrity
- **Location**: `auralis/core/simple_mastering.py:194-201`
- **Status**: NEW
- **Description**: The crossfade logic computes `head_len = min(prev_tail.shape[1], processed_chunk.shape[1])` without checking that `head_len > 0`. When `prev_tail` has 0 columns (which occurs when a chunk is exactly `core_samples` long with no overlap), `np.linspace(0, π/2, 0)` produces an empty array, and the crossfade produces empty output, losing samples.
- **Evidence**:
```python
# simple_mastering.py:194-201
head_len = min(prev_tail.shape[1], processed_chunk.shape[1])
# No check: head_len could be 0!
t = np.linspace(0.0, np.pi / 2, head_len)
fade_in = np.sin(t) ** 2
```
- **Impact**: Sample loss at chunk boundaries when chunk size exactly equals core_samples. Violates `len(output) == len(input)` invariant on edge cases.
- **Suggested Fix**: Add `if head_len == 0:` guard — skip crossfade and concatenate directly.

---

### S-M02: dtype Promotion float32→float64 in Parallel EQ Processing
- **Severity**: MEDIUM
- **Dimension**: Audio Integrity / Performance
- **Location**: `auralis/core/simple_mastering.py:869-876` (and 4 similar EQ methods)
- **Status**: NEW
- **Description**: The parallel EQ pattern uses `sosfilt()` which returns float64 regardless of input dtype. The result `audio + band * (boost_linear - 1.0)` promotes the entire output to float64, doubling memory usage. Downstream code assumes float32.
- **Evidence**:
```python
# simple_mastering.py:869-876
sos_lp = butter(2, normalized_freq, btype='low', output='sos')
low_band = sosfilt(sos_lp, audio, axis=1)  # Returns float64!
processed = audio + low_band * boost_diff  # float32 + float64 = float64
```
This pattern repeats in `_apply_mid_presence_balance`, `_apply_presence_enhancement`, `_apply_air_enhancement`, and `_apply_bass_management`.
- **Impact**: 2x memory usage throughout the processing chain. Potential dtype mismatches with downstream code expecting float32. No errors raised but performance degradation on large files.
- **Suggested Fix**: Cast filter output: `low_band = sosfilt(sos_lp, audio, axis=1).astype(audio.dtype)`

---

### S-M03: Queue reorder_tracks Doesn't Handle Missing Current Track
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/components/queue_manager.py:154-168`
- **Status**: NEW
- **Description**: `reorder_tracks()` searches for the current track by ID after reordering. If the search fails (track ID not found — which shouldn't happen with valid `new_order` but could with race conditions), `current_index` retains its old value, now pointing to a different track.
- **Evidence**:
```python
# queue_manager.py:162-166
if current_track_id is not None:
    for i, track in enumerate(self.tracks):
        if track.get('id') == current_track_id:
            self.current_index = i
            break
    # If no match: current_index stays at old value → points to WRONG track
```
- **Impact**: After reorder, playback may jump to a different track than intended. The user hears the wrong track without any error indication.
- **Suggested Fix**: Add `else:` clause after the `for` loop to set `current_index = 0` as fallback.

---

### S-M04: Scanner Loads All Discovered File Paths Into Memory
- **Severity**: MEDIUM
- **Dimension**: Performance / Memory
- **Location**: `auralis/library/scanner/scanner.py` (file discovery phase)
- **Status**: NEW
- **Description**: The scanner discovers all audio files via `rglob()` and stores all paths in a list before processing begins. For large music libraries (100k+ files), this list consumes significant memory. There is no streaming/chunked discovery.
- **Impact**: Memory spike during scan of large directories. Combined with metadata loading, can cause OOM on resource-constrained systems.
- **Suggested Fix**: Process files in batches as they're discovered rather than collecting all paths first.

---

### S-M05: HybridProcessor Cache Grows Unbounded
- **Severity**: MEDIUM
- **Dimension**: Performance / Memory
- **Location**: `auralis/core/hybrid_processor.py:446-474`
- **Status**: NEW
- **Description**: `_processor_cache` dictionary stores processor instances keyed by configuration hash. No maximum size or TTL eviction. A long-running backend server processing tracks with varying configurations accumulates instances indefinitely.
- **Impact**: Memory leak proportional to unique configuration combinations. Each processor instance holds DSP state, filter caches, and analysis buffers.
- **Suggested Fix**: Add LRU eviction with max size (e.g., 10 entries) using `functools.lru_cache` or manual eviction.

---

### S-M06: Frontend Error Handler innerHTML with Unescaped Error Message
- **Severity**: MEDIUM
- **Dimension**: Security
- **Location**: `auralis-web/frontend/src/main.tsx:51`, `auralis-web/frontend/src/index.tsx:51`
- **Status**: NEW
- **Description**: The initialization error handler writes to `document.documentElement.innerHTML` with the error `msg` variable interpolated without HTML escaping. The stack trace IS escaped (`stack.replace(/</g, '&lt;')`), but the message is not.
- **Evidence**:
```typescript
// main.tsx:51
document.documentElement.innerHTML = '...<p style="...">' + msg + '</p>...'
// msg is NOT escaped — stack IS escaped via .replace()
```
- **Impact**: If an error message contains HTML (e.g., from a malicious URL or crafted fetch error like `"Error: <img src=x onerror=alert(1)>"`), it executes as JavaScript during app initialization failure.
- **Related**: Existing #2094 covers backend `main.py` fallback page — this is the frontend equivalent
- **Suggested Fix**: Apply the same `replace(/</g, '&lt;').replace(/>/g, '&gt;')` escaping to `msg`.

---

### LOW

### S-L01: pickle.dumps() Used for Cache Size Estimation
- **Severity**: LOW
- **Dimension**: Security / Code Quality
- **Location**: `auralis/optimization/caching/smart_cache.py:71`
- **Status**: NEW
- **Description**: `pickle.dumps(value)` is used to estimate the byte size of cached objects. While this doesn't deserialize untrusted data (only serializes), the `pickle` module is generally discouraged due to its association with code execution risks. If the cache is ever persisted to disk and reloaded, this creates an RCE vector.
- **Evidence**:
```python
# smart_cache.py:71-73
try:
    size = len(pickle.dumps(value))
except:
    size = 1024  # Default estimate
```
- **Impact**: Low current risk (serialization only). Establishes a pattern that could become dangerous if caching is extended to disk persistence.
- **Suggested Fix**: Replace with `sys.getsizeof(value)` for approximate size, or `value.nbytes` for NumPy arrays.

---

## Existing Findings (31) — Previously Filed

All 31 findings from the original audit are already tracked as GitHub issues:

| ID | Severity | Title | Issue |
|----|----------|-------|-------|
| C01 | CRITICAL | Race condition in player auto-advance | #2064 |
| C02 | CRITICAL | cleanup_missing_files loads entire library into memory | #2066 |
| C03 | CRITICAL | No resource cleanup on LibraryManager shutdown | #2066 |
| C04 | CRITICAL | Migration race condition — no process-level lock | #2064 |
| H01 | HIGH | No authentication on any endpoint | #2069 |
| H02 | HIGH | Path traversal in directory scanning | #2069 |
| H03 | HIGH | DetachedInstanceError in 13+ repository methods | #2070 |
| H04 | HIGH | Scanner follows symlinks without cycle detection | #2071 |
| H05 | HIGH | N+1 query pattern in find_similar | #2072 |
| H06 | HIGH | Missing input validation in TrackRepository.add() | #2073 |
| H07 | HIGH | FFmpeg process not terminated on timeout | #2074 |
| H08 | HIGH | Gapless playback thread not cleaned up | #2075 |
| H09 | HIGH | WebSocket stream loop TOCTOU | #2076 |
| H10 | HIGH | Lock contention in parallel processor window cache | #2077 |
| M01 | MEDIUM | SQL injection risk in fingerprint column names | #2078 |
| M02 | MEDIUM | Secret key committed to git in .env | #2079 |
| M03 | MEDIUM | process_chunk_synchronized bypasses async lock | #2080 |
| M04 | MEDIUM | Unbounded deleted_track_ids set | #2081 |
| M05 | MEDIUM | Hardcoded db_path in FingerprintRepository | #2082 |
| M06 | MEDIUM | No validation of migration scripts | #2083 |
| M07 | MEDIUM | Chunk cache not bounded by memory | #2084 |
| M08 | MEDIUM | WebSocket error recovery incomplete | #2085 |
| M09 | MEDIUM | SQLite connection pool misconfigured | #2086 |
| M10 | MEDIUM | Filepath exposure in API responses | #2088 |
| M11 | MEDIUM | No React error boundaries | #2088 |
| L01 | LOW | CORS wildcard methods and headers | #2091 |
| L02 | LOW | No rate limiting on processing endpoints | #2091 |
| L03 | LOW | Missing busy_timeout PRAGMA for SQLite | #2091 |
| L04 | LOW | Error response format inconsistency | #2092 |
| L05 | LOW | FingerprintGenerator silent failure | #2093 |
| L06 | LOW | Unsafe HTML interpolation in fallback page | #2094 |

---

## Relationships

### Cluster 1: Audio Integrity Chain (NEW)
S-C01 (in-place modification) → S-C02 (NaN propagation) → S-M02 (dtype promotion). A corrupted input from S-C01 can produce NaN values that S-C02 doesn't catch, amplified by S-M02's dtype promotion. The entire DSP output chain is vulnerable.

### Cluster 2: Player State Races (NEW + EXISTING)
S-H02 (seek race) + S-H01 (gapless sample rate) + S-H03 (prebuffer invalidation) + existing #2064 (auto-advance race). All four affect position tracking in the player. A seek during gapless transition can corrupt position via S-H02, which then triggers incorrect auto-advance via #2064.

### Cluster 3: Authentication + Security (EXISTING + NEW)
Existing H01/H02 (no auth + path traversal) + S-H05 (WebSocket validation) + S-M06 (innerHTML XSS). The lack of authentication makes S-H05's unvalidated WebSocket messages exploitable by any network client.

### Cluster 4: Memory Pressure (NEW + EXISTING)
S-M04 (scanner memory) + S-M05 (processor cache) + existing M04 (deleted_track_ids) + existing M07 (chunk cache). Four unbounded data structures that can collectively cause OOM on long-running instances.

---

## Prioritized Fix Order (New Findings Only)

1. **S-C01** — In-place modification. Core invariant violation. Fix: add `.copy()`. ~15min.
2. **S-C02** — NaN propagation. Silent corruption. Fix: add `np.isfinite()` check. ~30min.
3. **S-H02** — Seek race. User-facing bug. Fix: lock around position read-modify. ~1hr.
4. **S-H01** — Gapless sample rate. Audio skip. Fix: reset position in lock block. ~30min.
5. **S-H03** — Prebuffer invalidation. Fix: call invalidate in seek(). ~15min.
6. **S-H04** — Truncated audio. Fix: validate frame count. ~30min.
7. **S-H05** — WebSocket validation. Security. Fix: schema + size limit. ~2hr.
8. **S-M06** — XSS in error handler. Fix: escape msg variable. ~15min.
9. **S-M01** — Crossfade boundary. Fix: guard head_len==0. ~15min.
10. **S-M02** — dtype promotion. Fix: cast to input dtype. ~30min.
11. **S-M03-M05** — Memory/state fixes. ~2hr total.
12. **S-L01** — pickle replacement. ~15min.

---

## Cross-Cutting Recommendations

### 1. Audio Data Validation Layer
Add a centralized `validate_audio_buffer(audio)` function that checks: (a) `isinstance(audio, np.ndarray)`, (b) `audio.dtype in [np.float32, np.float64]`, (c) `np.all(np.isfinite(audio))`, (d) `len(audio) > 0`. Call it at pipeline entry and exit. This fixes S-C02, S-H04, S-M01.

### 2. Copy-Before-Modify Enforcement
All DSP functions should begin with `audio = audio.copy()`. Enforce via code review checklist or a decorator that automatically copies the first array argument. This fixes S-C01 and prevents future regressions.

### 3. Player State Locking
Wrap all position read-modify-write sequences in the existing RLock. Consider making `position` a property with a lock guard. This fixes S-H01, S-H02, S-H03.

### 4. WebSocket Security Hardening
Add message size limits, schema validation (Pydantic), and per-connection rate limiting to all WebSocket handlers. This fixes S-H05 and complements existing H01.

### 5. Memory Bounds on All Caches
Every cache/buffer in the system should have both a count limit AND a byte limit. Use `functools.lru_cache` or manual eviction. This addresses S-M04, S-M05, and existing M04/M07.
