# Phase 1: Fingerprint Extraction Pipeline Design

**Date**: November 24, 2025
**Status**: Design Phase
**Objective**: Design background fingerprint extraction with worker threads + sidecar caching

---

## Architecture Overview

```
Library Scanner                  Fingerprint Queue          Worker Thread Pool
┌─────────────────┐            ┌──────────────────┐       ┌─────────────────┐
│ User adds 100   │            │ asyncio.Queue    │       │ 4 Worker Threads│
│ tracks to       │──add────→  │                  │       │                 │
│ library         │            │ [track1, track2, │─process→ Extract 25D   │
└─────────────────┘            │  track3, ...]    │       │ Fingerprints    │
                               └──────────────────┘       │                 │
                                                          │ Cache .25d file │
                                                          └─────────────────┘
                                                                  ↓
                                                          Database Storage
                                                          ┌──────────────────┐
                                                          │ tracks table:    │
                                                          │ - fingerprint_   │
                                                          │   status: enum   │
                                                          │ - fingerprint_   │
                                                          │   computed_at    │
                                                          │ - fingerprint    │
                                                          │   data: BLOB     │
                                                          └──────────────────┘
```

---

## 1. Database Schema Updates

### Track Status Tracking

```sql
ALTER TABLE tracks ADD COLUMN fingerprint_status TEXT
  DEFAULT 'pending'
  CHECK (fingerprint_status IN ('pending', 'processing', 'complete', 'error'));

ALTER TABLE tracks ADD COLUMN fingerprint_computed_at TIMESTAMP;

ALTER TABLE tracks ADD COLUMN fingerprint_error_message TEXT;

-- Create index for efficient querying
CREATE INDEX idx_tracks_fingerprint_status ON tracks(fingerprint_status);
```

### New Fingerprint Data Table (Optional)

```sql
CREATE TABLE track_fingerprints (
  id INTEGER PRIMARY KEY,
  track_id INTEGER NOT NULL UNIQUE,
  fingerprint_vector BLOB NOT NULL,  -- 25 floats, serialized
  hash TEXT NOT NULL,                -- Hash for cache validation
  computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
);

CREATE INDEX idx_fingerprints_track_id ON track_fingerprints(track_id);
```

### Migration File

```python
# auralis/library/migrations/add_fingerprint_status.py
def up(connection):
    cursor = connection.cursor()

    # Add columns to tracks table
    cursor.execute("""
        ALTER TABLE tracks ADD COLUMN fingerprint_status TEXT
        DEFAULT 'pending'
    """)

    cursor.execute("""
        ALTER TABLE tracks ADD COLUMN fingerprint_computed_at TIMESTAMP
    """)

    cursor.execute("""
        ALTER TABLE tracks ADD COLUMN fingerprint_error_message TEXT
    """)

    # Create index
    cursor.execute("""
        CREATE INDEX idx_tracks_fingerprint_status
        ON tracks(fingerprint_status)
    """)

    connection.commit()

def down(connection):
    cursor = connection.cursor()
    cursor.execute("DROP INDEX idx_tracks_fingerprint_status")
    cursor.execute("ALTER TABLE tracks DROP COLUMN fingerprint_status")
    cursor.execute("ALTER TABLE tracks DROP COLUMN fingerprint_computed_at")
    cursor.execute("ALTER TABLE tracks DROP COLUMN fingerprint_error_message")
    connection.commit()
```

---

## 2. Fingerprint Queue System

### Class: FingerprintExtractionQueue

```python
# auralis/library/fingerprint_queue.py

class FingerprintExtractionQueue:
    """
    Manages asynchronous fingerprint extraction using worker threads.

    Features:
    - asyncio.Queue for thread-safe job management
    - Configurable number of worker threads
    - Retry logic for failed extractions
    - Priority-based extraction (recent tracks first)
    - Background processing without blocking UI
    """

    def __init__(self, num_workers: int = 4, max_retries: int = 3):
        self.queue = asyncio.Queue()
        self.num_workers = num_workers
        self.max_retries = max_retries
        self.active_extractions = {}  # {track_id: status}
        self.extraction_tasks = []

    async def add_track(self, track_id: int, filepath: str, priority: int = 0):
        """Add track to extraction queue (higher priority = processed first)"""
        await self.queue.put((priority, track_id, filepath))

    async def add_tracks_batch(self, tracks: List[Tuple[int, str]]):
        """Add multiple tracks in priority order"""
        # Most recent tracks first (priority -track_id sorts by recency)
        sorted_tracks = sorted(tracks, key=lambda t: t[0], reverse=True)
        for track_id, filepath in sorted_tracks:
            await self.add_track(track_id, filepath, priority=-track_id)

    async def start_workers(self):
        """Start worker threads"""
        for i in range(self.num_workers):
            task = asyncio.create_task(self._worker())
            self.extraction_tasks.append(task)

    async def _worker(self):
        """Worker thread: extract fingerprints continuously"""
        while True:
            try:
                _, track_id, filepath = await self.queue.get()

                try:
                    self.active_extractions[track_id] = "processing"

                    # Check if already extracted
                    if self._is_cached(filepath):
                        fingerprint = self._load_from_cache(filepath)
                        logger.info(f"Loaded fingerprint from cache for track {track_id}")
                    else:
                        # Extract fingerprint
                        fingerprint = self._extract_fingerprint(filepath)

                        # Cache to .25d file
                        self._save_to_cache(filepath, fingerprint)
                        logger.info(f"Extracted and cached fingerprint for track {track_id}")

                    # Update database
                    self._update_database(track_id, fingerprint)
                    self.active_extractions[track_id] = "complete"

                except Exception as e:
                    logger.error(f"Extraction failed for track {track_id}: {e}")
                    self.active_extractions[track_id] = "error"
                    # Retry logic could be added here

                finally:
                    self.queue.task_done()

            except asyncio.CancelledError:
                break

    def _is_cached(self, filepath: str) -> bool:
        """Check if .25d sidecar file exists and is valid"""
        # Uses SidecarManager
        pass

    def _load_from_cache(self, filepath: str) -> Dict[str, float]:
        """Load fingerprint from .25d sidecar file"""
        pass

    def _extract_fingerprint(self, filepath: str) -> Dict[str, float]:
        """Extract 25D fingerprint from audio file"""
        pass

    def _save_to_cache(self, filepath: str, fingerprint: Dict[str, float]):
        """Save fingerprint to .25d sidecar file"""
        pass

    def _update_database(self, track_id: int, fingerprint: Dict[str, float]):
        """Update database with fingerprint status and data"""
        pass

    async def stop_workers(self):
        """Gracefully stop all workers"""
        for task in self.extraction_tasks:
            task.cancel()
        await asyncio.gather(*self.extraction_tasks, return_exceptions=True)

    def get_status(self) -> Dict[str, Any]:
        """Get current extraction status"""
        return {
            "queue_size": self.queue.qsize(),
            "active_extractions": len(self.active_extractions),
            "active_jobs": self.active_extractions
        }
```

---

## 3. .25d Sidecar File Format

### File Format

```
.25d File (Binary Format)
┌────────────────────┐
│ Header (16 bytes)  │
├────────────────────┤
│ Version: uint32    │ 0x25D00001 (hex)
│ Timestamp: uint64  │ File modification time
│ Count: uint32      │ Number of dimensions (25)
├────────────────────┤
│ 25 Floats (100B)   │
│ [float32 x 25]     │
├────────────────────┤
│ Checksum (4 bytes) │ CRC32 of data
└────────────────────┘
Total: 120 bytes per file
```

### Implementation

```python
# auralis/library/sidecar_manager.py (extend)

class SidecarManager:
    """Manage .25d sidecar files for fingerprint caching"""

    SIDECAR_EXT = ".25d"
    FORMAT_VERSION = 0x25D00001

    def save_fingerprint(self, audio_filepath: str, fingerprint: Dict[str, float]) -> bool:
        """Save fingerprint to .25d sidecar file"""
        sidecar_path = Path(audio_filepath).with_suffix(".25d")

        try:
            # Extract values in order (must be consistent)
            values = np.array([
                fingerprint['sub_bass_pct'], fingerprint['bass_pct'],
                # ... 23 more values
                fingerprint['phase_correlation']
            ], dtype=np.float32)

            # Create binary file
            with open(sidecar_path, 'wb') as f:
                # Write header
                f.write(struct.pack('<I', self.FORMAT_VERSION))  # Version
                f.write(struct.pack('<Q', int(time.time())))     # Timestamp
                f.write(struct.pack('<I', 25))                   # Count

                # Write data
                f.write(values.tobytes())

                # Write checksum
                checksum = zlib.crc32(values.tobytes()) & 0xffffffff
                f.write(struct.pack('<I', checksum))

            return True
        except Exception as e:
            logger.error(f"Failed to save fingerprint to {sidecar_path}: {e}")
            return False

    def load_fingerprint(self, audio_filepath: str) -> Optional[Dict[str, float]]:
        """Load fingerprint from .25d sidecar file if valid"""
        sidecar_path = Path(audio_filepath).with_suffix(".25d")

        if not sidecar_path.exists():
            return None

        try:
            with open(sidecar_path, 'rb') as f:
                # Read header
                version = struct.unpack('<I', f.read(4))[0]
                timestamp = struct.unpack('<Q', f.read(8))[0]
                count = struct.unpack('<I', f.read(4))[0]

                if version != self.FORMAT_VERSION or count != 25:
                    logger.warning(f"Invalid sidecar format: {sidecar_path}")
                    return None

                # Read data
                data = f.read(100)  # 25 float32s
                if len(data) != 100:
                    logger.warning(f"Incomplete sidecar data: {sidecar_path}")
                    return None

                values = np.frombuffer(data, dtype=np.float32)

                # Read and verify checksum
                checksum = struct.unpack('<I', f.read(4))[0]
                expected_checksum = zlib.crc32(data) & 0xffffffff

                if checksum != expected_checksum:
                    logger.warning(f"Checksum mismatch: {sidecar_path}")
                    return None

                # Reconstruct fingerprint dict (order matters!)
                keys = [
                    'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
                    'upper_mid_pct', 'presence_pct', 'air_pct',
                    'lufs', 'crest_db', 'bass_mid_ratio',
                    'tempo_bpm', 'rhythm_stability', 'transient_density', 'silence_ratio',
                    'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
                    'harmonic_ratio', 'pitch_stability', 'chroma_energy',
                    'dynamic_range_variation', 'loudness_variation_std', 'peak_consistency',
                    'stereo_width', 'phase_correlation'
                ]

                return dict(zip(keys, values))

        except Exception as e:
            logger.debug(f"Failed to load fingerprint from {sidecar_path}: {e}")
            return None

    def is_valid(self, audio_filepath: str) -> bool:
        """Check if .25d file exists and is valid"""
        sidecar_path = Path(audio_filepath).with_suffix(".25d")

        if not sidecar_path.exists():
            return False

        # Optional: Check if sidecar is newer than audio file
        try:
            audio_mtime = Path(audio_filepath).stat().st_mtime
            sidecar_mtime = sidecar_path.stat().st_mtime
            return sidecar_mtime > audio_mtime
        except:
            return False
```

---

## 4. Library Scanner Integration

### Update LibraryScanner

```python
# auralis/library/scanner.py (extend)

class LibraryScanner:
    """Scan and catalog library, triggering fingerprint extraction"""

    def __init__(self, library_manager, fingerprint_queue: FingerprintExtractionQueue = None):
        self.library_manager = library_manager
        self.fingerprint_queue = fingerprint_queue

    async def scan_directory(self, directory: str):
        """Scan directory and queue fingerprint extraction"""

        new_tracks = []

        for filepath in self._find_audio_files(directory):
            # Add track to library (unchanged)
            track = self.library_manager.add_track(filepath)

            if track:
                new_tracks.append((track.id, filepath))

        # Queue fingerprint extraction for new/updated tracks
        if self.fingerprint_queue:
            logger.info(f"Queueing {len(new_tracks)} tracks for fingerprint extraction")
            await self.fingerprint_queue.add_tracks_batch(new_tracks)

        return len(new_tracks)
```

---

## 5. Database Repository Pattern

### FingerprintRepository

```python
# auralis/library/repositories/fingerprint_repository.py

class FingerprintRepository:
    """Repository for fingerprint data access"""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def update_status(self, track_id: int, status: str, error_msg: str = None):
        """Update fingerprint status"""
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE tracks SET fingerprint_status = ?, fingerprint_computed_at = ? WHERE id = ?",
            (status, datetime.now() if status == 'complete' else None, track_id)
        )
        if error_msg:
            cursor.execute(
                "UPDATE tracks SET fingerprint_error_message = ? WHERE id = ?",
                (error_msg, track_id)
            )
        self.connection.commit()

    def get_pending_tracks(self, limit: int = 100) -> List[Tuple[int, str]]:
        """Get tracks awaiting fingerprint extraction"""
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT id, filepath FROM tracks WHERE fingerprint_status = 'pending' LIMIT ?",
            (limit,)
        )
        return cursor.fetchall()

    def save_fingerprint(self, track_id: int, fingerprint: Dict[str, float]):
        """Save fingerprint vector to database"""
        cursor = self.connection.cursor()

        # Serialize fingerprint
        fingerprint_bytes = self._serialize_fingerprint(fingerprint)
        fingerprint_hash = hashlib.sha256(fingerprint_bytes).hexdigest()

        cursor.execute(
            "INSERT OR REPLACE INTO track_fingerprints (track_id, fingerprint_vector, hash) VALUES (?, ?, ?)",
            (track_id, fingerprint_bytes, fingerprint_hash)
        )

        self.connection.commit()

    def get_fingerprint(self, track_id: int) -> Optional[Dict[str, float]]:
        """Load fingerprint from database"""
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT fingerprint_vector FROM track_fingerprints WHERE track_id = ?",
            (track_id,)
        )
        row = cursor.fetchone()

        if row:
            return self._deserialize_fingerprint(row[0])
        return None

    def _serialize_fingerprint(self, fingerprint: Dict[str, float]) -> bytes:
        """Convert fingerprint dict to binary"""
        keys = [...]  # 25 keys in order
        values = np.array([fingerprint[k] for k in keys], dtype=np.float32)
        return values.tobytes()

    def _deserialize_fingerprint(self, data: bytes) -> Dict[str, float]:
        """Convert binary back to fingerprint dict"""
        values = np.frombuffer(data, dtype=np.float32)
        keys = [...]  # 25 keys in order
        return dict(zip(keys, values))
```

---

## 6. Integration with LibraryManager

### Update LibraryManager

```python
# auralis/library/manager.py (extend)

class LibraryManager:
    """Library management with fingerprint extraction integration"""

    def __init__(self, ...):
        ...
        self.fingerprint_queue = FingerprintExtractionQueue(num_workers=2)
        self.fingerprint_repository = FingerprintRepository(self.connection)
        self.extraction_tasks = []

    async def initialize_async(self):
        """Start background workers (call from app startup)"""
        await self.fingerprint_queue.start_workers()
        logger.info("Fingerprint extraction workers started")

    async def shutdown_async(self):
        """Stop background workers gracefully (call from app shutdown)"""
        await self.fingerprint_queue.stop_workers()
        logger.info("Fingerprint extraction workers stopped")

    def get_fingerprint_status(self) -> Dict[str, Any]:
        """Get current fingerprint extraction status"""
        return self.fingerprint_queue.get_status()
```

---

## 7. Test Fixtures

### Test Fingerprint Data

```python
# tests/fixtures/fingerprint_fixtures.py

@pytest.fixture
def reference_fingerprint():
    """Known good 25D fingerprint"""
    return {
        'sub_bass_pct': 5.2,
        'bass_pct': 14.8,
        'low_mid_pct': 16.1,
        'mid_pct': 29.5,
        'upper_mid_pct': 20.3,
        'presence_pct': 10.2,
        'air_pct': 3.9,

        'lufs': -15.5,
        'crest_db': 16.3,
        'bass_mid_ratio': -1.2,

        'tempo_bpm': 124.0,
        'rhythm_stability': 0.87,
        'transient_density': 0.65,
        'silence_ratio': 0.08,

        'spectral_centroid': 0.52,
        'spectral_rolloff': 0.58,
        'spectral_flatness': 0.32,

        'harmonic_ratio': 0.68,
        'pitch_stability': 0.72,
        'chroma_energy': 0.61,

        'dynamic_range_variation': 0.54,
        'loudness_variation_std': 0.47,
        'peak_consistency': 0.71,

        'stereo_width': 0.58,
        'phase_correlation': 0.92
    }

@pytest.fixture
def synthetic_audio_3min():
    """3-minute synthetic audio for testing"""
    sr = 44100
    duration = 180
    return np.random.randn(sr * duration), sr
```

---

## 8. Timeline & Next Steps

### Week 1 (Current)
- ✅ Day 1: Audit fingerprint completeness & profile speed
- Days 2-3: Design background extraction pipeline (THIS DOC)
- Days 4-5: Implement database schema + repository
- Days 6-7: Implement FingerprintExtractionQueue

### Week 2
- Days 1-2: Integrate with LibraryScanner
- Days 3-4: Test with real audio library (100+ tracks)
- Days 5-7: Optimize harmonic analyzer (if needed)

### Success Criteria (Phase 1 Complete)
- ✅ All 25 dimensions extracting
- ✅ Background extraction doesn't block UI
- ✅ .25d files generated for all library tracks
- ✅ Database properly tracks fingerprint status
- ✅ Tests validate caching + database consistency

---

## 9. Implementation Checklist

### Database & Schema
- [ ] Create migration script
- [ ] Update Track model with fingerprint_status columns
- [ ] Create FingerprintRepository class
- [ ] Add tests for repository operations

### Fingerprint Queue
- [ ] Implement FingerprintExtractionQueue class
- [ ] Implement worker thread pool
- [ ] Add priority-based queueing
- [ ] Add tests for queue operations

### Sidecar Caching
- [ ] Extend SidecarManager with binary format
- [ ] Implement save/load fingerprint methods
- [ ] Add CRC32 validation
- [ ] Add tests for cache correctness

### Integration
- [ ] Update LibraryManager with async initialization
- [ ] Update LibraryScanner to queue fingerprints
- [ ] Add shutdown hooks
- [ ] Test end-to-end flow

### Optimization (Optional)
- [ ] Profile harmonic analyzer bottleneck
- [ ] Implement faster harmonic ratio algorithm
- [ ] Target: < 2s extraction for 3-min track

---

**Status**: Ready for Implementation
**Next**: Begin coding FingerprintExtractionQueue class

