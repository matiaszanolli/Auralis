# Comprehensive Auralis Audit — 2026-02-12

## Executive Summary

**Total findings: 31** — 4 CRITICAL, 10 HIGH, 11 MEDIUM, 6 LOW

| Severity | Count | Key themes |
|----------|-------|------------|
| CRITICAL | 4 | Player race condition, OOM on cleanup, DB shutdown corruption, migration race |
| HIGH | 10 | No authentication, path traversal, detached ORM instances, symlink loops, FFmpeg leak |
| MEDIUM | 11 | SQL injection risk, unbounded caches, event loop bypass, secret key in VCS |
| LOW | 6 | CORS config, rate limiting, SQLite PRAGMA, response inconsistency |

**Most impactful:** The combination of no authentication (H01) with path traversal (H02) allows any network client to scan arbitrary directories. The player race condition (C01) can cause audible skips in production.

---

## Findings

### CRITICAL

### C01: Race Condition in Player Auto-Advance
- **Severity**: CRITICAL
- **Dimension**: Concurrency / Player State
- **Location**: `auralis/player/enhanced_audio_player.py:364-383`
- **Status**: NEW
- **Description**: When playback reaches end-of-track, a background thread is spawned without any guard against concurrent invocation. The check at line 364 (`position >= total_samples`) is not atomic with the thread spawn. Multiple threads can enter `_auto_advance_delayed` simultaneously. The `time.sleep(0.1)` at line 381 is not a real synchronization mechanism.
- **Evidence**:
```python
# Line 364-371
if self.playback.position >= self.file_manager.get_total_samples():
    if self.auto_advance and not self.queue.is_queue_empty():
        import threading
        threading.Thread(
            target=self._auto_advance_delayed,
            daemon=True
        ).start()
```
- **Impact**: Track skipping, queue corruption, wrong track loaded. Silent failure — user hears glitched audio with no error.
- **Related**: C04 (another unguarded concurrent pattern)
- **Suggested Fix**: Use an atomic flag (`threading.Event` or `_auto_advance_in_progress`) to ensure only one auto-advance thread runs at a time.

---

### C02: cleanup_missing_files Loads Entire Library Into Memory
- **Severity**: CRITICAL
- **Dimension**: Library / Performance
- **Location**: `auralis/library/repositories/track_repository.py:660-690`
- **Status**: NEW
- **Description**: `session.query(Track).all()` at line 674 loads every track object (with all columns and eager relationships) into memory. For a library with 50k+ tracks, this causes OOM. Additionally, deleting tracks in a loop with cascade can hit SQLite busy timeouts.
- **Evidence**:
```python
# Line 674
tracks = session.query(Track).all()  # Loads ALL tracks into memory
for track in tracks:
    if not os.path.exists(track.filepath):
        session.delete(track)
```
- **Impact**: OOM crash on large libraries. SQLite lock contention during mass delete.
- **Suggested Fix**: Process in chunks of 1000 using `.offset().limit()`. Only select `id` and `filepath` columns. Batch delete with `filter(Track.id.in_(ids)).delete()`.

---

### C03: No Resource Cleanup on LibraryManager Shutdown
- **Severity**: CRITICAL
- **Dimension**: Library / Data Integrity
- **Location**: `auralis/library/manager.py` (class-level)
- **Status**: NEW
- **Description**: `LibraryManager` has no `shutdown()` or `__del__` method. When the application exits, SQLite connections are not properly closed, WAL journal is not checkpointed, and the connection pool is not disposed. This can leave the WAL file in an incomplete state.
- **Evidence**: The class initializes `self.engine = create_engine(...)` but has no corresponding cleanup. No `atexit` handler registered.
- **Impact**: WAL corruption on unclean shutdown. Database lockfile left behind. Potential data loss of uncommitted WAL transactions.
- **Suggested Fix**: Add `shutdown()` method that runs `PRAGMA wal_checkpoint(TRUNCATE)` and `engine.dispose()`. Register via `atexit.register()`.

---

### C04: Migration Race Condition — No Process-Level Lock
- **Severity**: CRITICAL
- **Dimension**: Library / Data Integrity
- **Location**: `auralis/library/migration_manager.py:268-326`
- **Status**: NEW
- **Description**: `check_and_migrate_database()` has no inter-process locking. If two processes (e.g., backend + scanner) start simultaneously, both can read version, decide migration is needed, and attempt it concurrently. Additionally, at line 308, migration proceeds even if backup creation fails.
- **Evidence**:
```python
# Line 302-308
if auto_backup and current_version > 0:
    try:
        backup_path = backup_database(db_path)
    except Exception as e:
        logger.warning("Proceeding without backup...")  # Proceeds anyway!
```
- **Impact**: Database corruption, schema inconsistency, data loss during parallel startup.
- **Suggested Fix**: Use `fcntl.flock()` on a migration lock file. Fail if backup creation fails.

---

### HIGH

### H01: No Authentication on Any Endpoint
- **Severity**: HIGH
- **Dimension**: Security
- **Location**: `auralis-web/backend/routers/*.py` (all 18 routers)
- **Status**: NEW
- **Description**: Zero authentication or authorization checks exist on any API endpoint. All routes accept unauthenticated requests. No 401/403 HTTP exceptions anywhere in the router code. Any network client can access all library data, modify metadata, trigger processing, and scan directories.
- **Evidence**: `grep -r "HTTPException.*401\|HTTPException.*403" auralis-web/backend --include="*.py"` returns 0 matches.
- **Impact**: Full access to library, metadata, processing, and file system scanning for any network client. Combined with H02, this allows arbitrary directory reconnaissance.
- **Suggested Fix**: Implement authentication middleware (JWT or session-based). Apply to all routes via FastAPI dependency injection.

---

### H02: Path Traversal in Directory Scanning Endpoint
- **Severity**: HIGH
- **Dimension**: Security
- **Location**: `auralis-web/backend/routers/files.py:74-134`
- **Status**: NEW
- **Description**: The `/api/library/scan` endpoint accepts a `directory` field from user input with no validation. The directory path is passed directly to `LibraryScanner.scan_single_directory()`. An attacker can scan `/../../../etc/` or any accessible path.
- **Evidence**:
```python
class ScanRequest(BaseModel):
    directory: str  # No validation

@router.post("/api/library/scan")
async def scan_directory(request: ScanRequest) -> Dict[str, Any]:
    directory = request.directory  # Directly used
```
- **Impact**: Arbitrary directory enumeration. Information disclosure of file system structure.
- **Related**: H01 (no auth makes this exploitable by anyone on the network)
- **Suggested Fix**: Validate against an allowlist of scan-permitted directories. At minimum, resolve path and ensure it's within user's home directory.

---

### H03: Detached Instance Errors in 13+ Repository Methods
- **Severity**: HIGH
- **Dimension**: Library / Data Access
- **Location**: `auralis/library/repositories/track_repository.py:169-181`, `auralis/library/repositories/album_repository.py:101-115` (and 11+ more methods)
- **Status**: NEW
- **Description**: Repository methods return SQLAlchemy ORM objects after closing the session in `finally`. Accessing relationships (`.artists`, `.album`, `.tracks`) after return triggers `DetachedInstanceError`. Despite `joinedload()` being used, the session is closed before the caller accesses the returned objects.
- **Evidence**:
```python
def get_by_id(self, track_id: int) -> Optional[Track]:
    session = self.get_session()
    try:
        return session.query(Track).options(joinedload(Track.artists)).first()
    finally:
        session.close()  # Session closed, returned object is detached
```
- **Impact**: Runtime exceptions when accessing related objects. Affects any code path that reads track.artists, album.tracks, etc.
- **Suggested Fix**: Call `session.expunge(obj)` before closing session to detach objects with their loaded relationships.

---

### H04: No Symlink Infinite Loop Protection in Scanner
- **Severity**: HIGH
- **Dimension**: Library / Reliability
- **Location**: `auralis/library/scanner/file_discovery.py:38-84`
- **Status**: NEW
- **Description**: `pathlib.Path.rglob()` at line 63 follows symlinks by default. If a symlink points to a parent directory (e.g., `/music/link -> /music`), the scanner enters an infinite loop.
- **Evidence**:
```python
if recursive:
    pattern_method = directory_path.rglob  # Follows symlinks
for ext in AUDIO_EXTENSIONS:
    for file_path in pattern_method(f"*{ext}"):  # Can loop forever
```
- **Impact**: Scanner hangs indefinitely. Application becomes unresponsive.
- **Suggested Fix**: Track visited inodes `(st_dev, st_ino)` to detect cycles. Add max depth limit.

---

### H05: N+1 Query Pattern in find_similar
- **Severity**: HIGH
- **Dimension**: Library / Performance
- **Location**: `auralis/library/repositories/track_repository.py:479-516`
- **Status**: NEW
- **Description**: The `find_similar()` method queries tracks without eager loading relationships, then accesses `.artists`, `.album`, and `.genres` in a loop, generating N+1 queries.
- **Impact**: For a result set of 50 tracks, this generates 150+ additional queries. Severe latency on the similarity endpoint.
- **Suggested Fix**: Add `.options(joinedload(Track.artists), joinedload(Track.album), joinedload(Track.genres))` to the query.

---

### H06: Missing Input Validation in TrackRepository.add()
- **Severity**: HIGH
- **Dimension**: Library / Data Integrity
- **Location**: `auralis/library/repositories/track_repository.py:41-160`
- **Status**: NEW
- **Description**: `add()` accepts a `Dict[str, Any]` with no validation of field types, ranges, or lengths. Duration can be negative, sample_rate can be zero, artist names can be 10k+ characters.
- **Impact**: Database bloat, invalid metadata, potential resource exhaustion. Corrupt entries that break downstream queries.
- **Suggested Fix**: Validate numeric ranges (duration > 0, sample_rate in [8000..384000], channels in [1,2,4,6,8]), text lengths (title < 500 chars, artist < 200 chars).

---

### H07: FFmpeg Process Not Terminated on Timeout
- **Severity**: HIGH
- **Dimension**: Error Handling / I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:77-85`
- **Status**: NEW
- **Description**: `subprocess.run()` with `timeout=300` raises `TimeoutExpired`, but the finally block deletes temporary files while FFmpeg may still be writing to them. No explicit process termination on timeout.
- **Impact**: Corrupted temporary files. File descriptor leaks. Next load of the same file gets incomplete data.
- **Suggested Fix**: Use `subprocess.Popen` with explicit `.kill()` and `.wait()` on timeout. Add delay before temp file cleanup.

---

### H08: Gapless Playback Thread Not Cleaned Up
- **Severity**: HIGH
- **Dimension**: Concurrency / Player State
- **Location**: `auralis/player/gapless_playback_engine.py:80-86`
- **Status**: NEW
- **Description**: Prebuffer thread is created as `daemon=True` and will be killed mid-operation on shutdown. If killed while holding file handles, descriptors leak. No guard against multiple concurrent prebuffer threads.
- **Evidence**:
```python
self.prebuffer_thread = threading.Thread(
    target=self._prebuffer_worker,
    daemon=True,  # Killed on exit
    name="GaplessPlayback-Prebuffer"
)
```
- **Impact**: File descriptor exhaustion over time. On Windows, file locks prevent deletion. Multiple threads possible on rapid queue changes.
- **Suggested Fix**: Check `is_alive()` before creating new thread. Use non-daemon thread with explicit join on shutdown.

---

### H09: WebSocket Stream Loop TOCTOU
- **Severity**: HIGH
- **Dimension**: Concurrency / Backend API
- **Location**: `auralis-web/backend/audio_stream_controller.py:461-489`
- **Status**: NEW
- **Description**: The streaming loop checks `_is_websocket_connected()` at the top of each iteration, but the connection can drop between the check and the actual send inside `_process_and_stream_chunk()`. Failed mid-stream sends waste CPU processing audio that won't be delivered.
- **Impact**: Wasted CPU on audio processing after disconnect. Chunk data accumulates in send buffer. Active stream not cleaned up.
- **Suggested Fix**: Check connection state inside `_process_and_stream_chunk()` before each send. Add `finally` block to clean up `active_streams`.

---

### H10: Lock Contention in Parallel Processor Window Cache
- **Severity**: HIGH
- **Dimension**: Concurrency / Performance
- **Location**: `auralis/optimization/parallel_processor.py:60-71`
- **Status**: NEW
- **Description**: The window cache `get_window()` holds a `threading.Lock` while computing `np.hanning(size)`. For large FFT sizes (8192+), this blocks all other parallel threads from accessing the cache.
- **Evidence**:
```python
with self.lock:
    if size not in self.window_cache:
        self.window_cache[size] = np.hanning(size)  # Blocks all threads
```
- **Impact**: Serializes parallel processing, defeating the purpose of parallelization. 8+ threads bottleneck on single lock holder.
- **Suggested Fix**: Compute window outside the lock, then lock only for cache insertion (double-check pattern).

---

### MEDIUM

### M01: SQL Injection Risk in Fingerprint Repository Column Names
- **Severity**: MEDIUM
- **Dimension**: Security / Library
- **Location**: `auralis/library/repositories/fingerprint_repository.py:477-483`
- **Status**: NEW
- **Description**: Column names from `fingerprint_data` dict keys are interpolated directly into SQL. While values are parameterized, column names are not. An attacker controlling dict keys could inject SQL.
- **Evidence**:
```python
cols_str = ', '.join(cols)  # Dict keys, unvalidated
sql = f"INSERT OR REPLACE INTO track_fingerprints (track_id, {cols_str}) VALUES (?, {placeholders})"
```
- **Impact**: SQL injection if fingerprint_data keys come from untrusted input. Currently low risk (keys are internal), but violates defense-in-depth.
- **Suggested Fix**: Validate column names against a whitelist of known fingerprint dimensions.

---

### M02: Hardcoded Secret Key Committed to Git
- **Severity**: MEDIUM
- **Dimension**: Security
- **Location**: `.env:6`
- **Status**: NEW
- **Description**: The `.env` file is tracked in git (`git ls-files .env` returns it) despite being in `.gitignore`. It contains a hardcoded secret key: `MATCHERING_SECRET_KEY=uCG4Pr9mS2hKzVnfYtN8wL3xQjE5RbAd` along with database credentials.
- **Impact**: Secret key and credentials exposed in version history. Even if removed now, they persist in git history.
- **Suggested Fix**: `git rm --cached .env`. Rotate the secret key. Use environment variables or a secrets manager.

---

### M03: process_chunk_synchronized Bypasses Async Lock
- **Severity**: MEDIUM
- **Dimension**: Concurrency
- **Location**: `auralis-web/backend/chunked_processor.py:714-733`
- **Status**: NEW
- **Description**: `process_chunk_synchronized()` creates a new event loop via `asyncio.run()` in a separate thread. This new event loop has its own lock context — the `_processor_lock` from the main event loop does NOT protect against concurrent access from this path.
- **Evidence**:
```python
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(
        lambda: asyncio.run(self.process_chunk_safe(chunk_index, fast_start))
    )  # New event loop = new lock instance context
```
- **Impact**: Concurrent processor access between sync and async code paths, potentially corrupting DSP state.
- **Suggested Fix**: Use `threading.RLock` instead of `asyncio.Lock` for cross-context safety.

---

### M04: Unbounded deleted_track_ids Set
- **Severity**: MEDIUM
- **Dimension**: Library / Memory
- **Location**: `auralis/library/manager.py:158-162`
- **Status**: NEW
- **Description**: `_deleted_track_ids` set grows without bound as tracks are deleted. After millions of deletions, this leaks significant memory. On restart, the set resets, so previously deleted IDs are no longer tracked.
- **Impact**: Memory leak proportional to number of deletions over application lifetime.
- **Suggested Fix**: Cap set size (e.g., 10k entries) with LRU eviction, or eliminate the set by checking the database directly.

---

### M05: Hardcoded Database Path in FingerprintRepository
- **Severity**: MEDIUM
- **Dimension**: Library / Architecture
- **Location**: `auralis/library/repositories/fingerprint_repository.py:471-472`
- **Status**: NEW
- **Description**: Three methods bypass the ORM session factory and hardcode `Path.home() / '.auralis' / 'library.db'` with raw `sqlite3.connect()`. This breaks test isolation, custom db paths, and multi-instance deployments.
- **Impact**: Tests cannot use in-memory databases. Custom database paths are ignored for fingerprint operations.
- **Suggested Fix**: Pass `db_path` from LibraryManager to FingerprintRepository at construction time.

---

### M06: No Migration Script Validation
- **Severity**: MEDIUM
- **Dimension**: Library / Safety
- **Location**: `auralis/library/migration_manager.py:103-129`
- **Status**: NEW
- **Description**: Migration scripts are read from disk and executed without validation. No check for destructive operations (DROP TABLE, TRUNCATE). No pre-migration dry run.
- **Impact**: Accidental data destruction from malformed migration scripts. No rollback on partial failure.
- **Suggested Fix**: Validate SQL statements before execution. Reject scripts containing destructive keywords without explicit override.

---

### M07: Chunk Cache Not Bounded by Memory
- **Severity**: MEDIUM
- **Dimension**: Backend / Performance
- **Location**: `auralis-web/backend/audio_stream_controller.py:47-115`
- **Status**: NEW
- **Description**: `SimpleChunkCache` limits by count (max 50 chunks) but not by memory. Each chunk can be 10-50MB of audio data. 50 chunks * 50MB = 2.5GB potential memory usage.
- **Impact**: Memory exhaustion on systems with limited RAM. No backpressure mechanism.
- **Suggested Fix**: Track `audio.nbytes` per cached chunk. Evict when total exceeds a configured memory limit.

---

### M08: WebSocket Error Recovery Incomplete
- **Severity**: MEDIUM
- **Dimension**: Backend / Error Handling
- **Location**: `auralis-web/backend/audio_stream_controller.py:479-489`
- **Status**: NEW
- **Description**: When chunk processing fails mid-stream, the handler sends an error message and returns immediately. No resource cleanup (processor state, cached chunks). Client has no recovery information.
- **Impact**: Stale processor state. Client in undefined state (partial stream received).
- **Suggested Fix**: Clean up processor and cache on error. Include recovery position in error message.

---

### M09: SQLite Connection Pool Misconfigured
- **Severity**: MEDIUM
- **Dimension**: Library / Concurrency
- **Location**: `auralis/library/manager.py:114-121`
- **Status**: NEW
- **Description**: `pool_size=32, max_overflow=32` creates up to 64 connection objects, but SQLite only allows one writer at a time. 63 threads will block on write contention. The 60-second timeout means hung requests.
- **Impact**: Apparent deadlocks under load. Write operations timeout after 60 seconds.
- **Suggested Fix**: Use `StaticPool` (single connection) or reduce pool size with WAL mode's reader concurrency.

---

### M10: Filepath Exposure in API Responses
- **Severity**: MEDIUM
- **Dimension**: Security
- **Location**: `auralis-web/backend/routers/metadata.py:121`
- **Status**: NEW
- **Description**: The metadata endpoint returns `track.filepath` in the response body, exposing the full server-side file path to the client.
- **Impact**: Information disclosure of server file system structure. Aids path traversal attacks.
- **Suggested Fix**: Remove `filepath` from API responses. Use track ID for all client-facing references.

---

### M11: No React Error Boundaries
- **Severity**: MEDIUM
- **Dimension**: Frontend / Reliability
- **Location**: `auralis-web/frontend/src/index.tsx`
- **Status**: NEW
- **Description**: The app renders without any React Error Boundary component. A rendering error in any component crashes the entire application. The only catch is the top-level async IIFE try/catch which only handles initialization errors, not runtime rendering errors.
- **Impact**: Any uncaught rendering error crashes the entire UI. User must manually reload.
- **Suggested Fix**: Add `<ErrorBoundary>` wrapper around `<App />` with a recovery UI.

---

### LOW

### L01: CORS Wildcard Methods and Headers
- **Severity**: LOW
- **Dimension**: Security
- **Location**: `auralis-web/backend/config/middleware.py:76-77`
- **Status**: NEW
- **Description**: `allow_methods=["*"]` and `allow_headers=["*"]` with `allow_credentials=True`. Per CORS spec, wildcard headers with credentials is technically invalid (browsers may handle inconsistently).
- **Impact**: Minor security hygiene issue. Allows unexpected HTTP methods.
- **Suggested Fix**: Explicitly list allowed methods and headers.

---

### L02: No Rate Limiting on Processing Endpoints
- **Severity**: LOW
- **Dimension**: Security / Performance
- **Location**: All routers (no rate limiting middleware found)
- **Status**: NEW
- **Description**: CPU-intensive endpoints like `/api/similarity/fit` and `/api/similarity/graph/build` can be called repeatedly without throttling.
- **Impact**: CPU exhaustion via repeated requests. Denial of service for other users.
- **Suggested Fix**: Add per-endpoint rate limiting middleware (e.g., `slowapi`).

---

### L03: Missing busy_timeout PRAGMA for SQLite
- **Severity**: LOW
- **Dimension**: Library / Configuration
- **Location**: `auralis/library/manager.py:124-142`
- **Status**: NEW
- **Description**: SQLite pragma setup does not include `PRAGMA busy_timeout`. While `connect_args={'timeout': 60}` is set, the SQL-level busy_timeout should also be configured for consistency.
- **Impact**: Inconsistent timeout behavior between Python-level and SQLite-level.
- **Suggested Fix**: Add `cursor.execute("PRAGMA busy_timeout=60000")` to pragma setup.

---

### L04: Error Response Format Inconsistency
- **Severity**: LOW
- **Dimension**: Backend / API
- **Location**: Multiple routers
- **Status**: NEW
- **Description**: Some endpoints return `{"error": "..."}`, others `{"message": "..."}`, others use FastAPI default `{"detail": "..."}`. Frontend must check multiple fields.
- **Impact**: Inconsistent client-side error handling. Increased maintenance burden.
- **Suggested Fix**: Standardize on FastAPI's `{"detail": "..."}` format via custom exception handler.

---

### L05: Fingerprint Generator Silent Failure
- **Severity**: LOW
- **Dimension**: Backend / Error Handling
- **Location**: `auralis-web/backend/audio_stream_controller.py:150-164`
- **Status**: NEW
- **Description**: FingerprintGenerator initialization failure is logged as a warning but not surfaced to the user. Audio streams proceed with degraded quality (no fingerprint-optimized mastering) without notification.
- **Impact**: Users unaware of suboptimal audio quality. No diagnostic information exposed.
- **Suggested Fix**: Store error state. Include fingerprint availability in stream metadata sent to client.

---

### L06: Unsafe HTML Interpolation in Fallback Page
- **Severity**: LOW
- **Dimension**: Security
- **Location**: `auralis-web/backend/main.py:184-194`
- **Status**: NEW
- **Description**: `frontend_path` is interpolated into HTML without escaping. While currently internally derived (low risk), the pattern is dangerous if the source changes.
- **Impact**: Potential HTML injection if path becomes user-controllable in the future.
- **Suggested Fix**: Use `html.escape()` on the path value.

---

## Relationships

### Cluster 1: Authentication + Path Traversal
H01 (no auth) + H02 (path traversal) + M10 (filepath exposure) form a chain: any network client can scan arbitrary directories AND learn server-side file paths from metadata responses.

### Cluster 2: Database Integrity
C02 (OOM cleanup) + C03 (no shutdown cleanup) + C04 (migration race) + M09 (pool misconfigured) all threaten database stability. A crash from C02 during cleanup, combined with C03's lack of WAL checkpoint, could corrupt the database. C04 makes recovery dangerous.

### Cluster 3: Concurrency in Audio Pipeline
C01 (auto-advance race) + H08 (gapless thread) + H10 (lock contention) + M03 (lock bypass) all affect audio pipeline correctness. The auto-advance race causes track skips, while M03's lock bypass can corrupt DSP state mid-chunk.

### Cluster 4: Repository Pattern Issues
H03 (detached instances) + H05 (N+1 queries) + H06 (no validation) + M05 (hardcoded db path) are all repository-layer issues sharing a root cause: the session management pattern (open/use/close in each method) doesn't properly detach objects.

---

## Prioritized Fix Order

1. **C01** — Player race condition. Audible artifact in production. Fix: atomic flag. ~1hr.
2. **H01 + H02** — Auth + path traversal. Security exposure. Fix: auth middleware + path validation. ~4hr.
3. **C03** — Shutdown cleanup. Data loss risk. Fix: `shutdown()` + `atexit`. ~1hr.
4. **C04** — Migration lock. Corruption risk. Fix: `fcntl.flock()`. ~2hr.
5. **H03** — Detached instances. Runtime exceptions. Fix: `session.expunge()` in 13 methods. ~3hr.
6. **C02** — Cleanup OOM. Production crash. Fix: chunked query. ~1hr.
7. **M02** — Secret in VCS. Fix: `git rm --cached .env`, rotate key. ~30min.
8. **H04** — Symlink loops. Scanner hang. Fix: inode tracking. ~2hr.
9. **M03** — Lock bypass. DSP corruption. Fix: use `threading.RLock`. ~1hr.
10. **H07-H10** — Remaining HIGH issues. ~8hr total.
11. **M01-M11** — MEDIUM issues. ~12hr total.
12. **L01-L06** — LOW issues. Opportunistic.

---

## Cross-Cutting Recommendations

### 1. Authentication Layer
Add a single authentication middleware before any router. Even basic API key auth would close H01, H02, and M10.

### 2. Repository Session Management
Refactor the repository base class to either (a) use scoped sessions that live longer than a single method call, or (b) systematically `expunge` all returned objects. This fixes H03 and prevents future detached instance bugs.

### 3. Database Lifecycle
Add `LibraryManager.shutdown()` with WAL checkpoint. Register with `atexit`. Add process-level lock for migrations. This fixes C03, C04, and improves M09.

### 4. Audio Pipeline Synchronization
Replace the `time.sleep(0.1)` pattern with proper synchronization primitives. Use `threading.RLock` (not `asyncio.Lock`) for cross-context safety. This fixes C01, M03, and H10.

### 5. Input Validation
Add Pydantic validators on all API request models (path fields, numeric ranges). Add column name whitelists for dynamic SQL. This fixes H02, H06, M01.
