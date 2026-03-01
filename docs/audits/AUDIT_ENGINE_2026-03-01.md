# Audio Engine Audit Report (v3)

**Date**: 2026-03-01
**Auditor**: Claude Sonnet 4.6 (automated)
**Scope**: Auralis core audio engine — 7 dimensions
**Method**: Systematic code review with 3 parallel exploration agents, followed by manual verification of all candidate findings against source code. Prior audit findings (ENG-11 through ENG-15) re-verified for regression.

## Executive Summary

Third audit pass of the Auralis core audio engine. All 5 findings from the 2026-02-22 audit are now fixed. Confirmed that commit `20b0a166` also resolves ENG-10 (PyO3 float64 mismatch) from the 2026-02-21 audit. Found 6 new issues. Eliminated 6 false positives from agent exploration.

**Results**: 6 confirmed findings (0 CRITICAL, 0 HIGH, 3 MEDIUM, 3 LOW).

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 3 |
| LOW | 3 |

## Prior Findings Status

| Finding | Issue | Status |
|---------|-------|--------|
| ENG-11: Compressor lookahead dead code | #2592 | **FIXED** — `process()` line 122 now guards with `if self.settings.enable_lookahead and self.lookahead_samples > 0:` |
| ENG-12: Stereo RMS averages channels before RMS | #2593 | **FIXED** — `continuous_mode.py:433` now uses `audio.ravel()` |
| ENG-13: Artist/genre get-or-create race condition | #2594 | **FIXED** — `try/except IntegrityError` with fallback query added |
| ENG-14: `np.hanning()` deprecated at 7 call sites | (no issue) | **FIXED** — all 7 sites now use `np.hann()` |
| ENG-15: `np.vectorize` in compressor (Python loop) | #2596 | **FIXED** — replaced by `_calculate_gain_reduction_vectorized()` (pure NumPy) |
| ENG-10 (2026-02-21): PyO3 float64 type mismatch | — | **FIXED** — commit `20b0a166` corrects `_validate_ffi_inputs()` to coerce to float64, not float32 |

## Findings

---

### ENG-16: `stereo_width_analysis()` returns NaN for constant or silent audio
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline / Sample Integrity
- **Location**: `auralis/dsp/utils/stereo.py:40`
- **Status**: NEW
- **Description**: `stereo_width_analysis()` calls `np.corrcoef(left, right)[0, 1]`. When both channels are constant (e.g., silence, DC offset, or a fully mono signal), NumPy's correlation coefficient is undefined — the correlation matrix contains NaN:
  ```python
  >>> np.corrcoef([0, 0, 0], [0, 0, 0])
  array([[ 1., nan],
         [nan,  1.]])
  ```
  The code does not guard against this. The computation `1.0 - np.abs(NaN)` is NaN. `np.clip(NaN, 0.0, 1.0)` returns NaN (NumPy does not saturate NaN on clip). `float(NaN)` is returned to callers.
- **Evidence**:
  ```python
  # stereo.py:40-47
  correlation = np.corrcoef(left, right)[0, 1]      # NaN for constant channels
  width = 1.0 - np.abs(correlation)                 # NaN propagates
  return float(np.clip(width, 0.0, 1.0))            # Returns float('nan')
  ```
  Affected call sites in `continuous_mode.py`:
  ```python
  # continuous_mode.py:~400 - used to decide if expansion should run
  current_width = stereo_width_analysis(audio)      # NaN for silent audio
  if current_width < target_width:                  # NaN < x → False, skips expansion
  ```
- **Impact**: For silent audio sections (e.g., silent intro/outro, gap between movements), stereo width adjustment is silently skipped rather than correctly treating the silence as mono (width=0.0). In fingerprinting, the NaN sanitizer at `audio_fingerprint_analyzer.py:220` catches it before DB storage, but emits a spurious warning log for every silent track, masking real analyzer bugs.
- **Suggested Fix**: Before computing the correlation, guard against zero-variance input:
  ```python
  if np.std(left) < 1e-9 or np.std(right) < 1e-9:
      return 0.0  # Constant channel → zero stereo width
  ```

---

### ENG-17: `_get_default_fingerprint()` frequency bands use percentage scale (×100 mismatch)
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:364-370`
- **Status**: NEW
- **Description**: `_analyze_frequency_cached()` normalizes band energies to 0–1 range (line 282–284: divide by `total_energy`). Its own exception fallback (lines 294–302) correctly returns `0.05, 0.15, 0.15, 0.30, 0.20, 0.10, 0.05` (summing to 1.0). However, `_get_default_fingerprint()` — called when the outer `analyze()` fails entirely (line 238–240) — returns the same keys with 100× larger values: `5.0, 15.0, 15.0, 30.0, 20.0, 10.0, 5.0`.
- **Evidence**:
  ```python
  # _analyze_frequency_cached() — inner fallback (line 294), correct 0-1 range:
  return {'sub_bass_pct': 0.05, 'bass_pct': 0.15, 'mid_pct': 0.30, ...}

  # _get_default_fingerprint() — outer fallback (line 364), 100x too large:
  return {'sub_bass_pct': 5.0, 'bass_pct': 15.0, 'mid_pct': 30.0, ...}
  ```
  When `analyze()` fails (outer try/except at line 238), the default fingerprint is stored in the database and used for similarity search. Any comparison between a real track (`sub_bass_pct ≈ 0.05–0.30`) and a defaulted track (`sub_bass_pct = 5.0–30.0`) produces a Euclidean distance dominated entirely by the frequency dimensions.
- **Impact**: Tracks for which fingerprinting fails (corrupt audio, unsupported edge cases) receive frequency dimension values 100× larger than any real fingerprint. Similarity search returns these tracks as maximally dissimilar from everything in the library, breaking recommendations and queue continuity.
- **Suggested Fix**: Align `_get_default_fingerprint()` to use the same 0–1 scale:
  ```python
  'sub_bass_pct': 0.05, 'bass_pct': 0.15, 'low_mid_pct': 0.15,
  'mid_pct': 0.30, 'upper_mid_pct': 0.20, 'presence_pct': 0.10, 'air_pct': 0.05
  ```

---

### ENG-18: `artist_repository.get_by_id/get_by_name()` use nested joinedload causing Cartesian product
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/artist_repository.py:34-35, 53`
- **Status**: NEW (related: prior ENG-05 fixed `get_all()`, these methods remained)
- **Description**: Both `get_by_id()` and `get_by_name()` use nested `joinedload`:
  ```python
  .options(
      joinedload(Artist.tracks).joinedload(Track.genres),  # Cartesian: tracks × genres
      joinedload(Artist.albums).joinedload(Album.tracks)   # Cartesian: albums × tracks
  )
  ```
  SQLAlchemy translates each nested joinedload into a SQL LEFT OUTER JOIN. For a single artist, this creates: `artist × tracks × genres + artist × albums × tracks` rows. An artist with 100 tracks × 4 genres = 400 rows fetched and deduplicated in memory for a single-row lookup. The `session.expunge(artist)` that follows correctly detaches the object, but the Cartesian fetch still occurs.
- **Evidence**:
  ```python
  # artist_repository.py:31-42 (get_by_id)
  artist = (
      session.query(Artist)
      .options(
          joinedload(Artist.tracks).joinedload(Track.genres),   # BUG
          joinedload(Artist.albums).joinedload(Album.tracks)    # BUG
      )
      .filter(Artist.id == artist_id)
      .first()
  )
  ```
  The `get_all()` method at line 65 does NOT use joinedload (fixed in prior audit), making this an inconsistency.
- **Impact**: Artist detail page loads are disproportionately slow for prolific artists. An artist with 500 tracks × 5 genres triggers a join producing 2,500 rows for a single lookup.
- **Suggested Fix**: Replace nested `joinedload` with `selectinload` at each level. `selectinload` issues separate IN-clause queries and avoids the Cartesian product:
  ```python
  .options(
      selectinload(Artist.tracks).selectinload(Track.genres),
      selectinload(Artist.albums).selectinload(Album.tracks)
  )
  ```

---

### ENG-19: `lookahead_buffer` partial-update path stores input reference without `.copy()`
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/compressor.py:203-204`
- **Status**: NEW
- **Description**: In `_apply_lookahead()`, when the incoming audio chunk is shorter than the lookahead buffer (`audio_len < buffer_size`), the buffer is updated by rolling and then assigning the new audio directly:
  ```python
  # compressor.py:203-204
  self.lookahead_buffer = np.roll(self.lookahead_buffer, -audio_len, axis=0)
  self.lookahead_buffer[-audio_len:, ...] = audio   # No .copy()
  ```
  The numpy slice assignment `buffer[-n:] = audio` copies the values from `audio` into the buffer's memory — it does NOT store a reference. So functionally this is safe. **However**, there is a shape mismatch risk: if `audio` is 1D (mono) and `self.lookahead_buffer` is 2D (initialized stereo on a previous stereo call), the assignment will broadcast incorrectly or raise a ValueError, corrupting buffer state.

  Contrast with the main path at line 196, which correctly uses `.copy()` and avoids such ambiguities.
- **Evidence**:
  ```python
  # Line 196 — main path (correct):
  self.lookahead_buffer = audio[-buffer_size:].copy()

  # Line 203-204 — partial path (no copy, shape mismatch risk):
  self.lookahead_buffer = np.roll(self.lookahead_buffer, -audio_len, axis=0)
  self.lookahead_buffer[-audio_len:, ...] = audio
  ```
  The buffer is initialized at lines 184–187 to match the first call's `audio.ndim`. If the compressor instance is ever called with audio of different ndim (e.g., mono then stereo, which can happen if the player switches between tracks), the assignment at line 204 will fail.
- **Impact**: In practice, the compressor sees consistent mono/stereo per instance lifetime. But the asymmetric copy pattern is fragile and the ndim mismatch path is a latent bug.
- **Suggested Fix**: Store a copy and add an ndim guard: `self.lookahead_buffer[-audio_len:, ...] = audio.copy()`. Also reset the buffer when audio ndim changes.

---

### ENG-20: Dead attribute expression `params.peak_target_db` left from disabled peak normalization
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_mode.py:453`
- **Status**: NEW
- **Description**: Line 453 is a bare expression statement that evaluates `params.peak_target_db` and immediately discards the value. The surrounding comment explains that "Step 2: Peak normalization" is disabled, but the expression accesses the parameter anyway with no assignment or side effect.
- **Evidence**:
  ```python
  # continuous_mode.py:448-454
  # Step 2: Peak normalization (DISABLED - use LUFS normalization instead)
  # ...
  # Only apply peak limiting if absolutely necessary to prevent clipping.
  params.peak_target_db          # ← Dead statement: value accessed but discarded
  current_peak_db = DBConversion.to_db(np.max(np.abs(audio)))
  ```
  This is not a `del` statement or an intentional side-effecting attribute access — `peak_target_db` is a plain float. No property getter or descriptor is involved.
- **Impact**: No runtime impact. Causes cognitive confusion: it looks like the parameter is being "consumed" when it isn't. Triggers a Pylance/mypy "expression value is unused" warning.
- **Suggested Fix**: Remove line 453 entirely.

---

### ENG-21: Unused `mask` variable in `_apply_window_smoothing()` — window applied to zero-energy bins
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/utils/interpolation_helpers.py:120-121`
- **Status**: NEW
- **Description**: `_apply_window_smoothing()` computes a boolean mask of non-zero envelope values but never uses it — the window is applied to all bins in the range regardless:
  ```python
  # interpolation_helpers.py:120-121
  mask = envelope[start_idx:end_idx + 1] > 0    # Computed, never used
  envelope[start_idx:end_idx + 1] *= window     # Applied to ALL bins
  ```
  Since `0 * window = 0`, multiplying zero bins by the window produces zero, which is the same result whether or not the mask is applied. The function's behavior is therefore correct in practice. However, the dead `mask` variable suggests the intended implementation was selective application: `envelope[...][mask] *= window[mask]` — which would only modulate the non-zero triangle interior, leaving gap regions at zero without attenuating them.
- **Evidence**: The function is called from `_interpolate_gains()` on triangular gain envelopes for psychoacoustic EQ band transitions. The intent of the mask was probably to preserve exact zeros at band edges rather than windowing them (even though 0 × window = 0 anyway).
- **Impact**: No audible impact (mathematical equivalence). Dead code increases cognitive load and obscures the original design intent.
- **Suggested Fix**: Remove the `mask` variable entirely, or add a comment explaining why window application to zeros is intentional. If selective application was the design intent, use: `envelope[start_idx:end_idx + 1] = np.where(mask, envelope[start_idx:end_idx + 1] * window, envelope[start_idx:end_idx + 1])`.

---

## False Positives Eliminated

| Claimed Finding | Reason Disproved |
|----------------|------------------|
| `executor.map(*zip(*chunks))` incorrect argument unpacking (CRITICAL) | `executor.map(f, *zip(*chunks))` is the correct Python idiom: zip transposes `[(a1,b1,c1), (a2,b2,c2)]` into iterables `(a1,a2), (b1,b2), (c1,c2)`, so map calls `f(a1,b1,c1)`, `f(a2,b2,c2)`. Functionally identical to the multiprocessing path. |
| SmartCache `KeyError` in `_remove_item()` | `_remove_item()` only accesses `self.sizes[key]` inside `if key in self.cache:`. All three dicts are written atomically in `put()` (lines 88-90). No code path can desynchronize them under normal operation. |
| Audio fingerprint shape heuristic causing wrong mono conversion | The heuristic `shape[0] <= 2` for ambiguous shapes only affects audio ≤ 2 samples long, which is caught by the minimum length check (`sr // 2` samples) at line 134 before mono conversion. Unreachable for real audio. |
| `_get_default_fingerprint()` scale mismatch causes KeyError or crash | No crash — wrong values are stored but don't cause exceptions. The bug is a scale mismatch (ENG-17), not a type error. |
| MigrationManager session leak when `__init__` raises | If `MigrationManager(db_path)` raises, the assignment `manager = ...` in `check_and_migrate_database()` never completes, so `manager` is undefined and the `finally` block's `manager.close()` raises `NameError`, not a session leak. In Python, `try/finally` only executes if the `try` block is entered. |
| `adjust_stereo_width()` in-place modification of `stereo_audio` | Returns `mid_side_decode(mid, adjusted_side)` which allocates a new array. Input `stereo_audio` is read but never written. |

## Checklist Summary

### Dimension 1: Sample Integrity
- [x] `len(output) == len(input)` — no new violations found
- [x] `audio.copy()` before in-place ops — maintained
- [x] dtype preservation — float32/float64 throughout
- [x] Clipping prevention — output clamped
- [x] **Stereo RMS** — FIXED (#2593, `audio.ravel()`)
- [x] Mono/stereo handling — correct
- [x] Bit depth output — pcm16/pcm24 correctly scaled

### Dimension 2: DSP Pipeline Correctness
- [x] Processing chain order — EQ → dynamics → mastering
- [x] Stage independence — each stage receives clean input
- [x] Parameter validation — CompressorSettings clamps all values
- [x] Windowing — `np.hanning` → `np.hann` (FIXED, all 7 sites)
- [x] Phase coherence — maintained
- [x] **Compressor lookahead** — FIXED (#2592)
- [x] **np.vectorize in compressor** — FIXED (#2596, pure NumPy)
- [ ] **stereo_width_analysis NaN** — ENG-16
- [ ] **params.peak_target_db dead statement** — ENG-20
- [ ] **lookahead partial-update no copy** — ENG-19
- [ ] **unused mask in _apply_window_smoothing** — ENG-21

### Dimension 3: Player State Machine
- [x] All items verified fixed (d4cd992f, #2583, #2585) — no regressions

### Dimension 4: Audio I/O
- [x] All items verified — no new findings

### Dimension 5: Parallel Processing
- [x] Chunk independence — `*zip(*chunks)` pattern verified correct
- [x] All parallel processing items verified — no new findings

### Dimension 6: Analysis Subsystem
- [x] Fingerprint service — MITIGATED (#2581)
- [x] PyO3 dtype mismatch — FIXED (commit 20b0a166)
- [ ] **`_get_default_fingerprint()` scale mismatch** — ENG-17
- [ ] **stereo_width NaN in fingerprint path** — ENG-16 (NaN sanitizer catches it but with spurious log)

### Dimension 7: Library & Database
- [x] `artist_repository.get_all()` — FIXED (selectinload, prior audit)
- [x] Artist/genre race condition — FIXED (#2594)
- [ ] **`get_by_id/get_by_name()` nested joinedload** — ENG-18
