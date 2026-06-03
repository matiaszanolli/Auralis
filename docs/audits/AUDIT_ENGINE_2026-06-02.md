# Audio Engine Audit — 2026-06-02

**Scope**: Auralis core audio engine — DSP pipeline, player, analysis, library, parallel processing, audio I/O.
**Depth**: deep (full call-graph tracing). **Limit**: unlimited.
**Dedup baseline**: 194 open GitHub issues + prior `docs/audits/` engine reports through 2026-06-01.
**Dimensions**: all 7 (Sample Integrity, DSP Pipeline, Player State, Audio I/O, Parallel Processing, Analysis, Library & Database).
**Baseline commit audited**: `0445aff3` (mastering engine fixes: HF budget, bass saturation, transients, stereo, loudness).

---

## Executive Summary

**16 new findings across 5 dimensions.** Dimensions 2 (DSP Pipeline) and 7 (Library & Database) are clean — no new issues beyond the prior baseline. The newly-landed mastering commit (`0445aff3`) is **clean on all sample-integrity invariants** — its changes were traced and disproved as bugs; one low-severity copy-discipline inconsistency it introduced is the only related finding.

| Severity | Count | IDs |
|----------|-------|-----|
| **CRITICAL** | 0 | — |
| **HIGH** | 0 | — |
| **MEDIUM** | 3 | PS-01, AN-01, AN-02 |
| **LOW** | 13 | SI-01, IO-01, IO-02, IO-03, IO-04, PP-01, PP-02, AN-03, AN-04, AN-05, AN-06, AN-07, AN-08 |

**No CRITICAL or HIGH findings.** All HIGH findings from the 2026-06-01 audit remain open (#4097, #4099, #4113, #4124) and were not regressed. The mastering commit specifically addressed the overdrive patterns that surfaced during that audit's analysis.

### Key Themes

1. **Player state TOCTOU (PS-01, MEDIUM).** `next_track()`/`previous_track()` check `_stop_requested` inside `_audio_lock`, but `stop()` never holds `_audio_lock` — creating a narrow race where the player enters `PLAYING` state after `stop()` returns. The `_stop_requested` mechanism (introduced in #3296, refined in #3669) does not cover this window.

2. **Analysis cross-contamination.** Fingerprint cache key omits the `fingerprint_strategy` parameter (AN-01), and `QualityMetrics` resets loudness state between tracks but not `crest_history` (AN-02, extends #4120). Both are silent — no error surfaces.

3. **Audio I/O edge cases.** Four LOW findings in I/O: a VBR MP3 OOM-guard bypass (IO-01), silent truncation of FLAC files (IO-02), OPUS/WAV metadata falling to a no-op generic path (IO-03), and hardcoded English-only MP3 comment tags (IO-04).

4. **Parallel processing dtype/shape hygiene.** Two LOW siblings of existing #4125: an inconsistent rank (1-D vs 2-D) from `extract_chunk_segment` on the mono padding path (PP-01), and a hardcoded `dtype=np.float32` in the silence padding allocation (PP-02).

5. **Analysis quality gaps.** Six LOW findings in analysis: dead `LoudnessMeter` instance (AN-03), executor shutdown race (AN-04), unwindowed FFT vs. windowed STFT inconsistency (AN-05), unfitted similarity system returning silent empty results (AN-06), crest factor on wrong signal (AN-07), `assert` swallowed as default (AN-08).

---

## Findings

### MEDIUM

#### PS-01: next_track() / previous_track() play() call races with stop() — PLAYING state after stop()
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:416`, `auralis/player/enhanced_audio_player.py:450-451`
- **Status**: NEW
- **Description**: Both `next_track()` and `previous_track()` check `_stop_requested.is_set()` inside `_audio_lock` and then call `self.playback.play()`. However `stop()` sets `_stop_requested` and calls `playback.stop()` **without holding `_audio_lock`**, creating a TOCTOU window. Race path: (1) `stop()` sets `_stop_requested`; (2) `next_track()` reads the flag as `False` (just before the set); (3) `stop()` calls `playback.stop()` → `state=STOPPED`; (4) `next_track()` calls `self.playback.play()` → `state=PLAYING`. The player is in `PLAYING` state after `stop()` returned.
- **Evidence**:
  ```python
  # enhanced_audio_player.py:416 (inside with self.file_manager._audio_lock:)
  if was_playing and not self._stop_requested.is_set():
      self.playback.play()
  # stop() at line 159-163 — no _audio_lock held:
  def stop(self) -> bool:
      self._stop_requested.set()
      self._auto_advancing.clear()
      return self.playback.stop()
  ```
- **Impact**: Player enters `PLAYING` state after `stop()` returns, causing unexpected audio output. Triggered under UI latency or when auto-advance coincides with the user pressing stop.
- **Suggested Fix**: Re-check `_stop_requested.is_set()` immediately after `playback.play()` returns (double-checked locking), or acquire `_audio_lock` inside `stop()` before the flag set so the check-then-play in `next_track()` is fully atomic with `stop()`.

---

#### AN-01: Fingerprint cache does not encode fingerprint_strategy — cross-strategy cache poisoning
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/fingerprint_storage.py:63-70`, `auralis/analysis/fingerprint/fingerprint_service.py:157-176`
- **Status**: NEW
- **Description**: Both the `.25d` file-cache key and the DB-cache lookup are keyed by `(file_path, mtime, size)` only — `fingerprint_strategy` (`"sampling"` or `"full-track"`) is not part of the key and is not stored as metadata. A `FingerprintService` instantiated with `fingerprint_strategy="full-track"` will silently read and serve a `"sampling"` fingerprint from cache. The two strategies produce materially different `harmonic_ratio`, `pitch_stability`, and `chroma_energy` values for tracks longer than 60 seconds. All current callers use `"sampling"`, making this latent but architecturally fragile.
- **Evidence**: `FingerprintStorage._get_cache_key()` at line 63: key is `md5(f"{abs_path}:{stat.st_mtime}:{stat.st_size}")` — no strategy in key. Strategy is used for compute but not for cache lookup.
- **Impact**: Silently serves wrong harmonic dimensions from cache if strategy changes or two instances with different strategies share the same library. Downstream similarity scores and mastering profile selection are corrupted without any error.
- **Suggested Fix**: Include the strategy string in the `.25d` cache key and add a `fingerprint_strategy` metadata column to `track_fingerprints`. Alternatively, mandate a single canonical strategy and enforce it as a constant.

---

#### AN-02: DynamicRangeAnalyzer.crest_history not reset in QualityMetrics.assess_quality() — extends scope of #4120
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/quality/quality_metrics.py:96-114`, `auralis/analysis/dynamic_range.py:32-76`
- **Status**: Existing: #4120 (this finding extends the scope — #4120 reports the raw `DynamicRangeAnalyzer` class; this instance is the concrete site inside long-lived `QualityMetrics`)
- **Description**: `QualityMetrics.assess_quality()` resets `self.loudness_meter` (line 99) before each call but does **not** reset `self.dynamic_range_analyzer.crest_history`. A long-lived `QualityMetrics` instance (e.g., `ContentAnalyzer.quality_metrics`) accumulates crest-factor readings from earlier tracks, contaminating `get_crest_factor_history()` for subsequent tracks. The `reset_history()` method exists on `DynamicRangeAnalyzer` but is never called from `QualityMetrics`.
- **Evidence**: `quality_metrics.py:99` calls `self.loudness_meter.reset()` but no corresponding `self.dynamic_range_analyzer.reset_history()` call exists in the file.
- **Impact**: `get_crest_factor_history()` returns mixed history from multiple tracks; temporal dynamic-range analysis gives wrong results for all tracks after the first.
- **Suggested Fix**: Add `self.dynamic_range_analyzer.reset_history()` immediately before `self.dynamic_range_analyzer.analyze_dynamic_range()` in `QualityMetrics.assess_quality()`.

---

### LOW

#### SI-01: transient_shaper aliases caller array on the both-bands-skipped path
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/stages/transient_shaper.py:67-93`
- **Status**: NEW
- **Description**: The stage does `processed = audio` (alias, no copy) at line 67, then conditionally calls `TransientShaper.apply()`. If both `bass_pct < 0.05` and `low_mid_pct < 0.05`, or `TransientShaper.apply()` hits its internal early returns, the stage returns the caller's array by reference. The two non-firing early returns above it (lines 45, 56) correctly use `audio.copy()`, creating inconsistent copy discipline. No impact today — `TransientShaper.apply()` is pure (returns `(audio + delta).astype(...)`) and the QuietBranch passes a branch-local copy — but it is a latent foot-gun.
- **Evidence**: `processed = audio` (l.67); `TransientShaper.apply()` returns bare `audio` at lines 78 and 84 when the boost is below threshold.
- **Impact**: None in the current call graph. Latent: a future in-place op or a caller that reuses the pre-stage buffer would silently mutate shared state.
- **Suggested Fix**: Change `processed = audio` to `processed = audio.copy()` on line 67 to match the discipline of the bypass paths above it.

---

#### IO-01: VBR MP3 bypasses pre-decode OOM guard when ffprobe omits format.duration
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:96-121,148-172`
- **Status**: NEW
- **Description**: `_probe_audio()` only sets `result_dict['duration']` when `probe_data.get('format', {}).get('duration')` is truthy. For VBR MP3 files lacking a Xing/VBRI seek table, ffprobe may return no `duration` key at all — `expected_duration` remains `None` and the pre-decode guard `if expected_duration is not None and ...` is silently bypassed. FFmpeg then decodes the full file to a temp WAV (≈800 MB for a 90-min 320 kbps file) before the post-decode check fires.
- **Evidence**: `ffmpeg_loader.py:96-100`: `if duration:` branch skips when ffprobe returns no duration. Guard at line 168: `if expected_duration is not None and expected_duration > MAX_DURATION_SECONDS` — evaluates `False` when `None`.
- **Impact**: Significant transient disk pressure or OOM on low-memory systems for oversized VBR files. Temp file is cleaned up in `finally`.
- **Suggested Fix**: Add a file-size-based fallback estimate (`file_size * 8 / min_bitrate`) as a secondary pre-decode guard when `expected_duration` is `None`.

---

#### IO-02: load_with_soundfile has no truncation detection for FLAC, AIFF, and AU
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/soundfile_loader.py:44-102`
- **Status**: NEW
- **Description**: `_get_wav_declared_size()` returns `None` for all non-WAV files, so the truncation check `if declared_size is not None and ...` is never reached for FLAC, AIFF, or AU. A cleanly-truncated FLAC loads silently, returning fewer samples with no warning. This affects the `unified_loader` path used for fingerprinting and reference analysis. The player path has an `sf.info().frames` comparison but the non-player paths do not.
- **Evidence**: `soundfile_loader.py:51-54`: `declared_size = _get_wav_declared_size(file_path)` returns `None` for FLAC; subsequent `if declared_size is not None` branch is never entered.
- **Impact**: A download-interrupted FLAC loads silently, producing an incorrect fingerprint or mastering reference with no user-visible signal.
- **Suggested Fix**: After `sf.read()`, compare `len(audio_data)` against `sf.info(str(file_path)).frames` for non-WAV formats and emit `WARNING_TRUNCATED_FILE` / `ERROR_TRUNCATED_FILE` codes.

---

#### IO-03: MetadataEditor falls to no-op generic path for OPUS and WAV files
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/library/metadata_editor/metadata_editor.py:108-125`, `auralis/library/metadata_editor/writers.py:151-168`
- **Status**: NEW
- **Description**: `MetadataEditor` dispatches on `isinstance(audio_file, OggVorbis)` but OPUS is `mutagen.oggopus.OggOpus` (not `OggVorbis`) and WAV is `mutagen.wave.WAVE`. Both fall to `read_generic_metadata()` / `write_generic_metadata()`. For OPUS this produces lowercase Vorbis comment keys; for WAV, `write_generic_metadata()` writes raw field names instead of ID3 frames, potentially producing a corrupt tag block.
- **Evidence**: `metadata_editor.py:476`: `elif isinstance(audio_file, OggVorbis) or ext in ('ogg', 'oga')` — OPUS file extension is `'opus'`, not `'ogg'`, so this branch is not entered.
- **Impact**: Metadata edits on OPUS silently degrade to an unvalidated generic write. WAV tag writes may produce corrupt ID3 frame serialization.
- **Suggested Fix**: Import `OggOpus` and `WAVE` from mutagen and add dispatch branches. OPUS can reuse the OGG Vorbis reader/writer; WAV should reuse the MP3 ID3 reader/writer.

---

#### IO-04: read_mp3_metadata hardcodes COMM::eng — silently misses non-English comments
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/library/metadata_editor/tag_mappings.py:30`, `auralis/library/metadata_editor/writers.py:70`
- **Status**: NEW
- **Description**: The MP3 tag mapping uses `'COMM::eng'` as the comment key. ID3v2 `COMM` frames include a language code, so files with `COMM::fra`, `COMM::deu`, or `COMM::` (empty language) are silently skipped on read. On write, `COMM(... lang='eng' ...)` is added alongside any existing non-English frame, creating duplicates. The same applies to `USLT::eng` for lyrics.
- **Evidence**: `tag_mappings.py:30`: `'comment': 'COMM::eng'`. `writers.py:70`: `audio_file['COMM::eng'] = COMM(encoding=3, lang='eng', desc='', text=str(value))`.
- **Impact**: Blank comment display for non-English comment tags; accumulating duplicate COMM frames visible in other players.
- **Suggested Fix**: Iterate all `COMM:*` keys in the reader rather than looking up a specific key. In the writer, preserve the existing COMM frame's language code if one exists.

---

#### PP-01: extract_chunk_segment returns 1-D on trim path but 2-D (N,1) on pad path for mono input
- **Severity**: LOW
- **Dimension**: Parallel Processing
- **Location**: `auralis-web/backend/core/chunk_operations.py:239-270`
- **Status**: NEW
- **Description**: For a 1-D mono `extracted` buffer, the pad branch executes `extracted = extracted[:, np.newaxis]` then concatenates, yielding shape `(N,1)`. The trim branch and the exact-match pass-through return the original 1-D slice. Same function, same mono input, three different possible ranks depending on validation branch taken — a shape-invariant violation.
- **Evidence**: Pad path at line 250: `extracted = extracted[:, np.newaxis]` → 2-D. Trim path at line 264: `extracted = extracted[:expected_for_validation]` → 1-D.
- **Impact**: None audible today — consumers treat 1-D and `(N,1)` as identical mono. The 1-D branch is also rarely reached since `simple_mastering` expands mono to stereo `(N,2)`. Latent break for any future shape-sensitive consumer.
- **Suggested Fix**: Normalize rank at the single return point — either always 2-D via `np.atleast_2d(extracted).T` on 1-D input on entry, or always strip trailing singleton dimension before returning.

---

#### PP-02: extract_chunk_segment silence padding hardcodes dtype=np.float32
- **Severity**: LOW
- **Dimension**: Parallel Processing
- **Location**: `auralis-web/backend/core/chunk_operations.py:247`
- **Status**: NEW (sibling of #4125, same dtype-hygiene class)
- **Description**: `np.zeros((padding_needed, num_channels), dtype=np.float32)` hardcodes the dtype rather than using `extracted.dtype`. For float64 input, `np.concatenate` upcasts the float32 padding, so there is no silent downcast in output — but the construction ignores the buffer's real dtype, the same anti-pattern flagged in #4125 and corrected at `chunked_processor.py:551`.
- **Evidence**: `chunk_operations.py:247`: `padding = np.zeros((padding_needed, num_channels), dtype=np.float32)`. Compare `chunked_processor.py:551`: `np.zeros((...), dtype=audio_chunk.dtype)`.
- **Impact**: Negligible at runtime today (pipeline is float32 end-to-end). Maintenance/consistency risk only.
- **Suggested Fix**: Use `dtype=extracted.dtype` for the padding allocation.

---

#### AN-03: ContentAnalyzer creates a LoudnessMeter that is never used — dead resource
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/content_analysis.py:74`
- **Status**: NEW
- **Description**: `ContentAnalyzer.__init__()` instantiates `self.loudness_meter = LoudnessMeter(sample_rate)` at line 74 but no method in the class ever calls any of its methods. Loudness measurement is entirely delegated to `self.quality_metrics.assess_quality()` which manages its own `LoudnessMeter` instance.
- **Evidence**: `grep "self.loudness_meter" auralis/analysis/content_analysis.py` returns only line 74.
- **Impact**: Minor per-instance initialization overhead; no correctness issue.
- **Suggested Fix**: Delete the construction at line 74 and remove the associated import if no longer needed.

---

#### AN-04: SampledHarmonicAnalyzer.close() races with concurrent _analyze_impl() — RuntimeError on shutdown
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/analyzers/batch/harmonic_sampled.py:66-82`, lines 160-178
- **Status**: NEW
- **Description**: `_get_executor()` releases `_executor_lock` before returning the executor to `_analyze_impl`. A concurrent `close()` can then shut down the executor between `_get_executor()` returning and `executor.submit()` being called, causing `RuntimeError: cannot schedule new futures after shutdown`. This is caught by `BaseAnalyzer.analyze()`'s `except Exception`, returning `DEFAULT_FEATURES` silently.
- **Evidence**: `_get_executor()` does not hold the lock during `executor.submit()`. `close()` acquires `_executor_lock` independently. `_analyze_impl` at line 167 calls `executor.submit(...)`.
- **Impact**: One extra fingerprint recomputation per track during shutdown. No data corruption. Low probability in practice.
- **Suggested Fix**: Track in-progress analysis count with an `_active_analyses` integer incremented on entry and decremented on exit under the lock; have `close()` wait for it to reach zero before shutting down the executor.

---

#### AN-05: Unwindowed global FFT for 7-band analysis vs. windowed STFT for spectral features — systematic leakage inconsistency
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:207-209`, `auralis/analysis/fingerprint/utilities/spectral_ops.py:200`
- **Status**: NEW
- **Description**: The 7-band frequency percentages (`sub_bass_pct`…`air_pct`) are computed from a single-shot `np.fft.rfft(audio_mono)` with no window function (rectangular window). The three spectral features (`spectral_centroid`, `spectral_rolloff`, `spectral_flatness`) are computed from a Hann-windowed `librosa.stft`. For transient-rich audio, a strong attack inflates high-frequency energy in the frequency bands but not in the spectral centroid, creating inconsistent characterization of the same signal.
- **Evidence**: `audio_fingerprint_analyzer.py:207`: `fft = np.fft.rfft(audio_mono)` — no window. `spectral_ops.py:200`: `S = librosa.stft(audio)` — Hann window implicit.
- **Impact**: Frequency-band fingerprint dimensions are biased by spectral leakage for transient-heavy content (metal, EDM, percussion). Reduces cross-genre similarity accuracy; not a crash or data-loss issue.
- **Suggested Fix**: Apply `np.hanning(len(audio_mono))` before `rfft` in `_analyze_frequency_cached`. Normalized energy ratios still sum to 1.0 since the window is applied uniformly.

---

#### AN-06: FingerprintSimilarity not fitted at startup — similarity API silently returns empty until manual trigger
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis-web/backend/config/startup.py:306-321`, `auralis/analysis/fingerprint/similarity.py:127-128`
- **Status**: NEW
- **Description**: `FingerprintSimilarity` is created at startup without fitting the normalizer. All `find_similar()` / `compute_similarity()` calls guard with `if not self.fitted: return []` and return HTTP 200 with empty results — no error is surfaced. There is no automated trigger to fit after scanning, so on a fresh install or library reset, the recommendation panel is permanently empty with no user-visible explanation.
- **Evidence**: `startup.py:312` comment: "will be created on-demand via /api/similarity/fit endpoint" — no auto-fit. `similarity.py:128`: `error("Similarity system not fitted")` then `return []`.
- **Impact**: Silent permanently-empty recommendation panel on fresh install or after library wipe. No automated signal to operators.
- **Suggested Fix**: Auto-trigger `similarity_system.fit()` in a background task after scan completes when fingerprint count meets `min_samples`. Alternatively, return HTTP 503 when the system is not fitted rather than an empty 200.

---

#### AN-07: FeatureExtractor.crest_factor_db computed on original audio instead of padded mono_audio
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/ml/feature_extractor.py:69`
- **Status**: NEW
- **Description**: `extract_features()` converts input to `mono_audio` and pads it to at least `sample_rate` samples (lines 55-65), then calls `crest_factor_db = crest_factor(audio)` using the **original** unpadded stereo `audio`. For very short stereo clips, `crest_factor()` computes over the full multi-channel array without per-channel handling, so the crest factor may reflect inter-channel rather than temporal dynamics.
- **Evidence**: `feature_extractor.py:55-65`: `mono_audio` computed and padded. `feature_extractor.py:69`: `crest_factor_db = crest_factor(audio)` — original `audio`, not `mono_audio`.
- **Impact**: Potentially inaccurate `crest_factor_db` for genre classifier on very short stereo clips. The upstream `ContentAnalyzer` enforces minimum audio length, limiting blast radius.
- **Suggested Fix**: Change line 69 to `crest_factor_db = crest_factor(mono_audio)`.

---

#### AN-08: VariationOperations uses assert for runtime contract — AssertionError swallowed as silent default
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/utilities/variation_ops.py:107`
- **Status**: NEW
- **Description**: `calculate_dynamic_range_variation()` uses `assert hop_length is not None and frame_length is not None` as a defensive pre-condition check. `AssertionError` is caught by `BaseAnalyzer.analyze()`'s broad `except Exception`, silently returning `dynamic_range_variation=0.5` default. Python's `-O` flag disables `assert` entirely, which would then produce a `TypeError` on the next line — also caught and swallowed.
- **Evidence**: `variation_ops.py:107`: `assert hop_length is not None and frame_length is not None`. `base_analyzer.py:67`: `except Exception as e: debug(...); return self.DEFAULT_FEATURES.copy()`.
- **Impact**: Silent wrong default value instead of a clear `ValueError`. No production impact today since all callers pass the required arguments.
- **Suggested Fix**: Replace the assert with `if hop_length is None or frame_length is None: raise ValueError("hop_length and frame_length must be provided when rms is pre-computed")`.

---

#### PS-02: AudioPlayer.position.setter non-atomic with gapless track swap — stale max_samples clamp
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:743-747`
- **Status**: NEW
- **Description**: The `position` property setter reads `max_samples` via `get_total_samples()` (acquires+releases `_audio_lock`) and then calls `self.playback.seek(value, max_samples)` (separate lock). A gapless transition between the two calls can make `max_samples` stale — the new shorter track receives a seek position beyond its own length. `AudioPlayer.seek()` already fixes this with an outer `_audio_lock` scope, but the setter is inconsistent.
- **Evidence**:
  ```python
  @position.setter
  def position(self, value: int) -> None:
      max_samples = self.file_manager.get_total_samples()  # lock acquired+released
      self.playback.seek(value, max_samples)                # separate lock
  ```
- **Impact**: If a caller uses `player.position = X` concurrently with gapless playback, position could be set beyond the new track's length. No production backend code calls the setter today (backend uses `AudioPlayer.seek()` directly).
- **Suggested Fix**: Wrap the setter body in `with self.file_manager._audio_lock:` to match the `AudioPlayer.seek()` pattern. Update the docstring, which incorrectly claims "thread-safe via PlaybackController.seek()".

---

## Relationships Between Findings

**Analysis cache integrity cluster**: AN-01 (strategy not in cache key) and AN-02 (crest_history not reset) both produce silently wrong fingerprint data with no user-visible error. They share the root cause of missing reset/invalidation discipline in the fingerprint subsystem.

**I/O metadata cluster**: IO-03 (OPUS/WAV dispatch gap) and IO-04 (hardcoded COMM::eng) both affect tag read/write correctness. IO-03 is a dispatch gap; IO-04 is a key-construction assumption. Both surface for international users or with non-standard encoders.

**Dtype/shape hygiene cluster**: PP-01 (shape inconsistency), PP-02 (dtype hardcode), and SI-01 (missing copy) are all latent consistency issues in the same codebase style class as #4125. None cause production bugs today.

**Player safety cluster**: PS-01 and PS-02 are both TOCTOU patterns in the player, separate from but thematically related to the prior #4096/#4098 findings. PS-01 is the higher-risk variant (MEDIUM) because it involves a state machine transition visible to the user.

---

## Prioritized Fix Order

| Priority | Finding | Rationale |
|----------|---------|-----------|
| 1 | **PS-01** (MEDIUM) | Player enters PLAYING after stop() — user-visible regression under any fast stop/skip interaction |
| 2 | **AN-01** (MEDIUM) | Silent wrong fingerprint from cache if strategy ever diverges; architectural debt that compounds |
| 3 | **AN-02** (MEDIUM) | Crest history cross-contamination; simple one-line fix; extends already-open #4120 |
| 4 | **IO-03** (LOW) | Corrupt WAV tag writes; OPUS metadata silently degraded; two-line dispatch fix |
| 5 | **IO-04** (LOW) | Growing duplicate COMM frames for non-English libraries; reader + writer fix |
| 6 | **AN-06** (LOW) | Recommendation panel permanently empty on fresh installs; user-facing with no signal |
| 7 | **AN-05** (LOW) | Spectral leakage bias affects similarity quality for metal/EDM libraries |
| 8 | **IO-01** (LOW) | VBR MP3 OOM guard bypass; disk pressure on low-memory systems |
| 9 | **IO-02** (LOW) | Silent truncated FLAC; corrupts fingerprint/mastering reference for damaged files |
| 10 | **SI-01** (LOW) | Copy discipline consistency in transient_shaper; no current impact |
| 11 | **PP-01, PP-02** (LOW) | Shape/dtype hygiene in chunk_operations; no current impact |
| 12 | **AN-04, AN-07, AN-08** (LOW) | Analysis edge cases; no production impact |
| 13 | **PS-02** (LOW) | Setter TOCTOU; no current production caller |
| 14 | **AN-03** (LOW) | Dead code cleanup |

---

## Dimensions with No New Findings

- **Dimension 2 (DSP Pipeline)**: Clean. The `0445aff3` mastering commit was fully traced — GIL release, stereo widener at `width_factor=0.63`, psychoacoustic EQ windowing, continuous-mode chain order, and HF budget stacking were all verified correct. The `hf_lift` intensity cap is redundant-but-harmless for loud branches.
- **Dimension 7 (Library & Database)**: Clean. All 8 scope items pass. Repository pattern, SQLite config, N+1 prevention, scanner robustness, migration safety, concurrent scan guards, `cleanup_missing_files` cursor pagination, and engine disposal are all intact.

---

*Run `/audit-publish docs/audits/AUDIT_ENGINE_2026-06-02.md` to create GitHub issues for these findings.*
