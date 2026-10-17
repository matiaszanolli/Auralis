# Core Audio Engine Audit — 2026-10-16

**Scope**: `auralis/` engine (sample integrity, DSP pipeline, player, audio I/O, chunked mastering, analysis, library) plus the backend call sites that feed it.
**Depth**: deep, 7 dimension agents, read-only. Most findings were confirmed by reading the cited lines; many HIGH/MEDIUM ones were also reproduced with small probes on synthetic audio.
**Baseline**: HEAD `0f722fbb`. Dedup was run against 137 open issues, the 300 most recently closed issues and `docs/audits/AUDIT_ENGINE_2026-09-1*.md`.

## Executive Summary

| Severity | Findings | NEW | Existing |
|---|---|---|---|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 8 | 8 | 0 |
| MEDIUM | 17 | 17 | 0 |
| LOW | 30 | 25 | 5 |
| **Total** | **55** | **50** | **5** |

The 55 findings are after folding 5 cross-dimension duplicates (60 raw), listed under "Merged duplicates" below. The 5 Existing ones are already tracked (#5512, #5116, #4970, #5339, #5537) and are kept for completeness; do not re-publish them.

**Key themes**

1. **The fingerprint pipeline is fed wrong data, and everything downstream inherits it.** The backend flattens stereo with `order='F'` so Rust sees `[all L, all R]` instead of interleaved samples (ENG-D6-01). The target service treats 0–1 band fractions as percentages and saturates every EQ band (ENG-D2-03). The band analysis is level-dependent (ENG-D6-02) and `transient_density` is not a transient measure (ENG-D6-03). Rows written by the on-demand path never get a current `fingerprint_version`, so they are recomputed on every play (ENG-D7-02).
2. **Chunk-local loudness handling flattens dynamics and can explode quiet material.** Final normalization re-levels every chunk to the track-wide target (ENG-D2-01), has no gain cap or working silence floor (ENG-D1-02), and the offline CLI peak-normalises each 30 s chunk on its own (ENG-D1-04). `LevelManager` then adds up to +40 dB after the limiter (ENG-D1-03).
3. **Stereo widening is mis-scaled.** `stereo_width_target=1.0` means maximum widening, not "preserve width" (ENG-D2-02).
4. **Queue entries have no stable shape.** Production entries use `filepath` or carry no path or id. The player's next/previous/gapless/shuffle code reads other keys, so tests pass on `file_path` fixtures while production silently does nothing (ENG-D3-01, -02, -03, -06).
5. **Library write paths do not respect FK and invariant assumptions.** Bulk deletes ignore association tables that have no `ON DELETE CASCADE` (ENG-D7-01). The scanner's change detection reads a column that plays and favourites bump (ENG-D7-04). Undecodable files are ingested as zero-duration tracks (ENG-D4-03).

**Most impactful**

- ENG-D1-01 — every mono track fails enhanced streaming.
- ENG-D6-01 — wrong fingerprints are persisted, which poisons mastering targets and similarity.
- ENG-D2-03 — a content-independent EQ tilt is applied to every track.
- ENG-D7-01 — the missing-file and folder-removal prunes silently do nothing for real tracks.

**Caveats**

- The Dim 5 and Dim 7 agents hit a `/tmp` disk-quota error (a Dim 4 probe filled the tmpfs; it was cleaned up). They ran no runtime probes, so their findings come from code reading only. This includes the Rust overflow claim in ENG-D5-07.
- Dim 6 did not check `dynamic_range.py` or the `quality_assessors/` scoring constants in depth.
- Open #5416 (np.hanning in the psychoacoustic EQ) looks already fixed in code (`scipy.signal.windows.hann`). It is worth checking and closing.
- The audit skills (`_audit-common.md`, `audit-engine.md`) say the optimizer wrapper "wraps `AdaptiveMode.process` and sits on every real mastering call". Dim 2 found the live path (`ContinuousMode`) does not call `AdaptiveMode.process`, so that claim is overstated. It needs correcting on the next `/audit-sync`.

## Merged duplicates

| Folded | Into | Note |
|---|---|---|
| ENG-D1-05 (Dim 1, MEDIUM) | ENG-D2-02 | `stereo_width_target=1.0` |
| ENG-D2-04 (Dim 2, HIGH) | ENG-D6-01 | `flatten(order='F')`, confirmed independently from the analysis side |
| ENG-D2-12 (Dim 2, LOW) | ENG-D3-09 | retired `warm`/`bright`/`punchy` profiles in `AutoMasterProcessor` |
| ENG-D7-05 (Dim 7, MEDIUM) | ENG-D4-04 | M4A `trkn`/`disk` tuples |
| ENG-D7-06 (Dim 7, LOW) | ENG-D6-04 | `FingerprintQuantizer` bounds |

# Findings

## High (8)

### ENG-D1-01: Single-channel `(N, 1)` chunks (every mono file) and >2-channel chunks crash the live HybridProcessor path
- **Severity**: HIGH
- **Dimension**: Sample Integrity (mono/stereo handling)
- **Location**: `auralis/analysis/loudness_meter.py:145-160` (stereo-only branch of `apply_k_weighting`); reached via `auralis/dsp/utils/adaptive.py:122-132` (`calculate_loudness_units`); gap at `auralis/core/hybrid_stage_dispatch.py:72-74` and `auralis-web/backend/core/audio_processing_pipeline.py:77-94`; shape is produced at `auralis-web/backend/core/chunk_operations.py:150-151`
- **Status**: NEW (regression introduced by #5221 / `91c46747`, 2026-08-26, which swapped `calculate_loudness_units` from shape-agnostic RMS to `LoudnessMeter`; not a regression of a closed issue's fix)
- **Description**: The live streaming path reads each chunk with `sf.SoundFile.read(..., always_2d=True)`, so a mono source arrives as shape `(N, 1)`. `HybridProcessor.validate_and_normalize_input` and `AudioProcessingPipeline.validate_audio` only upmix `ndim == 1`, so an `(N, 1)` buffer goes straight into `ContinuousMode`. The first stage-journal snapshot calls `calculate_loudness_units`, which only upmixes `ndim == 1` and otherwise hands the buffer to `LoudnessMeter.apply_k_weighting`. The 2-D branch of that function hard-codes channel indices 0 and 1 (`audio_chunk[0, 1]`, `pre_filter_zi[:, ch]`), so a 1-channel (or 3+-channel) array raises `IndexError`. Before #5221 the function was `to_db(rms(audio)) - 23` and accepted any shape.
- **Evidence**:
  ```
  # chunk_operations.py:150-151
  audio = f.read(frames_to_read, dtype='float32', always_2d=True)      # mono -> (N, 1)
  # hybrid_stage_dispatch.py:72   only ndim == 1 is upmixed
  # adaptive.py:122               only ndim == 1 is upmixed
  # loudness_meter.py:147         pre_zi * audio_chunk[0, 1]   -> IndexError on (N, 1)
  ```
  Probe (`d1/t2.py`): write a mono WAV, `ChunkOperations.load_chunk_from_file(...)` -> `(352800, 1)`, then `AudioProcessingPipeline.process_audio(..., processor_factory=ProcessorFactory())` ->
  `IndexError: index 1 is out of bounds for axis 1 with size 1` from `FullAudioMeasurement` -> `calculate_loudness_units`. Probe `d1/t3.py`: `(N, 3)` and `(N, 6)` input -> `IndexError: index 2 is out of bounds for axis 1 with size 2` at the same site. A 1-D mono array works (it is upmixed), so the offline job path (`load_audio` returns 1-D mono) is unaffected; only chunked streaming is.
- **Impact**: Enhanced (chunked) streaming of any mono track, and of any >2-channel WAV that libsndfile opens natively, fails on every chunk. `stream_enhanced_chunks` catches the exception per chunk, sends a "Failed to process audio chunk" error and skips the chunk, so the listener hears gaps for the whole track. Mono/FLAC/MP3 files are common in a music library. Secondary hazard if only the loudness meter is fixed: `validate_audio` (and `validate_and_normalize_input`) return a silent `(N, 1)` buffer unchanged at lines 77-79 / 91-92 *before* any channel normalisation, so silent mono chunks would be 1-channel while non-silent ones become 2-channel, and `send_pcm_chunk` flattens and interleaves them as if all chunks had the same channel count.
- **Suggested Fix**: Normalise channel layout once, at the engine entry, before the silence/short early returns: treat `(N, 1)` like 1-D (upmix to `(N, 2)`), and downmix or reject `C > 2` explicitly. Independently make `LoudnessMeter.apply_k_weighting` / `calculate_loudness_units` shape-safe (squeeze `(N, 1)`; iterate channels without assuming 2) and add a regression test that runs a `(N, 1)` chunk through `HybridProcessor.process`.

---

### ENG-D1-02: Chunk-local LUFS normalisation has no gain cap or silence floor; near-silent chunks are boosted by 47-140 dB
- **Severity**: HIGH
- **Dimension**: Sample Integrity (NaN/Inf and level handling; also touches DSP correctness)
- **Location**: `auralis/core/processing/continuous_dsp_ops.py:201-226` (`_apply_final_normalization`, Step 1), `auralis/dsp/utils/adaptive.py:128-137` (`calculate_loudness_units` -70 LUFS floor)
- **Status**: NEW
- **Description**: `_apply_final_normalization` measures the loudness of *the chunk it was handed* and applies `adjustment = target_lufs - current_lufs` with no upper bound. The #4104 guard for "silent audio" (`if not np.isfinite(current_lufs): ... return audio`, lines 202-216) was written when the meter could return -inf. Since #5221, `calculate_loudness_units` converts every non-finite result to the finite floor `-70.0`, so that branch can never fire. The only other silence protection is the exact-zero check (`np.allclose(audio, 0, atol=1e-10)`) in `validate_*`. Any chunk that is not digitally exact zero but is very quiet (dither, room tone, vinyl lead-in, decoded-MP3 silence) is therefore amplified to the track's target loudness. The peak stage that follows only caps the *peak* at -0.3 dBFS; it does nothing about the +60 dB gain.
- **Evidence**: Probes against the live `HybridProcessor` with 10 s stereo white-noise chunks (`d1/t9.py`, `d1/t10.py`, `d1/t15.py`):

  | Mode | input RMS | output RMS |
  |---|---|---|
  | fixed targets (`set_fixed_mastering_targets`, target -14 LUFS), the .25d sidecar path | -40.8 dB (music) | -17.4 dB |
  | fixed targets | -60.9 dB noise | -20.1 dB |
  | fixed targets | -80.9 dB noise | -20.1 dB |
  | fixed targets | -100 / -140 / -160 dB noise | -20.1 dB (+80 to +140 dB gain) |
  | per-chunk fingerprint path | -80.9 dB noise | -34.0 dB (+47 dB) |

  Music at -10 / -20 / -30 / -40 dB RMS all land at -17.4 dB RMS in fixed-target mode, i.e. every chunk is forced to the same loudness regardless of its own level.
- **Impact**: Any chunk whose whole 15 s analysis window is quiet-but-not-zero (hidden-track gap, long quiet intro or outro with dither, a pianissimo passage) is turned into audible full-programme-loudness hiss. Because normalisation is chunk-local, the same mechanism flattens section-to-section dynamics of ordinary material: a quiet section is raised to the target and a loud one is pulled down, so verse/chorus relationships are lost chunk by chunk (the backend `LevelManager` only limits adjacent-chunk changes after the fact). The `LevelManager` silence floor (-60 dB) cannot help because it measures the already-boosted output.
- **Suggested Fix**: Bound the adjustment (for example clamp to a few dB around the file-level gain, or skip normalisation when `current_lufs` is below a silence floor such as -50 LUFS), and restore a real "too quiet to normalise" guard now that the meter never returns -inf. If track-level consistency is intended, derive the gain from the file-level fingerprint rather than from each chunk's own measurement.
- **Related**: ENG-D1-04 (same root cause in the offline CLI path).

---

### ENG-D2-01: Fixed-targets path re-levels every chunk to the track-wide LUFS target, flattening intra-track dynamics
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_dsp_ops.py:201-226` (called from `continuous_stages.py:222-244`); fed by `auralis-web/backend/core/mastering_target_service.py:394-399`
- **Status**: NEW
- **Description**: In fixed-targets mode `params.target_lufs` is a single track-level number (`0.4*track_lufs + 0.6*(-14)`), but `_apply_final_normalization` measures the loudness of whatever buffer it is handed (a 15 s backend chunk) and applies `adjustment = target_lufs - current_lufs` (any `|adj| > 0.5`). Every chunk is therefore forced to the same absolute loudness regardless of how loud that part of the song is. The gain that should be applied is a constant per track (`target_lufs - track_lufs`), not a per-chunk re-derivation. The only counterweight, `LevelManager.smooth_transition`, merely caps the boundary RMS step at 1.5 dB and does nothing when neighbours already match.
- **Evidence**: `HybridProcessor` with `set_fixed_mastering_targets({'target_lufs': -14.0, ...})`, processing a quiet and a loud passage of the same synthetic track as two chunks:
  `quiet in LUFS -35.8 peak 0.05 -> out LUFS -14.0` ; `loud in LUFS -11.3 peak 0.80 -> out LUFS -14.0`.
  A 24 dB difference between sections becomes 0 dB. Call path: `process_chunk_core` -> `AudioProcessingPipeline.apply_enhancement(targets=...)` -> `processor.process(audio)` -> `HybridProcessor._process_adaptive_mode` -> `continuous_mode.process(..., fixed_params=self.current_targets)` -> `_apply_final_normalization`. The fingerprint (non-fixed) path is much less affected because its `target_lufs` is derived from the chunk's own LUFS with a lift that tracks the input.
- **Impact**: Quiet intros, verses, breakdowns and fades are boosted to the loudness of choruses on every track with a cached fingerprint (the primary streaming path); macro-dynamics are erased at 10-15 s granularity, quiet/noisy passages (room tone, fade tails) are pulled up by tens of dB until the -0.3 dBFS peak clamp stops them.
- **Suggested Fix**: Carry the track-level source loudness in the targets (e.g. `source_lufs`) and apply one constant gain `target_lufs - source_lufs` (with the peak clamp), instead of measuring each chunk.

### ENG-D2-02: Fixed-targets conversion sets `stereo_width_target=1.0`, which is maximum widening, not "preserve width"
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/fixed_target_params.py:91`; consumed at `auralis/core/processing/continuous_dsp_ops.py:116-179`
- **Status**: NEW
- **Description**: `convert_targets_to_parameters` hardcodes `stereo_width_target=1.0  # Default: preserve width`. The width axis is a side-gain factor with unity at 0.5 (`WIDTH_FACTOR_UNITY`, `side_gain = 2*factor`); 1.0 means side x2. `_apply_stereo_width` only eases widening away via a peak gate (-3..-2 dBFS), so the amount of widening depends on the chunk's source peak. The fingerprint path generates ~0.5-0.55 for typical material.
- **Evidence**: `ContinuousMode._apply_stereo_width(audio, convert_targets_to_parameters({...}))` on a correlated stereo signal: side RMS out/in = 1.85 (+5.3 dB) at source peak 0.25 and 0.5; 1.00 at peak 0.9. Band-wise side gains reach ~1.47x (300 Hz-2 kHz), ~1.76x (2-8 kHz), ~1.94x (>8 kHz).
- **Impact**: Every cached-fingerprint track is widened by up to +5 dB side level unless its chunks peak above -2 dBFS; because the gate is evaluated per chunk on a peak that varies by section, the stereo image can jump between adjacent chunks of the same track (audible at seams). Mono compatibility of bright content degrades.
- **Suggested Fix**: Use `WIDTH_FACTOR_UNITY` (0.5) as the neutral default (or derive from the fingerprint's `stereo_width` like `calculate_stereo_width`), and add a regression test asserting the fixed path leaves a stereo signal's side/mid ratio unchanged.
- **Also reported as**: ENG-D1-05 (merged; same defect found by another dimension)

### ENG-D2-03: `generate_targets_from_fingerprint` treats 0-1 band fractions as percentages, so every track gets near-saturated EQ boosts
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis-web/backend/core/mastering_target_service.py:405-428,440-457` (consumed by `auralis/core/processing/fixed_target_params.py:35-55`)
- **Status**: NEW (cross-boundary: bug is in the backend target generator; effect is in the DSP EQ)
- **Description**: The `*_pct` fingerprint dimensions are 0-1 fractions (`schema.py` `Unit.FRACTION`, `rust_fingerprint.py` "already 0-1 fractions that sum to ~1.0"). `_calculate_eq_adjustment(current_pct, ideal)` computes `(ideal - current)*0.5` with ideals of 5.0/15.0/18.0/22.0/20.0/13.0/7.0 (percent points, "+-1% = +-0.5 dB"). With fractions, `diff` is ~5-22, so every band saturates at the +6 dB clamp (sub_bass and air land at +2.5/+3.5). The same defaults (`5.0`, `15.0`...) in the `.get()` calls are also percent-scaled.
- **Evidence**: `generate_targets_from_fingerprint({'sub_bass_pct':0.05,'bass_pct':0.30,'low_mid_pct':0.10,'mid_pct':0.20,'upper_mid_pct':0.08,'presence_pct':0.05,'air_pct':0.01,...})` -> `eq_adjustments_db = {sub_bass 2.475, bass 6.0, low_mid 6.0, mid 6.0, upper_mid 6.0, presence 6.0, air 3.495}`; `convert_targets_to_parameters` -> shelves `+8.5 / +6 / +6 / +6 / +9.5 dB`. Pink-noise end-to-end through `HybridProcessor` with these targets vs neutral targets: band deltas (40-120 ... 10-18 kHz) = `[-0.84, +0.61, +0.44, +1.02, +1.67, +1.92, +0.63] dB` after loudness normalization, i.e. a content-independent ~2.7 dB treble-over-bass tilt for every track.
- **Impact**: The fingerprint-driven EQ on the primary streaming path is effectively disabled and replaced by a constant bright tilt (+LUFS-drift guard and normalization then hide the level change). Contradicts the project's HF-overdrive tuning (delta_eq caps at 1.5-2 dB lift).
- **Suggested Fix**: Compute the adjustment in fraction units (ideals 0.05/0.15/..., `diff*100*0.5`) or better, route fixed-target EQ through `delta_eq.compute_delta_eq`; add a unit test on `generate_targets_from_fingerprint` with realistic fractions.

### ENG-D4-01: FFmpeg decode fails with a UnicodeDecodeError whenever ffmpeg's stderr contains non-UTF-8 bytes (ID3v1 Latin-1 tags, non-UTF-8 filenames)
- **Severity**: HIGH
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:172-173` (`subprocess.run(..., text=True)`), `auralis/io/loaders/ffmpeg_loader.py:181-187` (`Popen(..., text=True)` + `communicate`), caught and mislabelled at `ffmpeg_loader.py:547-548`
- **Status**: NEW
- **Description**: Both ffmpeg invocations capture output in text mode with the strict default decoder (UTF-8). ffmpeg runs at its default log level, so stderr carries the input banner, including the file's metadata tags and the input path. libavformat prints ID3v1 tags as raw Latin-1 bytes, and a non-UTF-8 filename is echoed byte for byte. The first such byte makes `communicate()` raise `UnicodeDecodeError`. The broad `except Exception` at line 547 turns it into `ERROR_FFMPEG_CONVERSION: 'utf-8' codec can't decode byte ...`. The file itself is perfectly decodable.
- **Evidence**: Reproduced. An MP3 with an ID3v1 tag containing `Caf\xe9 Cr\xe8me` (and no ID3v2), then `load_audio()`:
  `ModuleError: FFmpeg conversion error: 'utf-8' codec can't decode byte 0xe9 in position 2026: invalid continuation byte`.
  A plain-ASCII-named file with the same tag fails the same way, and a file named `Caf\xe9.mp3` (raw 0xE9 in the name) fails too. `ffmpeg -i file -f null - 2>&1 | cat -v` shows `title : CafM-i CrM-hme`, i.e. raw 0xE9 on stderr. `get_audio_info()` (ffprobe JSON) succeeds for the same files, so the library shows them as healthy.
- **Impact**: Every FFmpeg-routed load of an affected file fails: `load_audio` (normal-stream temp-WAV conversion, fingerprint, mastering-target service, export jobs) and `loader.load` (player). Old MP3 libraries with accented ID3v1-only tags are the common case. The user gets a misleading "FFmpeg conversion error" for a healthy file. `check_ffmpeg()` uses `text=True` too but only reads `-version`, which is ASCII.
- **Siblings**: `ffmpeg_loader.py:173` (no-cancel path) and `:181` (cancellable path) are the only two capture sites. The ffprobe calls (`ffmpeg_loader.py:280`, `unified_loader.py:265`) also use `text=True`, but ffprobe's JSON output is escaped and worked in the repro.
- **Suggested Fix**: Pass `encoding='utf-8', errors='replace'` (or capture bytes and decode with `errors='replace'`) in both calls. Add `-nostdin -hide_banner -loglevel error` so stderr stays small and free of metadata. Add a test with a Latin-1 ID3v1 fixture.

### ENG-D6-01: Backend fingerprint producers flatten stereo with `order='F'`, feeding the Rust engine non-interleaved samples (wrong fingerprints persisted)
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis-web/backend/analysis/fingerprint_generator.py:154-161`, `auralis-web/backend/core/mastering_target_service.py:231-238`
- **Status**: NEW (same two call sites as Existing #5531, but a different defect: #5531 is about the missing sanitizer / duration cap / windowing; this is channel layout). Overlaps with the DSP-pipeline sibling agent's report - CONFIRMED from the analysis side.
- **Description**: `auralis_dsp.compute_fingerprint(audio, sr, channels=2)` expects a 1-D buffer of *interleaved* samples (L0,R0,L1,R1,...). The Rust code downmixes with `(audio[2i] + audio[2i+1]) * 0.5` and extracts `left = step_by(2)`, `right = skip(1).step_by(2)` (`vendor/auralis-dsp/src/fingerprint_compute.rs:214-222`). The in-engine marshaller `AudioFingerprintAnalyzer._analyze_unchecked` builds `interleaved[0::2]=left; interleaved[1::2]=right` (`audio_fingerprint_analyzer.py:153-156`) and `compute_fingerprint_schema`'s docstring says the same. `load_audio()` returns shape `(samples, channels)` (`unified_loader.py`). For an `(N, 2)` array, `flatten(order='F')` is column-major = `[L0..L(N-1), R0..R(N-1)]`, which is NOT interleaved (C-order, the default, would be). The comment next to it ("Interleave: L1,R1,L2,R2...") is wrong.
- **Evidence**: Both sites do `audio_array = <audio>.flatten(order='F')` for `channels == 2`. Reproduction with a 220 Hz tone + 3 kHz bursts, 44.1 kHz stereo `(N,2)`:
  ```
  key               interleaved(correct)  flatten('F')(backend)
  bass_pct          0.9538                0.0
  low_mid_pct       0.0                   0.9472      <- whole spectrum shifted up an octave
  presence_pct      0.0006                0.0507
  tempo_bpm         109.96                79.5
  transient_density 0.411                 0.781
  stereo_width      0.2154                0.0486
  phase_correlation 0.86                  0.9949
  spectral_centroid 0.0426                0.09        (rolloff 0.022 -> 0.044)
  ```
  The 'F' buffer makes the Rust "mono" the average of adjacent samples of L (then of R), i.e. a low-passed signal at half rate analysed as if at full rate (frequencies doubled), and `left`/`right` become even/odd samples of the same channel (stereo_width/phase_correlation meaningless). No test pins the layout (`grep "order='F'" tests` is empty).
- **Impact**: Every stereo track fingerprinted via `FingerprintGenerator.get_or_generate` (stream start in `stream_fingerprint.py:69`, `analysis/fingerprint_queue.py:220`, `config/startup/fingerprint.py:79`) or `MasteringTargetService.extract_fingerprint_from_audio` (Tier-3 path) gets a wrong 25D fingerprint: band energies, centroid/rolloff, tempo, transient density and both stereo dimensions are off. Wrong values are persisted to the DB / `.25d` sidecar, and drive `ProcessingCoordinates` (spectral balance coordinate), mastering targets and similarity search. Mono files are unaffected. Persisted rows stay wrong until re-fingerprinted (no algorithm-version bump distinguishes them).
- **Suggested Fix**: Replace with C-order interleave (`audio.reshape(-1)` / `np.ascontiguousarray(audio).ravel()` for `(N,2)`), or better route both sites through `AudioFingerprintAnalyzer.analyze()` / `compute_windowed_fingerprint()` (also closes #5531). Add a regression test comparing the generator's output with `AudioFingerprintAnalyzer.analyze` on a stereo array, and bump `FINGERPRINT_ALGORITHM_VERSION` / re-fingerprint affected rows.
- **Also reported as**: ENG-D2-04 (merged; same defect found by another dimension)

### ENG-D7-01: `cleanup_missing_files()` and `remove_tracks_under_folder()` bulk-DELETE tracks without clearing `track_artist`/`track_genre`/`track_playlist`, so the foreign keys reject the delete for every real track
- **Severity**: HIGH
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_maintenance.py:154-160` (`cleanup_missing_files`), `:240-243` (`remove_tracks_under_folder`); contrast `auralis/library/repositories/track_repository_lifecycle.py:263-272` (`delete`)
- **Status**: NEW (the fixes for closed #5458 and #5467 call these two methods and are ineffective for any track that has an artist, genre or playlist row)
- **Description**: Both methods run `session.execute(delete(Track).where(Track.id.in_(ids)))`. `track_artist`, `track_genre` and `track_playlist` reference `tracks.id` with plain `FOREIGN KEY ... REFERENCES tracks(id)` and no `ON DELETE` action. That holds for fresh databases (`models/base.py:24-50`, built by `create_all`) and for migrated ones (v000 initial schema, v015->v016 rebuild). Every pooled connection runs `PRAGMA foreign_keys=ON` (`database.py:172`). A Core/ORM bulk delete does not touch `secondary` tables, so SQLite raises `FOREIGN KEY constraint failed` as soon as one doomed track has an association row. Nearly every scanned track does, because the scanner stores artists and genres. `TrackRepository.delete()` handles this: it deletes the three association tables first, and its docstring says "The three association tables predate ON DELETE CASCADE". The two bulk paths were written without that step.
- **Evidence**:
  ```python
  # track_repository_maintenance.py:154-160
  if still_missing:
      session.execute(delete(Track).where(Track.id.in_(still_missing)))
      session.commit()          # IntegrityError -> caught by outer `except`, rollback(), raise
  # track_repository_lifecycle.py:263-272 (the correct sibling)
  for association in (track_playlist, track_genre, track_artist):
      session.execute(delete(association).where(association.c.track_id == track_id))
  ```
  Callers swallow the exception: `auralis-web/backend/services/missing_tracks.py:34-37` and `:65-70` log a warning and return 0. The regression tests (`tests/regression/test_cleanup_missing_files_pagination.py`, `tests/regression/test_remove_tracks_under_folder_5467.py`) add tracks with no artists, genres or playlists, so no association row exists and the FK never fires. `tests/backend/test_manual_scan_prunes_missing_5458.py` mocks `cleanup_missing_files` entirely.
- **Impact**: Removing a scan folder (#5467) and the post-scan prune of deleted or moved files (#5458) silently do nothing for real libraries. Dead entries stay in the library and stay playable-looking; a removed scan folder's tracks stay visible while the path-validated endpoints reject them with 400. The WebSocket `library_tracks_removed` frame never fires. The failure is a one-line warning, so it is easy to miss. Because each batch is one atomic DELETE, the first batch that contains a track with relationships aborts the whole run.
- **Suggested Fix**: Extract the association-table cleanup from `TrackRepository.delete()` into a shared helper (for example `_delete_tracks_by_ids(session, ids)`) and use it from `delete()`, `cleanup_missing_files()` and `remove_tracks_under_folder()`. Add a regression test whose tracks have an artist, a genre and a playlist membership.

---


## Medium (17)

### ENG-D1-03: `LevelManager` applies up to +40 dB of gain after the brick-wall limiter; nothing re-checks the ceiling before float32 PCM goes on the wire
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity (clipping prevention)
- **Location**: `auralis-web/backend/core/level_manager.py:205-239` (boost branch), `:41` (`MAX_GAIN_CORRECTION_DB = 40.0`), called from `auralis-web/backend/core/chunk_render.py:295`; consumer `auralis-web/backend/core/stream_protocol.py:172` (`astype(np.float32)` then raw bytes, no clamp)
- **Status**: NEW
- **Description**: `HybridProcessor` ends in a brick-wall limiter at -0.3 dBFS (0.966). `process_chunk_core` then runs `LevelManager.smooth_transition`, which multiplies the chunk by `required_adjustment_db = target_diff - level_diff_db` whenever the chunk's RMS differs from the previous chunk's by more than 1.5 dB. For a chunk that is quieter than its predecessor this is a *boost*, applied to a signal whose peaks already sit at the limiter ceiling. There is no peak check after the gain. The streamed samples are sent as unclamped float32 (`send_pcm_chunk`), so overs reach the client's Web Audio output; the cached copy goes through `saver.save`, which hard-clips to +/-1.0, so first play and cached replay clip differently.
- **Evidence**: Probe `d1/t4.py`: chunk 0 RMS ~ -12 dB, chunk 1 RMS ~ -22 dB, both with a peak of 0.966 (the limiter ceiling). `smooth_transition` returns `gain = +8.4 dB`, output peak = **1.68**. The existing tests (`tests/backend/test_level_manager_smoothing.py`) only bound the silence-burst case (`peak_out <= peak_in * 2`); none asserts a ceiling.
- **Impact**: Audible hard clipping (in the browser output stage, or in the WAV cache) on the first high-crest, lower-RMS chunk following a louder section, e.g. verse after chorus with drum transients limited to the ceiling. Occurs only when the quieter chunk's peaks are near the limiter ceiling, so it is intermittent.
- **Suggested Fix**: Cap the boost by the available headroom (`min(required_gain, ceiling / chunk_peak)`) or run a final safety limiter after `smooth_transition`; add a regression test with peak-limited chunks.

---

### ENG-D1-04: Offline mastering CLI peak-normalises every 30 s chunk independently, boosting quiet sections and tails by up to +50 dB
- **Severity**: MEDIUM (offline CLI subsystem, see note in `simple_mastering.py`; treat as an offline-tool bug)
- **Dimension**: Sample Integrity (level handling across chunks)
- **Location**: `auralis/core/mastering_branches/continuous.py:215-230` (`normalize(processed, adapted_peak)`), driven by `auralis/core/mastering_chunk_loop.py:151-196`
- **Status**: NEW
- **Description**: `SimpleMasteringPipeline` processes the file in 30 s chunks, and `_process` is called on each chunk independently. Both `loudness_maximizer` ("the push gain is derived from FILE-LEVEL fingerprint values ... so every chunk receives the same gain and inter-chunk loudness stays consistent") and the pre-scan for `_song_peak_db` exist to keep gain file-consistent. The last step of the branch then undoes that: `normalize(processed, adapted_peak)` scales *the chunk* so its own peak equals 0.84-0.89, whatever the chunk's level. `dsp.basic.normalize` boosts any chunk with a non-zero peak.
- **Evidence**: End-to-end probe `d1/t6.py` (`master_file` on a 75 s file: 30 s at full level, 30 s at -30 dB, 15 s at -50 dB; sample count preserved, 3,307,500 in and out):

  | Section | input RMS | output RMS |
  |---|---|---|
  | 0-30 s | -10.3 dB | -10.1 dB |
  | 30-60 s | -40.8 dB | -10.4 dB |
  | 60-75 s | -60.8 dB | -10.2 dB |

  Per-chunk `_process` probe (`d1/t5.py`): peaks from -2.4 to -62.4 dB all come out at -1.5 dB peak / -9.6 dB RMS.
- **Impact**: A quiet movement, a long fade-out, or a silent/near-silent tail chunk is brought up to the same level as the loudest section (a -60 dB tail is boosted ~+50 dB). The 3 s crossfade turns the chunk-to-chunk difference into a level ramp rather than a click, but macro-dynamics are destroyed and noise floors are raised. Not on the shipped app's path.
- **Suggested Fix**: Replace the per-chunk `normalize` with a file-level gain (computed once in `prepare_file` from the song peak / loudness) applied identically to every chunk.
- **Related**: ENG-D1-02 (same pattern in the live path).

---

### ENG-D2-05: The reference-cloud (Phase 4) target derivation, `delta_eq` and album mode are unreachable in production: nothing passes a `fingerprint_repository` to `ContinuousMode`
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline (config reachability)
- **Location**: `auralis/core/hybrid_setup.py:97-99`; reader at `auralis/core/processing/continuous_mode.py:129-155`
- **Status**: NEW
- **Description**: `ContinuousMode.__init__(..., fingerprint_repository=None)` is the only way `_reference_context()` returns a cloud (and so the only way `target_derivation.derive_target`, `delta_eq.compute_delta_eq`/`generate_eq_curve_from_target`, `derive_album_target` run). `build_hybrid_components` constructs it as `ContinuousMode(config, content_analyzer, fingerprint_analyzer)` and nothing ever assigns `.fingerprint_repository`. `git log -S"fingerprint_repository" -- auralis/core` returns only the Phase 4 commit `6051d5e8`, so the "wired through pipeline" claim never reached `HybridProcessor`. Meanwhile the backend maintains the cloud (`_init_reference_cloud_refresh` -> `refresh_cloud`), so the data is produced but never read by mastering.
- **Evidence**: grep for `fingerprint_repository` / `_reference_cloud` / `get_reference_cloud` across `auralis/` and `auralis-web/backend` shows only `continuous_mode.py` itself and the cloud refresh/seeding code; the only constructor call is `hybrid_setup.py:97`. (The 2026-09-17 audit attributed the cloud's inactivity to #5530 only; it is inactive even with a populated cloud.)
- **Impact**: The "symmetric, capped delta-from-target EQ" that replaced the HF-boosting deficit curve (and per-album consistency, #3481 Phase 1) never runs. Per-chunk (non-fixed) mastering always uses the legacy deficit curve; fixed-target mastering uses the broken ENG-D2-03 curve.
- **Suggested Fix**: Pass `repository_factory.fingerprints` into the processor (e.g. via `ProcessorFactory`/`build_hybrid_components`), or delete the dead derivation chain; add a wiring test asserting `HybridProcessor(...).continuous_mode.fingerprint_repository is not None` in the backend factory.

### ENG-D2-06: `ExpansionStrategies.apply_rms_reduction_expansion` ("de-mastering") is a uniform gain and cannot change crest factor; net effect is nil
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/base/compression_expansion.py:203-236` (gain at `:221-224`); parameters from `parameter_generator_dynamics.py:144-173`
- **Status**: NEW (same bug class as the closed #5309, which removed the sibling crest-preservation guard)
- **Description**: The strategy claims to "increase crest factor through RMS reduction" but implements `amplify(audio, -target_crest_increase*amount)`, a scalar gain. Peak and RMS move together, so crest is invariant. The stage then runs before stereo/normalization and `_apply_final_normalization` re-measures loudness and re-boosts to `target_lufs`, undoing the attenuation (except inside the 0.5 dB dead-band).
- **Evidence**: `apply_rms_reduction_expansion(x, {'target_crest_increase': 3.0, 'amount': 0.85})`: crest 19.580 -> 19.580 dB, RMS -19.98 -> -22.53 dB. `tests/auralis/core/test_compression_expansion_invariants.py` only asserts input immutability.
- **Impact**: The whole expansion parameter family (`target_crest_increase`, `amount = 0.85*(1-dyn)^2`) is a placebo: heavily compressed sources get no dynamics restoration. The temporary 0-2.5 dB attenuation also biases the downstream peak-gated width stage and guard measurements.
- **Suggested Fix**: Remove the stage (as done for the crest guard in #5309) or implement a real downward/upward expander (level-dependent gain); add a crest-delta test.

### ENG-D2-07: `BrickWallLimiter` "look-ahead" window looks backward; the gain steps down instantly at the peak sample
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/brick_wall_limiter.py:122-149` (origin at `:138-144`)
- **Status**: NEW (the closed #3308 fix and the 2026-07-29 audit assumed the opposite)
- **Description**: In `scipy.ndimage.maximum_filter1d`, a positive `origin` shifts the window toward EARLIER samples, so `origin=(lookahead-1)//2` makes `peak_envelope[i] = max(x[i-size+1 .. i])` (a post-peak hold), not a look-ahead. The code comment states the opposite. With instant attack the gain curve drops from 1.0 to `thr/peak` in a single sample at the peak and then releases.
- **Evidence**: `maximum_filter1d(spike@20, size=8, origin=3)` flags outputs 20..27. Real limiter (`threshold -0.3 dB, lookahead 2 ms`): input 0.5 with one 1.5 sample at index 10000 -> gain 1.0 at 9999, 0.644 at 10000 (no pre-reduction). No test checks reduction before the peak.
- **Impact**: Every limited peak produces a hard gain step (broadband click/distortion) instead of a ramped attack; the documented "no clicks/pops, eliminates overshoot" is false. Reach in the shipped chain is small (ContinuousMode pins peaks at -0.3 dBFS before the limiter, so it engages by fractions of a dB), but it is the last stage for reference/hybrid/adaptive modes and any hot signal.
- **Suggested Fix**: Use a negative origin (window `[i, i+size)`), then smooth the attack (e.g. `uniform_filter1d` / min-filter then ramp over `lookahead` samples) and add a test asserting gain at `peak_idx - lookahead` is already below 1.

### ENG-D3-01: Engine next/previous/gapless read `file_path`/`path`, but every production queue entry uses `filepath` or has no path at all
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/gapless_playback_engine.py:138,279`; `auralis/player/player_queue_navigation_mixin.py:168`; `auralis/player/components/queue_manager.py:22-23` (`_track_matches`); producers at `auralis/player/queue_controller.py:431`, `auralis-web/backend/services/queue_set_mixin.py:123-127`, `auralis-web/backend/services/queue_edit_mixin.py:57`, `auralis/library/models/track.py:154-186`
- **Status**: NEW
- **Description**: The engine resolves a queue entry's file with `entry.get('file_path') or entry.get('path')`. The entries the application actually puts in the engine queue never carry those keys:
  - `QueueService.set_queue` calls `queue.set_queue([t.filepath ...])`, which `QueueController.set_queue` wraps as `{'filepath': <str>}` (no `id`, no `file_path`).
  - `QueueService.add_track_to_queue` and `POST /api/player/load` build `{'id':…, 'filepath':…}`.
  - `QueueController.add_track_from_library`, `search_and_add` and `load_playlist` store `Track.to_dict()`, which has `id` but no path key at all (the `filepath` is deliberately stripped, #3205).
  The backend's own readers (`entry_filepath`, `queue_edit_mixin.py:148`) look for `filepath` first, so the two sides disagree on the schema. Only `AudioPlayer.add_to_queue` (`player_queue_navigation_mixin.py:221`) accepts `filepath`.
- **Evidence**: Running the exact production sequence (`queue.set_queue(paths, 1)`, `load_file`, `play`):
  `peek {'filepath': '.../c.wav'}`; `next_track -> False current .../b.wav`; `previous_track -> False ... idx 1`; and with `add_track({'id': i, 'filepath': p})` entries `next -> False`.
  Call path: `AudioPlayer.next_track` -> `GaplessPlaybackEngine.advance_with_prebuffer` -> `file_path = next_track.get('file_path') or next_track.get('path')` -> `None` -> `return False` (line 280-281). `_prebuffer_worker` logs "Next track has no file path" and returns (line 139-141), so nothing is ever prebuffered. `previous_track` moves the queue index, finds no path, and rolls back (line 168-195). Tests mask this: `tests/auralis/player/test_gapless_playback_engine.py` and `test_previous_track_resume.py` build entries as `{"file_path": ...}`.
- **Impact**: The engine's gapless/prebuffer, `next_track()` and `previous_track()` are inoperative for all real queue entries. `POST /api/player/next` and `/previous` always answer "No next track available" / fail (the frontend does not call them today: `PLAYER_NEXT` has no consumer outside `config/api.ts`, which is the only reason this is not user-visible). The moment anything reaches for engine-side navigation or an audio output is attached, gapless playback silently does not happen.
- **Siblings**: Same key set is repeated in `_track_matches` (`queue_manager.py:22-23`), `_prebuffer_worker` (138), `advance_with_prebuffer` (279, 303-305) and `previous_track` (168).
- **Related**: ENG-D3-03 (becomes live once this is fixed), ENG-D3-02. Closed #5508 (invalidation) assumed the prebuffer works.
- **Suggested Fix**: Add one `entry_filepath(entry)` helper in `auralis/player/components/queue_manager.py` (accepting `filepath`, `file_path`, `path`) and use it at all five engine sites plus `add_to_queue`; add a test that drives `next_track()`/`previous_track()` with entries shaped exactly like `QueueService` produces.

---

### ENG-D3-02: `shuffle()`/`unshuffle()` identify the current track by `id` only, so idless queue entries lose the current-track pointer
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/components/queue_manager.py:378-391` (`shuffle`), `:399-410` (`unshuffle`)
- **Status**: NEW
- **Description**: `shuffle()` keeps the playing track "in place" by looking it up with `track.get('id') == current_track_id`. When the current entry has no `id`, `current_track_id` is `None`, the pin block is skipped, and `current_index` is left untouched while `random.shuffle(self.tracks)` has permuted the list underneath it. `unshuffle()` has the same gap and then restores the stale `_pre_shuffle_index`. Every queue created by the app's main path (`QueueService.set_queue` -> `{'filepath': ...}` entries, see ENG-D3-01) has no `id`. The sibling mutators `reorder_tracks` (`:327-337`) and `move_track` (`:348-356`) were already fixed to track the current item by object identity for exactly this case (#4776); `shuffle`/`unshuffle` were missed. The frontend does call `POST /api/player/queue/shuffle` (`useQueueMutations.ts:276`), which reaches `QueueManager.shuffle()` through `QueueService.shuffle_queue`.
- **Evidence**: `t2.py`: with `set_queue([10 paths], start_index=3)`, calling `shuffle()` changed `get_current_track()` in 178 of 200 seeded runs; with `{'id': i, ...}` entries 0 of 200. After `shuffle(); next_track(); unshuffle()` on idless entries the current track changed from `/m/5.flac` to `/m/3.flac`.
- **Impact**: After shuffling, the engine's current pointer jumps to a random different track while the loaded audio is unchanged; queue state sent to clients (`current_index`, `current_track`) shows the wrong now-playing item, and the next advance continues from the wrong position. Unshuffle then restores the pre-shuffle index regardless of where playback went.
- **Siblings**: Duplicate ids (same track twice) also resolve to the first match in both methods.
- **Related**: #5315 (second shuffle snapshot, closed) fixed the snapshot but not the identity.
- **Suggested Fix**: Capture `current_track = self._get_current_track_unlocked()` and re-locate it by identity (`track is current_track`) after the shuffle/restore, exactly as `reorder_tracks` does; fall back to index only when there is no current track.

---

### ENG-D3-03: Prebuffer-match test treats two missing ids as equal, so a stale prebuffer for a different track is swapped in
- **Severity**: MEDIUM (latent: unreachable in production until ENG-D3-01 is fixed, reachable today for any entry with a path key and no `id`)
- **Dimension**: Player State
- **Location**: `auralis/player/gapless_playback_engine.py:298-306`
- **Status**: NEW
- **Description**: `prebuffer_matches` is `prebuffered_info.get('id') == next_track.get('id') or <path> == file_path`. If neither dict has an `id` (idless entries, the common shape, see ENG-D3-01/02), `None == None` is `True` and the path comparison is never needed. The queue-level equivalent `_track_matches` (`queue_manager.py:16-24`) handles this correctly (it only compares ids when both are non-None); the gapless engine does not reuse it. `previous_track()` moves the queue index without invalidating the prebuffer (it is not an "edit"), so the buffer for the old "next" track is exactly the stale case; `start_prebuffering()` also declines while an earlier worker is alive.
- **Evidence**: `t3.py`: queue `[A,B,C]` of `{'file_path': ...}` entries, `current_index = 1` (next is C), buffer left over for B. `advance_with_prebuffer(True)` returned `True`; result: `queue now at {'file_path': '/m/C.wav'} engine audio len 100 current_file /m/C.wav` where the 100-sample audio is B's prebuffer. Queue and loaded audio now describe different tracks.
- **Impact**: Wrong audio is installed under the next track's name (track mismatch rather than a gap); position, duration, fingerprint scheduling and `current_file` all describe C while the samples are B's. Sample counts are consistent, so nothing detects it.
- **Siblings**: None; this is the only place the engine compares queue entries by hand.
- **Related**: #2303 (the original stale-prebuffer guard), #3352.
- **Suggested Fix**: Replace the inline expression with the shared `_track_matches(prebuffered_info, next_track)` and add a test with idless entries and a stale buffer.

---

### ENG-D4-02: FFmpeg intermediate WAV is not RF64-capable; decodes over 4 GiB are silently truncated at 2^32 bytes with no warning
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:456-474` (no `-rf64 auto`); siblings `auralis-web/backend/core/seekable_source.py:92-95` (`sf.write(..., format="WAV", subtype="FLOAT")`), `auralis/core/simple_mastering.py:185` (`sf.write(..., subtype="PCM_24")`), `auralis/io/saver.py:55`
- **Status**: NEW
- **Description**: `MAX_DECODED_BYTES` admits decodes up to 6 GiB of float32, but the temp WAV that ffmpeg writes is a plain RIFF with a 32-bit size. Above 4 GiB the size field wraps, and libsndfile then reports and reads only the wrapped frame count. `_get_wav_declared_size` sees a *small* declared size against a larger real file, so the truncation check does not fire. The duration check at `ffmpeg_loader.py:519-535` only warns below 90%, so a loss of 3.6% passes silently.
- **Evidence**: Reproduced. A 5800 s, 96 kHz, stereo ALAC `.m4a` (decoded size 4.15 GiB, under the 6 GiB budget) gave `load_with_ffmpeg()` -> `(536870911, 2)` frames, 5592.4 s, against 5800.0 s expected. No warning was raised. ffmpeg with `-rf64 auto` wrote the full 556,800,000 frames, and `sf.info` reported `RF64`, 5800.0 s. `sf.write(format='WAV')` of the same 556.8 M-frame float32 array produced a file that `sf.info` reports as 536,870,911 frames, so the backend's `convert_to_temp_wav` has the same truncation. The `simple_mastering.py` and `saver.py` writes are the same libsndfile WAV behaviour once the output exceeds 4 GiB; I did not run those two separately.
- **Impact**: Long hi-res files (about 93 min or more at 96 kHz stereo, about 46 to 70 min at 192 kHz) lose their tail. Playback ends early, fingerprint and mastering see a shortened track, and nothing is logged. Rare input, but the loss is silent.
- **Suggested Fix**: Add `-rf64 auto` to the ffmpeg output args. Use `format='RF64'` in the Python temp-WAV writers (or a lower decode budget for WAV staging). Raise instead of warn when the decoded frame count is below the ffprobe duration by more than a small tolerance.

### ENG-D4-03: Library scan ingests undecodable files as tracks with duration 0 and no sample rate, and reports zero failures
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/library/scanner/audio_analyzer.py:58-99` (returns the object even when both probes fail); consumer `auralis/library/scanner/batch_processor.py:135-139` (the "unreadable or unsupported file" branch can never trigger for these)
- **Status**: NEW
- **Description**: `extract_audio_info` only returns `None` on an exception. When `sf.info` fails and `_probe_audio` returns its all-`None` dict (corrupt, truncated or garbage content), it leaves `duration`, `sample_rate` and `channels` unset and still returns the object. `oversize_probe_detail(None, None, None)` returns `None`, so the #5312 guard passes. The batch processor then adds the track.
- **Evidence**: `AudioAnalyzer().extract_audio_info()` returned `(None, None, None, 'MP3'/'M4A'/'OPUS'/'WAV'/'FLAC')` plus a hash for `garbage.mp3`, `garbage.m4a`, `garbage.opus`, `truncated.m4a`, a 100-byte `tiny.mp3`, a header-only `hdr.wav` and a zero-byte `empty.wav`. A real `LibraryScanner.scan_directories()` on a temp DB (isolated HOME) with 1 good MP3, 1 garbage MP3 and 1 truncated M4A returned `files_added=3, files_failed=0`. The DB rows were `('good.mp3', 3.0, 48000, 2, 'MP3')`, `('trunc.m4a', 0.0, None, None, 'M4A')` and `('garbage.mp3', 0.0, None, None, 'MP3')`.
- **Impact**: Corrupt files appear in the library at 0:00. Fingerprint workers and playback then fail on them; the zero-duration crash in closed #5272 is the downstream symptom. The scan summary reports no failures, so the user never learns which files are bad (the intent of #4841).
- **Suggested Fix**: In `extract_audio_info`, return `None` when no probe yielded a positive duration and a sample rate and channel count (or when `sample_rate`/`channels` are missing). The existing "failed" branch in `batch_processor` then reports it.

### ENG-D4-04: Scanner tag extraction drops track/disc numbers for every M4A and reads no tags at all from WMA
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/library/scanner/metadata_extractor.py:121-127` and `:144-150` (MP4 `trkn`/`disk` are tuples); `:51-62` (`TAG_MAPPINGS` has no ASF keys)
- **Status**: NEW (sibling of, but distinct from, open #5536, which covers WMA *writes*, and closed #5506, which covers MP4 writes)
- **Description**: For MP4, `audio_file['trkn']` is `[(3, 12)]`. After `value = value[0]` it is the tuple `(3, 12)`. `_normalize_field_value` tests `'/' in str(value)`, which is false for `"(3, 12)"`, so it calls `int((3, 12))`. That raises `TypeError`, is swallowed, and returns `None`, so `track` and `disc` are never stored. For ASF/WMA the keys are `Title`, `Author`, `WM/AlbumTitle`, `WM/Genre` and so on, none of which are in the mapping, so no field is extracted.
- **Evidence**: Same tags written with ffmpeg (`title, artist, album, album_artist, date, genre, track=3/12, disc=1/2`), then `MetadataExtractor().extract_metadata_from_file()`:
  - `m.flac`, `m.mp3`, `m.ogg`, `m.opus` all return the full set, including `track: 3, disc: 1`.
  - `m.m4a` returns title, artist, album, albumartist, date, year and genre, with no `track` or `disc`.
  - `m.wma` returns `{}`.
- **Impact**: Every M4A/ALAC album loses track and disc numbers at scan time, so track ordering inside albums and disc grouping degrade. WMA tracks show only the filename as title and have no artist or album. No audio is affected.
- **Suggested Fix**: Handle tuple values for `trkn` and `disk` (take `value[0]`). Add ASF key candidates (`Title`, `Author`, `WM/AlbumTitle`, `WM/AlbumArtist`, `WM/Genre`, `WM/TrackNumber`, `WM/PartOfSet`, `WM/Year`), unwrapping `ASFUnicodeAttribute` with `.value`.
- **Also reported as**: ENG-D7-05 (merged; same defect found by another dimension)

### ENG-D5-01: Chunk loop truncates >2-channel sources to the first two channels, bypassing the project's BS.775 downmix
- **Severity**: MEDIUM (offline CLI only)
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:175-178`
- **Status**: NEW. This is the defect class fixed by #3743 and #5242 in the loaders, left behind at a bypass site. The loop reads through `sf.SoundFile` directly and never goes through `auralis/io`.
- **Description**: For any source with more than 2 channels, the loop does `chunk = chunk[:, :2]`. Its comment calls this "L+R only", and the earlier comment at lines 63-66 says ">2ch sources are downmixed to L+R". It is a truncation, not a downmix. For 5.1/7.1 content it drops Center (vocals/dialogue), LFE and the surrounds. The project already has `auralis/io/processing.py::downmix_to_stereo` (BS.775 matrix). Its docstring says the same `audio_data[:, :2].copy()` truncation in the loaders "drops Center (vocals/dialogue), LFE, and surround content" and was replaced by #3743. Non-canonical counts are routed through FFmpeg (`-ac 2`) per #5242. FFmpeg-only formats are pre-converted to a stereo temp WAV in `simple_mastering.py:180-186`. So only soundfile-native multichannel files (WAV/FLAC/AIFF/OGG with more than 2 channels) reach this truncation.
- **Evidence**:
  ```python
  elif chunk.ndim == 2 and chunk.shape[1] > 2:
      # Multi-channel (e.g. 5.1 surround): take L+R only.
      chunk = chunk[:, :2]
  ```
  The caller `mastering_prepare.prepare_file` only reads `channels` for display. No downmix or layout check happens anywhere before the loop. The pre-scan `_song_peak_db` (`mastering_prepare.py:211-222`) and the notch window (`:146-148`) read all channels, so they also measure content that the output never contains.
- **Impact**: A 5.1 FLAC/WAV mastered with `auto_master.py` silently loses its center and surround content. The output looks like a normal stereo master with no warning. The peak and notch pre-scans are computed from channels that are then discarded, so those measurements are inconsistent with the processed audio.
- **Suggested Fix**: Reuse `downmix_to_stereo` / `requires_layout_aware_downmix` from `auralis/io/processing.py`. Downmix per chunk for the canonical 6/8 channel counts. Route other counts through the FFmpeg pre-conversion path, or raise a clear error. Do not add a second inline matrix.

### ENG-D6-02: Rust band-energy analysis floors every FFT bin at 1e-10, so the 7-band fingerprint depends on signal level (quiet material is skewed toward a bin-count-proportional spectrum)
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `vendor/auralis-dsp/src/frequency_analysis.rs:50-55` (`compute_psd`, `.max(1e-10)`), consumed at `:99-140` (`compute_frequency_distribution`)
- **Status**: NEW
- **Description**: `compute_psd` normalises power by `fft_size^2` and then floors every bin at an *absolute* 1e-10. With a 2^19-2^20 point FFT (30 s analysis window at 22.05 kHz) per-bin normalised power for ordinary program material at the HF end is far below 1e-10, so the floor, not the signal, sets those bins. Because each band is the sum over its bins, the floor contributes `n_bins_in_band * 1e-10`, which grows with band width (air/presence get the most bins) and becomes a large fraction of the total as the level drops. The "fractions summing to 1" therefore depend on loudness, not only on spectral shape - and the fingerprint exists precisely to characterise quiet/loud material.
- **Evidence**: 30 s of 1/f ("pink") noise, 22.05 kHz mono, scaled to different levels, `auralis_dsp.compute_fingerprint` bands `[sub, bass, low_mid, mid, up_mid, presence, air]`:
  ```
  RMS -14 dBFS: [0.169, 0.223, 0.113, 0.221, 0.112, 0.111, 0.052]
  RMS -25 dBFS: [0.157, 0.208, 0.105, 0.208, 0.112, 0.131, 0.077]
  RMS -31 dBFS: [0.104, 0.138, 0.071, 0.160, 0.127, 0.229, 0.171]
  RMS -37 dBFS: [0.038, 0.053, 0.032, 0.130, 0.165, 0.331, 0.250]
  RMS <=-50:    [0.0036,0.0173,0.0227,0.1363,0.1817,0.3635,0.2749]   (pure floor, identical at -50/-70)
  ```
  Same spectral shape, 23 dB quieter: bass 0.22 -> 0.05, air 0.05 -> 0.25. Real music with a steep HF roll-off (lossy sources with a 16 kHz low-pass) is hit at far higher levels than pink noise.
- **Impact**: Quiet / dynamic material (classical, film, old recordings - the "quiet recordings" the mastering engine explicitly boosts) gets a spuriously bright band profile; `spectral_balance` coordinate, bass-aware targets (`bass_pct`), and band-based similarity all inherit it. Not a crash; silent accuracy degradation.
- **Suggested Fix**: Floor relative to the spectrum (e.g. `max_power * 1e-12`) or drop the floor and only guard the final division (`total > 0` is already checked); then bump `FINGERPRINT_ALGORITHM_VERSION`.

### ENG-D6-03: `transient_density` measures sample-to-sample amplitude change over only the first second, not transients (sine = drums); `bass_mid_ratio` likewise uses only the first ~3 s
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `vendor/auralis-dsp/src/fingerprint_compute.rs:468-490` (`estimate_transient_density`); sibling `:127-175` (`compute_bass_mid_ratio`, `fft_size = len.next_power_of_two().min(65536)` + `.take(fft_size)`)
- **Status**: NEW
- **Description**: `estimate_transient_density` takes `windows(2).take(frame_size.min(len-1))` with `frame_size = sample_rate` - i.e. only the first 1 s of the (already 90 s) analysis window - and counts samples whose `|x[n+1]-x[n]| > 0.01` (absolute threshold). That is a measure of HF-content x absolute level over one second, not of onsets/transients, and it ignores the remaining 89 s. `compute_bass_mid_ratio` runs a single FFT on at most the first 65 536 samples (~3 s at 22.05 kHz) of the same window, while the sibling band analysis uses 30 s (`frequency_analysis.rs:86-88`) - inconsistent scopes inside one fingerprint. `schema.py` documents `transient_density` as a 0-1 normalised dimension and `adaptive_loudness.py` consumes it as "transient density".
- **Evidence**: mono 22.05 kHz, 20 s:
  ```
  steady 220 Hz tone + 4 noise-click/s drums, amp 0.3 : 0.647
  same, first 1.5 s silenced (intro)                  : 0.0
  same, 30 dB quieter                                 : 0.0025
  pure 220 Hz sine, amp 0.3, NO transients            : 0.643
  pure 5 kHz sine, amp 0.3                            : 0.982
  ```
  Consumers: `auralis/dsp/utils/adaptive_loudness.py:113-123` (`bass_pct > 0.15 and transient_density > 0.35` -> gain reduction `bass_pct*transient_density*6*loudness_factor`, up to ~1.6 dB), fed from `auralis/core/mastering_branches/continuous.py:70-73` and `auralis/core/processing/adaptive_mode.py:270-276`.
- **Impact**: Makeup-gain decisions depend on whether the first second of the analysis window is loud/HF-rich rather than on percussive content: a track with a quiet start of the body window gets 0 (no bass-transient reduction), a loud tonal track gets ~0.65 (reduction applied). Fingerprint similarity on this dimension is meaningless. Moderate, content-dependent mastering inconsistency; no crash.
- **Suggested Fix**: Compute the metric over the whole window using an onset-strength envelope (the crate already has `tempo`/`onset_detector`/spectral-flux code) and derive onsets/sec normalised to 0-1; give `compute_bass_mid_ratio` the same 30 s span as the band analysis (averaged frames). Bump the algorithm version.

### ENG-D7-02: Repository write paths other than the extractor never advance `fingerprint_version`, so rewritten rows stay "stale" and are never served from the cache
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_crud_mixin.py:58-61` (`add`), `:102-105` (`update`); `auralis/library/repositories/fingerprint_upsert_mixin.py:75-91` (`upsert` ON CONFLICT clause); `auralis/library/models/fingerprint.py:80` (`default=1`)
- **Status**: NEW (related: #5530, #5539)
- **Description**: Reads treat a row as usable only if `fingerprint_version >= FINGERPRINT_ALGORITHM_VERSION` (`fingerprint_shared._current_fingerprint_clause`, currently 8). Only `FingerprintExtractor._prepare_for_storage` stamps the version into the dict it passes to `upsert()`. Two other writers do not:
  1. `FingerprintCrudMixin.add()` builds `TrackFingerprint(track_id=..., **data)` with no version, so the ORM default `1` applies. `update()` only `setattr`s the keys it is given. The live on-demand path `AudioStreamController` -> `ensure_fingerprint_available` -> `FingerprintGenerator.get_or_generate` (`auralis-web/backend/analysis/fingerprint_generator.py:284`) stores through `add()` with raw schema dimensions.
  2. `upsert()` only refreshes the dimension columns on conflict. Its own comment says `fingerprint_version` "stay as whatever store_fingerprint set". `FingerprintService._save_to_database` (`auralis/analysis/fingerprint/fingerprint_service.py:275`) calls `upsert(track_id, fp_data)` with dimensions only.
  The result is a freshly computed row marked version 1 (via `add`) or left at its old version (via `upsert` on an existing outdated row). `get_by_track_id()` and `exists()` hide it, even though the data is current. `FingerprintService._load_from_database` documents this path as "self-healing: it recomputes and rewrites", but the rewrite never makes the row current.
- **Evidence**: `fingerprint_generator.get_or_generate`: `get_by_track_id` returns None (row is v1 < v8) -> decode the full file -> Rust fingerprint -> `fingerprint_repo.add` (which updates the existing row, version still 1). The next call misses again. The only thing that eventually promotes the row is the background outdated-queue pass, which goes through the extractor. A fresh install is worse: while #5530 breaks the extractor's `upsert`, the ORM `add()` path works, so every on-demand row is version 1 and is recomputed on every play.
- **Impact**: Repeated full-file decode plus fingerprint on every play or seek-start of any track whose row came from `add()` or an outdated `upsert()`. This is wasted CPU and I/O, and a 30 s timeout exposure on the stream-start path. It persists until the background queue reaches the track, which can take hours after each `FINGERPRINT_ALGORITHM_VERSION` bump (all rows go stale at once).
- **Suggested Fix**: Make the repository stamp the version itself: add `fingerprint_version = excluded.fingerprint_version` to the `upsert()` DO UPDATE clause (the INSERT already supplies `:fp_version`), and make `add()`/`update()` set `FINGERPRINT_ALGORITHM_VERSION`. Change the model default from `1` to the current constant, or drop it.

---

### ENG-D7-03: Playlist `position` invariant (contiguous 0..N-1) is broken by `add_track(position=...)` and by track deletion
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/playlist_membership_mixin.py:129-175` (`add_track` explicit-position branch); `auralis/library/repositories/track_repository_lifecycle.py:263-269` and `track_repository_maintenance.py:154-160` (association rows deleted without compaction); `auralis/library/repositories/playlist_ordering_mixin.py:146-161` (`reorder_track` assumes contiguity)
- **Status**: NEW (adjacent to open frontend issue #5189)
- **Description**:
  1. `POST /api/playlists/{id}/track` is documented as the drag-and-drop "positional insert" (`routers/playlists.py:440-455`). With an explicit `position`, `add_track` deletes the row if it already exists and then inserts at `position`. It never shifts the rows at or after `position`, and never closes the gap left by the delete. `track_playlist` has no unique constraint on `(playlist_id, position)`, so two rows share a position and `ORDER BY position` ties resolve by storage order, which is undefined.
  2. `TrackRepository.delete()` removes `track_playlist` rows but does not decrement later positions (`remove_track` does, via the #3725 compaction). After any library track is deleted, the playlists that contained it have a gap.
  3. `reorder_track` looks rows up by `position == from_index` and checks `to_index < COUNT(*)`. After (1) or (2) this returns "Invalid from_index" or reorders the wrong row.
- **Evidence**: Playlist `[A0, B1, C2]`, drag C to index 0: delete C -> `[A0, B1]`; insert C at 0 -> `[A0, C0, B1]`. The tie between A and C is resolved by rowid, so the playlist reads `A, C, B` instead of `C, A, B`. For an insert of X at 1: `[A0, B1, X1, C2]`, which reads `A, B, X, C` instead of `A, X, B, C`. After deleting B from the library: `[A0, C2]`; `reorder_track(from_index=1)` finds no row at position 1 and returns False.
- **Impact**: Playlists silently reorder wrongly after drag-and-drop inserts or moves, and become un-reorderable after tracks are removed from the library. Order is user data.
- **Suggested Fix**: In `add_track`'s explicit-position branch, shift `position >= :pos` up by one inside the same transaction (and compact after the delete in the move case). Compact `track_playlist` positions for affected playlists in the shared track-delete helper from ENG-D7-01.

---

### ENG-D7-04: Scanner change detection compares file mtime to `Track.updated_at`, which every play, favorite and fingerprint-status write bumps
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/batch_processor.py:118-130`; bumpers: `auralis/library/repositories/track_repository_maintenance.py:48-61` (`record_play`), `:63-86` (`set_favorite`), `auralis/library/repositories/fingerprint_stats_repository.py:46-53` (`update_status`); `auralis/library/models/base.py:68-69` (`TimestampMixin.updated_at` has `onupdate`)
- **Status**: NEW
- **Description**: A rescan decides whether a file changed with `existing_track.updated_at >= file_mtime`, treating `updated_at` as "last time this row was synced from the file". But `updated_at` is the generic row-mutation clock: SQLAlchemy applies `onupdate` to Core/ORM updates, including `record_play()`, `set_favorite()` and `update_status()`. Two consequences follow:
  - Missed edits: edit a file's tags externally after the last scan, then play it before the next scan. `record_play` sets `updated_at` to now, which is later than the file mtime, so the file is "unmodified" and the retag, re-rip or replacement is never ingested.
  - Re-processing loop: a file whose mtime is newer than `updated_at` but whose extracted fields are identical to the DB (artwork or ReplayGain-only rewrite, a copy with a future mtime) produces no net ORM change in `update_by_filepath`, so SQLAlchemy emits no UPDATE and `updated_at` is never advanced. Every later scan re-reads, re-analyses and re-"updates" that file.
- **Evidence**: `if updated_at and updated_at >= file_mtime: return 'skipped'`, with `updated_at` coming from the tracks row that `record_play` just touched (`values(play_count=..., last_played=func.now())` triggers `updated_at`'s `onupdate`).
- **Impact**: Library metadata drifts from files for exactly the tracks the user actually plays. Cases where file content changes without a metadata change in the library (a re-ripped or remastered file in place) keep stale duration, sample rate and sidecar state.
- **Suggested Fix**: Store a dedicated `file_mtime`/`scanned_at` watermark on the track (or compare `filesize` and mtime as the sidecar already does) and update it on every scan visit, instead of reusing `updated_at`.

---


## Low (30)

### ENG-D1-06: Psychoacoustic EQ overlap-add zeroes output sample 0 of every call, even with a flat EQ
- **Severity**: LOW
- **Dimension**: Sample Integrity (sample preservation)
- **Location**: `auralis/core/processing/eq_processor.py:206-243`
- **Status**: NEW
- **Description**: The WOLA synthesis window is a symmetric Hann, whose first sample is exactly 0.0. Output sample 0 is covered only by frame 0 at window position 0, so `window_norm[0] == 0` and `processed_audio[0] == 0`. The normalisation then divides `0` by `max(window_norm, eps)`, which is still `0`; the comment ("only the very first window sample ... has landed") acknowledges the coverage but the result is a zeroed sample rather than the input sample. The #4852 fix recovers samples 1..hop but not sample 0.
- **Evidence**: Probe `d1/t11.py`: constant 0.3 input, flat target -> output `[0.0, 0.3, 0.3, 0.3 ...]`, interior max deviation 9e-8. In `HybridProcessor` probes the first output sample of a 440 Hz-style signal is also ~0.
- **Impact**: One sample at the very start of each EQ call. In the chunked path chunks N>0 start inside the preceding context and the sample is trimmed away, so it is only audible as a 1-sample step at sample 0 of chunk 0 of a track that starts abruptly with a non-zero level (and at the start of every offline job render). Inaudible for most material.
- **Suggested Fix**: Where `window_norm` is below a small threshold, take the un-EQ'd input sample (or use a periodic Hann / offset the first window) instead of dividing zero by eps.

---

### ENG-D2-08: Generated DSP parameters and config fields that nothing reads (dead config), including a compression stage that ignores its own threshold/attack/release
- **Severity**: LOW
- **Dimension**: DSP Pipeline (config reachability)
- **Location**: `auralis/core/processing/parameter_generator_dynamics.py:67-226`, `parameter_generator_eq.py:97-102`, `continuous_stages.py:118`, `base/compression_expansion.py:94-123`, `auralis/core/config/settings.py:16-70`, `unified_config.py` (`limiter`)
- **Status**: NEW (siblings of #5112 and the closed #5302/#4613)
- **Description**: In the live ContinuousMode chain these are produced and never consumed: `ProcessingParameters.dynamics_blend`, `.limiter_params`, `.peak_target_db` (readers are only the backend reporting router); `compression_params['threshold'|'attack'|'release']` (`apply_clip_blend_compression` reads only `ratio` and `amount`, and uses an absolute soft-clip threshold `0.8-(ratio-1)*0.1`, so it is level-dependent and does nothing below ~0.72 peak: crest unchanged at peaks 0.5/0.7, -0.5 dB at 0.95); `eq_curve['*_freq']` (band edges are hardcoded at 250/500/2000/4000 Hz in `EQProcessor._eq_curve_to_array`); `_stage_input_gain` (`hasattr(params,'input_gain')` is always False); `content_profile` adjustments in `EQProcessor._apply_content_adjustments` / `curves.apply_content_adaptation` (the profile only contains `{'fingerprint': ...}`, so genre/centroid/dynamic_range keys never match). Config: `UnifiedConfig.limiter` (`LimiterConfig`, 8 fields; the limiter is built with hardcoded -0.3 dB/2 ms/50 ms), `AdaptiveConfig.chunk_size_ms`, `latency_budget_ms`, `enable_genre_detection`, `enable_user_learning`, `learning_rate` (validated/factory-set, never read).
- **Evidence**: grep of `dynamics_blend|limiter_params|peak_target_db` outside `parameter_generator*`/`fixed_target_params` finds no DSP reader; probe of `apply_clip_blend_compression` at peaks 0.5/0.7/0.95: max abs diff 0.0000/0.0000/0.0551.
- **Impact**: Tuning these (or the router that displays `limiter`/`peak_target_db`) has no effect on audio; the compression stage's behaviour depends on file level rather than the dynamics coordinate.
- **Suggested Fix**: Delete the unread fields (as #5302 did) or wire them; make compression level-relative (threshold from the generated dB value, applied after loudness alignment).

### ENG-D2-09: Step 3 "HF-aware safety limiter" in the live normalization path is unreachable
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_dsp_ops.py:233-251`; trigger in `auralis/core/processing/hf_aware_limiter.py:70-77`
- **Status**: NEW
- **Description**: Step 2 applies a whole-buffer gain so the peak is at most -0.3 dBFS (`SAFE_CEILING_DB = -0.3`), then Step 3 calls `apply_hf_aware_limiter`, which bypasses unless peak > `SAFETY_THRESHOLD_DB = -0.1`. After Step 2 the peak can never exceed -0.3, so Step 3 never fires and the "Phase 5 HF-preserving limiter" is dead in production. Peak control is by gain reduction of the entire chunk (loudness drops for peaky material).
- **Evidence**: Spy on `apply_hf_aware_limiter` across 4 normalization runs (target LUFS -14..-2, high-crest inputs): returned `limiter_applied=False` every time, input peak <= 0.966 (-0.3 dB).
- **Impact**: Misleading comments and dead code; peaky chunks lose loudness instead of being limited.
- **Suggested Fix**: Either remove Step 3 or make Step 2 a limiter (not a gain clamp) and run the HF-aware limiter on it.

### ENG-D2-10: Final loudness normalization has a hard 0.5 dB dead-band (categorical step)
- **Severity**: LOW
- **Dimension**: DSP Pipeline (parameter-space continuity)
- **Location**: `auralis/core/processing/continuous_dsp_ops.py:220-226`
- **Status**: NEW
- **Description**: `if abs(adjustment) > 0.5: audio = amplify(audio, adjustment)`: an adjustment of 0.49 dB applies nothing, 0.51 dB applies the full 0.51 dB, a 0.5 dB jump in output level for a 0.02 dB input difference. This is the one guard left that #4860 did not convert to `smooth_gate`.
- **Evidence**: code inspection; output gain function `g(adj) = adj if |adj|>0.5 else 0`.
- **Impact**: Near-target tracks land within +-0.5 dB of target in an unprincipled way; adjacent chunks straddling the threshold get 0.5 dB steps.
- **Suggested Fix**: Apply the full adjustment (or ramp it with `smooth_gate(|adj|, 0.0, 0.5)`).

### ENG-D2-11: `AdaptiveCompressor` gain smoothing has attack and release swapped (dormant path)
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/compressor.py:134-136` with `vectorized_envelope.py:77-82,162-170` (and `envelope.py:35-43`)
- **Status**: NEW
- **Description**: The envelope follower treats `input > envelope` as attack. The compressor feeds it gain reduction in dB (<= 0, more negative = more compression), so growing compression is `input < envelope` and takes the slow release coefficient, while recovery takes the fast attack coefficient.
- **Evidence**: threshold -20 dB, ratio 4, attack 10 ms, release 100 ms, step input: gain reduction reaches 63% in 99.5 ms (should be ~10 ms) and recovers to 37% in 10.0 ms (should be ~100 ms).
- **Impact**: Transients overshoot and gain snaps back (pumping). Currently dormant: its only consumer is `AutoMasterProcessor` (`enable_auto_mastering=False` in `config/startup/components.py:186`, and nothing in the backend calls `AudioPlayer.get_audio_chunk`), but it will be wrong the moment the player chain is enabled. (`AutoMasterProcessor` also computes `adaptive_params['compression_ratio']` and never reads it.)
- **Suggested Fix**: Follow the gain-reduction magnitude (`-gr`) in the follower, or swap the coefficient selection; add a step-response test.

### ENG-D2-13: Offline `sub_bass_control` switches a 25 Hz rumble high-pass on at a hard `sub_bass_pct >= 0.33` threshold
- **Severity**: LOW
- **Dimension**: DSP Pipeline (offline CLI subsystem, per #4873)
- **Location**: `auralis/core/stages/sub_bass_control.py:59-72`; `auralis/core/mastering_presets.py:220,226,230`
- **Status**: NEW
- **Description**: In an otherwise continuous path, a zero-phase 1st-order 25 Hz HP (about -6 dB at 25 Hz, -1 dB at 50 Hz) is on/off by an `if sub_bass_pct >= SUB_HP_ACTIVATE_PCT` test: two tracks at 0.329 and 0.331 get audibly different bass floors.
- **Evidence**: code inspection.
- **Impact**: Small (offline tool only), but it is the categorical-step pattern the continuous design forbids.
- **Suggested Fix**: Ramp the HP depth/cutoff with `ramp_to_s_curve(sub_bass_pct, 0.25, 0.45)`.

---

### ENG-D3-04: `load_file()` / `load_track_from_library()` swap the audio in one critical section and reset the position in a later one
- **Severity**: LOW (latent: only a `get_audio_chunk()` consumer observes it, and none exists in production)
- **Dimension**: Player State
- **Location**: `auralis/player/audio_file_manager.py:61-64`; `auralis/player/player_file_loading_mixin.py:61-71`, `:126-129`; `auralis/player/integration_manager.py:259-274`
- **Status**: NEW
- **Description**: `AudioFileManager.load_file()` takes `_audio_lock`, installs `audio_data`/`current_file`/`sample_rate`, and releases it. The caller then separately re-takes `_audio_lock` to call `playback.load_and_stop()`. The comment at `player_file_loading_mixin.py:62-66` claims re-taking the RLock "keeps swap+reset visible to readers as a single critical section", but the lock is not held across the two steps, so it does not. In `load_track_from_library` the gap additionally contains `set_current_track`, `record_play` (DB write) and `_auto_select_reference` (a second full-file decode plus a similarity query). For that whole window the playback state can still be PLAYING with the previous track's position against the new track's audio.
- **Evidence**: Call order in `PlayerFileLoadingMixin.load_track_from_library`: `integration.load_track_from_library` (-> `file_manager.load_file`, lock released at `audio_file_manager.py:64`) -> reference decode -> `with defer, _audio_lock: playback.load_and_stop()`. The regression test for the original issue (`tests/auralis/player/test_load_track_lock.py`) only asserts the lock depth is >0 when `load_and_stop` runs, which is true here; it does not model the swap being a separate acquisition.
- **Impact**: A concurrent `get_audio_chunk()` in that window reads the new track at a stale position (position may exceed the new track's length, which also trips the end-of-track test and can spawn a spurious auto-advance). `position <= duration` is violated transiently; `get_playback_info()` hides it by clamping. Not reachable in production today.
- **Siblings**: `load_file` and `load_track_from_library` in the same mixin.
- **Related**: #5105, #3667/#4219 (the lock-depth fix this complements).
- **Suggested Fix**: Pass an `on_loaded` hook (or return the decoded buffer) so the swap and `load_and_stop()` run under one `_audio_lock` acquisition, the way `advance_with_prebuffer(on_swap=...)` already does.

---

### ENG-D3-05: `rollback_index()` restores a saved index unconditionally and can leave `current_index` out of bounds
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/components/queue_manager.py:200-211`; caller `auralis/player/player_queue_navigation_mixin.py:153-196` (`previous_track`)
- **Status**: NEW
- **Description**: `previous_track()` saves the index, moves the queue back, then performs a blocking `load_file()` with no queue lock held. If the load fails it calls `rollback_index(saved_index)`, which writes the old integer back even if the queue was edited during the load. The backend's queue edits take `_set_queue_engine_lock`, not the navigation sequencer lock, so they can interleave.
- **Evidence**: `t4.py`: `set_queue([A,B], 1)`; `saved = snapshot_index()` (1); `previous_track()` (index 0); `remove_track(0)` (queue `[B]`); `rollback_index(1)` -> `len 1 current_index 1 current_track None`, `get_queue_info()['has_previous'] == True`.
- **Impact**: Queue left with `current_index == len(tracks)`: no current track, `peek_next` returns None, status reports a previous track that is the only track. Needs a failed load racing an edit, hence LOW.
- **Siblings**: None (only caller).
- **Related**: #3668/#3726 (locked rollback), which made the write locked but not conditional.
- **Suggested Fix**: Make rollback a compare-and-set (`rollback_index(saved, expected_current)` only writes if the index is still the one `previous_track` produced) or clamp to `len(tracks) - 1`.

---

### ENG-D3-06: Every queue edit invalidates the prebuffer but nothing re-arms it, so the next transition is never gapless
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:97`; `auralis/player/queue_controller.py:55-62,193-197` (and every `_notify_changed()` call); `auralis/player/gapless_playback_engine.py:82-118`
- **Status**: NEW
- **Description**: The #5508 fix registers `gapless.invalidate_prebuffer` as the queue change listener. It runs after every `add_track`, `insert_track`, `remove_track`, `set_repeat`, `shuffle`, etc., including edits that do not change the next track (appending to the end of the queue). It only clears the buffer; it does not call `start_prebuffering()`. The only re-arm points are `load_file`, `load_track_from_library` and the end of `advance_with_prebuffer`. Additionally `start_prebuffering()` returns early while an older worker thread is alive (line 107-109), and that worker later stores the buffer for the track it peeked before the edit, with no re-peek.
- **Evidence**: Sequence: track A playing with B prebuffered -> `add_track(C)` -> `_notify_changed()` -> `invalidate_prebuffer()` clears B -> A ends -> `advance_with_prebuffer` logs "Prebuffer not available, loading" and does a blocking decode (line 336-346) instead of a gapless swap.
- **Impact**: After any queue edit during playback the following transition takes the slow path (tens to hundreds of ms of blocking decode before the swap), losing the gapless guarantee that #5508 set out to protect. Only audible with an output consumer, hence LOW.
- **Siblings**: `queue.set_change_listener` is the single registration; all `QueueController` mutators share it.
- **Related**: Closed #5508.
- **Suggested Fix**: Make the listener `invalidate_prebuffer()` then `start_prebuffering()`, and have it skip invalidation when `peek_next_track()` still matches `next_track_info`.

---

### ENG-D3-07: Playback never leaves PLAYING at the end of the last track
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/player_streaming_mixin.py:96-120` (`get_audio_chunk` end-of-track branch)
- **Status**: NEW
- **Description**: When `end_of_track` is true the mixin only acts if `auto_advance and queue.has_next_track()`. With no next track (and repeat off) nothing stops playback, emits an event, or resets the position. The state machine stays PLAYING with `position == total_samples` and returns silence indefinitely.
- **Evidence**: `t5.py`: single-track queue, `play()`, ten `get_audio_chunk(1024)` calls on a 4410-sample file -> `state PlaybackState.PLAYING pos 4410 total 4410`.
- **Impact**: A consumer polling `state`/`is_playing` never learns the queue finished; "playing" persists at EOF. Latent today (no `get_audio_chunk` consumer; the backend streams separately), so LOW.
- **Siblings**: None.
- **Related**: #5114 (position clamp at EOF).
- **Suggested Fix**: In the `end_of_track` branch, when no advance is possible, call `playback.stop()` (outside the `_audio_lock` section) and notify an `ended` callback.

---

### ENG-D3-08: Auto-selected reference is decoded on every library load but never reaches the real-time level matcher
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/integration_manager.py:287-324` (`_auto_select_reference`), `:259-274`; contrast `auralis/player/player_file_loading_mixin.py:97-101` (`load_reference`)
- **Status**: NEW
- **Description**: `IntegrationManager._auto_select_reference` calls `file_manager.load_reference()` (full decode, stores `reference_data`) and broadcasts `reference_loaded`, but never calls `processor.set_reference_audio()`. Only the explicit `AudioPlayer.load_reference()` path does. `RealtimeLevelMatcher.enabled` is only set to True by `set_reference_audio`, so the level-matching stage stays inert for auto-selected references, and `file_manager.reference_data` has no other consumer (grep: only the property accessors).
- **Evidence**: `auto_reference_selection = True` by default (`integration_manager.py:85`), `POST /api/player/load` -> `AudioPlayer.load_track_from_library` -> `integration.load_track_from_library` -> `_auto_select_reference` (`:274`). `grep set_reference_audio` over `auralis/player/`: only `player_file_loading_mixin.py:313` and `realtime/`.
- **Impact**: Each library load pays a `find_similar` query plus a second full-file decode into RAM for nothing, and the real-time processor lifecycle is out of step with the loaded reference. Also lengthens the ENG-D3-04 window. No audible effect today.
- **Siblings**: `_auto_select_reference` has two decode sites (`:294`, `:312`).
- **Related**: #5098 (wire up level matching in the offline pipeline).
- **Suggested Fix**: Either route the result through `processor.set_reference_audio()` or set `auto_reference_selection = False` by default and drop the unused decode.

---

### ENG-D3-09: Real-time `AutoMasterProcessor` still defines the retired `warm` / `bright` / `punchy` profile table
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/realtime/auto_master.py:37,43-48,253`
- **Status**: NEW
- **Description**: The 2026-09-13 directive (`c195ac80`, `ae9d28e3`) removed `gentle`/`warm`/`bright`/`punchy`/`live` from engine tables. `AutoMasterProcessor.profiles` still carries `balanced`, `warm`, `bright`, `punchy`, advertised through `get_stats()['available_profiles']` and accepted by `set_auto_master_profile()`. This is a separate fallback-gain taxonomy from the enhancement presets and its only entry points (`AudioPlayer.set_auto_master_profile`, `RealtimeProcessor.set_auto_master_profile`) have no production caller, but it is an engine table defining removed names. Tests pin the four-profile list (`tests/auralis/player/test_realtime_processor.py:338,393,476`).
- **Evidence**: `auto_master.py:45-48` dict literal; `grep set_auto_master_profile` over `auralis/` and `auralis-web/backend/`: definitions only.
- **Impact**: Reintroduces the vocabulary the user deleted and gives a future UI/API a way to surface it. No runtime effect today.
- **Siblings**: Tests above would need updating.
- **Related**: Preset-narrowing directive (Retired Architecture table); needs a user decision whether the realtime profiles are in or out of that scope.
- **Suggested Fix**: Collapse to the neutral `balanced` entry (or delete the profile feature with its dead entry points) and update the four test assertions.

---
- **Also reported as**: ENG-D2-12 (merged; same defect found by another dimension)

### ENG-D3-10: `QueueController.shuffle()` / `unshuffle()` do not maintain `shuffle_enabled`, so `get_queue_info()` misreports the state
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/queue_controller.py:391-401` vs `:308-338`; `auralis/player/components/queue_manager.py:454`
- **Status**: NEW
- **Description**: `set_shuffle(enabled)` sets `shuffle_enabled` and reorders. `shuffle()`/`unshuffle()` reorder only. The backend (`QueueService.shuffle_queue`/`unshuffle_queue`) calls the latter, so the engine's `get_queue_info()['shuffle_enabled']` stays `False` after a REST shuffle and `True` after an `unshuffle()` that follows `set_shuffle(True)`.
- **Evidence**: `queue_manager.get_queue_info` reports `self.shuffle_enabled` (line 454); only `QueueController.set_shuffle` writes it (grep).
- **Impact**: Engine-reported shuffle flag disagrees with the actual order; consumers of the engine queue info (the player state manager mirrors its own flag, so no user-visible effect found today).
- **Siblings**: `repeat_enabled` is only set by `set_repeat`; the REST repeat endpoint updates only `PlayerStateManager`, never the engine (`player_queue.py:130-145`), so engine `peek_next`/`next_track` never wrap even when the UI shows repeat all.
- **Related**: ENG-D3-02.
- **Suggested Fix**: Have `shuffle()` set the flag True and a successful `unshuffle()` set it False, under the queue lock.

---

### ENG-D3-11: `pause()` records `_pause_requested` after the transition (reverse of `stop()`), leaving a stale flag if a `play()` interleaves
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:169-178` (`pause`), `:151-167` (`play`), consumed at `player_queue_navigation_mixin.py:148-149,191-192`
- **Status**: NEW
- **Description**: `stop()` sets `_stop_requested` first and transitions second, and `play()` clears the flag after its transition (#3669), which is race-safe. `pause()` does the opposite: `playback.pause()` first, then `_pause_requested.set()`. If a concurrent `play()` runs between the two lines it clears the flag and the later `set()` re-arms it while the state is PLAYING. The next `next_track()`/`previous_track()` with `was_playing` then executes `elif self._pause_requested.is_set(): self.playback.pause()` and pauses the player at the track boundary though the user last pressed play.
- **Evidence**: Interleaving: T1 `playback.pause()` -> True; T2 `playback.play()` -> True, `_pause_requested.clear()`; T1 `_pause_requested.set()`. Final: PLAYING with the flag set.
- **Impact**: Spurious pause on the next track change. The REST layer serializes transport commands with `_playback_lock`, so this needs direct (non-REST) concurrent callers; LOW.
- **Siblings**: None.
- **Related**: #5240 (introduced the flag).
- **Suggested Fix**: Mirror `stop()`: set `_pause_requested` before `playback.pause()` and clear it again if `pause()` returned False.

---

### ENG-D4-05: `loader.load()` (the player's loader) skips the validation `load_audio()` applies: severely truncated WAV, NaN/Inf and zero-frame files are accepted silently
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loader.py:147-243` vs `auralis/io/unified_loader.py:73-131` and `auralis/io/loaders/soundfile_loader.py:48-87`
- **Status**: NEW
- **Description**: `load()` is a second implementation of the load path. It calls `sf.read` directly. It never runs the RIFF-size truncation check, `validate_audio()` (empty-audio check, NaN/Inf sanitising), or the empty-file check. Its only truncation test, `len(audio) < file_info.frames`, cannot catch WAV, because libsndfile adjusts `frames` to the data actually present (the reason `soundfile_loader` inspects the RIFF header).
- **Evidence**: Same files through both loaders:
  - A WAV cut to 5.8% of its declared size: `load_audio` raises `ERROR_TRUNCATED_FILE`; `load` returns `(8316, 2)` with no log.
  - A float WAV containing NaN and Inf: `load_audio` returns finite audio; `load` returns audio with `isnan(...).any() == True`.
  - A zero-frame WAV: `load_audio` raises `ERROR_EMPTY_AUDIO`; `load` returns `(0, 2)`.
  - Error types also differ (`RuntimeError` vs `ModuleError`).
- **Impact**: The player (`AudioFileManager.load_file`, `GaplessPlaybackEngine`) plays a truncated file as a short clip with no diagnostic. NaN is partly mitigated by the realtime output guard added in #5313. Low frequency, bounded impact.
- **Suggested Fix**: Have `load()` delegate to the shared `load_with_soundfile` / `load_with_ffmpeg` plus `validate_audio` (it already shares the budget helpers) instead of keeping its own `sf.read` branch. This is the project's "improve existing code rather than duplicate logic" rule.

### ENG-D4-06: `ffprobe -v quiet` discards every diagnostic, so probe failures read "FFprobe failed: (no output)"
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:79-88` (`ffprobe_command`), consumers `ffmpeg_loader.py:287-289` (`warning(f"ffprobe failed: {result.stderr}")`) and `auralis/io/unified_loader.py:272-280`
- **Status**: NEW
- **Description**: `ffprobe_command` hard-codes `-v quiet`, so a non-zero exit has an empty stderr. `get_audio_info` then reports `FFprobe failed: (no output)`. `_probe_audio` logs `ffprobe failed: ` with nothing after it, and `load_with_ffmpeg` raises a generic "Could not probe sample rate / channel count".
- **Evidence**: `get_audio_info()` on `garbage.mp3`, `garbage.m4a`, `garbage.opus`, `tiny.mp3`, `trunc.m4a` and a directory named `dir.mp3` all returned `error: 'Module error: FFprobe failed: (no output)'`. The directory case is indistinguishable from a decode failure.
- **Impact**: Diagnostics only: support and users cannot tell a missing moov atom from a bad header. This is the probe-side sibling of the redaction work in #4806, which assumed there would be a last stderr line to keep.
- **Suggested Fix**: Use `-v error` in `ffprobe_command`. `redact_subprocess_output` already reduces it to one line and strips the path.

### ENG-D4-07: `validate_audio()` allocates a full-size temporary for its peak check, doubling peak memory on large decodes
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/processing.py:56` (`np.max(np.abs(audio_data))`) and `:62` (`np.abs(audio_data) >= 0.99`)
- **Status**: NEW
- **Description**: `np.abs` materialises a second full-size float32 array for the peak, and again for the clipping count whenever the peak is at least 0.99, which is typical of loud masters. The decode budget (`MAX_DECODED_BYTES`, 6 GiB) is sized for the decoded buffer alone; the comment in `unified_loader.py:120-124` acknowledges later copies but not this one.
- **Evidence**: 1800 s, 44.1 kHz, stereo float32 WAV (606 MiB array): max RSS 194 MiB at start, 800 MiB after `load_with_soundfile`, 1406 MiB after `validate_audio`, a +606 MiB step equal to the array size.
- **Impact**: A decode near the cap (about 5 GiB) peaks at about 10 GiB or more. On 16 GB desktops that risks an OOM for 2 h hi-res material. Normal-length tracks are unaffected.
- **Suggested Fix**: Compute the peak as `max(float(audio.max()), -float(audio.min()))`, and count clipped samples in blocks.

---

### ENG-D5-02: Staged render file is created by `mkstemp` (mode 0600), so every published master ends up owner-only
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:91-112`
- **Status**: NEW. Introduced as a side effect of #5109 (`0f8ea21d`); no open issue covers it.
- **Description**: #5109 stages the render into a `tempfile.mkstemp(...)` file and then `os.replace()`s it onto the final path. `mkstemp` creates the file with mode 0600. `sf.SoundFile(mode='w')` reopens the existing inode, which keeps its mode. `os.replace` preserves the inode, so the published master is 0600 instead of the umask-derived 0644 the old direct write produced. There is no `chmod`/umask handling in the function. The code comment says this is the "same shape" as `core/encoding/atomic_io.py`, which has the same gap, but that helper only writes backend-private cache files. The helper also does an `fsync` before the rename; the chunk loop does not, so a power loss right after the rename can expose an empty or short file under the final name.
- **Evidence**: `tmp_fd, tmp_name = tempfile.mkstemp(dir=..., prefix=..., suffix=...)` -> `os.close(tmp_fd)` -> render into `tmp_path` -> `os.replace(tmp_path, final_path)`. A grep for `chmod|umask|st_mode` in this file and in `tests/auralis/core/test_mastering_atomic_output_5109.py` finds nothing.
- **Impact**: Masters written into a shared or served folder (NAS or media-server library, files owned by a different user than the player) become unreadable to other users and services. The cause is not obvious to the user.
- **Suggested Fix**: After the render and before `os.replace`, apply `os.chmod(tmp_path, 0o666 & ~current_umask)`, or copy the mode from the replaced file when one exists. Add `os.fsync` to match the backend helper. Add a permission assertion to the #5109 test.

### ENG-D5-03: Stage-info aggregation does not de-duplicate per-chunk stages and its docstring still describes the pre-fix behaviour
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:42-49`, `:224-233`
- **Status**: Existing: #5512 (open). The fix in `e5e2cd05` landed, but the polish is still missing.
- **Description**: The `process_chunks` docstring still says "info is only updated once, from chunk 0", which is the bug that was fixed. The `stage not in info['stages']` check compares whole dicts. `peak_reduction` (`mastering_process_chunk.py:115`) carries per-chunk `target`/`result` floats, so it appends one entry per triggering chunk.
- **Evidence**: Re-read in this audit; both the docstring and the equality dedup are still as described.
- **Impact**: Diagnostics only.
- **Suggested Fix**: As in #5512: fix the docstring, and dedup on `stage['stage']` or collapse the per-chunk fields.

### ENG-D5-04: A very short final chunk crashes `sosfiltfilt` (padlen)
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:157-158` (last chunk read with no left context). Crash sites: `auralis/core/dsp/resonance_notcher.py:214`, `transient_shaper.py:102`, `harmonic_exciter.py:135,147`, `parallel_eq.py`, `stages/sub_bass_control.py:72`.
- **Status**: Existing: #5116 (open). The scope extension was already recorded in the 2026-09-13 audit (ENG-D5-01 there). Re-verified: the raw `sosfiltfilt` calls are still unguarded, and the loop still reads the last chunk with exactly `total_frames - read_pos` samples.
- **Description**: When `total_frames % chunk_size` is smaller than scipy's padlen (about 9-15 samples), the last chunk is processed alone and `sosfiltfilt` raises. Those samples already sit in the previous chunk's overlap tail, so the extra chunk is redundant.
- **Evidence**: The comment on #5116 and the 09-13 reproduction. Thanks to #5109 no partial output is published.
- **Impact**: The whole file fails for roughly 1 in 10^5 lengths.
- **Suggested Fix**: Fold a final remainder shorter than the crossfade (or than a safe minimum) into the previous chunk, or route all sites through `sosfiltfilt_safe`.

### ENG-D5-05: True-Peak guard applies one gain to a whole 33 s chunk and swallows every failure
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:204-212`
- **Status**: Existing: #4970 (open)
- **Description**: `processed_chunk * (_TP_CEILING / _tp)` scales the entire chunk (core plus overlap) by a single factor derived from its one highest 4x-oversampled peak, and it is computed from the cold-start head and the end-edge tail as well. `except Exception: pass` hides any failure.
- **Evidence**: Re-read; unchanged.
- **Impact**: Level steps between chunks, spread over the 3 s crossfade, and silent loss of the guard.
- **Suggested Fix**: As in #4970. A file-level or limiter-based approach would also address ENG-D1-04.

### ENG-D5-06: Seam safety rests on an unchecked crossfade-versus-stage-settle-time relationship
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_config.py:61-65` (`CHUNK_DURATION_SEC`, `CROSSFADE_DURATION_SEC`); stateless per-chunk stages in `mastering_process_chunk.py:70-161`
- **Status**: Existing: #5339 (open)
- **Description**: No state is carried between chunks. Every `_process` call starts the transient-shaper envelopes, the limiter (`create_brick_wall_limiter`, a fresh one per chunk, `loudness_maximizer.py:80`) and the filters cold. Continuity relies on the 3 s equal-gain crossfade (`sin^2`/`cos^2`) hiding that settling. The relationship is not asserted anywhere, and `CROSSFADE_DURATION_SEC` is freely configurable.
- **Evidence**: I traced the crossfade arithmetic: `head_len = min(prev_tail, chunk)` and `write_region == core_samples`. The seam is sample-exact and continuous at both ends (chunk 1 weight 1 at the first overlap sample, chunk 2 weight 1 at the last). Only the settle-time assumption is unchecked.
- **Impact**: Latent. It only matters if the config values are changed, or if a stage with a longer settle time is added.
- **Suggested Fix**: As in #5339: validate `CROSSFADE_DURATION_SEC` against the longest stage settle time, and add a whole-versus-chunked equivalence test.

### ENG-D5-07: Rust `process_chunks` is dead code, and its unchecked `chunk_size - overlap` is a latent defect
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs:747-809`, `vendor/auralis-dsp/src/chunk_processor.rs:47-60`
- **Status**: Existing: #5537 (open). The siblings below are additions for that issue, not a new issue.
- **Description**: The Rust function is dead, as #5537 says. It has zero production callers, an identity `process_fn`, an `f64`-only input (the engine works in `f32`), a hard-coded 2205-sample linear crossfade (the Python loop uses an equal-gain `sin^2`), and a docstring that promises a `'peaks'` key that does not exist. Beyond what #5537 lists, there is no validation of `overlap` against `chunk_size`. `let hop_size = chunk_size - overlap;` is `usize` arithmetic. The wrapper accepts any value from Python. `Cargo.toml` has no `[profile]` section, so release builds default to overflow-checks off.
  - `overlap > chunk_size`: this should wrap to a huge hop, `num_chunks` becomes 0 or 1, and the function should return an all-zero output of the right shape with no error.
  - `overlap == chunk_size`: `hop_size` is 0, division by zero, a panic that is caught and returned as `RuntimeError`.
  I did not run this (no shell); the wrap behaviour is inferred from code and the default release profile.
- **Impact**: None on the shipped path today. It would matter only if the binding were wired in. Deleting it, as #5537 suggests, removes all of this.
- **Suggested Fix**: Delete the binding, or add `overlap < chunk_size` validation and a float32 path before wiring it in.

---

### ENG-D6-04: `FingerprintQuantizer` bounds for `bass_mid_ratio` and `transient_density` disagree with the live schema (sibling of #5509's band-scale bug; dead write path)
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/library/fingerprint_quantizer.py:60,65` (vs `auralis/analysis/fingerprint/schema.py:65,73` and `rust_fingerprint.py:96-102`)
- **Status**: NEW (sibling of Existing #5509 / #5538). The band bounds themselves were fixed 0-100 -> 0-1 by `e5e2cd05` and now AGREE with the Rust output, which emits 0-1 fractions (sum ~1.0, see ENG-D6-02 output).
- **Description**: Two other dimensions are still on the wrong scale. `bass_mid_ratio` is a signed dB value (`10*log10(f/(1-f))`, clamped +/-60, schema range -10..20) but the quantizer bounds are `(0.0, 100.0)` "Ratio 0-100", so every mid-heavy track (negative dB, the common case) clamps to 0. `transient_density` is 0-1 everywhere but is bounded `(0.0, 100.0)` ("per second"), leaving about 3 usable levels for the whole range.
- **Evidence**: `quantize({'bass_mid_ratio': -6.0, 'transient_density': 0.6, ...})` then `dequantize` gives `bass_mid_ratio=0.0`, `transient_density=0.784` (true 0.6; step size 0.39).
- **Impact**: None today - only the dead `store_fingerprint()` path writes `fingerprint_blob` and nothing reads it (#5509). Becomes silent data loss the moment that path is wired up.
- **Suggested Fix**: Fold into #5509's resolution: delete the dead path (preferred) or set `bass_mid_ratio` to `(-60, 60)` and `transient_density` to `(0, 1)`, and derive bounds from `schema.DIMENSION_SCHEMA` instead of a second hand-maintained table.
- **Also reported as**: ENG-D7-06 (merged; same defect found by another dimension)

### ENG-D6-05: `LoudnessMeter` K-weighting is not the BS.1770-4 filter (Butterworth HPF instead of the RLB filter), so LUFS is off by 0.1-1 dB, most on bass-heavy material
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/loudness_meter.py:67-81` (HPF `signal.butter(2, 38.13475657, 'high')`), shelf at `:83-100`
- **Status**: NEW
- **Description**: The code claims BS.1770-4 compliance, but the RLB high-pass is realised as a 2nd-order *Butterworth* (Q=0.707). The standard's filter has Q~0.5003 (double pole near 38 Hz, 48 kHz coefficients `a=[1,-1.99004745,0.99007225]`, `b=[1,-2,1]`). The Butterworth rolls off differently below ~150 Hz, so low-frequency content is measured louder than the standard. The shelf is an RBJ approximation (-0.245 dB at 997 Hz).
- **Evidence**: 48 kHz stereo, steady signals, comparing `LoudnessMeter` (400 ms chunks, then `finalize_measurement`) with the published 48 kHz BS.1770 coefficient pair applied via `scipy.signal.lfilter`:
  ```
  signal      reference   LoudnessMeter
  997 Hz      -20.000     -20.245
  100 Hz      -21.825     -20.782   (+1.04 dB)
  8 kHz       -16.652     -16.697
  pink noise  -18.309     -18.214
  ```
- **Impact**: Integrated LUFS from `quality_metrics`, `loudness_assessment` (standards-compliance scoring), and `mastering_prepare` source-loudness measurement is biased by ~0.1-0.3 dB on typical program and up to ~1 dB on bass-dominant tracks. Within 1 LU, so low severity.
- **Suggested Fix**: Use the standard's biquad coefficients (derive for arbitrary fs from the analog prototype, as pyloudnorm / ffmpeg ebur128 do) for both stages; add a test against the 48 kHz reference coefficients.

---

### ENG-D7-07: `FileDiscovery.should_skip_path` rejects every file when the scan root sits under any hidden directory
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/file_discovery.py:199-207`
- **Status**: NEW
- **Description**: `should_skip_path` iterates `file_path.parts` and `file_path.parents` of the full absolute path. Any ancestor component beginning with `.` (for example `/home/u/.local/share/music`, `~/.var/app/...`, a relative `../music`, or `/media/u/.stash/`) makes every file under the scan root skipped. The recursive walk already filters hidden directory names relative to the root (`_walk_directory:154-157`), so the second check only adds this false positive. Likewise, `parent.name in SKIP_DIRECTORIES` matches ancestors above the root.
- **Evidence**: `for part in file_path.parts: if part.startswith('.') and len(part) > 1: return True`.
- **Impact**: A scan of such a root finds 0 files with only a debug-level trace; the user sees an empty scan with no explanation.
- **Suggested Fix**: Evaluate hidden/skip rules on the path relative to the scan root, not on the absolute path.

---

### ENG-D7-08: Album get-or-create in `TrackRepository.add()` mishandles artist-less tracks, and its race guard can never fire
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_lifecycle.py:93-110` (`_get_or_create_album`), `:146-151` (`add`); `auralis/library/models/album.py:35-38` (no unique constraint)
- **Status**: NEW (the update path was fixed in #5457; `add()` was not)
- **Description**:
  1. With no artist tag, `add()` passes `artist_id=None`. `_get_or_create_album` then looks up by title alone (`.first()` across all artists) and never creates when `artist_id is None`. A track tagged only with an album title is either dropped from any album, or attached to some other artist's album that happens to share the title ("Greatest Hits"). The update path (`_assign_album`) creates an ownerless album instead, so first-scan and rescan disagree.
  2. `_get_or_create_album` wraps the insert in a savepoint with an `except IntegrityError` fallback (#3365), but `albums` has no `UNIQUE(title, artist_id)` (the v018->v019 migration states this explicitly). The IntegrityError can never occur, so two concurrent scans (allowed when `max_concurrent_scans > 1`) adding tracks of the same new album create duplicate album rows.
- **Impact**: Mis-grouped or missing albums for untagged-artist files; duplicate album rows under concurrent scans.
- **Suggested Fix**: Route `add()` through the same `_assign_album` semantics as the update path; add a unique index on `(title COLLATE NOCASE, artist_id)` (with a migration that merges existing duplicates) or serialise album creation.

---

### ENG-D7-09: No orphan sweep for albums, artists and genres after tracks are deleted
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/album_repository.py`, `artist_repository.py`, `genre_repository.py` (no prune method); `track_repository_lifecycle.py:delete`, `track_repository_maintenance.py:cleanup_missing_files`
- **Status**: NEW (becomes visible once ENG-D7-01 is fixed)
- **Description**: Deleting tracks never removes the albums, artists or genres that lose their last track. `get_all()` for each of those repositories counts and lists every row, and `StatsRepository.get_library_stats()` counts them in `total_albums`/`total_artists`/`total_genres`. None of the three repositories has a prune/cleanup method.
- **Impact**: After a folder removal or prune, the Albums/Artists/Genres views show empty entries with `track_count = 0`, and library statistics overstate counts.
- **Suggested Fix**: Add a repository-level `prune_orphans()` and call it at the end of the shared track-delete helper (or filter zero-track rows in the list queries).

---

### ENG-D7-10: `MigrationManager.get_current_version()` maps any exception to version 0, which routes an existing database into `initialize_fresh_database()`
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/migration_manager.py:99-101`, `:176-193`
- **Status**: NEW
- **Description**: `except Exception: return 0` conflates "schema_version table missing" (genuinely fresh) with any read error. In `migrate_to_latest`, version 0 calls `initialize_fresh_database()`, which runs `create_all` (a no-op for existing tables) and stamps the database as the latest schema. In `check_and_migrate_database`, `auto_backup` is also skipped when `current_version == 0`. If the SELECT fails transiently while `create_all` and the version INSERT succeed, a database at an older schema is stamped current without applying any migration and without a backup.
- **Evidence**: `if auto_backup and current_version > 0:` guards the backup; `if current_version == 0: return self.initialize_fresh_database()`.
- **Impact**: Narrow trigger (a failing read that does not also fail the following writes, with the 60 s busy timeout making a lock error unlikely), but the result is a permanently mismatched schema with no restore point.
- **Suggested Fix**: Treat only "no such table schema_version" as fresh; re-raise other `OperationalError`s.

---

### ENG-D7-11: `QueueHistoryRepository.push_to_history()` returns an expired, detached entry once history exceeds the limit
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/queue_history_repository.py:88-96` and `:232-259`
- **Status**: NEW (the feature has no frontend caller, #5526)
- **Description**: `push_to_history` commits, refreshes the entry, then calls `_cleanup_old_history`, which commits again when `count > HISTORY_LIMIT`. With the default `expire_on_commit=True`, that second commit expires `history_entry`; the method then `expunge`s it and returns it. Its attributes can no longer be loaded. `routers/player_queue_history.py:70` calls `entry.to_dict()` on the return value.
- **Evidence**: For the 21st and every later push the cleanup commit runs, so `entry.to_dict()` raises `DetachedInstanceError` after the write has already succeeded.
- **Impact**: `POST` record-queue-history returns 500 on every call after 20 entries, even though the row was stored. Unreachable from the current UI.
- **Suggested Fix**: Serialise or refresh the entry after the cleanup commit (or run cleanup before the final commit), so the returned object is loaded.

---

# Relationships

- **Fingerprint chain**: ENG-D6-01 → ENG-D6-02/-03 → ENG-D2-03 → ENG-D2-05 (reference-cloud targets unreachable) → ENG-D7-02 (version never advances, so rows are re-fingerprinted on every play, repeating the bad data). Fix D6-01 first, because D2-03 and D6-02/-03 are measured on fingerprints it corrupts. After fixing it, existing persisted fingerprints need to be regenerated.
- **Loudness chain**: ENG-D2-01, ENG-D1-02, ENG-D2-10 and ENG-D2-09 are all in `_apply_final_normalization`. ENG-D1-04 is the same pattern in the offline CLI path, and ENG-D1-03 stacks on the live path after the limiter. One redesign (a track-level gain plus a bounded per-chunk correction) addresses all of them.
- **Queue shape chain**: ENG-D3-01 hides ENG-D3-03 (the `None == None` prebuffer match becomes live once next/previous works) and ENG-D3-06 (nothing re-arms the prebuffer after an edit). Fix D3-01 and D3-03 together.
- **Scanner/library chain**: ENG-D4-03 (undecodable files ingested), ENG-D4-04 (tags dropped), ENG-D7-04 (change detection) and ENG-D7-01 (prune fails) all sit on the scan → persist → prune path. D4-03 and D7-01 together mean bad rows get in and then cannot be removed.
- **Mono/multichannel**: ENG-D1-01 (crash on `(N,1)` and >2 channels in the live path) and ENG-D5-01 (the chunk loop truncates >2 channels) are the same blind spot in two paths; both should route through the existing `downmix_to_stereo`.

# Prioritized Fix Order

1. **ENG-D6-01** — one-line fix at two call sites (`np.ascontiguousarray(audio).ravel()` / `audio.reshape(-1)` for interleave), plus a regression test and regeneration of persisted fingerprints.
2. **ENG-D1-01** — mono playback crash; likely a small guard or a shared channel-normalisation helper.
3. **ENG-D2-03** — fraction/percentage unit mismatch in the target service.
4. **ENG-D2-02** — set `stereo_width_target` to the neutral value (0.5) and drop the peak gating.
5. **ENG-D7-01** — clear association rows (or add `ON DELETE CASCADE` via migration) and fix the tests that use artist-less tracks.
6. **ENG-D1-02 / ENG-D2-01** — add a gain cap and fix the silence floor, then rethink per-chunk normalisation (shared with ENG-D1-03, -04).
7. **ENG-D4-01** — decode ffmpeg stderr with `errors="replace"`.
8. **ENG-D3-01 / -02 / -03** — normalise queue entry shape at one boundary, use identity for shuffle, and compare ids only when non-None.
9. The rest of the MEDIUM findings, then LOW. Several LOW dead-config items (ENG-D2-08, -09) are good candidates for a single cleanup commit.

# Appendix: Checked and clean (per dimension)

### Dim 1: Sample Integrity
- **Sample count through `HybridProcessor.process`**: lengths 1023, 1024, 1025, 5000, 132317 and 6 s of audio all returned `len(out) == len(in)` (`d1/t12.py`, `d1/t1.py`); mono 1-D input returns `(N, 2)` by design with the same length. Existing sample-count asserts being `assert` (stripped under `-O`) is already tracked as #5533 / #5511.
- **Per-stage dtype in `ContinuousMode`**: instrumented all five stages in both fingerprint and fixed-target modes; float32 in, float32 out at every stage (`d1/t13.py`). `amplify`, `normalize`, `PeakNormalizer`, `soft_clip`, `BrickWallLimiter` (including `_release_envelope`), `hf_aware_limiter`, `ParallelEQUtilities`, `VectorizedEQProcessor` / `apply_eq_gains`, `adjust_stereo_width_multiband`, `ResonanceNotcher`, the transient shaper and harmonic exciter all cast back to the input dtype.
- **Copy-before-modify**: `ContinuousMode.process` copies first; `amplify`, `compression_expansion.py` strategies, `process_chunk`, `AutoMasterProcessor`, `RealtimeProcessor.process_chunk`, `AudioFileManager.get_audio_chunk` and `validate_audio_finite(repair=True)` all work on copies. The three in-place index assignments found by grep (`base_assessor.py:85`, `compression_expansion.py:78/185`) operate on freshly made copies. Bypass paths return copies (#5107 intact). Rust bindings take read-only arrays (no `PyReadwriteArray`/`as_slice_mut` in `vendor/auralis-dsp/src`).
- **Clipping prevention in `HybridProcessor`**: peaks of 3.5 in -> output peak 0.9661 (-0.3 dBFS) with finite float32 output (`d1/t12.py`); the limiter's per-sample gain is bounded by `threshold/peak` in both its attack and release branches. (The only post-limiter gain is ENG-D1-03.)
- **NaN/Inf**: `validate_audio_finite` is applied on input (fail-fast), after limiter (fail-fast), in `_apply_final_normalization` (repair), `RealtimeProcessor.process_chunk` (repair, #5313), `saver.save` (repair, #5507), the WAV encoder (rejects) and `AudioProcessingPipeline.apply_enhancement` (falls back to unprocessed audio). The short-buffer gap is #5191, the bare FFmpeg temp-WAV write is #5532.
- **Bit-depth output**: `saver.save` casts to float32, repairs non-finite values, clips to [-1, 1] and lets libsndfile quantise to PCM_16/24/32; `Result`/`pcm16`/`pcm24` only describe the target. No dither is a documented decision (#4981). The unused `PCM_32` label in `WAVEncoder.SUPPORTED_SUBTYPES` ("(float)") is cosmetic.
- **Loaders**: `load_with_soundfile`, `loader.load`, `load_with_ffmpeg` (now `pcm_f32le`, #5317), `validate_audio` (NaN sanitising), `downmix_to_stereo` (peak-bounded, dtype-preserving) and `resample_audio` (dtype-preserving) have no sample-integrity defects beyond what is listed.
- **WOLA / psychoacoustic EQ frame handling**: terminal-frame zero-padding, buffer extension by `chunk_size`, even-`fft_size` guard and Hermitian mirroring are correct; only the sample-0 issue (ENG-D1-06) remains.
- **Chunk reassembly in the offline CLI loop**: `write_region` length is asserted against `core_samples`, tail/head lengths are consistent (including the short-final-chunk case), output is clipped to [-1, 1] before PCM_24 write, and sample count was preserved end to end (`d1/t6.py`).
- **Incidental**: open issue #5416 ("np.hanning() back in production psychoacoustic EQ") appears already fixed - no `np.hanning` remains under `auralis/`, and `PsychoacousticEQ` / `EQProcessor` use `scipy.signal.windows.hann`. Worth closing after confirming.

### Dim 2: DSP Pipeline
- Processing chain order (input gain -> EQ -> dynamics -> stereo -> normalization -> limiter) is explicit in `continuous_stages.py:95-101` and consistent with comments; guard knees (`smooth_gate`, phase/tilt/EQ-drift) have correct signs.
- WOLA: fixed 50% hop, full-Hann synthesis window, normalized by accumulated window weight; interior reconstruction exact (tested in `tests/regression/test_eq_overlap_add.py`); sample 0 = 0 is a documented, accepted property. No configurable overlap introduced. Analysis window is applied once (no double windowing).
- EQ band mapping is by band centre frequency (`EQProcessor._eq_curve_to_array`), 25 bands matching `create_critical_bands()`; no index fallback. Hermitian mirroring correct for even `fft_size` (guarded in `EQSettings.__post_init__`).
- Sub-bass/parallel EQ stages use zero-phase filtering and add `band*(gain-1)` on the dry signal (no crossover notch); `ParallelEQUtilities` axis handling matches the transposed offline pipeline.
- `ProcessingSpaceMapper` axes route through `_smooth_unit` (tanh, NaN -> 0.5); coordinates bounded in (0,1); generator outputs (`target_lufs`, EQ via `tanh`, stereo target 0.05-0.95) are bounded and finite; expansion/target-LUFS monotone in dynamics (compression "amount" is an intentional bell).
- Unknown/legacy preset names degrade cleanly: `PreferenceVector.from_preset_name('Gentle') -> neutral`, `get_preset_profile('warm') -> None` (no raise); `preset_profiles`/`UnifiedConfig` carry `'adaptive'` only.
- Optimizer wrapper: `AdaptiveMode.process` wrapper (`profiler.time_function`) preserves return value/exceptions via `functools.wraps`+`try/finally`, guarded by an RLock; note it is NOT on the live path (ContinuousMode does not call `AdaptiveMode.process`), so the audit docs' "runs on every real mastering call" is overstated.
- Rust boundary: all 11 wrappers release the GIL (`py.detach`), convert panics to `RuntimeError`, validate inputs for `compute_fingerprint`; only `compute_fingerprint` is called from Python in production (apart from the ENG-D2-04 marshalling bug on the Python side).
- dtype/copy: `amplify`, `soft_clip`, `_apply_spectral_tilt_correction`, stereo helpers and the EQ keep the input dtype and never mutate the caller's array; sample counts preserved through EQ/limiter (verified for 1000/5000/88323-sample inputs).
- K-weighted `calculate_loudness_units` is a fresh meter per call (no cross-thread filter state).

### Dim 3: Player State
- State transitions atomic: `PlaybackController.play/pause/stop/seek/load_and_stop/set_error` all mutate under `_lock` and snapshot state for notification outside the lock; `defer_notifications` is thread-local and flushes after `_audio_lock` is released (verified at every `with defer, _audio_lock` site in `enhanced_audio_player.py`, `player_file_loading_mixin.py`, `player_queue_navigation_mixin.py`).
- Callback safety: `PlaybackController._dispatch_callbacks`, `IntegrationManager._notify_callbacks` and `GaplessPlaybackEngine._notify_prebuffer_callbacks` all snapshot under the lock and invoke outside it. The only nested lock chains found (`update_lock -> _audio_lock -> PlaybackController._lock`, `_position_lock -> _audio_lock`) have no reverse edge anywhere in `auralis/player/`.
- Position invariant during seek/steady state: `seek()` clamps to `[0, max_samples]` under `_audio_lock`; `read_and_advance_position` clamps the stored position (#5114); `_get_position_seconds` clamps to duration. (The only transient violation found is ENG-D3-04.)
- `stop()` vs `play()` race: all four interleavings of the `_stop_requested` set/clear and the state transition end in a consistent state (flag ordering is correct for stop, see ENG-D3-11 for the pause asymmetry).
- Gapless swap atomicity: `advance_with_prebuffer` performs all blocking I/O before any lock, commits the queue advance via `advance_if_next_matches`, and swaps `audio_data`/`sample_rate`/`current_file` plus the position reset under one `update_lock` + `_audio_lock` acquisition (#5105 fix still in place). The sample-rate mismatch guard falls back cleanly.
- Resource cleanup: `AudioPlayer.cleanup()` signals `_cleanup_in_progress`, bumps the fingerprint generation, joins the advance thread (read under `_audio_lock`), clears audio, joins the prebuffer worker (`_shutdown` checked inside `_thread_lock`, #4631) and resets effects. No leaked threads found. `stop()` intentionally keeps the decoded audio loaded.
- Mixin composition: every mixin touches `file_manager`/`playback`/`queue` through the same `_audio_lock` / `PlaybackController._lock` / `QueueManager._lock`; property getters/setters in `player_properties_mixin.py` are locked (#5329 still fixed). `AudioPlayer.position` getter reads `playback.position` raw, an int read that is atomic, not worth a finding.
- Queue bounds for remove/insert/reorder/move/clear/set_queue/load_playlist: index adjustments are correct and all run under `QueueManager._lock`; `set_queue`/`load_playlist` are atomic (#5355), `remove_if_index_matches_current` is atomic (#5360). The one bounds hole is the rollback in ENG-D3-05.
- Real-time processor: `RealtimeProcessor` snapshots `effects_enabled` then releases its lock before DSP; lock order `RealtimeProcessor.lock -> inner lock` is consistent across `set_effect_enabled`, `get_processing_info`, `reset_all_effects`; non-finite guard present (#5313); output is a copy with dtype preserved. There is no start/stop lifecycle tied to playback (state such as compressor envelope and gain-smoother is not reset on stop/seek/track change), but the chain is unreachable in production so no finding was filed.
- Fingerprint loader: generation check and processor write are under `_fingerprint_lock` on all three paths (#3719); `_schedule_fingerprint_load` is called from `load_file`, `load_track_from_library` and the gapless `next_track`.
- `previous_track` resume logic and the `_stop_requested` / `_pause_requested` re-check after `playback.play()` (#4126, #5240) behave as documented for the interleavings reachable under the backend's transport lock.
- ERROR state: `set_error()` is only entered from failed loads and is cleared by the next successful `load_and_stop()`; `play()` correctly refuses in ERROR. Not a finding.
- Not in scope / not filed: `NavigationService.jump_to_track` calls a non-existent `QueueController.set_current_index` (already recorded in AUDIT_CONCURRENCY_2026-09-13.md; the method has no router caller).

### Dim 4: Audio I/O
- Format coverage: round-tripped synthetic MP3, M4A (AAC and ALAC), raw AAC, OGG (Vorbis and FLAC-in-Ogg), OPUS, WMA, FLAC, WAV (u8, s16, s24, s32, f32, f64), AIFF (including big-endian s16), AU. Peak and RMS matched the source in every case, and the sample rate was taken from metadata each time, including 8 kHz, 22.05 kHz and 192 kHz. Only MP3-only e2e coverage in the test suite is already #5336.
- Channel handling: mono returns 1-D from `load_audio` and stereo-duplicated from `load`, by design. 3, 4, 6 and 8 channel WAV, 6 channel FLAC and 6 channel M4A all came back stereo. Layout-ambiguous counts (3, 4, 5, 7) are routed through FFmpeg (#5242 holds).
- Corrupt-file handling: garbage, header-only, empty and truncated inputs across wav, flac, mp3, m4a and opus all raise `ModuleError` with a specific code (or `RuntimeError` from `loader.load`), never a crash. A directory named `*.mp3` gives file-not-found. A truncated MP3 loads with the 90% warning.
- FFmpeg cancellation: `cancel_event` set 0.3 s into a 1 h MP3 decode raised `CancelledError` after 0.55 s, left no `ffmpeg` or `ffprobe` process (`pgrep -x` = 0) and no `auralis_*` temp file. Timeout kill is covered by `subprocess.run` and `_terminate_process` (SIGTERM, then SIGKILL).
- File path safety: `reject_protocol_path` is called before every ffmpeg/ffprobe argv. `-protocol_whitelist file` is pinned and `--` is used for ffprobe (#4834, #5326). Desktop spawns the backend with piped stdio, so ffmpeg's missing `-nostdin` is not reachable there.
- Large-file budgets: the duration cap plus the `oversize_decode_detail` byte cap are applied pre-decode on every path (soundfile, ffmpeg, `load`, probes). Only the >4 GiB container limit (ENG-D4-02) and the temporary in ENG-D4-07 were found.
- `results.py` / `saver.py`: format and subtype validation, output-directory check, NaN repair (#5507) and clip to [-1, 1] are all in place; the no-dither choice is documented (#4981). `Result` has no scaling logic of its own.
- `resample_audio` preserves dtype and sample ordering. `resampy` is installed and pinned, so the linear-interpolation fallback is not live.
- Metadata extraction robustness: malformed or mixed-format key lookups are caught per key (the Vorbis `ValueError` case), and MP3, FLAC, OGG and OPUS tags parse correctly (title, artist, album, albumartist, year, genre, track, disc).

### Dim 5: Chunked Mastering
- **Chunk independence / copies**: `process_chunk` starts with `audio.copy()`, and `ContinuousMasteringBranch.apply` copies again. `new_tail` is `.copy()`, so a view into `processed_chunk` is never carried. The input buffer is never mutated.
- **Reassembly**: sequential, in index order. `write_region.shape[1] == core_samples` is enforced for non-first chunks (RuntimeError, #2515). The per-chunk sample-count invariant is a real `raise` (#5511 fix in `e5e2cd05`). The post-loop `chunks_processed != total_chunks` check catches short renders.
- **Last chunk**: not zero-padded and not dropped. `head_len = min(prev_tail, chunk)` handles a final chunk shorter than the overlap, and `overlap_after` is clamped to the remaining samples. Only the padlen crash (ENG-D5-04) applies.
- **Partial failure**: any raise propagates out of `_render_to_sink`, and `process_chunks` unlinks the staged `.part` file (`BaseException`). `prev_tail` is committed only after `write` succeeds. No half-written master is published (#5109). A poisoned carried context is moot because the whole render aborts.
- **Carried context**: only `prev_tail` is carried and it evolves correctly. Notches (`_notches`), `_source_lufs`, `_source_crest_db` and `_song_peak_db` are computed once per file in `prepare_file`, reset at its start, and set under `_process_lock` (#3715), so no per-chunk reset exists. The remaining state loss (limiter and envelopes) is ENG-D5-06.
- **Analysis scope**: the effective intensity and makeup gain come from the whole-track fingerprint. The headroom clamp uses the whole-song peak from the pre-scan (the per-chunk Stage-1 `peak_db` is intentional and documented). Notches come from one middle 30 s window, applied uniformly. The loudness maximizer push is constant across chunks. The one per-chunk gain re-derivation is the final peak `normalize`, which is ENG-D1-04.
- **Crossfade**: the equal-gain `sin^2`/`cos^2` blend is correct for correlated overlap (#4966). It is computed in the chunk dtype (#3684), the zero-length overlap guard is in place (#2157), and the output is clamped to [-1, 1] before the PCM_24 encode (#3660).
- **Mono and channel layout**: a 1-D read is expanded to 2 channels and the sink is always 2 channels (#4494). The transpose is unconditional (#2292).
- **Rust boundary**: the channel-axis guard (1-2 channels, `(channels, samples)`) is present (#4502), and the GIL is released with `py.detach` plus `catch_unwind`. Both are moot because the function is dead (ENG-D5-07).
- **Notch context**: `contextualize_notches` is continuous (tanh), bounded, and uses config constants. No NaN path was found that is not caught by `_assert_finite`.

### Dim 6: Analysis
- **Fingerprint determinism**: pure Rust/NumPy/librosa with no RNG; `windowed_compute` has a single windowing implementation shared by the library-scan, on-demand and pre-loaded-audio branches (#4595/#4994 still in place, `_crop_and_resample` shared). Residual divergence only in the two backend producers (Existing #5531 plus ENG-D6-01).
- **Resource bounds**: `compute_windowed_fingerprint` bounds work to a 90 s body + 2x30 s probes at 22.05 kHz on all three branches, incl. the FFmpeg branch (#5110 bounded decode with pre-roll). Rust FFTs are sized to the window. Unbounded paths are only the two backend producers (full `load_audio()` of a multi-hour file, no cap) - Existing #5531. Rust `compute_fingerprint` has no length cap of its own, but every in-engine caller is windowed.
- **Batch vs streaming**: only one analysis implementation exists now (Rust via `AudioFingerprintAnalyzer`); no separate streaming analyzer to diverge.
- **ML model lifecycle**: `auralis/analysis/ml/genre_classifier.py` is a hand-weighted rule-based classifier, no model file to reload; `ContentAnalyzer` creates it once per instance (`content_analyzer.py:47`). The fixed 44.1 kHz FeatureExtractor limitation is Existing #5244.
- **Thread safety**: `FingerprintNormalizer.fit()` locking (#5243) present; `LoudnessMeter` is created per call in `dsp/utils/adaptive.py` to avoid shared filter state; `quality_metrics` resets via `_reset_analyzers` (#4539). Rust call releases the GIL (`py.detach`).
- **KeyboardInterrupt**: `windowed_compute` catches `Exception` only, so interrupts propagate; `services/fingerprint_worker.py:171` re-raises `BaseException` on the calling thread (`53cef6b4` fix in place).
- **NaN/Inf**: `sanitize_non_finite` is wired in `analyze()` and again at the end of `compute_windowed_fingerprint` (#5103/#5505 in place); bypass at the two backend sites is Existing #5531.
- **Rust output scale vs persisted data / `e5e2cd05`**: Rust emits band fractions in 0-1, `rust_fingerprint` renames only, quantizer band bounds now 0-1 and agree; quantizer blobs come only from the dead `store_fingerprint()` path, so no stale 0-100 data is persisted in practice. Remaining quantizer mismatches: ENG-D6-04.
- **Quality metrics**: `loudness_variation_std` consumers use `log1p`/smoothing so the Rust 0-50 clamp (schema doc says 0-10) is tolerated in `continuous_space.py`; true-peak (`resample_poly` x4) over-reads only for very small chunks (1024-sample chunks +1.1 dB), but production feeds 400 ms chunks where chunked equals whole-buffer (verified: -1.41 dBTP both ways for a 0.85 sine). Centroid/rolloff 0-1 normalisation vs Hz consumers fixed by #5470.
- **Not deeply re-verified** (time-boxed): `dynamic_range.py` DR computation (advisory per Existing #5222), `phase_correlation.py` (#5418 closed), `quality_assessors/` scoring constants.

### Dim 7: Library & Database
- Repository pattern: no raw SQL found outside the two fingerprint upserts (`text()` INSERT ... ON CONFLICT), `claim_next_outdated_fingerprint` (read-only SELECT/UPDATE with `+` index hint, documented #5310), the playlist `INSERT OR IGNORE ... SELECT` (documented atomicity), and `RepositoryFactory.reset_library` (ORM `delete()`). No f-string SQL with unvalidated input (column names pass `_validate_fingerprint_columns`).
- Detached ORM instances: track read paths all carry `_track_eager_options()`; album/artist/genre/playlist reads use named option tuples; `to_dict()` goes through `_safe_collection()`/`_safe_scalar()`; post-commit paths in `update_metadata`, `update_by_filepath`, `update`, `update_artwork_path`, genre `create`/`update` re-query or touch the relationship before expunge. (Exception: `GenreRepository.get_tracks_by_genre` omits `selectinload(Track.genres)`, but it has no production caller in `auralis/` or `auralis-web/backend/`, so not reported.)
- `BaseRepository._session_scope()`: rollback-on-escape and `close()` in `finally` are correct. The only hand-rolled lifecycle left is `RepositoryFactory.reset_library` (try/rollback/finally close, correct) and `LibraryDatabase.get_session()` (zero callers).
- SQLite config: `check_same_thread=False`, `pool_pre_ping=True`, WAL, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout` set on every pooled connection; 0o600 hardening on DB, WAL/SHM and backup files.
- Engine disposal: `shutdown()` checkpoints (TRUNCATE), optimizes, disposes, clears `self.engine` in `finally`, and is idempotent. `atexit` holds a strong reference to each instance by design.
- Migration safety: file lock plus same-process thread lock (global), version re-check after lock, backup via the Online Backup API with `closing()`, per-step atomic DDL plus version insert on a raw connection, failed-step restore (#5316). `split_sql_statements` uses `sqlite3.complete_statement`. v017->v018 index is intentionally non-unique, so fresh (unique) and migrated (non-unique) `filepath_key` indexes differ by design; documented in the migration header.
- Concurrent scans: scan slot and per-directory reservation are atomic under `_scan_slots_lock`; slots and paths are released in `finally` (including the rejected-by-path branch); exclusive-access flag shares the same lock; reset uses `try_begin_exclusive_access`.
- `cleanup_missing_files` memory: id-cursor batching of (id, filepath) tuples only, unmounted-volume guard on the parent directory, re-verification before delete (the FK failure is ENG-D7-01, not an OOM or cursor problem).
- N+1: album/artist/genre/playlist list endpoints use correlated count subqueries via `with_expression`; track lists use eager options; `_attach_genre_names` is a single grouped query.
- Scanner robustness: symlink cycle detection by (dev, inode), depth cap, `PermissionError`/`OSError` handled per directory, non-ASCII paths go through `make_filepath_key` casefold on case-insensitive platforms, oversized/forged headers refused at scan time (#5312).
- Scheduler claims: claim by unique placeholder INSERT / version-0 UPDATE with rowcount check; cursor wrap; `release_claims` shared by the failure path and startup recovery.
- Schema parity: `create_missing_declared_indexes` plus model-declared indexes cover the #5321 gap. `reset_library` deletes children before parents and the `similarity_graph` FK has `ON DELETE CASCADE`.
- Existing tests that cover behaviours I considered: `record_play` atomicity (#5157), `TrackRepository.delete` atomic rowcount (#5173), settings lock (#5334).