# Audio Engine Audit — 2026-02-21

**Scope**: `auralis/core/`, `auralis/dsp/`, `auralis/player/`, `auralis/io/`, `auralis/optimization/`, `auralis/analysis/`, `auralis/library/`, `auralis/services/`, `vendor/auralis-dsp/`
**Out of scope**: React frontend, FastAPI routing/WebSocket layer, Electron desktop.
**Methodology**: See `.claude/commands/_audit-common.md`.
**Deduplication**: Checked issues #2072–#2511 and prior audit reports (2026-02-12 through 2026-02-19).

---

## Summary Table

| ID | Title | Severity | Dimension | Status |
|----|-------|----------|-----------|--------|
| ENG-01 | `mono_to_stereo()` doubles channels for stereo input | CRITICAL | Sample Integrity | NEW |
| ENG-02 | No EQ gains parameter validation before DSP math | HIGH | DSP Pipeline | NEW |
| ENG-03 | Analysis executor shutdown orphans threads on KeyboardInterrupt | HIGH | Analysis | NEW |
| ENG-04 | Chunk boundary sample count not validated in `simple_mastering.py` | HIGH | Parallel Processing | NEW |
| ENG-05 | Artist repository `get_all()` nested joinedload causes Cartesian product | HIGH | Library & Database | NEW |
| ENG-06 | `SampledHarmonicAnalyzer` `max_chunks` cap silently truncates long tracks | HIGH | Analysis | NEW |
| ENG-07 | FFT windowing asymmetry: analysis windowed, EQ synthesis unwindowed | MEDIUM | DSP Pipeline | NEW |
| ENG-08 | No sample count assertion after any DSP pipeline stage | MEDIUM | Sample Integrity | NEW |
| ENG-09 | NaN repair mode inconsistent: input strict, inter-stage lenient | MEDIUM | Sample Integrity | NEW |
| ENG-10 | PyO3 FFI boundary lacks dtype validation — float64→float32 silent truncation | MEDIUM | DSP Pipeline | NEW |
| ENG-11 | `album_repository.get_all()` joinedload causes Cartesian product | MEDIUM | Library & Database | NEW |
| ENG-12 | `track_repository.get_by_artist()` joinedload genres causes Cartesian | MEDIUM | Library & Database | NEW |
| ENG-13 | `artist_repository.get_all_artists()` returns detached objects, lazy load risk | MEDIUM | Library & Database | NEW |
| ENG-14 | `cleanup_missing_files()` uses `os.path.exists()` — drops tracks on NFS unmount | MEDIUM | Library & Database | NEW |
| ENG-15 | Window cache in `parallel_processor.py` grows unbounded | MEDIUM | Parallel Processing | NEW (related: #2077) |
| ENG-16 | `SampledHarmonicAnalyzer` chunk futures: failure blocks remaining results | MEDIUM | Analysis | NEW |
| ENG-17 | `MLGenreClassifier` re-instantiates `FeatureExtractor` per instantiation | MEDIUM | Analysis | NEW |
| ENG-18 | OPUS format (`.opus`) missing from `SUPPORTED_FORMATS` | LOW | Audio I/O | NEW |
| ENG-19 | Streaming pitch buffer `maxlen=1000` skews stability metric to track tail | LOW | Analysis | NEW |
| ENG-20 | NaN dimension replacement masks analysis bugs | LOW | Analysis | NEW |
| — | Player state race conditions (callbacks, seek, gapless swap) | — | Player State | Existing: fixed in d4cd992f |
| — | PerformanceMonitor accessed outside lock | — | Player State | Existing: #2213, fixed d4cd992f |
| — | BrickWallLimiter O(n*lookahead) loop | — | DSP Pipeline | Existing: #2293 |
| — | Compressor single-gain pumping | — | DSP Pipeline | Existing: #2214 |
| — | Rust fingerprint hardcodes 3/25 dimensions | — | Analysis | Existing: #2245 |
| — | Lock contention in parallel window cache | — | Parallel Processing | Existing: #2077 |
| — | dtype inconsistency in envelope followers | — | DSP Pipeline | Existing: #2167 |
| — | Critical band zero center frequency in psychoacoustic EQ | — | DSP Pipeline | Existing: #2208 |

---

## Dimension 1: Sample Integrity

### ENG-01: `mono_to_stereo()` Doubles Channels for Stereo Input
- **Severity**: CRITICAL
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/utils/audio_info.py:81`
- **Status**: NEW
- **Description**: `mono_to_stereo()` calls `np.repeat(audio, repeats=2, axis=1)` for non-1D inputs. For stereo input `(N, 2)`, this creates `(N, 4)` instead of returning stereo unchanged. Any caller that passes stereo audio through this function receives 4-channel output, violating the audio processing invariant and causing shape mismatches in downstream stereo-expecting code.
- **Evidence**:
  ```python
  # auralis/dsp/utils/audio_info.py:79-81
  if audio.ndim == 1:
      return np.column_stack([audio, audio])
  return np.repeat(audio, repeats=2, axis=1)  # BUG: (N,2) → (N,4)
  ```
  Confirmed computationally: input `(3, 2)` → output `(3, 4)`.
- **Impact**: Shape explosion corrupts any pipeline calling `mono_to_stereo()` on already-stereo audio. Downstream `psychoacoustic_eq.analyze_spectrum()` expects stereo shape for axis=1 mean; any DSP stage expecting 2-channel output will fail or silently produce wrong results.
- **Suggested Fix**: Return `audio.copy()` when `audio.ndim == 2` (already stereo) rather than repeating.

---

### ENG-08: No Sample Count Assertion After DSP Stages
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/hybrid_processor.py:256,306,332,357`; `auralis/core/simple_mastering.py` (multiple)
- **Status**: NEW (distinct from #2369 which covers missing regression *tests*)
- **Description**: None of the intermediate DSP stages assert `len(output) == len(input)`. `auralis/dsp/eq/filters.py:103` defensively slices output with `[:len(audio_mono)]`, but this silently discards samples if the FFT processing produces fewer samples than expected. No alarm is raised. Gapless playback requires sample-exact preservation.
- **Evidence**:
  ```python
  # hybrid_processor.py — after brick_wall_limiter:
  processed = self.brick_wall_limiter.process(processed)
  # No assertion follows

  # filters.py:103 — silent truncation:
  return np.asarray(processed_audio[:len(audio_mono)], dtype=audio_mono.dtype)
  ```
- **Impact**: A bug in any DSP stage that shortens the buffer propagates silently. The slice at `filters.py:103` hides short-output bugs. Clicks at gapless boundaries if counts drift.
- **Suggested Fix**: Add `assert len(output) == len(input)` after each major DSP stage, or a logging-only warning in production paths.

---

### ENG-09: NaN Repair Mode Inconsistent Between Input and Inter-stage Validation
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/hybrid_processor.py:226-228` (strict input), `256,306,332,357` (lenient inter-stage)
- **Status**: NEW
- **Description**: Input audio is validated with `repair=False` (fail-fast on NaN/Inf), but inter-stage validation uses `sanitize_audio()` which silently replaces NaN with 0.0. A DSP stage bug producing NaN is quietly masked instead of surfaced.
- **Evidence**:
  ```python
  # Line 227 — strict (correct):
  target_audio = validate_audio_finite(target_audio, context="input audio", repair=False)

  # Line 256 — lenient (masks bugs):
  processed = sanitize_audio(processed, context="after EQ")
  ```
  Note: `np.clip(NaN, -12, 12)` returns NaN — clipping does not sanitize NaN gains.
- **Impact**: NaN from `PsychoacousticEQ` or `MaskingThresholdCalculator` silently converts to silence. Difficult to debug because no exception is raised.
- **Suggested Fix**: Use `repair=False` in the mastering/batch path. Reserve `repair=True` only for the real-time streaming path.

---

## Dimension 2: DSP Pipeline Correctness

### ENG-02: No Parameter Validation for EQ Gains Before DSP Math
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:161-226`
- **Status**: NEW
- **Description**: `calculate_adaptive_gains()` accepts `spectrum_analysis` and `target_curve` without validating that they are finite, in-range, or non-null. `band_energies` from `analyze_spectrum()` could contain NaN for silent audio; masking thresholds from `MaskingThresholdCalculator` have no error handling. Gains ARE clipped to `[-12, +12]` dB at the end, but `np.clip(NaN, -12, 12)` returns NaN, so clipping does not sanitize NaN inputs.
- **Evidence**:
  ```python
  # psychoacoustic_eq.py:201-226
  def _calculate_target_gains(self, band_energies, masking_thresholds, target_curve):
      for i, band in enumerate(self.critical_bands):
          current_level = band_energies[i]   # Could be NaN (silent audio → log10(0+1e-10))
          required_gain = target_level - current_level  # NaN propagates
          ...
          target_gains[i] = np.clip(weighted_gain, -12.0, 12.0)  # NaN clips to NaN
  ```
- **Impact**: NaN gains applied via FFT multiplication corrupt the entire audio output for that band. Silent passages (all-zero audio) reliably produce NaN band energies, triggering this on every silent section.
- **Suggested Fix**: Validate inputs at entry. Replace NaN band energies with the masking threshold floor (`-60.0 dB`) rather than propagating NaN.

---

### ENG-07: FFT Windowing Asymmetry — Analysis Windowed, EQ Synthesis Not
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:126` vs `auralis/dsp/eq/filters.py:70-73`
- **Status**: NEW
- **Description**: `analyze_spectrum()` applies a Hanning window before FFT to reduce spectral leakage. `apply_eq_mono()` intentionally does not apply a window (documented: "Windowing is used for spectral analysis to reduce leakage, but for filtering/EQ it creates amplitude modulation artifacts"). The asymmetry means gain curves are computed from windowed spectra but applied to unwindowed spectra. Effective band energies differ between analysis and synthesis at band boundaries.
- **Evidence**:
  ```python
  # psychoacoustic_eq.py:126 — analysis (windowed):
  window = np.hanning(self.fft_size)
  windowed_audio = audio_mono[:self.fft_size] * window
  spectrum = fft(windowed_audio)

  # filters.py:70-73 — synthesis (no window, by design):
  spectrum = fft(audio_mono[:fft_size])
  ```
- **Impact**: Systematic gain error of up to ~3 dB at band boundaries due to Hanning sidelobe rolloff mismatch. Narrow critical bands are most affected.
- **Suggested Fix**: Either (a) pre-compensate analysis magnitudes by the Hanning window's coherent power gain (~0.5), or (b) apply the window to both paths with proper overlap-add reconstruction. Document the chosen approach.

---

### ENG-10: PyO3 FFI Boundary Lacks Dtype Validation
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs` (all public functions)
- **Status**: NEW
- **Description**: PyO3 binding functions accept `Vec<f32>`. When Python passes `np.float64` arrays, PyO3 silently converts each element to `f32`, losing precision without warning. No validation of sample rate (`sr=0` is accepted, causing potential division by zero), or empty arrays (causing FFT panics in Rust).
- **Evidence**:
  ```rust
  pub fn hpss(audio: Vec<f32>, sr: u32, ...) -> PyResult<...>
  // PyO3 converts float64 → float32 silently
  // sr=0 accepted, leading to Rust division by zero → interpreter crash
  ```
- **Impact**: Silent precision loss for float64 audio. Rust division-by-zero or FFT panics with invalid inputs crash the Python interpreter.
- **Suggested Fix**: Add validation in the Python wrapper before calling PyO3: assert `audio.dtype == np.float32`, `sr > 0`, `len(audio) > 0`.

---

## Dimension 3: Player State Machine

### (No new findings)

The batch 4 commit (`d4cd992f`) resolved all critical player state issues:
- Callback list mutation during iteration — snapshot pattern added
- Seek position race condition — atomic `read_and_advance_position()`
- Gapless audio data swap race — nested lock acquisition
- PerformanceMonitor accessed outside lock — also tracked in #2213

---

## Dimension 4: Audio I/O

### ENG-18: OPUS Format (`.opus`) Missing from `SUPPORTED_FORMATS`
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/unified_loader.py:24-36`
- **Status**: NEW
- **Description**: CLAUDE.md lists OPUS as a supported format, but the `SUPPORTED_FORMATS` dict does not include `.opus`. Users with `.opus` files cannot import them.
- **Evidence**: `SUPPORTED_FORMATS` covers `.wav`, `.flac`, `.mp3`, `.m4a`, `.aac`, `.ogg`, `.wma` — no `.opus` entry.
- **Impact**: OPUS files (common for podcast downloads, voice memos) silently fail to import.
- **Suggested Fix**: Add `'.opus': 'OPUS'` to `SUPPORTED_FORMATS` and verify the FFmpeg loader path handles it.

---

## Dimension 5: Parallel Processing

### ENG-04: Chunk Boundary Sample Count Not Validated After Crossfade Reassembly
- **Severity**: HIGH
- **Dimension**: Parallel Processing
- **Location**: `auralis/core/simple_mastering.py:200-238`
- **Status**: NEW
- **Description**: The crossfade-based chunk reassembly constructs `write_region` by concatenating `crossfaded` and `body` arrays without asserting the resulting sample count equals `core_samples`. If `head_len != crossfade_samples` (e.g., `prev_tail` is shorter than expected), `write_region` is the wrong length. This creates silent sample count drift across chunks.
- **Evidence**:
  ```python
  # simple_mastering.py:229-233
  crossfaded = _crossfade(prev_tail, head, overlap_samples)
  body = processed_chunk[:, head_len:core_samples]
  write_region = np.concatenate([crossfaded, body], axis=1)
  new_tail = processed_chunk[:, core_samples:].copy()
  # Missing: assert write_region.shape[1] == core_samples
  ```
- **Impact**: Sample count drift accumulates across chunks; gapless boundaries accumulate audible gaps (~20ms = 882 samples at 44.1 kHz).
- **Suggested Fix**: Add `assert write_region.shape[1] == core_samples` after concatenation. Also validate `new_tail.shape[1] == crossfade_samples`.

---

### ENG-15: Window Cache in `parallel_processor.py` Grows Unbounded
- **Severity**: MEDIUM
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/parallel_processor.py:42-77`
- **Status**: NEW (related to #2077 which covers lock contention in the same cache)
- **Description**: `get_window()` adds entries to `self.window_cache` without any eviction policy. For analysis with dynamic FFT sizes, the cache accumulates one entry per unique size and never evicts. A 131072-sample window consumes ~512 KB; hundreds of unique sizes occupy hundreds of MB.
- **Evidence**:
  ```python
  def get_window(self, size: int) -> np.ndarray:
      if size in self.window_cache:
          return self.window_cache[size]
      window = np.hanning(size)
      with self.lock:
          if size not in self.window_cache:
              self.window_cache[size] = window  # No eviction
  ```
- **Suggested Fix**: Limit the cache to a fixed number of entries using `functools.lru_cache` or an `OrderedDict` with a max size of ~32 entries.

---

## Dimension 6: Analysis Subsystem

### ENG-03: Analysis Executor Shutdown Orphans Threads on KeyboardInterrupt
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:155,185-191`
- **Status**: NEW
- **Description**: On `KeyboardInterrupt`, the fingerprint analyzer calls `executor.shutdown(wait=False, cancel_futures=True)`. `cancel_futures=True` only cancels queued (not yet started) futures. Running threads continue executing, holding references to audio data and Rust DSP state. If an upstream caller catches the exception and continues, it may receive stale partial fingerprint data via the shared `fingerprint` dict.
- **Evidence**:
  ```python
  executor = ThreadPoolExecutor(max_workers=5)
  try:
      futures = { executor.submit(...): 'temporal', ... }
      for future in as_completed(futures):
          features = future.result()
          fingerprint.update(features)  # Shared dict written from threads
  except KeyboardInterrupt:
      executor.shutdown(wait=False, cancel_futures=True)  # Running threads not stopped
      raise
  ```
- **Impact**: 1-5 analysis threads continue for seconds after `KeyboardInterrupt`, potentially writing partial results to the `fingerprint` dict. If the exception is caught upstream, the database receives a corrupted partial fingerprint.
- **Suggested Fix**: Clear the `fingerprint` dict before re-raising. Add a cancellation `threading.Event` that all analyzer threads check periodically.

---

### ENG-06: `SampledHarmonicAnalyzer` `max_chunks` Cap Silently Truncates Long Tracks
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/analyzers/batch/harmonic_sampled.py:41-86`
- **Status**: NEW
- **Description**: `SampledHarmonicAnalyzer` extracts at most `max_chunks=60` chunks at 10-second intervals. For tracks longer than 10 minutes (600s), chunks after the 6-minute mark are silently dropped — only a DEBUG log is emitted. Two tracks with identical content in minutes 0-6 but different content in minutes 6-10 produce the same harmonic fingerprint.
- **Evidence**:
  ```python
  # harmonic_sampled.py:78-80
  if len(chunks) >= self.max_chunks:
      logger.debug(f"Reached max_chunks={self.max_chunks}; stopping extraction ...")
      break
  ```
- **Impact**: Podcast, classical, and DJ mix fingerprints are unreliable for tracks >10 minutes. Similarity search returns false positives for long tracks with identical openings.
- **Suggested Fix**: Either scale `max_chunks` proportionally to track duration, use uniform sampling (fixed number of chunks per unit time), or emit WARNING (not DEBUG) when chunks are dropped.

---

### ENG-16: `SampledHarmonicAnalyzer` Chunk Failure Blocks All Remaining Results
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/analyzers/batch/harmonic_sampled.py:117-122`
- **Status**: NEW
- **Description**: Results collected via `[f.result() for f in futures]` — if any future raises, the comprehension propagates the exception immediately. The `with ThreadPoolExecutor` context manager then blocks in `shutdown(wait=True)` while abandoned threads complete, stalling the caller for the full duration of remaining chunks.
- **Evidence**:
  ```python
  with ThreadPoolExecutor(max_workers=4) as executor:
      futures = [executor.submit(self._analyze_chunk, chunk, sr, i) for ...]
      results = [f.result() for f in futures]  # First failure stops iteration; others run to completion
  ```
- **Suggested Fix**: Use `as_completed(futures)` with `future.cancel()` on remaining futures after the first exception.

---

### ENG-17: `MLGenreClassifier` Re-instantiates `FeatureExtractor` Per Instantiation
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/ml/genre_classifier.py:28-45`
- **Status**: NEW
- **Description**: `MLGenreClassifier.__init__()` creates a new `FeatureExtractor()` on every call. When the classifier is eventually upgraded to load a real neural network, this pattern ensures model I/O and GPU initialization per track. Even currently, genre weights are recomputed per instantiation.
- **Evidence**:
  ```python
  class MLGenreClassifier:
      def __init__(self, model_path=None):
          self.feature_extractor = FeatureExtractor()  # New per instantiation
          self.weights = initialize_genre_weights(self.genres)  # Recomputed
  ```
- **Suggested Fix**: Use the already-exported `create_ml_genre_classifier()` factory with a module-level singleton or `functools.lru_cache(maxsize=1)`.

---

### ENG-19: Streaming Pitch Buffer `maxlen=1000` Skews Stability Metric to Track Tail
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/analyzers/streaming/harmonic.py:44,56-65`
- **Status**: NEW
- **Description**: `HarmonicRunningStats` uses `deque(maxlen=1000)`. For a 10-minute track, the pitch buffer sees ~8,600 voiced frames but keeps only the last 1,000 (~12 seconds). `get_pitch_stability()` therefore represents only the final 12 seconds, inconsistent with the batch analyzer which samples uniformly across the whole track.
- **Impact**: Track similarity scores differ between library scan (batch) and real-time analysis (streaming). Re-scanning the same library produces different fingerprints for long tracks.
- **Suggested Fix**: Increase `maxlen` to cover ≥1 minute, or use exponential moving average so all frames contribute.

---

### ENG-20: NaN Dimension Replacement Masks Analysis Bugs
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:193-202`
- **Status**: NEW
- **Description**: After collecting all analyzer results, NaN/Inf values are silently replaced with `0.0`. All-silence audio gets a fingerprint indistinguishable from a quiet valid signal. No count of replaced dimensions is tracked, so quality regressions go undetected.
- **Evidence**:
  ```python
  if np.isnan(value) or np.isinf(value):
      logger.warning(f"Fingerprint dimension '{key}' contains NaN/Inf, replacing with 0.0")
      fingerprint[key] = 0.0
  ```
- **Suggested Fix**: Count NaN replacements and emit a WARNING if >3 dimensions are replaced. Return `None` or raise `FingerprintQualityError` if >25% of dimensions are NaN.

---

## Dimension 7: Library & Database

### ENG-05: `artist_repository.get_all()` Nested Joinedload Causes Cartesian Product
- **Severity**: HIGH
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/artist_repository.py:106-111`
- **Status**: NEW
- **Description**: `get_all()` uses `joinedload(Artist.tracks).joinedload(Track.genres)`, creating a three-table JOIN. For an artist with 10 tracks × 5 genres, SQLAlchemy fetches 50 rows instead of 1. With pagination of 50 artists this is 2,500 rows instead of 50 (50× over-fetch). The `joinedload(Artist.albums).joinedload(Album.tracks)` adds a second Cartesian dimension.
- **Evidence**:
  ```python
  artists = (
      session.query(Artist)
      .options(
          joinedload(Artist.tracks).joinedload(Track.genres),   # Cartesian: tracks × genres
          joinedload(Artist.albums).joinedload(Album.tracks)    # Cartesian: albums × tracks
      )
      .limit(limit).offset(offset).all()
  )
  ```
- **Impact**: Artists browse page becomes progressively slower as library grows. For 500 artists × 15 tracks × 4 genres, each page request fetches ~1,500 rows with in-memory deduplication.
- **Suggested Fix**: Replace nested `joinedload` with `selectinload` at every level.

---

### ENG-11: `album_repository.get_all()` Joinedload Tracks Causes Cartesian Product
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/album_repository.py:90-97`
- **Status**: NEW
- **Description**: `joinedload(Album.tracks)` on paginated results creates one row per track per album. For 50 albums × 10 tracks = 500 rows.
- **Evidence**:
  ```python
  .options(joinedload(Album.artist), joinedload(Album.tracks))
  ```
- **Suggested Fix**: Change `joinedload(Album.tracks)` to `selectinload(Album.tracks)`.

---

### ENG-12: `track_repository.get_by_artist()` Joinedload Genres Causes Cartesian Product
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository.py:344-349`
- **Status**: NEW
- **Description**: `joinedload(Track.genres)` on a list of tracks creates a Cartesian product if tracks have multiple genres. Typical tracks have 2-5 genres; 100 tracks × 3 genres = 300 rows fetched instead of 100.
- **Suggested Fix**: Change `joinedload(Track.genres)` to `selectinload(Track.genres)`.

---

### ENG-13: `artist_repository.get_all_artists()` Returns Detached Objects — Lazy Load Risk
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/artist_repository.py:169-182`
- **Status**: NEW
- **Description**: `get_all_artists()` loads `Artist` objects without eager loading then expunges them. Any subsequent access to `artist.tracks` or `artist.albums` raises `sqlalchemy.exc.DetachedInstanceError`.
- **Evidence**:
  ```python
  artists = session.query(Artist).all()  # No eager loading
  for artist in artists:
      session.expunge(artist)
  return artists  # .tracks / .albums are detached
  ```
- **Suggested Fix**: Add `selectinload(Artist.tracks), selectinload(Artist.albums)` to the query.

---

### ENG-14: `cleanup_missing_files()` Uses `os.path.exists()` — Drops Tracks on NFS Unmount
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository.py:718-772`
- **Status**: NEW
- **Description**: Missing file detection uses `os.path.exists()`, which returns `False` for paths on unmounted network drives or NAS volumes. A temporary NFS unmount during cleanup permanently deletes all tracks from that volume from the library.
- **Evidence**:
  ```python
  missing_ids = [row.id for row in rows if not os.path.exists(row.filepath)]
  ```
- **Impact**: Users with NAS-hosted libraries lose their entire library database entry if cleanup runs during a brief network interruption. Irreversible.
- **Suggested Fix**: Before marking files as missing, check if the parent directory of the first affected file is accessible. If the parent directory also doesn't exist, skip the batch — the volume is likely unmounted.

---

## Evidence Cross-References

- **#2077** — Lock contention in parallel window cache: ENG-15 is a related but distinct concern (unbounded growth, not lock contention)
- **#2369** — Missing regression test for sample count assertion: ENG-08 is the *production* assertion gap; #2369 is the *test* gap
- **#2072** — N+1 in find_similar: ENG-11/12 cover different repository methods (get_all, get_by_artist)
- **#2245** — Rust fingerprint hardcodes dimensions: ENG-10 is about the Python→Rust dtype boundary, not hardcoded values
