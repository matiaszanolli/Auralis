# Audio Engine Audit Report (v4)

**Date**: 2026-03-02
**Auditor**: Claude Opus 4.6 (automated)
**Scope**: Auralis core audio engine — 7 dimensions
**Method**: Systematic code review with 4 parallel exploration agents (DSP + sample integrity, player + I/O, parallel processing + analysis, library + database), followed by manual verification of all HIGH-severity findings against source code. Prior audit findings (ENG-16 through ENG-21) re-verified for regression.

## Executive Summary

Fourth audit pass of the Auralis core audio engine. Five of six findings from the 2026-03-01 audit (ENG-16 through ENG-20) are now fixed. ENG-21 (unused mask variable) remains. Found 15 new issues across all 7 dimensions. Eliminated 9 false positives from agent exploration.

**Results**: 15 confirmed findings (0 CRITICAL, 4 HIGH, 7 MEDIUM, 4 LOW).

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 4 |
| MEDIUM | 7 |
| LOW | 4 |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| ENG-16: stereo_width_analysis NaN for silent audio | #2611 | **FIXED** — `stereo.py:39-42` now guards `np.std(left) < 1e-9` before `np.corrcoef()` |
| ENG-17: _get_default_fingerprint() scale ×100 mismatch | #2612 | **FIXED** — values corrected to 0-1 range (`0.05, 0.15, 0.15, 0.30, 0.20, 0.10, 0.05`) |
| ENG-18: artist_repository nested joinedload Cartesian product | #2613 | **FIXED** — `get_by_id()` and `get_by_name()` now use `selectinload` at each level |
| ENG-19: lookahead_buffer partial-update no .copy() | #2614 | **FIXED** — ndim guard added, copy pattern consistent |
| ENG-20: Dead attribute expression params.peak_target_db | #2615 | **FIXED** — line removed |
| ENG-21: Unused mask in _apply_window_smoothing() | #2616 | **STILL OPEN** — `mask` variable on line 120 still computed but unused |

## Findings

---

### ENG-22: EQ overlap-add loop overwrites samples instead of summing them

- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/eq_processor.py:166-191`
- **Status**: NEW
- **Description**: The psychoacoustic EQ processing loop steps by `chunk_size // 2` (50% overlap) but uses direct assignment (`=`) to write processed chunks into the output buffer. In a correct overlap-add implementation, overlapping regions must be **summed** (`+=`) while each chunk is multiplied by a synthesis window so that overlapping windows add to unity. With `=`, the second chunk completely overwrites the first chunk's contribution in the overlapping region, discarding 50% of the processed spectral data.
- **Evidence**:
  ```python
  # eq_processor.py:166-191
  chunk_size = self.psychoacoustic_eq.fft_size
  processed_audio = np.zeros_like(audio)

  for i in range(0, len(audio), chunk_size // 2):  # 50% overlap
      end_idx = min(i + chunk_size, len(audio))
      chunk = audio[i:end_idx]
      # ... pad and process ...
      processed_audio[i:end_idx] = processed_chunk[:valid_length]  # = instead of +=
  ```
  Compare with correct overlap-add in `parallel_processor.py` which uses `+=` with crossfade windows.
- **Impact**: Loss of ~50% of processed spectral data per overlap region, causing audible discontinuities at chunk boundaries (clicks/pops) and tonal artifacts from abrupt transitions. The 50% overlap provides no benefit since each region is fully overwritten.
- **Suggested Fix**: Apply a Hann synthesis window to each processed chunk and use `+=` instead of `=`, or remove the overlap entirely and step by full `chunk_size` if overlap-add is not intended.

---

### ENG-23: AdaptiveLimiter applies a single scalar gain to the entire chunk

- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/limiter.py:78-102`
- **Status**: NEW
- **Description**: `_process_core()` finds a single peak level for the entire chunk (`np.max(np.abs(audio))` at line 89), derives a single gain scalar (line 93), and applies it uniformly to every sample (line 102: `delayed_audio * smoothed_gain`). When a chunk contains a loud transient in one region and quieter material elsewhere, the entire chunk is attenuated by the amount needed for the loudest sample.
- **Evidence**:
  ```python
  # limiter.py:88-102
  peak_level = np.max(np.abs(audio))              # single scalar from entire chunk
  if peak_level > threshold_linear:
      required_gain = threshold_linear / peak_level # single scalar
  else:
      required_gain = 1.0
  smoothed_gain = self.gain_smoother.process(required_gain)
  limited_audio = delayed_audio * smoothed_gain    # applied uniformly
  ```
  Contrast with `BrickWallLimiter._process_core()` which correctly computes a per-sample gain curve using `scipy.ndimage.maximum_filter1d`.
- **Impact**: Over-attenuation of quiet passages within a chunk, loss of dynamics (acts like an infinite-ratio block compressor), and pumping artifacts between chunks. The `gain_smoother` only smooths between chunk-level scalars, not within a chunk.
- **Suggested Fix**: Compute a per-sample gain reduction envelope based on the lookahead peak buffer (similar to `BrickWallLimiter._process_core()`).

---

### ENG-24: LowMidTransientEnhancer global normalization alters entire signal level

- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/dynamics/lowmid_transient_enhancer.py:173-176`
- **Status**: NEW
- **Description**: After adding transient expansion energy to local windows around detected peaks, the function checks if any sample exceeds 1.0 and divides the **entire** signal by `max_val`. If a single expanded transient peaks at 1.05, all audio is scaled down by 1/1.05, reducing the level of unaffected regions by ~0.4 dB. For aggressive settings (expansion ratio up to 3.0x), a single peak could reduce the whole signal by several dB.
- **Evidence**:
  ```python
  # lowmid_transient_enhancer.py:173-176
  max_val = np.max(np.abs(output))
  if max_val > 1.0:
      output = output / max_val  # global normalization from local enhancement
  ```
- **Impact**: Global level reduction from localized transient expansion defeats the enhancement purpose. Subsequent processing stages see a lower-level signal, changing their behavior.
- **Suggested Fix**: Apply localized peak limiting (e.g., `np.clip` or `soft_clip()`) only to the expanded regions instead of normalizing the entire signal.

---

### ENG-25: `normalize()` returns an alias instead of a copy for silent audio

- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/basic.py:34-48`
- **Status**: NEW
- **Description**: When `peak > 0`, the multiplication `audio * scalar` creates a new array (copy). When `peak == 0` (silent audio), the original array is returned directly as an alias. This creates an inconsistent copy/alias contract.
- **Evidence**:
  ```python
  # basic.py:34-48
  def normalize(audio, target_level=1.0):
      peak = np.max(np.abs(audio))
      if peak > 0:
          return audio * float(target_level / peak)  # new array
      return audio                                    # alias to input
  ```
- **Impact**: If any caller modifies the result of `normalize()` in-place when input is silent, it corrupts the original. Latent until a caller both modifies the result in-place AND passes silent audio.
- **Suggested Fix**: Change the fallback to `return audio.copy()`.

---

### ENG-26: `previous_track()` never resumes playback after loading

- **Severity**: HIGH
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:295-304`
- **Status**: NEW
- **Description**: `previous_track()` calls `self.load_file()` which internally calls `self.playback.stop()`, transitioning to STOPPED state. It then checks `self.playback.is_playing()` — which is always `False` after stop — so `play()` is never called. Compare with `next_track()` (line 276) which correctly captures `was_playing = self.playback.is_playing()` **before** loading.
- **Evidence**:
  ```python
  # enhanced_audio_player.py:295-304
  def previous_track(self) -> bool:
      prev_track = self.queue.previous_track()
      if prev_track:
          file_path = prev_track.get('file_path') or prev_track.get('path')
          if file_path and self.load_file(file_path):       # stop() called inside
              if self.playback.is_playing():                 # ALWAYS False after stop
                  self.playback.play()                       # never reached
              return True
      return False

  # next_track() (line 276) — correct pattern:
  def next_track(self) -> bool:
      was_playing = self.playback.is_playing()   # captured BEFORE load
      if self.gapless.advance_with_prebuffer(was_playing):
          if was_playing:
              self.playback.play()
  ```
- **Impact**: When a user presses "previous track" while playing, playback stops instead of continuing. The user must manually press play again. User-facing functional bug.
- **Suggested Fix**: Capture `was_playing` before calling `load_file()`, use it to conditionally call `play()` after.

---

### ENG-27: `read_and_advance_position()` allows unbounded position growth past track end

- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/playback_controller.py:128-143`
- **Status**: NEW
- **Description**: When the audio callback continues delivering chunks after the track reaches its end (while waiting for auto-advance or if no next track exists), `read_and_advance_position()` keeps incrementing `self.position` by `chunk_size` with no upper bound. This violates the critical invariant: **position <= duration**.
- **Evidence**:
  ```python
  # playback_controller.py:128-143
  def read_and_advance_position(self, advance_by: int) -> int:
      with self._lock:
          pos = self.position
          self.position += advance_by   # no upper-bound clamp
          return pos
  ```
  The `_get_position_seconds()` in `integration_manager.py:252` then reports `position_seconds > duration_seconds`.
- **Impact**: Frontend progress bar displays incorrect values (e.g., 120s / 90s). Position grows arbitrarily while outputting silence until next track loads.
- **Suggested Fix**: Clamp position in `_get_position_seconds()`: `return min(self.playback.position / sample_rate, duration)`.

---

### ENG-28: Player loader bypasses FFmpeg for M4A/AAC/WMA/OPUS formats

- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loader.py:33-35`
- **Status**: NEW
- **Description**: The player subsystem uses `auralis/io/loader.py` which relies exclusively on `soundfile` (libsndfile). The more capable `unified_loader.py` — which routes M4A, AAC, WMA, and OPUS through FFmpeg — is never used by the player. `soundfile` does not natively support these formats.
- **Evidence**:
  ```python
  # loader.py:33-35
  def load(file_path, file_type="audio"):
      audio_data, sample_rate = sf.read(file_path, dtype=np.float32, always_2d=True)
  ```
  Used by `audio_file_manager.py:17` and `gapless_playback_engine.py:17`.
- **Impact**: M4A, AAC, WMA, and OPUS tracks fail to load in the player with ERROR state, despite being processable by the backend streaming API. Inconsistent format support across the application.
- **Suggested Fix**: Import from `unified_loader.py` which handles FFmpeg fallback, or add FFmpeg fallback to `loader.py`.

---

### ENG-29: Multi-channel downmix retains full array in memory (no `.copy()`)

- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loader.py:43`
- **Status**: NEW
- **Description**: `audio_data[:, :2]` creates a NumPy view, not a copy. The view holds a reference to the original N-channel array, preventing GC from freeing unused channels. Compare with `soundfile_loader.py:73` which correctly uses `.copy()`.
- **Evidence**:
  ```python
  # loader.py:43
  audio_data = audio_data[:, :2]           # view, not copy

  # soundfile_loader.py:73 — correct:
  audio_data = audio_data[:, :2].copy()    # releases unused channels
  ```
- **Impact**: For a 10-minute, 6-channel, 48kHz file: ~92 MB wasted memory per loaded track. Doubles with gapless prebuffer.
- **Suggested Fix**: Add `.copy()`: `audio_data = audio_data[:, :2].copy()`.

---

### ENG-30: `dynamic_range_variation` fingerprint dimension always returns default 0.5

- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/utilities/variation_ops.py:95-119`
- **Status**: NEW
- **Description**: `librosa.feature.rms()` defaults to `center=True`, which zero-pads the audio by `frame_length // 2` on each side before framing, producing more output frames than `get_frame_peaks()` which uses unpadded framing. The difference is consistently 2 extra frames. At line 112, `20 * np.log10(peaks_safe / rms_safe)` raises `ValueError` due to shape mismatch (e.g., `(39,)` vs `(41,)` for 10s audio). The broad `except Exception` at line 117 catches this and returns hardcoded `0.5` for every track.
- **Evidence**:
  ```python
  # variation_ops.py:98-102 — librosa with center=True (default)
  rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
  # 10s audio at 22050 Hz → 41 frames

  # variation_ops.py:107 — get_frame_peaks uses manual unpadded framing
  frame_peaks = VariationOperations.get_frame_peaks(audio, hop_length, frame_length)
  # 10s audio at 22050 Hz → 39 frames

  # variation_ops.py:112 — shape mismatch causes ValueError
  crest_db = 20 * np.log10(peaks_safe / rms_safe)  # (39,) / (41,) → ValueError

  # variation_ops.py:117-119 — swallowed by broad except
  except Exception as e:
      logger.debug(f"Dynamic range variation calculation failed: {e}")
      return 0.5  # ← every track lands here
  ```
  Both standalone and `calculate_all()` paths (lines 218-232) trigger the same bug.
- **Impact**: The `dynamic_range_variation` dimension of the 25D fingerprint is never computed. All tracks get identical 0.5. Similarity search loses one discriminative axis — classical (high variation) and pop (low variation) are indistinguishable on this dimension. Fixing requires full fingerprint recomputation.
- **Suggested Fix**: Pass `center=False` to `librosa.feature.rms()` at lines 98-102 and 221-225 to match `get_frame_peaks` framing.

---

### ENG-31: `shutdown()` WAL checkpoint silently fails due to raw string execute

- **Severity**: HIGH
- **Dimension**: Library & Database
- **Location**: `auralis/library/manager.py:213,222`
- **Status**: NEW
- **Description**: SQLAlchemy 2.0+ no longer accepts raw string arguments to `Connection.execute()`. Lines 213 and 222 pass plain strings which raise `ObjectNotExecutableError`. Both calls are guarded by broad `except Exception` handlers that log the error but swallow it, so neither WAL checkpoint nor query planner optimization ever executes.
- **Evidence**:
  ```python
  # manager.py:213
  result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # raises ObjectNotExecutableError
  # manager.py:222
  conn.execute("PRAGMA optimize")                           # same
  ```
  Both need `from sqlalchemy import text` and wrapping: `conn.execute(text("PRAGMA ..."))`.
- **Impact**: On every shutdown, the WAL file is never checkpointed. The `-wal` and `-shm` files persist and grow across sessions. `PRAGMA optimize` never runs, so query planner statistics degrade for large libraries. The shutdown method reports success despite both critical steps failing.
- **Suggested Fix**: Wrap both PRAGMAs with `text()`: `conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))`.

---

### ENG-32: `FingerprintService` bypasses repository pattern with raw `sqlite3` — queries nonexistent columns

- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/analysis/fingerprint/fingerprint_service.py:106-341`
- **Status**: NEW
- **Description**: This service creates its own raw `sqlite3.Connection` objects outside the SQLAlchemy engine. It queries `SELECT tempo_bpm, lufs, crest_db, bass_pct, mid_pct, ... FROM tracks WHERE filepath = ?` — but these columns do not exist on the `tracks` table. They exist on `track_fingerprints` (via the `TrackFingerprint` model in `fingerprint.py`). Both `_load_from_database` and `_save_to_database` will always fail silently (exception handlers return `None`/`False`), making the database cache tier permanently non-functional.
- **Evidence**:
  ```python
  # fingerprint_service.py:128-138
  cursor.execute("""
      SELECT tempo_bpm, lufs, crest_db, bass_pct, mid_pct, ...
      FROM tracks WHERE filepath = ?          -- columns don't exist on tracks table
  """, (filepath,))
  ```
  The `TrackFingerprint` model (in `auralis/library/models/fingerprint.py:40-54`) defines these columns on the `track_fingerprints` table, not `tracks`.
- **Impact**: The "database cache tier" in the 3-tier caching strategy always fails through to file cache or recomputation. Users experience slower fingerprint lookups. Raw `sqlite3` connections also bypass connection pooling and WAL configuration.
- **Suggested Fix**: Rewrite `_load_from_database`/`_save_to_database` to use `FingerprintRepository` from the repository layer, or at minimum fix the table name to `track_fingerprints`.

---

### ENG-33: `count()` on `joinedload` queries returns inflated totals

- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository.py:406-413, 437-444, 468-476`
- **Status**: NEW
- **Description**: `get_recent()`, `get_popular()`, and `get_favorites()` call `.count()` on queries that include `joinedload(Track.artists)`. SQLAlchemy translates `joinedload` into a LEFT OUTER JOIN. For a track with N artists, the JOIN produces N rows. `.count()` counts joined rows, not distinct tracks. For a library where tracks average 1.5 artists, the total is inflated by ~50%.
- **Evidence**:
  ```python
  # track_repository.py:406-413
  query = (
      session.query(Track)
      .options(joinedload(Track.artists), joinedload(Track.album))
      .order_by(Track.created_at.desc())
  )
  total = query.count()   # counts JOIN rows, not distinct tracks
  ```
  `get_all()` (line 501) correctly uses a separate `session.query(Track).count()` without joinedload.
- **Impact**: Pagination metadata (`total` field) is incorrect — frontend shows wrong "showing X of Y" counts and requests pages beyond the real total that return empty results.
- **Suggested Fix**: Compute `total` with a separate query: `total = session.query(func.count(Track.id)).scalar()`.

---

### ENG-34: `QueueTemplateRepository.search()` does not escape LIKE metacharacters

- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/queue_template_repository.py:345-366`
- **Status**: NEW
- **Description**: Every other `search()` method in the codebase (track, album, artist, genre) escapes LIKE metacharacters (`%`, `_`, `\`) before interpolation (fix #2405). This method was missed. Also, line 357 calls `query.lower()` but discards the return value (strings are immutable).
- **Evidence**:
  ```python
  # queue_template_repository.py:359
  templates = session.query(QueueTemplate).filter(
      (QueueTemplate.name.ilike(f'%{query}%'))     # unescaped metacharacters
  )
  ```
- **Impact**: Searching queue templates with `%` or `_` characters returns over-broad results. LOW severity due to small dataset.
- **Suggested Fix**: Apply the same escaping pattern used in other search methods.

---

### ENG-35: Missing database indexes on frequently-filtered and frequently-sorted columns

- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/models/core.py`, `auralis/library/models/fingerprint.py`
- **Status**: NEW
- **Description**: Several columns used in `WHERE`, `ORDER BY`, or `JOIN` conditions lack database indexes:
  1. `Track.favorite` — filtered with `== True` in `get_favorites()` on every Favorites page load
  2. `Track.play_count` — `ORDER BY play_count DESC` in `get_popular()`
  3. `Track.created_at` (from `TimestampMixin`) — `ORDER BY created_at DESC` in `get_recent()`
  4. `SimilarityGraph.track_id` — filtered in `get_neighbors()`, has ForeignKey but SQLite does NOT auto-index FK columns
  5. `SimilarityGraph.rank` — `ORDER BY rank` in `get_neighbors()`
- **Evidence**: Column definitions in `core.py:72` (`play_count`), `core.py:75` (`favorite`), and `fingerprint.py:196` (`track_id`) all lack `index=True`.
- **Impact**: For large libraries (50k+ tracks, 500k+ similarity edges), "Recent", "Popular", and "Favorites" pages require full table scans. Similarity lookups degrade linearly.
- **Suggested Fix**: Add `index=True` to these column definitions and create a composite index `(track_id, rank)` on `SimilarityGraph`.

---

### ENG-36: `get_current_version()` leaves session invalidated after query failure

- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/migration_manager.py:149-170`
- **Status**: NEW
- **Description**: When the `schema_version` table doesn't exist (fresh database), `session.query(SchemaVersion)` raises `OperationalError`. The exception handler catches it and returns 0 but does not call `self.session.rollback()`. In SQLAlchemy, the session enters an invalidated state. Subsequent operations (like `_record_migration()` using `session.add()` + `session.commit()`) may fail with `InvalidRequestError`.
- **Evidence**:
  ```python
  # migration_manager.py:167-170
  except Exception as e:
      logger.debug(f"Schema version table not found: {e}")
      return 0  # ← no session.rollback()
  ```
- **Impact**: On a truly fresh database, the migration sequence can fail with a cryptic `InvalidRequestError`, preventing application startup. Partially mitigated by `Base.metadata.create_all()` bypassing the session.
- **Suggested Fix**: Add `self.session.rollback()` before `return 0` in the exception handler.

---

## False Positives Eliminated

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| `ParallelFFTProcessor` chunk slicing creates views not copies | Chunks are read-only (windowed + FFT'd, never mutated). View is safe. |
| `fingerprint_service.py _load_from_database` uses `conn` after `with` block | sqlite3 `with` is a transaction manager, not a connection closer. Safe. |
| `feature_extractor.py _onset_rate` division by `len(audio) / sr` | Minimum audio length enforced at line 67. No div-by-zero possible. |
| `ContentAnalysisOperations._to_mono` uses axis=1 | Content analysis subsystem uniformly uses `(samples, channels)` layout. Consistent. |
| Streaming harmonic analyzer non-determinism via `np.random.randint` | Expected: reservoir sampling (Vitter's Algorithm R). |
| `QualityMetrics` loudness chunking drops partial last chunk | Standard per ITU-R BS.1770-4 requiring complete 400ms gating blocks. |
| `lru_cache` on `create_ml_genre_classifier` thread safety | Python's `lru_cache` has internal lock. Cached instance has no mutable post-construction state. |
| `QualityMetrics.assess_quality` stereo layout assumption | All callers consistently provide `(samples, channels)` format. |
| `simple_mastering.py` chunked crossfade assembly incorrect | Equal-power cosine crossfade verified correct. Assertion at line 232 catches drift. |

## Checklist Summary

### Dimension 1: Sample Integrity
- [x] `len(output) == len(input)` — no new violations
- [x] `audio.copy()` before in-place ops — maintained (ENG-19 fixed)
- [x] dtype preservation — float32/float64 throughout
- [x] Clipping prevention — output clamped
- [x] Mono/stereo handling — correct
- [x] Bit depth output — pcm16/pcm24 correctly scaled
- [ ] **LowMidTransientEnhancer global normalization** — ENG-24
- [ ] **normalize() alias for silent audio** — ENG-25

### Dimension 2: DSP Pipeline Correctness
- [x] Processing chain order — EQ → dynamics → mastering
- [x] Parameter validation — CompressorSettings clamps all values
- [x] Phase coherence — maintained
- [x] **stereo_width_analysis NaN** — ENG-16 FIXED
- [x] **params.peak_target_db dead statement** — ENG-20 FIXED
- [ ] **EQ overlap-add overwrites instead of summing** — ENG-22
- [ ] **AdaptiveLimiter scalar gain on entire chunk** — ENG-23
- [ ] **Unused mask in _apply_window_smoothing** — ENG-21 (still open)

### Dimension 3: Player State Machine
- [x] State transitions under RLock — properly serialized
- [x] Queue bounds — validated under QueueManager RLock
- [x] Callback safety — snapshot-outside-lock pattern
- [x] Resource cleanup — cleanup() chain properly signals shutdown
- [ ] **previous_track() never resumes playback** — ENG-26
- [ ] **Position unbounded growth past track end** — ENG-27

### Dimension 4: Audio I/O
- [x] Corrupt file handling — meaningful errors
- [x] FFmpeg subprocess cleanup — timeout + finally block
- [x] File path safety — validated before FFmpeg
- [x] Sample rate detection — from metadata
- [ ] **Player loader bypasses FFmpeg** — ENG-28
- [ ] **Multi-channel downmix no copy** — ENG-29

### Dimension 5: Parallel Processing
- [x] Chunk independence — verified copies
- [x] Reassembly order — correct
- [x] Boundary smoothing — crossfade verified
- [x] Sample count preservation — assertion at line 232

### Dimension 6: Analysis Subsystem
- [x] Fingerprint determinism — confirmed
- [x] ML model lifecycle — cached via lru_cache
- [x] Quality metrics — ITU-R BS.1770-4 compliant
- [x] Thread safety — no shared mutable state
- [ ] **dynamic_range_variation always 0.5** — ENG-30

### Dimension 7: Library & Database
- [x] Artist/genre race condition — FIXED (#2594)
- [x] artist_repository selectinload — FIXED (ENG-18)
- [x] Engine disposal — FIXED (#2066)
- [ ] **WAL checkpoint raw string execute** — ENG-31
- [ ] **FingerprintService raw sqlite3, wrong table** — ENG-32
- [ ] **count() inflated by joinedload** — ENG-33
- [ ] **LIKE metacharacters unescaped** — ENG-34
- [ ] **Missing database indexes** — ENG-35
- [ ] **get_current_version() session invalidated** — ENG-36
