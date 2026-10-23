# Audio Engine Audit — 2026-10-22

**Scope**: Auralis core audio engine. The seven `/audit-engine` dimensions were Sample Integrity, DSP Pipeline, Player State, Audio I/O, Chunked Mastering, Analysis, and Library & Database.
**Depth**: deep. **Limit**: none. **HEAD**: `44e4d433`.
**Method**: each dimension ran as a fresh sub-audit of the current source. Findings were checked with probes on synthetic and real audio. Every probe used a scratch `HOME` and scratch temp DBs, so the real library was never touched and no repo file changed. Each finding was deduplicated against the full issue dump (`gh issue list --state all`, 5613 issues, highest #5859). Prior reports in `docs/audits/` were used only for that dedup check.
**Environment note**: the `auralis_dsp` wheel is **not built** in the repo venv. The Analysis sub-audit compiled the cdylib into a scratch target dir to probe the Rust fingerprint. The DSP sub-audit could only exercise the fingerprint-driven path through stubs, the fixed-target path and the pure-Python generators. See E2-01: a missing wheel silently turns adaptive mastering into a bypass.

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 13 |
| LOW | 38 |
| **Total** | **52** |

By dimension: Sample Integrity 5 · DSP Pipeline 10 · Player State 8 · Audio I/O 4 · Chunked Mastering 5 · Analysis 11 · Library & Database 9.

The shipped streaming path is HybridProcessor → ContinuousMode with fixed targets, then the brick-wall limiter and the PCM saver. It held every hard invariant under probing: sample count preserved across awkward lengths and layouts, input arrays never mutated, dtype stable, output finite and peak-bounded, and pcm16/pcm24 scaling symmetric. No CRITICAL finding survived. Most of the remaining engine debt was filed by the 2026-10-21 round, and ~80 of those issues are still open (listed under Known/Existing below). Most new findings sit in four places:

1. **Library scaling (the one HIGH).** E7-01: the `track_artist` and `track_genre` tables have no index and no primary key. Every artist/genre join is a full-table scan. `find_similar` runs on every `POST /api/player/load` because `auto_reference_selection=True` and `recommended_reference` is never written. On a 50k-track library it took 20–41 s, against 9–18 ms with four indexes. The v002→v003 migration comment claiming the foreign keys "already have indexes" is wrong for SQLite.
2. **Failures that hide as success.** Several paths report success when they did nothing or did it wrong:
   - E2-01: a fingerprint failure, including a missing Rust wheel, returns unmastered audio as a normal result.
   - E1-02: a non-finite parameter yields a whole chunk of silence. Zero-repair runs before the HybridProcessor fail-fast and the pipeline fallback.
   - E4-01: the MP3/WAV tag writer drops five fields but returns success.
   - E7-03: one looping symlink makes a scan silently skip its directory.
   - E7-04: `skip_existing=False` reports "added" without changing anything.
   - E5-02: the CLI exits 0 on partial failure.
3. **Fingerprint measurements that depend on level or silence.** These dimensions feed the processing coordinates and k-NN target selection, and the values are persisted:
   - E6-01: spectral flatness and harmonic ratio have an absolute per-bin floor, a sibling of closed #5570.
   - E6-02: one silent second takes `loudness_variation_std` from 0.05 to 12.7, against a 0–10 schema range.
   - E6-07: the body-window probe correction uses the silence sentinel as a measurement.
   - E6-10: a single NaN sample yields a plausible fingerprint that passes validation.
4. **Categorical steps left in the continuous space.** E2-02 is a hard -50 LUFS gate (22 dB swing across 0.2 dB of input). E2-05 is a sign flip in the tilt guard. E2-03 is the stereo-width dead-bands and mixed units.

Player findings (E3-*) and the realtime DSP findings (E1-01 and E1-03) are **latent**. `AudioPlayer.get_audio_chunk()` has no production caller and the backend builds the player with `enable_auto_mastering=False`. Severities are capped accordingly. Offline-CLI findings (E2-04, E5-*) are rated at offline-tool weight, per #4873.

## Findings
### CRITICAL (0)

None.

### HIGH (1)

#### E7-01: `track_artist` / `track_genre` (and `albums.artist_id`) have no index and no PK, so every artist/genre lookup is a full-table scan; `find_similar` on every library track load takes 20-40 s at 50k tracks
- **Severity**: HIGH
- **Dimension**: Library & Database
- **Location**: `auralis/library/models/base.py:24-35` (table definitions); `auralis/library/migrations/migration_v000_to_v001_initial_schema.sql:112-125`; `auralis/library/migrations/migration_v002_to_v003.sql:45-46` (false comment); `auralis/library/repositories/track_repository_search.py:223-276` (`find_similar`); `auralis/player/integration_library.py:77-119` (caller); `auralis/library/repositories/artist_repository.py:21-60, 155-170`; `auralis/library/repositories/base.py` (`correlated_count`)
- **Status**: NEW (#2693 added only title/year/favorite indexes; #5321 repaired only declared model indexes; neither covers these tables. #5753 is a different fresh-vs-migrated diff)
- **Description**: `track_artist` and `track_genre` are declared as plain `Table(...)` with `ForeignKey` columns and nothing else: no PRIMARY KEY, no UNIQUE, no `Index`. The v0->v1 DDL is identical, and migration v002->v003 skips them with the comment "Association tables ... already have indexes from their foreign key constraints". That is false in SQLite: a FOREIGN KEY constraint indexes only the parent key, never the child column. `schema_indexes.create_missing_declared_indexes()` repairs only indexes declared on the models, so it cannot add them either. `albums.artist_id` has the same gap (only `idx_albums_title`, `idx_albums_year` exist). Every `Track.artists`/`Track.genres` join, selectinload, `.any()` EXISTS, `correlated_count(track_artist, ...)` and `_attach_genre_names` therefore runs `SCAN track_artist` (or `track_genre`). Correlated EXISTS and correlated count subqueries become O(rows x table).
- **Evidence**: Synthetic library built in a scratch DB: 50,000 tracks, 5,000 artists (10 contiguous tracks each), 30 genres.
  - `PRAGMA index_list(track_artist)` -> `[]`, `index_list(track_genre)` -> `[]`; `EXPLAIN QUERY PLAN` for the artist count -> `CORRELATED SCALAR SUBQUERY` + `SCAN track_artist`.
  - `db.tracks.find_similar(track, limit=3)`: **20,660 ms** (track id 25000), **41,329 ms** (track id 49995). After `CREATE INDEX` on `track_artist(artist_id)`, `track_artist(track_id)`, `track_genre(genre_id)`, `track_genre(track_id)`: **9.2 ms / 17.6 ms**.
  - `db.artists.get_all(order_by='track_count')`: **4,544 ms** -> **3.5 ms** with the indexes (30k tracks/3k artists variant: 1,625 ms -> 3.3 ms; quadratic in library size).
  - `db.genres.get_all(limit=50)`: 32 ms -> 1.5 ms (30k tracks).
  - Live caller: `POST /api/player/load` -> `AudioPlayer.load_track_from_library` -> `IntegrationManager.load_track_from_library` -> `_auto_select_reference` (`auto_reference_selection = True` by default, `integration_manager.py:85`) -> `repos.tracks.find_similar(track, limit=3)`. `Track.recommended_reference` is never written anywhere in the tree (grep), so the early return at `integration_library.py:95` never fires and `find_similar` runs on every load.
- **Impact**: Track load blocks for tens of seconds on a 50k-track library (scales roughly with N x position of the artist's rows), and the artist list sorted by track/album count takes seconds and grows quadratically. Every track read (`joinedload(Track.artists)`, `selectinload(Track.genres)`) also pays a table scan per page, which is why `get_by_id` costs about 10 ms even on tiny result sets. The absence of any PK/UNIQUE also lets a raw path insert duplicate (track, artist) rows silently (the `normalize_existing_artists.py` merge relies on `UPDATE OR IGNORE`, which can never ignore anything on a table without a unique constraint).
- **Siblings**: `albums.artist_id` (no index; `correlated_count(Album, Album.artist_id, Artist)` and `Artist.albums` selectin scan `albums`); `GenreRepository.get_tracks_by_genre` (30 s for one genre at 30k tracks, but the method is dead per #5754); `track_artist`/`track_genre` FK checks on `DELETE FROM tracks`.
- **Suggested Fix**: Declare `Index('ix_track_artist_artist_id', 'artist_id')`, `track_id` variants, and ideally composite PRIMARY KEYs `(track_id, artist_id)` / `(track_id, genre_id)` (after de-duplicating) on the association tables, plus `Index('idx_albums_artist_id', 'artist_id')`; add a schema v24 migration that creates them (`CREATE INDEX IF NOT EXISTS`) so upgraded databases get them too (`create_missing_declared_indexes` will then cover fresh ones). Separately, stop running `find_similar` on every track load (nothing consumes its result unless a reference file exists).

### MEDIUM (13)

#### E1-01: LowMidTransientEnhancer stacks every overlapping peak window, so each realtime buffer gets about +20 dB of low-mid and heavy hard clipping
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/dynamics/lowmid_transient_enhancer.py:130-179` (the `for peak_idx in peaks` loop, `output[start:end] += ...`, then `np.clip(output, -1.0, 1.0, out=output)`); call site `auralis/player/realtime/auto_master.py:190-203`
- **Status**: NEW (the closed #2202 and #2682 fixed the envelope and the global normalisation, not the stacking)
- **Description**: `AutoMasterProcessor` calls `enhance_transients(chunk, intensity=0.35, attack_samples=int(sr*0.05))` on every 1024-sample buffer. `attack_samples` is 2205, larger than the buffer, so for every detected peak `start=max(0, p-2205)` and `end=min(len, p+2205)` span the whole buffer. The loop then adds `low_mid * (expansion_env*1.7 - 1.0) * blend` over that whole-buffer window once per peak, with no de-duplication and no `distance=` in `find_peaks`. Peaks are taken at `height > mean + 0.5*std` of a 441-sample savgol-smoothed |HF| envelope, so a 1024-sample buffer typically holds several. The low-mid band is boosted K times instead of once, where K is the peak count of that buffer. Additional defects of the same loop: (a) the `blend` ramp (20 samples, `ramp_len = min(20, window_len)`) falls at the buffer edges, so the added term drops to 0 at both ends of every buffer (amplitude modulation at 43 Hz); (b) filtfilt band extraction runs independently per 1024-sample buffer, so the band has edge effects at every boundary; (c) `np.clip(..., out=output)` is a hard clip, the only safety net, and the output has no relation to the input level.
- **Evidence**: Probe 1: music-like stereo (110 Hz + 440 Hz tones + noise, input peak 0.23), 1024-sample buffers, `intensity=0.35`, `attack_samples=2205` (the exact production call). Per-buffer low-mid band gain (150-1500 Hz): median +22.1 dB, max +22.7 dB, min 0.0 (buffers with no peak). Probe 2: synthetic noise plus HF bursts: 88 316 of 172 000 output samples at |x| >= 1.0 (clipped), mean band gain +19.5 dB. `mean |out-in|` is 0.17 in the first 20 samples of a buffer, 0.69 mid-buffer and 0.39 in the last 20 samples, which shows the edge modulation. The call site comment says "Subtle, not overwhelming".
- **Impact**: When enabled, quiet dynamic material (fingerprint `lufs < -13` and `crest > 14`, the exact class this stage targets) is boosted about 20 dB in the low-mids and hard-clipped. Reach is gated: `enable_auto_mastering=False` in the backend startup (`config/startup/components.py:177-180`) and `AudioPlayer.get_audio_chunk()` has no production consumer. This is latent, hence MEDIUM and not HIGH.
- **Siblings**: `enhance_transients` also returns `(n,)` for an `(n,1)` input (`_enhance_channel` calls `audio.squeeze()`); probe: `(2000,1) -> (2000,)`. Unreachable today because `AudioFileManager.get_audio_chunk` always returns `(n,2)`.
- **Suggested Fix**: Sum the per-peak contributions into one envelope buffer and take the max (or cap with a single `np.minimum`) before adding to `output`, size `attack_samples` against the buffer, and keep filter state across buffers or process on a longer analysis window. Replace the hard clip with the soft clipper or a gain-reduction stage.

#### E1-02: ContinuousMode / AdaptiveMode / HybridMode repair non-finite audio by zeroing the whole buffer, which pre-empts the fail-fast and the pipeline's unprocessed-audio fallback and ships a silent chunk
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/continuous_dsp_ops.py:227` (`repair=True`), `auralis/core/processing/adaptive_mode.py:240`, `auralis/core/processing/hybrid_mode.py:109`; the guards they defeat: `auralis/core/hybrid_processor.py:259,287` and `auralis/core/hybrid_stage_dispatch.py:126` (`repair=False`), `auralis-web/backend/core/audio_processing_pipeline.py:~262-275` (fallback to the unprocessed `audio`)
- **Status**: NEW (related to closed #4237, #2520, #4672, #5505; the #5505 fix is present at the analyzer, see Evidence)
- **Description**: `HybridProcessor` documents that output NaN/Inf must "surface DSP bugs rather than silently masking them with zero-replacement" (#2520) and `AudioProcessingPipeline.apply_enhancement` falls back to the unprocessed chunk when the processor returns non-finite audio (#4672). But `ContinuousMode._apply_final_normalization` (and the two legacy modes) run `validate_audio_finite(..., repair=True)` on the full buffer BEFORE the output reaches either guard. `repair=True` replaces every non-finite sample by 0.0 with only a WARNING log. A non-finite stage parameter makes the whole buffer NaN (an FFT frame or a gain multiplies every sample), so the repair turns the entire chunk into digital silence. The `repair=False` check at the HybridProcessor boundary and the pipeline fallback never see a non-finite array, so neither fires. The silent chunk is then level-smoothed, WAV-encoded and written to the chunk cache.
- **Evidence**: Probe (3 s stereo float32, per-chunk fingerprint path, `fingerprint_analyzer.analyze` stubbed to return a fingerprint dict with one bad field, `quality_gate_enabled=False`): `stereo_width=nan/inf/-inf` -> `finite=True peak=0.0000 zero_frac=1.000`; `bass_pct=nan` or `-inf` -> `zero_frac=1.000`; `bass_pct/low_mid_pct/mid_pct/upper_mid_pct/presence_pct/air_pct=-1e30` -> `zero_frac=1.000`. Hybrid mode with a NaN sample in `reference` (`HybridProcessor.process(target, reference)`): `peak=0.0000 rms=-240 dB` (silence), whereas the same input in reference mode raises `ModuleError`. The #5505 source fix is live (`analysis/fingerprint/audio_fingerprint_analyzer.py:28` `sanitize_non_finite`, `sidecar_validation.py:100` `isfinite`), so no current producer of a non-finite fingerprint was found; the channel is a defense-in-depth gap that makes any future non-finite source (an out-of-range DB row, a new stage bug) a silent 10-second mute instead of a loud failure or the documented fallback.
- **Impact**: Whole-chunk silence cached on disk for the lifetime of the cache entry, with no error and no fallback. Not HIGH because no live source was found after #5505/#5531.
- **Siblings**: the three `repair=True` sites above. `RealtimeProcessor.process_chunk` (`processor.py:182`) and `saver.save` (`saver.py:44`) also repair, but those are last-boundary writers, which is the right place.
- **Suggested Fix**: Repair only when the non-finite fraction is tiny (for example under 0.1% of samples) and otherwise raise (or return the input) so the existing fail-fast and fallback fire; log at ERROR with the stage name. Validate `reference` at the `HybridProcessor.process` boundary like `target`.

#### E1-03: RealtimeLevelMatcher is a per-1024-sample AGC with a per-sample smoother, so every upward level step gets a 5 ms burst of up to +20 dB and chunk dynamics collapse to the reference RMS
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/player/realtime/level_matcher.py:90-112` (gain = `current_target_rms / current_rms` recomputed every chunk, `gain_smoother.process(len(audio))`) with `auralis/player/realtime/gain_smoother.py:48-58` (`alpha` is per SAMPLE: 0.02 attack / 0.005 release)
- **Status**: NEW (distinct from open #5707, which covers only the fade-in from `current_target_rms = 0`, and from open #5721, the peak-derived chunk gain)
- **Description**: Each 1024-sample (23 ms) buffer is measured and a fresh target gain is computed from that buffer's RMS against the whole-file RMS of the reference. `AdaptiveGainSmoother.process` uses the closed form `g[n] = target + (g0-target)*(1-alpha)^n` with alpha per sample, so the gain converges to the new target in about 230 samples (5 ms, attack) or 900 samples (release). The consequences are (1) the output RMS of every buffer is forced to the reference RMS, which removes all buffer-to-buffer dynamics (not "level matching" but a 23 ms AGC); (2) at an upward level step the smoother starts from the previous (high) gain, so the first few ms of the louder buffer are multiplied by up to the 10x clamp before the gain settles; the burst only stops at the chunk-level safety clamp in `RealtimeProcessor`, which then scales the whole buffer down.
- **Evidence**: Probe (reference RMS 0.1, 1500 warm-up buffers so the #5707 ramp has converged, then buffer amplitudes 0.02,0.02,0.02,0.4,0.4,0.4,0.02,0.4...): input RMS dB `[-37,-37,-37,-11,-11,-11,-37,-11]`; output RMS dB `[-20.3,-20.0,-20.0,-11.2,-19.8,-20.0,-20.2,-11.2]`. The first loud buffer of each step stays at -11 dB (burst), the rest are pinned at -20 dB (the reference RMS). On the 0.02 -> 0.4 transition buffer the effective gain is 2.35 at sample 3-10 and 0.15 over the last 300 samples.
- **Impact**: Pumping at the 43 Hz buffer rate and broadband bursts on every onset when level matching is active. Level matching is on by default (`PlayerConfig.enable_level_matching=True`) once a reference is set, but `AudioPlayer.get_audio_chunk()` has no production consumer, so this is latent.
- **Siblings**: none in the shipped chunk pipeline (the backend `LevelManager` ramps across chunks properly).
- **Suggested Fix**: Make the matcher program-level (smooth the measured RMS over seconds with a per-time-unit time constant) and convert the smoother's alpha to per-second time constants applied per sample; or delete the unwired realtime chain.

#### E2-01: Any fingerprint failure (missing Rust module, Rust error, resample error) turns mastering into a silent bypass that reports success
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:105-161`, `auralis/core/processing/continuous_mode.py:246-258`, `auralis/core/hybrid_processor.py:230-258`
- **Status**: NEW
- **Description**: `AudioFingerprintAnalyzer._analyze_unchecked` wraps everything (the `import auralis_dsp` inside `compute_fingerprint_schema`, `librosa.resample`, the Rust call, and the `KeyError` that `rust_fingerprint_to_schema` raises on a partial dict) in `except Exception` and returns `{}`. `ContinuousMode._resolve_parameters` treats `{}` as "nothing to do": it logs at `debug` level, returns `None`, and `process()` returns the untouched copy. `HybridProcessor._process_adaptive_mode` then runs only the brick-wall limiter and returns it as a normal result. Nothing in the engine, the job layer or startup distinguishes "mastered" from "bypassed". The shipped chunked-streaming path is not affected when a fixed-target sidecar exists, but the per-chunk fingerprint path and every whole-file adaptive job (`job_execution.py` calls `processor.process(audio)` with no targets) are.
- **Evidence**: reproduced in this venv, where `auralis_dsp` is not installed: `HybridProcessor(UnifiedConfig()).process(x)` for a 2 s stereo sine returned `np.array_equal(y, x) == True`, `continuous_mode.last_parameters is None`, no exception, and the only signal was one `Audio fingerprint analysis failed: No module named 'auralis_dsp'` log line. A grep for `auralis_dsp` in `auralis-web/backend` shows only `analysis/fingerprint_generator.py`; there is no startup or health check that the Rust module imports.
- **Impact**: With the wheel missing (the documented dev failure "Rust module missing -> maturin develop") or any transient analyzer failure, every adaptive job completes as "Processing complete" with unmastered audio. In the per-chunk streaming path a single failing chunk is bypassed while its neighbours are mastered, which gives a level and tone jump at the seam.
- **Siblings**: `HybridProcessor.process` documents "surface DSP bugs rather than masking them" for NaN/Inf (`validate_audio_finite(..., repair=False)`), but this failure mode is masked. `hybrid_stage_dispatch.MIN_SAMPLES` comment still says "the fingerprint stage alone needs 11025 samples"; the analyzer now needs `sr // 2` = 22050, and anything in between is also silently bypassed.
- **Suggested Fix**: Let `ImportError` and Rust errors propagate from `ContinuousMode` (or raise a dedicated `FingerprintUnavailable` that the job and stream layers surface), keep the silent skip only for the explicit too-short case, and add a startup check that `import auralis_dsp` works.

#### E2-02: Per-chunk / whole-file loudness normalization has a hard gate at -50 LUFS: a 0.2 dB change in input level swings the gain by 22 dB
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_dsp_ops.py:178-218` (gate at `:197`), `auralis/dsp/utils/adaptive.py:82` (`SILENCE_FLOOR_LUFS = -50.0`)
- **Status**: NEW (the #5551 fix introduced the gate; #5700 covers a different defect in the same function)
- **Description**: `_normalize_chunk_loudness` returns the audio untouched when `current_lufs <= SILENCE_FLOOR_LUFS` (-50 LUFS), otherwise it applies `clip(target - current, +-24 dB)`. Every other guard in this module was converted to a `smooth_gate` knee (#4860, #5108, #5578); this one stayed a step. The floor is also far above digital silence: -50 LUFS is quiet-but-real programme (ambient intros, classical pianissimo, fade tails), and room tone or tape hiss at -49 LUFS is still lifted by about +21 dB, which is the exact failure #5551 was meant to prevent.
- **Evidence**: probe on 5 s stereo noise, target -28 LUFS, through `ContinuousDSPOpsMixin._normalize_chunk_loudness`:
  `in -49.0 LUFS -> gain +21.0 dB; in -49.9 -> +21.9; in -50.1 -> +0.0; in -51.0 -> +0.0; in -55.0 -> +0.0`.
- **Impact**: Reached whenever `fixed_params` is None: whole-file adaptive jobs (one measurement for the whole track: a master at -50.1 LUFS gets no lift while -49.9 gets +22 dB) and the per-chunk fingerprint path (adjacent chunks across the floor get a 22 dB level step, e.g. a decaying outro or quiet intro). It contradicts the continuous-space invariant that near-identical inputs get near-identical treatment.
- **Siblings**: none in the live chain (`_apply_final_normalization` source-LUFS branch has no gate).
- **Suggested Fix**: Replace the step by `smooth_gate` on `current_lufs` over a knee well below programme level (for example -70..-55 LUFS), so the lift fades out to 0 near true silence instead of switching.

#### E3-01: Gapless transition zero-pads the tail of the last chunk, so every track change has up to one chunk of silence
- **Severity**: MEDIUM (the rubric rates an audible gapless gap HIGH; capped at MEDIUM because `get_audio_chunk` is dormant in the shipped backend)
- **Dimension**: Player State
- **Location**: `auralis/player/player_streaming_mixin.py:90-117`; `auralis/player/audio_file_manager.py:141-153`; `auralis/player/gapless_playback_engine.py:73-110`
- **Status**: NEW (no open or closed issue matched "gapless" + pad/tail/final chunk)
- **Description**: `get_audio_chunk()` reads the final chunk of track A and only then spawns the auto-advance thread (`end_of_track = pos + chunk_size >= total_samples`). `AudioFileManager.get_audio_chunk()` fills the short tail of that final chunk with zeros (`np.vstack([chunk, padding])`). The swap to track B (prebuffer or not) lands after the chunk is already returned. B's first sample therefore reaches the output at the start of the next callback, after `chunk_size - remaining` zero samples. That is a uniformly distributed 0..`chunk_size-1` samples of digital silence per transition (mean about 11.6 ms and up to 23.2 ms at the default `buffer_size=1024` at 44.1 kHz). If the advance thread is slower than one callback period, whole chunks of silence follow (position is pinned at `total_samples`, so the same zero-tail read repeats). The engine docstring claims "<10ms gap".
- **Evidence**: Probe: 6-chunk track A (5420 samples of 0.5), prebuffer for B (0.25) already present and valid, callbacks 20 ms apart. Output run-lengths were `[(0.5, 5420), (0.0, 724), (0.25, 3072)]`: 724 zero samples (16.4 ms) at the A-to-B seam, equal to `6*1024 - 5420`. Call path: `get_audio_chunk` -> `file_manager.get_audio_chunk(pos, 1024)` pads -> `_auto_advance_next` -> `next_track` -> `advance_with_prebuffer` swap + `seek(0)`.
- **Impact**: An audible click or gap (>1 ms silence) at every auto-advance for any engine consumer that drives `get_audio_chunk`. The prebuffer machinery (#2075, #5105, #5583) exists to deliver gapless playback but cannot, because the seam is not sample-exact.
- **Siblings**: The same zero-padded final chunk is used by the `reached_end_without_advance` branch, where it is harmless.
- **Suggested Fix**: When `end_of_track` and a next track is available and prebuffered, perform the swap inline under `_audio_lock` and fill the chunk remainder from the new track's first samples. Alternatively, pre-extend the read across the track boundary.

#### E4-01: MP3 and WAV metadata writer silently drops bpm / composer / publisher / lyrics / copyright
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/library/metadata_editor/writers.py:81-138` (`write_mp3_metadata`); dispatch for MP3 and WAV at `auralis/library/metadata_editor/metadata_editor.py:~160-175`
- **Status**: NEW
- **Description**: `TAG_MAPPINGS['mp3']` declares 14 fields. The "set" branch of `write_mp3_metadata` is an `if/elif` chain that handles only title, artist, album, albumartist, year, genre, track, disc and comment. For `bpm`, `composer`, `publisher`, `lyrics` and `copyright` no branch matches, so a non-empty value is accepted and discarded without a warning. Only the "clear" branch (`value is None or ''`) reaches those keys. WAV goes through the same writer (embedded ID3, #4130). The API accepts all five fields (`routers/metadata_models.py:24-28`, `MetadataUpdateRequest`). The route then reports them under `updated_fields` and returns `success: True` (`routers/metadata_tracks.py:~205-215`). FLAC, Ogg/Opus and M4A do write composer/lyrics/copyright.
- **Evidence**: `MetadataEditor().write_metadata('w.mp3', {'title':'T','artist':'A','bpm':120,'composer':'C','publisher':'P','lyrics':'L','copyright':'(c)','track':'3'}, backup=False)` returned True. `read_metadata` then gave `{'title':'T','artist':'A','track':'3'}`. The same call on `w.flac` and `w.opus` round-trips all of the fields. The same result occurred for `w.wav`. `grep -rn "composer\|bpm\|publisher" tests/auralis/library/test_metadata_editor.py` finds nothing, so no test pins this behaviour.
- **Impact**: Edits to composer, publisher, lyrics, copyright or BPM on any MP3 or WAV are silently lost. The UI shows success, and a `metadata_updated` WS event lists the fields as written. MP3 is the most common library format.
- **Siblings**: The reader (`read_mp3_metadata`, `readers.py:23-52`) already knows TBPM, TCOM, TPUB, USLT and TCOP, so only the write side is incomplete.
- **Suggested Fix**: Drive the ID3 write from a `{field: frame_class}` table (TBPM, TCOM, TPUB, USLT, TCOP) in place of the hand-written elif chain. Add a per-format round-trip test over every key in `TAG_MAPPINGS`.

#### E4-02: M4A metadata edit fails outright for files with a BPM (tmpo) or PUBLISHER atom, because the writer emits str where mutagen needs int/bytes and the reader renders freeform bytes as "b'...'"
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/library/metadata_editor/writers.py:162-195` (write_mp4_metadata, specifically `:195` `audio_file[tag_key] = [str(value)]`); `auralis/library/metadata_editor/readers.py:~91-99` (read_mp4_metadata, `str(value)`); frontend round-trip at `auralis-web/frontend/src/components/library/EditMetadataDialog/useMetadataForm.ts:128-141`
- **Status**: NEW
- **Description**: The generic M4A branch writes `[str(value)]` for every non-track field. Two M4A atoms need other types.
  - `tmpo` (BPM) must be `[int]`. The `str` value raises `MP4MetadataValueError` at `audio_file[...] = ...`.
  - The `----:com.apple.iTunes:PUBLISHER` freeform atom must be `MP4FreeForm`/bytes. The `str` value raises `TypeError: can't concat str to bytes` at save.

  On the read side the freeform value is `MP4FreeForm` (a bytes subclass), so `str(value)` yields the literal text `"b'Pub'"`. The edit dialog loads all fields via `read_metadata` and re-sends every non-empty field on save (`useMetadataForm.ts:128-141` converts bpm to an int). So for an M4A that has a tmpo or PUBLISHER atom, even a title-only edit includes `bpm`/`publisher` and the whole save fails. The writer's rollback restores the file, so nothing is corrupted, but the user can never save.
- **Evidence**: Reproduced with `MP4('y.m4a')` carrying `tmpo=[120]` and a freeform PUBLISHER of `b'Pub'`.
  - `read_metadata` returned `{'bpm': '120', 'publisher': "b'Pub'"}`.
  - Emulating the dialog with `write_metadata('y.m4a', {'title':'New','bpm':120}, backup=True)` raised `MP4MetadataValueError: '<=' not supported between instances of 'int' and 'str'`. The tags were unchanged afterwards.
  - Single-field writes on a clean M4A: bpm and publisher raise (`TypeError: can't concat str to bytes` for publisher). composer, lyrics, copyright, title, track and year succeed.
- **Impact**: iTunes- or DJ-tool-tagged M4A files commonly carry tmpo, so metadata editing is unusable for them. A PUBLISHER freeform atom causes the same failure and also displays as `b'...'`.
- **Siblings**: Dispatch precedence in `metadata_editor.py` (`isinstance(...) or ext == ...`) lets the extension override the real container. An MP3 stream named `.m4a` was sent to the MP4 writer and failed with `TypeError: ['T'] not a Frame instance` (the backup restore keeps the file intact). The `read_mp4_metadata` track/disc formatting also renders a missing total as `3/0`.
- **Suggested Fix**: In the MP4 writer, write `[int(value)]` for `tmpo` and `[MP4FreeForm(str(value).encode('utf-8'))]` for freeform atoms. In the reader, decode `MP4FreeForm` as UTF-8 (with `errors='replace'`). Prefer `isinstance` over the extension in the dispatch.

#### E6-01: `spectral_flatness` and `harmonic_ratio` are level-dependent (absolute 1e-10 per-bin floor left in `compute_spectral_flatness`)
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `vendor/auralis-dsp/src/spectral_features.rs:82-112` (`compute_spectral_flatness`, the `p > 1e-10` filter); consumer `vendor/auralis-dsp/src/fingerprint_compute.rs:519-526` (`estimate_harmonic_ratio = 1 - flatness`)
- **Status**: NEW (same defect class as closed #5570, whose fix only touched `frequency_analysis.rs`; verified that fix is still in place, so this is a sibling, not a regression)
- **Description**: The PSD is normalised by `fft_size^2` (so absolute bin values are tiny: about 1e-7 * sigma^2 for a 90 s window), and flatness then discards every bin below an absolute 1e-10 before taking the geometric mean. Which bins survive depends on the signal level, so flatness drifts toward the loud bins only (and `harmonic_ratio`, its complement, drifts the other way) as a track gets quieter. Below roughly -40 dBFS RMS broadband material has no surviving bins and reads flatness 0.0 / harmonic_ratio 1.0 ("pure tone"). #5570 removed exactly this floor from the 7-band split and its comment says "the floor bought nothing but level dependence"; the same floor remains one file over.
- **Evidence**: Real audio, 60 s mono excerpts, `compute_fingerprint_schema` at 22.05 kHz, level shifted digitally (spectral_centroid and transient_density are identical across shifts, so only these dims move):
  - piano stem (-24 dBFS RMS): shift 0 / -10 / -20 / -30 / -40 dB -> flatness 0.078 / 0.198 / 0.445 / 0.744 / 0.956, harmonic_ratio 0.922 / 0.802 / 0.555 / 0.256 / 0.044
  - drums stem: flatness 0.137 -> 0.215 -> 0.513 -> 0.823 -> 0.990
  - white noise, 90 s window: -36 dB flatness 0.965; -48 dB flatness 0.000 / harmonic_ratio 1.000 (discontinuous flip)
- **Impact**: `harmonic_ratio` is a `DISTANCE_FEATURES` entry in `core/processing/target_derivation.py:52-56` (reference-cloud k-NN that picks the EQ target) and both dims carry weight in `analysis/fingerprint/distance.py` (similarity). Two masters of the same song at different gain, or a quiet vs loud track with the same timbre, get different "tonality" and therefore different neighbours/targets. Stored fingerprints are persisted, so the error is not transient.
- **Siblings**: `compute_spectral_centroid` / `compute_spectral_rolloff` use `total_power < 1e-10` (about -86 dBFS RMS, only bites on near-silence; not a defect in practice).
- **Suggested Fix**: Compute flatness over all bins with a relative floor (e.g. `max(psd) * 1e-12`, or add a tiny epsilon in f64) so the ratio is scale-invariant; bump `FINGERPRINT_ALGORITHM_VERSION` so stored rows are recomputed (and see #5697 so stale `.25d` is not re-stamped current).

#### E6-02: Digital-silence frames inflate `loudness_variation_std`, `dynamic_range_variation` and `peak_consistency`
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `vendor/auralis-dsp/src/variation_analysis.rs:10-24` (silent frame -> 0.0 dB), `:112-126` (`compute_loudness_variation`), `:83-103`, `:139-158`; floor from `vendor/auralis-dsp/src/dsp_math.rs:36-44` (`estimate_lufs` returns -120 for silence)
- **Status**: NEW (the 2026-10-16 audit noted the 0-50 clamp vs the 0-10 schema range as "tolerated"; it did not look at silent frames)
- **Description**: The three variation dims take the std-dev / CV of per-1 s-frame values, including frames that are digitally silent. A silent frame contributes `-120` LUFS (loudness), `0.0` dB (crest) and `0.0` peak, so one silent second dominates the statistic. Schema range for `loudness_variation_std` is 0-10 dB (`schema.py:87`); Rust clamps at 50.
- **Evidence**: 60 s of constant-level noise, 1/3/10 s of zeros inserted at t=20 s, `compute_fingerprint_schema`: `loudness_variation_std` = 0.05 (no gap) -> 12.71 / 21.64 / 37.01; `dynamic_range_variation` 0.087 -> 0.221 / 0.317 / 0.44; `peak_consistency` 0.067 -> 0.147 / 0.240 / 0.454. A steady-level signal is reported as wildly dynamic.
- **Impact**: `continuous_space._calculate_dynamic_range` (`core/processing/continuous_space.py:282-291`) takes 25 % of the dynamics coordinate from `log1p(loudness_variation_std)`, so any track with a silent second in its 90 s body window (hidden-track gaps, a rest, a gap before the encoded tail on short files) is steered as "more dynamic". The stored value is also clamped to 20 by the quantizer, so DB row and live value differ. k-NN `DISTANCE_FEATURES` includes `loudness_variation_std`, `dynamic_range_variation` and `peak_consistency`, so neighbour search is skewed the same way.
- **Siblings**: all three functions in `variation_analysis.rs`; `fingerprint_compute.rs:estimate_transient_density` handles silence explicitly (does not have this problem).
- **Suggested Fix**: Skip frames whose RMS is below a relative/absolute silence gate (the `silence_ratio` dim already measures them) before the std-dev/CV, require a minimum number of non-silent frames, and clamp to the schema range; bump `FINGERPRINT_ALGORITHM_VERSION`.

#### E6-03: Whole-file processing jobs bypass every analysis window: unbounded fingerprint + an unread quality gate (O(duration) memory and CPU)
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/core/processing/continuous_mode.py:250-254` (`fingerprint_analyzer.analyze(processed_audio, ...)` on whatever it is handed); `auralis/core/processing/continuous_quality.py:42-67` + `continuous_stages.py:111` (`QualityMetrics.compare_quality(target_audio, processed_audio)`); caller `auralis-web/backend/core/job_execution.py:165,195,203` (`processor.process(audio)` with the full decoded file)
- **Status**: NEW (Related #5712: that issue covers the gate's KeyError on short chunks and its ~2 s per-gate cost, not its O(duration) footprint on whole-file jobs)
- **Description**: Every other 25D producer is bounded (windowed fingerprint: 90 s body + 2x30 s probes; `evaluate_mastering_files`: 3x8 s windows; `MasteringFingerprint`: 90 s). The processing-job path loads the entire file, and `HybridProcessor._process_adaptive_mode` -> `ContinuousMode.process` (no `fixed_params`, `current_targets` is only set by the chunked streaming path) analyses all of it, then `quality_gate_enabled=True` (default, runs on the first call and every 5th) runs `assess_quality` on input and output in full. Nothing reads `last_quality_comparison` / `last_mastering_measurements` anywhere outside `continuous_quality.py` (grep), so the gate's cost buys nothing. There is no duration limit in the job router/engine.
- **Evidence** (measured, stereo 44.1 kHz noise, scratch Rust build):
  - `AudioFingerprintAnalyzer.analyze`: 30 s -> 277 MB RSS / 0.37 s; 120 s -> 504 MB / 1.06 s; 300 s -> 850 MB / 2.67 s (about +2.2 MB per second of audio, one `2^k` FFT per stage grows with it; `audio_to_freq_domain` runs twice).
  - `QualityMetrics.assess_quality`: 15 s -> +68 MB / 0.99 s; 60 s -> +130 MB / 2.7 s; 180 s -> +378 MB / 7.8 s (about +2.1 MB and 43 ms per second; `SpectrumAnalyzer.analyze_file` keeps one Python dict of lists per 1024-sample hop).
  - Extrapolated (linear): a 1 h DJ mix needs roughly +8 GB for the fingerprint and +7.5 GB (x2 for before/after) for the gate on top of the decoded audio and the DSP copies; a 6 h podcast roughly 6x that.
- **Impact**: One long job can exhaust RAM on the desktop host (the job executor is a thread pool in the same process as the player), and the gate adds minutes of pure-Python work whose output is discarded.
- **Siblings**: `ContinuousMode.derive_album_target` (`continuous_mode.py:181-184`) also fingerprints whole tracks (dormant today, see #5560/#5722).
- **Suggested Fix**: Make `ContinuousMode` (or `HybridProcessor.process` for non-chunk callers) fingerprint through the shared windowed pipeline (`crop_preloaded_windows`) when the input exceeds ~90 s, and drop the quality gate or run it on the same 3x8 s windows `evaluate_mastering_files` uses.

#### E7-02: Library ordering is BINARY and search is ASCII-only: lowercase titles sort after every capital, the NOCASE indexes are never used, and `ILIKE` misses non-ASCII case variants
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_search.py:181, 214` (`Track.title.asc()`); `album_repository.py:130, 210`; `artist_repository.py:215` (`Artist.name`); `genre_repository.py:100, 147, 287`; `playlist_query_mixin.py:70, 142`; indexes at `models/track.py:112` (`idx_tracks_title`), `models/album.py:36` (`idx_albums_title`); `ilike` filters in `track_repository_search.py:34-45` and the album/artist/genre/playlist `search()` methods
- **Status**: NEW
- **Description**: #2693/#5321 added `idx_tracks_title` and `idx_albums_title` as `... COLLATE NOCASE` indexes, but no repository ever orders or compares with `collate(..., 'NOCASE')` (`grep -in "nocase\|collate" repositories/` is empty). `ORDER BY title` therefore uses the default BINARY collation: the index is ignored (full scan + temp b-tree) and the order is case-sensitive. `ILIKE` on SQLite renders `lower(col) LIKE lower(?)`, and SQLite's `lower()`/`LIKE` fold only ASCII, so non-ASCII letters never match across case.
- **Evidence**:
  - Probe (`tracks.get_all`): titles `banana, Apple, cherry, Zebra, éclair, Mango` -> `['Apple', 'Mango', 'Zebra', 'banana', 'cherry', 'éclair']`; `albums.get_all` -> `['AlbumB', 'albumA']`.
  - `EXPLAIN QUERY PLAN select * from tracks order by title limit 50` -> `SCAN tracks` + `USE TEMP B-TREE FOR ORDER BY`; the same query with `COLLATE NOCASE` -> `SCAN tracks USING INDEX idx_tracks_title`.
  - Probe (`tracks.search`): stored `éclair`; queries `éclair` -> hit; `ÉCLAIR`, `Éclair` -> `[]`; ASCII `APPLE` -> hit.
- **Impact**: Server-paginated library, album, artist and playlist lists present "A-Z" in ASCII-binary order (every lowercase-initial title/name such as "blink-182", "deadmau5", "iron & wine" appears after all capitalized ones, and accented initials last), and infinite scroll makes the misordering permanent across pages. The NOCASE indexes cost write time and disk and serve nothing. Typing accented names with different capitalisation ("BEYONCÉ", "Sigur Rós") returns no results.
- **Siblings**: tracks `get_all`/`get_favorites`/`search`, albums `get_all`/`search`, artists `get_all`/`search`, genres `get_all`/`search`, playlists `get_all`/`search`, `get_tracks_by_genre`.
- **Suggested Fix**: Order with `collate(Track.title, 'NOCASE')` (and the same for album/artist/genre/playlist name columns) so the existing indexes are used. For Unicode-correct search, compare against a casefolded shadow column or register a Python `casefold()` SQLite function on connect.

#### E7-03: One unreadable or looping symlink aborts discovery of its whole directory (and all subdirectories after it)
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/file_discovery.py:121-140` (`_walk_directory`)
- **Status**: NEW (#2071/#4823 added directory-cycle detection and the containment policy; #5594 is the hidden-ancestor bug. None covers ELOOP/EACCES from `DirEntry.is_dir`)
- **Description**: The loop body calls `entry.is_dir(follow_symlinks=True)` / `entry.is_file(follow_symlinks=True)` inside a single `try` that wraps the whole `os.scandir` iteration, with `except PermissionError` / `except OSError` outside the loop. `DirEntry.is_dir()` swallows only `FileNotFoundError`; for a symlink it `stat()`s the target, so a self-referential or mutually referential link (ELOOP) or a link into a directory the user cannot search (EACCES) raises out of the loop. The `except` then logs one error and the generator for that directory ends: every remaining entry, including subdirectories, is never visited. The inode-visited cycle guard only handles loops that resolve to a directory.
- **Evidence**: Probe: a directory with 8 `f*.mp3` files and `sub/s.mp3`, plus `ln -s loop loop` -> `discover_audio_files()` returned `[]` (0 of 9); with a `a_b <-> b_a` link pair also 0. Removing only the loop links -> all 9 found. `scandir` order is arbitrary, so the files lost depend on where the bad link falls in the listing (here it came before everything).
- **Impact**: A library scan reports success with a silently incomplete result (the `files_found` count simply omits the files; nothing is marked failed). Tracks in the affected directory are never added, and a user cannot tell why. The symlink-loop robustness item on the checklist is only half met.
- **Siblings**: Non-recursive branch uses `pathlib.is_file()` (which swallows OSError) and is unaffected.
- **Suggested Fix**: Move the per-entry classification into its own `try/except OSError` that logs and `continue`s, so only that entry is skipped; keep the outer handler for the `scandir()` call itself.

### LOW (38)

#### E1-04: Compression/width helpers take numpy-scalar and out-of-range parameters at face value (float32 -> float64 promotion, sign inversion above ratio about 9)
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/base/compression_expansion.py:111-121` (`apply_clip_blend_compression`: `audio * (1.0 - amount) + compressed * amount`, `threshold = 0.8 - (ratio - 1.0) * 0.1`); `auralis/dsp/utils/stereo.py:104-122` (`adjust_stereo_width`, public via `dsp/utils/__init__.py:45`)
- **Status**: NEW
- **Description**: The shipped path stays float32 only because every producer wraps its values in `float()` (`parameter_generator_dynamics.generate_compression`, `fixed_target_params`). The consumer does not defend itself, unlike its siblings (`PeakNormalizer`, `reference_mode`, #5106). With a numpy scalar `amount` (`dict[str, float]` in `ProcessingParameters` admits `np.float64`), NEP 50 treats it as strongly typed and the blend returns float64. Separately, `ratio` and `amount` are not range-checked: `threshold = 0.8 - (ratio-1)*0.1` goes to 0 at ratio 9 and below 0 above it, and `soft_clip` with a negative threshold maps small samples through `sign*(threshold + ...)`, which inverts their sign.
- **Evidence**: Probe: `apply_clip_blend_compression(float32, {'ratio': np.float64(2.0), 'amount': np.float64(0.5)})` returns float64 (2- and 1-channel and 1-D); `adjust_stereo_width(float32, np.float64(0.8))` returns float64. Probe: input samples `[0.01, 0.1, 0.5]`, `amount=1.0`: ratio 2.5 -> unchanged; ratio 9 -> `[0.007, 0.067, 0.32]`; ratio 12 -> `[-0.095, -0.037, 0.203]` (sign flipped, 0.01 became -0.095).
- **Impact**: Latent. Today ratio is at most 1.8 (fingerprint path) or the constant 2.5 (`mastering_target_generation.py:79`), and `amount` is a Python float, so audio is unaffected. The downstream limiter and `save()` would mask a float64 result, so a regression would show as a cache/dtype mismatch, not as a crash.
- **Siblings**: `adjust_stereo_width_multiband` already casts back (`stereo.py:249`), the plain `adjust_stereo_width` does not.
- **Suggested Fix**: `amount = float(np.clip(comp_params['amount'], 0.0, 1.0))` and clamp `ratio` to the generator's range; cast the result back with `np.asarray(result, dtype=audio.dtype)` in `adjust_stereo_width`.

#### E1-05: HybridProcessor's input contract is not enforced: channels-first input is silently returned unprocessed, integer input fails deep inside with an opaque error, `(N,1)` mono breaks the "(N,2)" contract
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/hybrid_stage_dispatch.py:67-98` (`validate_and_normalize_input`)
- **Status**: NEW
- **Description**: The validator converts only 1-D input to stereo and gates on `shape[0] < MIN_SAMPLES`, dtype is never checked, and channel count is never checked. (a) A librosa-style `(2, N)` array has `shape[0] == 2 < 1024`, so it is "too short" and `target.copy()` is returned unprocessed with only a warning that says "Audio too short ... ~0.0ms", i.e. a silent no-op on a public API (`process_adaptive`, `process_reference` are re-exported from the package). (b) An `int16` array passes validation, runs fingerprinting/analysis and then dies inside `eq_processor` at `np.finfo(audio.dtype)` with `ValueError: data type <class 'numpy.int16'> not inexact`, after the expensive work. (c) The docstring promises "(0, 2) for mono and stereo alike", but a 2-D `(N,1)` mono array (what the backend's `always_2d=True` chunk loader produces) is not widened and comes back `(N,1)`. That works (the stages guard on `shape[1] == 2`), but it is undocumented and the stereo-width stage and phase guard are silently skipped for mono.
- **Evidence**: Probe: `(2, 88200)` float32 -> out `(2, 88200)` with peak 0.4957 (input unchanged, no processing); `(88200,)` -> `(88200, 2)`; `(88200, 1)` -> `(88200, 1)`; `(88200, 6)` -> `(88200, 6)` processed; int16 `(88200, 2)` -> `ValueError ... not inexact`.
- **Impact**: Wrong layout silently yields unmastered audio; wrong dtype yields a confusing late failure. The backend cannot trigger either (it passes `(N, C)` float32), so this is a library-API hardening gap.
- **Siblings**: none.
- **Suggested Fix**: Reject (or transpose with an explicit flag) a 2-D array whose first axis is 8 or fewer while the second is large, reject non-floating dtypes with a clear `ValueError` at the top of `validate_and_normalize_input`, and document that `(N,1)` stays mono.

#### E2-03: Stereo "width" scales are still mixed in three places: generator output, genre profiles, and a hard dead-band
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/parameter_generator_stereo.py:24-53`; `auralis/core/config/genre_profiles.py` + `settings.py:84-90` (`stereo_width` validated 0..2) -> `auralis/core/analysis/target_generator.py:77,108-113` -> `auralis/core/processing/adaptive_mode.py:200-226`; `auralis/core/processing/base/stereo_width_processor.py:105`
- **Status**: NEW (same defect class as closed #4503 and #5553, different sites)
- **Description**:
  1. `calculate_stereo_width` feeds the fingerprint `stereo_width` (side/total energy fraction, 0 = mono) into `current + 0.45*(0.72 - current)` and then returns `0.5 + 0.45*tanh(...)` as a width FACTOR (0.5 = unity side gain, applied as `side *= 2*factor`). The unity point of that mapping is a side-energy fraction of about 0.31, so sources with a side fraction below 0.31 are narrowed (0.10 -> side gain 0.76, 0.20 -> 0.87) and wider ones are widened (0.50 -> 1.19). The `stereo.py` header documents this confusion (scale 3 vs scale 2).
  2. In the hybrid / legacy `AdaptiveMode` chain, `GenreProfile.stereo_width` (defaults 0.6-1.2, validated as 0..2) is passed unchanged as the width factor to `apply_stereo_width_safe`. Probe through `adjust_stereo_width_multiband` on a correlated stereo signal: factor 0.7 -> +2.54 dB side level, 0.8 -> +3.58 dB, 1.0 -> +5.35 dB (documented maximum), ambient 1.2 -> +6.82 dB (beyond the documented 0..1 range; `adjust_stereo_width` has no clamp). Every hybrid-mode job is therefore widened by default regardless of the source.
  3. `apply_stereo_width_safe` skips the whole adjustment while `abs(target_width - 0.5) <= 0.1` and `adjust_stereo_width_multiband` skips it for `abs(width_factor - 0.5) < 0.01`: hard dead-bands, so factor 0.59 gives exactly 0 dB and 0.61 gives about +1.4 dB (the continuous chain eased its other widening gates, #5108).
- **Impact**: Audible, content-independent stereo-image changes in the per-chunk fingerprint path (1) and in hybrid-mode jobs (2); a categorical step (3). The main streaming path (fixed targets, factor 0.5 since #5553) is unaffected.
- **Siblings**: `GenreProfile.__post_init__` accepts `stereo_width` up to 2.0 although the consumer's range is 0..1.
- **Suggested Fix**: Define the generator and the genre table in width-factor units (or convert from side-energy fraction explicitly with an identity point), clamp factors to 0..1 in `adjust_stereo_width*`, and replace the dead-bands by a smooth ramp.

#### E2-04: `ParallelEQUtilities` "too short" fallback is a broadband gain, not "no shaping"
- **Severity**: LOW (offline CLI weight, #4873)
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/dsp/parallel_eq.py:105-109,181-185,259-263`; consumers `auralis/core/stages/sub_bass_control.py:50-55`, `bass_enhancement.py`, `clarity_boost.py`, `presence_enhancement.py`, `mid_warmth.py`, `air_enhancement.py`
- **Status**: NEW (introduced by the #5116 fix; #5736 covers the raw `sosfiltfilt` sites, a different defect)
- **Description**: The three methods extract a band with `sosfiltfilt_safe(..., on_too_short="passthrough")` (the default) and then return `audio + band * (10**(boost_db/20) - 1)`. When the buffer is no longer than scipy's `padlen`, the passthrough makes `band == audio`, so the result is `audio * 10**(boost_db/20)`: the whole signal gets the stage's boost or cut. The comment says the intended degrade is "no shaping applied", and `sosfiltfilt_safe`'s own docstring says band extraction must use `"zeros"`.
- **Evidence**: `ParallelEQUtilities.apply_low_shelf_boost(x, 6.0, 100.0, 44100)` on 8 samples: `np.allclose(y, x * 10**(6/20)) == True`; `apply_bandpass_boost(x, -4.0, 2000, 8000, 44100)` on 14 samples: `np.allclose(y, x * 10**(-4/20)) == True`.
- **Impact**: A final chunk of up to 9 (shelves) / 15 (band-pass) samples gets a full-band +/-boost instead of nothing (for example the sub-bass cut becomes a broadband cut, a bass boost a +6 dB gain). Masked today because other stages still raise on such a chunk (#5736); it becomes live as soon as that is fixed.
- **Siblings**: all `ParallelEQUtilities` callers above (the HP branch in `sub_bass_control.py:80-90` is correct: it filters in place, so passthrough really means no shaping).
- **Suggested Fix**: Pass `on_too_short="zeros"` at the three band-extraction sites in `parallel_eq.py` (so `diff == 0`), and add a test with 5- and 12-sample buffers asserting identity.

#### E2-05: Dynamics tilt guard picks its driver with a hard `abs()` comparison, so the correction flips sign across a tie
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_stages.py:162-185` (selection at `:168`)
- **Status**: NEW
- **Description**: `dominant_shift = bass_shift if abs(bass_shift) >= abs(high_shift) else -high_shift`. When bass and high energy fractions move in the SAME direction (mid fraction dropping), the sign of the correction depends on which magnitude is larger. #4860 smoothed the trigger knee but left this selector.
- **Evidence**: with the shipped knee and cap: `bass_shift=0.1200, high_shift=0.1199 -> -0.941 dB`; `high_shift=0.1201 -> +0.943 dB`; at 0.20: `-2.000` vs `+2.000 dB`.
- **Impact**: A 0.0002 difference in measured band shift flips a spectral tilt of up to +/-2 dB (low shelf cut + high boost, or the reverse). Needs both bass and high fractions to shift the same way by more than about 5%, so it is uncommon; the discontinuity is exactly what the continuous-space design forbids.
- **Siblings**: none.
- **Suggested Fix**: Use a smooth combination such as `(bass_shift - high_shift) / 2` (tilt = difference of the two shifts), which is continuous and still zero when both move together.

#### E2-06: More config fields with no reader, and DSP constants that shadow them
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:40-43,113` (`EQSettings.smoothing_factor`, `masking_threshold_db`, `PsychoacousticEQ.perceptual_weighting`); `auralis/dsp/eq/masking.py:40,59` (hardcoded `-60.0` / `-80.0`); `auralis/core/config/unified_config.py:31-33,43-45` (`max_length`, `temp_folder`); `auralis/core/config/settings.py` (`enable_genre_detection`)
- **Status**: NEW (sibling of #5576, which lists a different field set; #4226 removed only `EQSettings.overlap`)
- **Description**: grep over `auralis/` and `auralis-web/backend` finds no reader for: `EQSettings.smoothing_factor` (the active smoothing knob is `adaptation_speed`), `EQSettings.masking_threshold_db` (the masking calculator hardcodes `-60.0` default and `-80.0` floor: the inverse bug), the `PsychoacousticEQ.perceptual_weighting` array (computed per instance, never used), `UnifiedConfig.max_length`, `UnifiedConfig.temp_folder`. `AdaptiveConfig.enable_genre_detection` is only echoed by `HybridProcessor.get_processing_info()`; `ContentAnalyzer` always classifies, so setting it to False changes nothing.
- **Impact**: Tuning these has no audible effect; an API or UI that shows them is misleading.
- **Siblings**: #5576 (generated parameters, `UnifiedConfig.limiter`, `AdaptiveConfig.chunk_size_ms`, `latency_budget_ms`).
- **Suggested Fix**: Delete the unread fields (as #5302 did) or wire them: derive the masking floor from `masking_threshold_db`.

#### E2-07: `ProcessingCoordinates.energy_level` has no consumer, and the whole `PreferenceVector` bias machinery only ever sees neutral input
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_space.py:36-55,188-200`, `parameter_generator.py:108-141`, `parameter_generator_dynamics.py`, `parameter_generator_eq.py`, `parameter_generator_stereo.py`
- **Status**: NEW
- **Description**: The continuous space advertises three axes. In the live generator `dynamic_range` drives dynamics/loudness, `spectral_balance` contributes only `0.04 * (spectral_balance - 0.5)` to stereo width (+/-0.02), and `energy_level` is read nowhere: `grep -rn "\.energy_level"` hits only `_apply_preference_bias` and `__str__`. Target LUFS and EQ use fingerprint fields directly. `PreferenceVector.from_preset_name` can only return the all-zero vector (only `'adaptive'` exists), so `_apply_preference_bias`, every `if preference:` branch and the `bass_boost`, `treble_boost`, `stereo_bias`, `loudness_bias` terms are dead; `generate_parameters` still clips the coordinates through `np.clip` every call.
- **Evidence**: parameter sweeps of `crest_db`, `lufs`, `bass_pct`, `air_pct`, `stereo_width` through `ProcessingSpaceMapper` + `ContinuousParameterGenerator`: no parameter responds to the energy axis; the only non-monotonic outputs are the documented bells (`compression ratio/amount`, `eq_blend`).
- **Impact**: One third of the advertised coordinate space is decorative, and the reachability checklist item ("a parameter must be read on the path that claims to honor it") fails for the coordinate and for the preference biases. No audio defect.
- **Siblings**: #5576.
- **Suggested Fix**: Either drive `calculate_target_lufs` / `eq_blend` from `energy_level` (it is the calibrated, bounded form of the same fingerprint field) or remove the axis and the dead preference branches.

#### E2-08: Profiler is write-only, and its `total_calls` is wrong after 1000 calls
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/optimization/profiling/performance_profiler.py:22-70`, `auralis/optimization/performance_optimizer.py:39-41`, `auralis/core/hybrid_setup.py:150-185`
- **Status**: NEW
- **Description**: The live wrapper is correct (verified: `functools.wraps`, result and exception preserved via `try/finally`, sample count untouched, records under an `RLock`, idempotent via `AdaptiveMode._optimized`, double-checked singleton). Defects around it: (a) `get_optimization_stats()` / `get_performance_report()` have no caller anywhere (not in the backend, not in tests); `PerformanceProfiler.memory_usage` is never written; `counters` is never reported. (b) `timings[func]` is trimmed from 1000 to 500 entries and the report computes `'total_calls': len(times)` and `'total_time_ms': sum(times)` from the trimmed window: 1500 calls report 999. (c) The wrapped `AdaptiveMode.process` is not on the shipped adaptive/streaming path (`_process_adaptive_mode` calls `ContinuousMode.process`); it runs only for `mode="hybrid"` jobs.
- **Impact**: None on audio. Misleading statistics if anyone wires the report up, and per-call lock traffic for data nothing reads.
- **Siblings**: none.
- **Suggested Fix**: Report `self.counters[f"{name}_calls"]` for `total_calls`, or delete the report, `memory_usage` and the optimizer wrapper together.

#### E2-09: Hybrid mode analyses the content twice per job and discards the first result
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/hybrid_mode.py:58-74,76-112`, `auralis/core/processing/adaptive_mode.py:77`
- **Status**: NEW
- **Description**: `HybridMode.process` calls `self.content_analyzer.analyze_content(target_audio)` (tempo estimate, ML genre classification, 25D Rust fingerprint) and passes the result to `_apply_hybrid_processing`, which never reads `content_profile`. The very next call, `self.adaptive_processor.process(...)`, runs `analyze_content` again. The no-reference fallback branch has the same duplicate.
- **Impact**: Roughly doubles the analysis cost of every hybrid-mode job for no output change.
- **Siblings**: none.
- **Suggested Fix**: Drop the first call and the unused parameter (or pass the profile into `AdaptiveMode.process`).

#### E2-10: `UnifiedConfig` validates with `assert` (gone under `-O`), and `from_dict` mutates the caller's dict
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/config/unified_config.py:51,56,60`, `settings.py` (18 asserts in `auralis/core/config/`), `unified_config.py:184-203`
- **Status**: NEW (sibling of open #5737; the same "raise, not assert" rule was applied to the processing path in #5511/#5533)
- **Description**: `internal_sample_rate`, `max_length`, `fft_size`, `adaptation_strength`, `chunk_size_ms` and the genre-profile ranges are checked only by `assert`. `UnifiedConfig.from_dict` also calls `config_dict.pop(key)` on its argument, so the caller's dict is emptied of the adaptive keys (it has no production caller, only tests).
- **Evidence**: `python -O`: `UnifiedConfig(internal_sample_rate=-5, fft_size=1000, max_length=-1)` constructs fine; `AdaptiveConfig(adaptation_strength=7.0, chunk_size_ms=1.0)` is accepted. Normal run: `d = cfg.to_dict(); UnifiedConfig.from_dict(d)` leaves `d` with only `internal_sample_rate`, `max_length`, `fft_size`.
- **Impact**: Under an optimized interpreter an invalid rate or non power-of-two FFT size reaches the DSP (only `EQSettings` re-checks evenness). Low reach.
- **Siblings**: #5737.
- **Suggested Fix**: Replace the asserts with `ValueError` raises and copy the dict in `from_dict`.

#### E3-02: `cleanup()` cannot abort an in-flight auto-advance, so it re-populates `audio_data` after `clear_all()` (the #3727 fix is entry-only)
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/player_streaming_mixin.py:146-185`; `auralis/player/enhanced_audio_player.py:254-297`; `auralis/player/gapless_playback_engine.py:122-240`
- **Status**: Regression of #3727 (closed; the fix is present but ineffective for the case it targets)
- **Description**: #3727 added `_cleanup_in_progress` so "a thread that outlives the join timeout still aborts before swapping audio_data". The flag is checked once, at the top of `_auto_advance_next`, before `next_track()`. A thread already inside `advance_with_prebuffer` (blocking decode, no lock held) never re-checks it. After `cleanup()`'s 2 s join times out it clears the player, and the advance then commits the queue advance and installs the decoded track into the cleaned player. It also calls `_schedule_fingerprint_load()`, which spawns a thread after `fingerprint_service.close()`.
- **Evidence**: Probe: `gapless._load_audio` replaced with a 3.5 s sleep, `_auto_advance_next` started in a thread, `cleanup()` called 0.3 s later. It took 2.0 s (join timeout), and `audio_data is None` right after `cleanup()`. After the thread finished, `audio_data` was loaded again, `current_file == '/etc/passwd'`, and `queue.current_index == 1`.
- **Impact**: At shutdown or test teardown the player holds a whole decoded track (40 MB to over 1 GB for long files) and a live fingerprint thread after `cleanup()` returned. This breaks the documented "audio_data is None after cleanup()" invariant for any track whose decode exceeds 2 s.
- **Siblings**: `previous_track()` and `load_file()` called from other threads have no cleanup guard either. `start_prebuffering()` is guarded by `_shutdown`.
- **Suggested Fix**: Check `_cleanup_in_progress` (or `_stop_requested`) inside `advance_with_prebuffer` after the blocking load and before `advance_if_next_matches`/the swap, for example via an `abort` predicate argument. Alternatively gate the swap in `_on_swap`.

#### E3-03: Previous track's fingerprint, adaptive params and DSP state stay active after a track change until the new fingerprint resolves
- **Severity**: LOW (dormant in the shipped backend: `enable_auto_mastering=False`, so `set_fingerprint` returns immediately)
- **Dimension**: Player State
- **Location**: `auralis/player/fingerprint_loader_mixin.py:355-381`; `auralis/player/realtime/processor.py:91-106`; `auralis/player/realtime/auto_master.py:215-235,285-363`; `auralis/player/realtime/level_matcher.py:69-82`
- **Status**: NEW (adjacent closed issues: #3463 scheduling after next_track, #4951 clear on failure, #3445 generation guard. None covers the interval before resolution.)
- **Description**: `_schedule_fingerprint_load()` bumps the generation and starts a loader thread but never clears the processor. `RealtimeProcessor.set_fingerprint()` is only called when `get_or_compute()` returns (or fails). On a cache miss that is a full 25D analysis. Until then `AutoMasterProcessor.adaptive_params` (makeup gain, compression ratio, target-peak ceiling) and the transient-enhancer gate (`self.fingerprint`) from the previous track keep shaping the new track. Nothing resets the compressor envelope, level-matcher `current_target_rms` or gain smoother on track change, seek or stop. `reset_all_effects()` runs only in `cleanup()`.
- **Evidence**: Read: `_schedule_fingerprint_load` only does `_track_generation += 1` then spawns a thread. `processor.set_fingerprint` is reached only from `_load_fingerprint_for_file` after `get_or_compute()` returns. `AutoMasterProcessor.process` reads `self.adaptive_params` on every chunk.
- **Impact**: With auto-mastering enabled, the first seconds (up to the analysis time) of each uncached track get the previous track's gain and ceiling, for example +6 dB makeup tuned for a quiet track applied to a loud one. The peak ceiling bounds clipping, but the loudness jump is audible.
- **Siblings**: `previous_track()`, `next_track()`, `load_file()` and `load_track_from_library()` all schedule through the same function.
- **Suggested Fix**: Inside the track-swap critical section (or at the top of `_schedule_fingerprint_load`) call `processor.set_fingerprint(None)` and reset stateful DSP (compressor, level-matcher smoother). Let the loader install the new fingerprint when it resolves.

#### E3-04: Playback state events are dispatched after the lock is released with no ordering, so concurrent transitions can deliver stale events last
- **Severity**: LOW (no production listener: the backend registers no engine callbacks)
- **Dimension**: Player State
- **Location**: `auralis/player/playback_controller.py:118-140,142-204`
- **Status**: NEW
- **Description**: Each mutator snapshots `state_info` under `_lock`, releases it (the #2291 deadlock fix), then calls `_notify_callbacks`. Two threads' dispatches can interleave in either order. Example: T1 `play()` transitions then is preempted, T2 `pause()` transitions and dispatches `pause`, then T1 dispatches `play`. An observer's last event says `play` while `state == PAUSED`. The event payload carries the transition-time `state`, not a version. `IntegrationManager._on_playback_state_change` enriches `position_seconds` and others at dispatch time but keeps the stale `state`/`action`. `defer_notifications()` preserves order only within one thread.
- **Evidence**: `play()`/`pause()`/`stop()`/`seek()`/`load_and_stop()`/`set_error()` all follow `with self._lock: ...; state_info = {...}` then `self._notify_callbacks(state_info)` outside the lock. There is no sequence number or dispatch lock.
- **Impact**: Any engine consumer that mirrors state from the last callback (UI synchroniser) can display a stale play/pause/stop state until the next event. Typical triggers are transport commands racing the auto-advance thread (`_auto_advance_next` calls `playback.stop()`/`play()`).
- **Siblings**: `IntegrationManager._notify_callbacks` has the same lock-free dispatch; the `playback_finished` and `file_loaded` events are also unordered against state events.
- **Suggested Fix**: Add a monotonic `seq` to `state_info` assigned under `_lock`, or serialise dispatch with a dedicated dispatch lock acquired before releasing `_lock`.

#### E3-05: Prebuffer re-arm can be lost when a queue edit lands between the worker's final re-peek and its exit
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/gapless_prebuffer.py:329-365,435-451,519-540`
- **Status**: NEW (the #5583 fix covers edits during the blocking decode, not this window)
- **Description**: `on_queue_changed()` re-arms via `start_prebuffering()`, which is a no-op while the previous worker thread is alive. The worker validates with `latest = peek_next_track()` and stores the buffer under `update_lock` afterwards, then logs and returns, so it stays alive for a short time. An edit that changes the next track inside that interval does this: its `on_queue_changed` sees no matching buffer, clears it, calls `start_prebuffering()` and is told "already running". The worker then stores the now-stale buffer (or has already exited) and nothing re-arms. The next `advance_with_prebuffer` discards the buffer and falls back to a blocking decode.
- **Evidence**: Sequence (worker W, editor E): W `latest = peek` (X, matches) -> E edits so next = Y -> E `on_queue_changed`: `peek` = Y, buffer None, `start_prebuffering()` sees `W.is_alive()` and returns -> W stores X -> W exits. Result: `next_track_info = X`, next = Y, no worker. The match check and the store are two separate critical sections.
- **Impact**: One non-gapless transition (blocking decode plus the E3-01 style silence) after an edit-while-prebuffering race. The window is microseconds to the length of the final `info()` log call, so it is rare.
- **Siblings**: Same pattern if a worker returns on "No next track to prebuffer" just before an `add_track`.
- **Suggested Fix**: Do the final match and the store in one `update_lock` section, and have the worker re-check once after clearing its own liveness (for example a `_rearm_requested` flag set by `start_prebuffering()` when it sees a live worker).

#### E3-06: `AudioPlayer.seek()` / `position` setter raise `OverflowError` for huge finite positions
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:217` and `:248-250`
- **Status**: NEW
- **Description**: `int(position_seconds * sample_rate)` is evaluated before the clamp. For a finite `position_seconds` above about 4e303, the product overflows to `inf` and `int(inf)` raises. `SeekRequest` rejects NaN and Inf but not large finite values (#4681 deliberately has no upper bound). The route's duration check is skipped when `state.duration == 0`, and `test_seek_overflow_protection` documents that such seeks are "passed straight through to the engine, which does not itself reject an out-of-range position".
- **Evidence**: Probe: loaded player, `seek(1e308)` raised `OverflowError: cannot convert float infinity to integer`; `seek(1e300)` returned True and clamped `position == 1000`. The exception propagates out of `with defer_notifications(), _audio_lock` (the locks are released), up through `PlaybackService.seek` to a 500.
- **Impact**: A client request produces a 500 and a stack trace instead of a clamp. No state corruption.
- **Siblings**: The `position` setter (`:248-250`) calls `playback.seek` with the caller's int and is unaffected; only the float-to-sample conversion path matters.
- **Suggested Fix**: Clamp in the float domain: `min(max(position_seconds, 0.0), total/sample_rate) * sample_rate` before `int()`.

#### E3-07: End-of-queue `playback_finished` is emitted unconditionally, even if `stop()` found the state already changed
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/player_streaming_mixin.py:125-138`
- **Status**: NEW
- **Description**: After releasing `_audio_lock` the end-of-queue branch calls `self.playback.stop()` and then sends `playback_finished` regardless of the return value. The comment says "the stop and the notification fire exactly once". That holds only for a single serial caller. If a user `stop()` (or a second `get_audio_chunk` caller, which the level-matcher comment describes as a prefetch/lookahead thread) transitions first, `playback.stop()` returns False but the finished event still goes out. A concurrent second caller passes the `is_playing()` gate under the lock before the first has stopped, and also sends a duplicate.
- **Evidence**: Code: `self.playback.stop()` result is discarded and `self.integration._notify_callbacks({'action': 'playback_finished', ...})` follows unguarded.
- **Impact**: A spurious or duplicate `playback_finished` that consumers can treat as the queue completing (history, "next album" logic).
- **Siblings**: `_auto_advance_next`'s `except` branch also calls `playback.stop()` and ignores the result, but emits nothing.
- **Suggested Fix**: `if self.playback.stop(): self.integration._notify_callbacks(...)`.

#### E3-08: `NavigationService.jump_to_track` depends on `QueueController.set_current_index`, which does not exist
- **Severity**: LOW (the method has no router or WebSocket caller today, so it is currently unreachable)
- **Dimension**: Player State
- **Location**: `auralis-web/backend/services/navigation_service.py:292-303`; `auralis/player/queue_controller.py` (no jump API); `auralis/player/components/queue_navigation.py:429-443` (`set_track_by_index`, not exposed)
- **Status**: NEW
- **Description**: `jump_to_track` guards on `hasattr(queue_manager, 'set_current_index')` where `queue_manager = audio_player.queue` is a `QueueController`. The controller exposes `current_index` (property) and, on the inner `QueueManager`, `set_track_by_index`, but no `set_current_index`. The guard is therefore always False on the real player, and the else branch runs: `track_path = queue[track_index]` is a queue-entry dict, which is passed to `audio_player.load_file()`. `AudioFileManager.load_file` swallows the `TypeError` from `Path(dict)`, returns False and `load_file` calls `set_error()`. `current_index` never moves and `play()` is rejected in ERROR. The tests pass because `MagicMock` satisfies `hasattr`.
- **Evidence**: `grep -rn set_current_index auralis auralis-web` returns only the two lines in `navigation_service.py`. `grep -n jump_to_track` finds no router caller.
- **Impact**: If the endpoint is wired up, jumping within the queue fails and wedges the player in ERROR. Today it is latent dead code with a phantom engine API.
- **Siblings**: Also covered by #5725 (a failed load forces ERROR), which turns this failure into a stuck state.
- **Suggested Fix**: Add a bounds-checked `QueueController.set_track_by_index()` (locked, then `_notify_changed()`) and have `jump_to_track` call it and then `load_file` the entry's `filepath`. Otherwise delete the method.

#### E4-03: ID3 multi-valued text frames are stored as one NUL-joined string in title/artist/genre
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/library/scanner/metadata_extractor.py:~154-157` and `:~173-176` (`str(value)` on an ID3 `TextFrame`); same pattern in `auralis/library/metadata_editor/readers.py:48`
- **Status**: NEW (the open #5732 covers only the Vorbis `value[0]` truncation and the unbounded track number, not ID3)
- **Description**: `extract_metadata` collapses only plain `list` values. An ID3 `TextFrame` is not a `list`, so it reaches `_normalize_field_value`, where `str(value)` is mutagen's `'\x00'.join(frame.text)`. An ID3v2.4 file with several artists, titles or genres therefore yields a single string with an embedded NUL. `audio_info_to_track_info` then passes it to `parse_featured_artists`, which does not split on NUL.
- **Evidence**: An MP3 with `TPE1=['X','Y']`, `TIT2=['A','B']` and `TCON='(17)'` gave `extract_metadata_from_file -> {'title': 'A\x00B', 'artist': 'X\x00Y', 'genre': 'Rock', ...}`. The artist `"X\x00Y"` becomes one Artist row with an embedded NUL.
- **Impact**: Artist rows with embedded NULs break dedup and grouping against the same artist tagged singly. They also break search, and display garbled or are dropped by clients that treat NUL as a terminator. Multi-artist v2.4 tagging is common (MusicBrainz Picard and similar tools).
- **Siblings**: The M4A/Vorbis list case is #5732 (value[0]). `readers.read_mp3_metadata` has the same NUL-joined string, which the edit dialog shows and writes back.
- **Suggested Fix**: For ID3 frames, read `frame.text` (a list) instead of `str(frame)`. Then share one list-aware path with the #5732 fix, so artist/genre keep every value and title takes the first.

#### E4-04: Library scan probes MP3/OGG/OPUS with libsndfile while playback decodes with FFmpeg, so stored duration and format disagree with the decoder (and `.opus` is stored as "OGG")
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/library/scanner/audio_analyzer.py:58-75` (`sf.info()` tried first for every extension, ffprobe only on exception); routing contrast `auralis/io/formats.py:23-30` and `auralis/io/unified_loader.py:96-100` (`FFMPEG_FORMATS` decode and `get_audio_info` use FFmpeg/ffprobe)
- **Status**: NEW
- **Description**: The loader and `get_audio_info` route `.mp3/.ogg/.opus` through FFmpeg/ffprobe by extension. `AudioAnalyzer.extract_audio_info` instead calls `sf.info()` for everything. With the pinned soundfile 0.14.0 (bundled libsndfile 1.2.2, which has MP3 and Opus-in-Ogg support), `sf.info()` succeeds for those formats. The ffprobe fallback therefore only runs for M4A/AAC/WMA. The scan stores libsndfile's duration and `info.format`. These come from different probes than the ones the decoder uses. The stored value also depends on the libsndfile build (an older libsndfile would take the ffprobe path).
- **Evidence**: Scan versus actual decode of the same files:

  | File | Scan (libsndfile) | Decoded (FFmpeg) |
  |---|---|---|
  | VBR MP3 without Xing | 3.0444 s | 3.0302 s |
  | `w.opus` | format `'OGG'` | decoded length 1.0 s |
  | `w.m4a` | `'M4A'` (ffprobe path) | n/a |

  An `.opus` track is stored as format `OGG`, but the same file through `get_audio_info` reports `OPUS`.
- **Impact**: Stored `duration` can exceed the number of decodable samples by tens of milliseconds, which feeds `content_chunk_count()` and seek geometry (the #5312 clamps contain the damage). The format column is inconsistent (`OGG` for Opus). The same file reports different durations on different machines. Low severity, because the differences are small.
- **Siblings**: `auralis/library/repositories/track_repository_lifecycle.py:~148-156` has the same `sf.info()`-first fallback when a caller passes no format/rate.
- **Suggested Fix**: Make the scanner use the loader's routing (`unified_loader.get_audio_info` or `extension in FFMPEG_FORMATS` then `_probe_audio`), and call `sf.info` only for `SOUNDFILE_FORMATS`. Take `format` from `formats.SUPPORTED_FORMATS`.

#### E5-01: auto_master folder mode names every output `<stem>_mastered.flac`, so same-stem inputs silently overwrite each other
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auto_master.py:78-81, 98-111`
- **Status**: NEW
- **Description**: Output name is `output_path / relative_path.parent / f"{relative_path.stem}_mastered.flac"`: the source suffix is dropped. `audio_files` is the union of six extensions, so `Track.flac`, `Track.mp3` and `Track.wav` in one folder (a common layout: lossless rip plus converted copy) all map to the same `Track_mastered.flac`. Each is rendered in sorted order, each one's `os.replace` (atomic, #5109) replaces the previous master, each counts toward `success_count`, and nothing is reported.
- **Evidence**: `sorted(set(audio_files))` keeps all three; `output_file = ... / f"{relative_path.stem}_mastered.flac"`; no existence/collision check; `success_count += 1` unconditionally after `master_single_file` returns.
- **Impact**: Silent loss of all but the last-sorted master per stem, wasted render time, and a "Completed: 3/3" summary that is wrong about what is on disk. Sources are untouched (this is not #5696).
- **Siblings**: Single-file mode (`-o` identical for two runs) is the user's own choice; only folder mode derives names.
- **Suggested Fix**: Build the name from the full source filename (`Track.mp3` -> `Track.mp3_mastered.flac`, or keep the suffix before `_mastered`), or detect a duplicate target before rendering and record it in `failed`.

#### E5-02: auto_master folder mode exits 0 when some files failed
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auto_master.py:183-185` (result built at :133-138)
- **Status**: NEW
- **Description**: `master_folder` deliberately continues past a failing file and returns `failed` (e.g. the tiny-final-chunk ValueError of #5736 or the `AttributeError` of #5710 land here), but `main()` only returns 1 when `result["count"] == 0`. Any batch with at least one success exits 0 whatever `result["failed"]` holds. The failures exist only as console text, which `-q` suppresses entirely.
- **Evidence**: `if result["count"] == 0: return 1` / `return 0`; `-q` passes `quiet=True` so the "Failed files" block at :127-130 never prints.
- **Impact**: A script or cron job running `auto_master.py dir/ -q` cannot detect partially failed batches; the failed tracks have no master and no signal.
- **Siblings**: none.
- **Suggested Fix**: Return non-zero when `result["failed"]` is non-empty (and print failures to stderr even under `-q`).

#### E5-03: `--intensity` is never validated; out-of-range values reach the stages and NaN aborts deep inside chunk 0
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auto_master.py:147-148` (argparse `type=float`, help says "0.0-1.0"); consumed at `auralis/core/mastering_process_chunk.py:90` (`calculate_intensity(intensity, ...)`)
- **Status**: NEW
- **Description**: No clamp or range check exists in argparse, `master_file`, `process_chunks` or `calculate_intensity`. `-i 20` becomes effective intensity 17.5 and `-i -1` becomes -0.88 (both accepted and rendered), and `-i nan` / `-i inf` only fail after fingerprinting, notch detection and the peak scan, inside chunk 0, with a message that points at DSP rather than the argument.
- **Evidence**: Probe `pipe._process(..., intensity=v)`: 20.0 -> `effective_intensity` 17.51, rendered; -1.0 -> -0.875, rendered; nan and inf -> `ModuleError: NaN or Inf values detected in audio in SimpleMastering continuous path after low-end/warmth`.
- **Impact**: Mistyped intensity silently produces an over- or inverse-processed master, or a late misleading failure.
- **Siblings**: none.
- **Suggested Fix**: Validate once at the CLI boundary (argparse `type` function rejecting non-finite and outside [0, 1]) and clamp in `master_file` for library callers.

#### E5-04: Mono sources are loudness-measured as one channel but rendered as dual-mono, so `_source_lufs` is 3 LU low
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_prepare.py:148-159` (window read as 1-D for mono) and `34-75` (`measure_window_loudness`); the render side is `auralis/core/mastering_chunk_assembly.py:50-51` (`np.stack([chunk, chunk])`)
- **Status**: NEW
- **Description**: `prepare_file` measures BS.1770 loudness on the raw `sf.read` window, which is 1-D for a mono file. BS.1770 sums channel power, so a lone channel reads 3 LU lower than the same signal on two channels. The chunk loop then renders the file as dual-mono stereo (`read_chunk`, #4494), whose real loudness is 3 LU higher than what was measured. `_source_lufs` drives the loudness maximizer's gap (`LOUDNESS_TARGET_LUFS - source_lufs`), so mono sources get a larger push than the identical content stored as 2-channel dual-mono.
- **Evidence**: `measure_window_loudness` on one 440 Hz tone: mono 1-D -17.66 LUFS, stereo of the same channel -14.65. Full `process_chunks` render of identical 12 s material: mono file `_source_lufs` -15.63, output RMS -14.02 dBFS; dual-mono stereo file `_source_lufs` -12.62, output RMS -14.53 dBFS (0.5 dB louder, more limited, from a pure container difference).
- **Impact**: Mono masters come out about 0.5 dB louder (and correspondingly lower crest) than the same material as stereo; small, but it is inconsistent treatment of identical audio.
- **Siblings**: `fingerprint['lufs']` (RMS proxy) feeds `calculate_intensity` and makeup gain from whatever the fingerprint service measured; not checked for the same channel convention (Dimension 6).
- **Suggested Fix**: Expand a 1-D/single-channel window to two channels (same as `read_chunk`) before `measure_window_loudness`, so the measurement describes the audio that is actually rendered.

#### E5-05: When the remainder is shorter than the crossfade, the final seam is a cold-started render with a crossfade shorter than #5339 requires
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:160-166`, `auralis/core/mastering_chunk_assembly.py:40-41, 151-177`; guard being bypassed: `auralis/core/mastering_config.py:88-102`
- **Status**: NEW (same root cause as open #5736 — a redundant final chunk — but a different, audible effect)
- **Description**: For the second-to-last chunk, `overlap_after = min(crossfade, remaining)` makes its tail cover the entire remainder, then the loop renders that remainder again as a separate last chunk with no left context. `head_len = min(prev_tail, chunk)` becomes the remainder length r, so the effective crossfade is r, not `CROSSFADE_DURATION_SEC`. #5339's guarantee (crossfade >= 20x the slowest per-chunk-reset envelope, i.e. 1.2 s) therefore does not hold for any file whose `total_frames % chunk_size` is below 1.2 s (about 4 % of files; remainders under 0.5 s are about 1.7 %). The warm rendering (second-to-last chunk's tail) is faded out and the cold-start rendering (fresh limiter, transient-shaper envelopes, zero-phase filter edges) wins at the end of the file.
- **Evidence**: Chunked (30 s) vs whole-file render of the same synthetic track, residual over the final remainder (RMS relative to signal): r = 5 s -96.7 dB, 1.5 s -79.7 dB, 0.5 s -57.4 dB (max |diff| 0.0010), 0.2 s -38.9 dB (0.0059), 0.05 s -24.0 dB (max |diff| 0.044 on a 0.9-peak signal). Pre-seam region is bit-identical in all cases.
- **Impact**: The last fraction of a second of an affected master differs from a continuous render by up to about -24 dB (very short remainders); inaudible for r > 0.2 s, small but real for tiny ones. Same condition makes remainders of 1-15 samples crash the render (#5736).
- **Siblings**: #5736 (tiny final chunk raises in raw `sosfiltfilt`); #5737 (guard is an `assert`, lower bound only).
- **Suggested Fix**: Fold a remainder that is <= `crossfade_samples` into the previous chunk (extend its core to EOF and emit no tail) instead of rendering it as its own chunk; this also removes the #5736 crash path.

#### E6-04: `FingerprintExtractionQueue.stop()` then `start()` is a silent no-op (library reset leaves the batch pool dead)
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/services/fingerprint_queue.py:105,155-171,184,222,246`; restart driver `auralis-web/backend/config/background_workers.py:start_background_workers` called from `auralis-web/backend/routers/library.py:163`
- **Status**: NEW
- **Description**: `stop()` sets `self.should_stop = True` and nothing ever clears it; `start()` neither resets it nor clears `self.workers`. The library-reset endpoint stops every registered worker, resets, then calls `worker.start()` on the same instance ("Always restart the workers we paused"). The new threads see `should_stop` already true and exit at the first `while not self.should_stop` check.
- **Evidence**: With a stub scheduler holding one pending track, `await q.start(); await q.stop(); await q.start()` -> new workers alive 0, `extract_and_store` calls 0, track still unclaimed; `len(q.workers)` grows to 4 (2 dead + 2 dead). The on-demand queue (`analysis/fingerprint_queue.py`) is task based and restartable, so post-reset scans are still served; only this pool is lost.
- **Impact**: After a library reset the batch pool never runs again until the app restarts: Phase 2 (re-fingerprint after a `FINGERPRINT_ALGORITHM_VERSION` bump) and `on_drained` (reference-cloud refresh) never fire, and `stats`/`workers` report a pool that does nothing.
- **Siblings**: `_on_worker_drained()` is called after Phase 1 (`fingerprint_queue.py:238`) and again after Phase 2 (`:261`) per worker, so `_drained_workers` reaches `len(self.workers)` when only half the workers have finished Phase 1 and `on_drained` fires while the others are still extracting; counters then reset. Count it once per worker.
- **Suggested Fix**: Reset `should_stop` (and `self.workers`) at the top of `start()`; use a `threading.Event` for the flag; make `_on_worker_drained` fire once per worker.

#### E6-05: `FingerprintExtractionQueue.stop()` is `async def` but joins worker threads synchronously on the event loop
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/services/fingerprint_queue.py:173-205` (`worker.join(timeout=remaining)` inside `async def stop`)
- **Status**: NEW (sibling of closed #4775, `LibraryAutoScanner._stop_watchdog` blocking on `Observer.join`, rated MEDIUM at a 5 s bound)
- **Description**: `stop()` is awaited from `stop_background_workers` (lifespan shutdown and `POST /api/library/reset`). Each join blocks the loop for as long as that worker is inside `_extract_bounded` (a decode + ~1 s of DSP, up to `track_timeout` = 600 s), capped by the 30 s overall timeout. The monitor stop (`monitor.stop()` -> `Thread.join(5.0)`) is also synchronous.
- **Evidence**: Code path above; `background_workers.py:WORKER_STOP_KWARGS` passes `timeout=30.0`, i.e. the loop can be frozen up to 30 s while the reset request holds the scan slot. No `asyncio.to_thread` anywhere in `stop()`.
- **Impact**: WebSocket pings and every other request stall while a library reset or shutdown waits on busy workers.
- **Siblings**: `AdaptiveResourceMonitor.stop()` (`library/resource_monitor.py:84-92`).
- **Suggested Fix**: `await asyncio.to_thread(self._join_workers, timeout)` (and the monitor stop likewise).

#### E6-06: `AdaptiveResourceMonitor` starts with semaphore size 4 while the real semaphore starts at `max(8, max_workers)`; first tick throttles the pool
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/library/resource_monitor.py:61,160-185`; `auralis/services/fingerprint_queue_scaling.py:56-58,72`
- **Status**: NEW (callbacks-under-lock in the same class is Existing #5756)
- **Description**: The monitor tracks its own `current_semaphore_size = 4` and only emits a change relative to that value. The queue's semaphore is built at `max(8, max_workers)` (up to 2x CPU cores). With RAM < 50 % at the first tick (the normal case) the monitor computes 5 and `_on_semaphore_change(5)` calls `processing_semaphore.resize(5)`, cutting capacity from e.g. 32 to 5, and then only climbs +1 per 2 s while RAM stays < 50 %. Once 16+ workers raise RAM into the 50-80 % band the ramp stops wherever it is and the semaphore stays below the worker count. Conversely, in the 50-80 % band from the start nothing is ever resized, so the "memory-aware" limit does not engage until RAM > 80 %.
- **Evidence**: Arithmetic from the two constants above (`min(4+1, max_semaphore)` -> 5) and `_on_semaphore_change` applying the value verbatim.
- **Impact**: Throughput of the startup fingerprint backlog is capped by a number unrelated to the configured pool; the intended memory guard is only reactive. No correctness effect.
- **Suggested Fix**: Seed `current_semaphore_size` from the real capacity (pass it to the monitor or `limits.initial_semaphore`).

#### E6-07: Probe correction mixes a -70 sentinel into the median for the body window only
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/windowed_compute.py:117-144` (`_apply_probe_correction`, `_rms_lufs_crest` returns `(-70.0, 0.0)` for silence)
- **Status**: NEW
- **Description**: The body window's `(lufs, crest)` is always appended; probes are appended only if `probe_lufs > -70.0`. A silent body therefore contributes the sentinel `-70.0 / 0.0` as if it were a measurement, and a single valid probe is enough to pass `len(all_lufs) >= 2`. Conversely a very quiet but non-silent probe (< -70 dB) is dropped as "silent". The whole function is wrapped in `except Exception: pass` with no log.
- **Evidence**: `_apply_probe_correction({'lufs': -120.0, 'crest_db': 0.0}, silent_body, [loud_probe, silent_probe])` -> `lufs = -42.34`, `crest_db = 7.29` (mean of the sentinel and the one real probe); a probe at -75.7 LUFS is skipped.
- **Impact**: A track whose 50 % window is silent (hidden-track gaps, album-length rips) is stored with a LUFS about 28 dB too low; low probability, persisted value.
- **Suggested Fix**: Treat all three windows symmetrically (drop windows at/below the silence floor, including the body) and log when the correction is skipped or raises.

#### E6-08: ML genre features use only the first 4096 samples (about 93 ms) of the input
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/ml/feature_extractor.py:129-170,184-205` (`audio[:4096]` in `_spectral_bandwidth/_contrast/_flatness/_energy_distribution/_extract_mfcc/_extract_chroma`; `audio[:8192]` in `_harmonic_ratio/_fundamental_frequency`)
- **Status**: NEW (Related #5746 channels-first bug and #5244 hard-coded 44.1 kHz; this is independent of both and survives fixing them)
- **Description**: `extract_features` receives the whole track in the hybrid/adaptive paths (`ContentAnalyzer.analyze_content`) but every spectral/MFCC/chroma/autocorrelation feature is computed from the first 4096/8192 samples only, so the genre (and the genre EQ curve in `eq_processor.py:131`) is decided by the first 93-186 ms. Fade-ins and digital silence at the start are the norm.
- **Evidence** (channels-first input, the layout the extractor assumes, 44.1 kHz): tone for the first 0.2 s then 19.8 s of noise -> `classical` (1.00); noise first 0.2 s then 19.8 s of tone -> `metal`; a pure 220 Hz tone with a 0.3 s silent lead-in -> `metal` (1.00) while the same tone without the lead-in -> `classical`; noise with a silent head -> `metal`.
- **Impact**: Reach is limited to `mode="hybrid"` jobs and the non-continuous `AdaptiveMode` (the shipped `ContinuousMode` does not call `ContentAnalyzer`), so LOW; but the result is effectively a function of the lead-in.
- **Suggested Fix**: Compute features over a representative window (e.g. the same body window as the fingerprint) or frame-average them.

#### E6-09: `MasteringFingerprint` analyses the first 90 s while the 25D fingerprint analyses the 50 % body window
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/mastering_fingerprint.py:128-131` (`librosa.load(..., duration=90)` with no offset; FFmpeg branch `raw_audio[..., :int(sr * 90)]`); contrast `auralis/analysis/fingerprint/windows.py:2-9,31-38`
- **Status**: NEW
- **Description**: `windows.py` states that "the library fingerprint and the mastering fingerprint must keep using the same one" and the multi-window study (#4595) showed a start-of-track window biases loudness by up to 9 dB on ambient intros. Only the 90 s *length* is shared; `MasteringFingerprint` still reads from t=0. Its `loudness_dbfs`, `crest_db`, `zero_crossing_rate` and `spectral_centroid` drive `DetectionRules.similarity_score` -> profile ranking in `AdaptiveMasteringEngine`.
- **Evidence**: `from_audio_file` passes no `offset`; `window_offset_s(0.5, total, 90)` is what every 25D loader uses.
- **Impact**: The recommended profile and its reasoning ("Very quiet original") follow the intro, not the body. The recommendation is advisory (UI + cache), hence LOW.
- **Siblings**: #5713 (same function decodes the whole FFmpeg-routed file).
- **Suggested Fix**: Reuse `load_librosa_windows` / `load_ffmpeg_windows` body window instead of a start crop.

#### E6-10: A single non-finite input sample produces a plausible, validator-passing fingerprint; no input check before Rust
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:28-80,106-121` (`sanitize_non_finite` is the only guard), `auralis/analysis/fingerprint/rust_fingerprint.py:108-115` (`bass_mid_ratio`), `auralis/analysis/fingerprint/windowed_compute.py:147-198` (no `isfinite` check on the loaded window)
- **Status**: NEW (the #5103/#5505 sanitizer is in place and works for values that stay NaN; this is the residue)
- **Description**: NaN in the audio propagates through the Rust FFTs into most dims. The post-hoc sanitizer only replaces dims that are still non-finite, with 0.0 regardless of schema range; dims that happen to turn finite pass untouched: the 7 band fractions become exactly uniform (1/7 each, sum 1.0, so `band_pct_valid` accepts them), `harmonic_ratio` 1.0 / `spectral_flatness` 0.0, and `bass_mid_ratio` maps NaN to +60 dB through `max(-60, min(60, nan))` (Python `min(60, nan)` returns 60). `lufs` NaN becomes 0.0 (the loudest possible value, outside the -40..-6 schema range).
- **Evidence**: 10 s stereo noise with one `np.nan` sample, `AudioFingerprintAnalyzer().analyze`: band fractions 0.004/0.017/.../0.277 -> 0.143 each (sum 1.0), harmonic_ratio 0.405 -> 1.0, spectral_flatness 0.595 -> 0.0, loudness_variation_std 0.035 -> 0.0; raw Rust dict has NaN lufs/crest/chroma/centroid, `bass_mid_ratio` arrives as +60.
- **Impact**: A float WAV with a glitch sample (the job path repairs NaN earlier, the windowed library path does not) is stored with a believable but wrong fingerprint, stamped current and never recomputed.
- **Siblings**: #5589 (`loader.load()` lets NaN/Inf through).
- **Suggested Fix**: Reject (or `np.nan_to_num`) non-finite audio before calling Rust and treat any non-finite result as a failed extraction instead of coercing to 0.0.

#### E6-11: Obsolete 300 MB size guard skips valid hi-res/long files in the batch extractor only
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/services/fingerprint_extractor.py:27,157-162`
- **Status**: NEW
- **Description**: `MAX_FINGERPRINT_FILE_SIZE_MB = 300` was added (#2896) when the extractor decoded the full file. Since #4595/#5110 `compute_windowed_fingerprint` decodes only 90 s + 2x30 s on all three branches, so memory no longer scales with file size (the comment at `:171-175` says so itself). The guard now only excludes valid tracks (a 24-bit/96 kHz FLAC passes 300 MB around 65-70 minutes, 24/192 around 35). `FingerprintGenerator`/`fingerprint_loading` (on-demand) have no such guard, so the same file is fingerprinted when played but never by the library scan, and each restart re-claims it for the three attempts of `MAX_EXTRACTION_ATTEMPTS`.
- **Evidence**: `extract_and_store` -> `_compute_fingerprint` returns None before any decode; worker raises "Extractor returned False" and `_release_failed_claim` retries.
- **Impact**: Missing library fingerprints (similarity, k-NN) for long/hi-res tracks; wasted claims on every start.
- **Suggested Fix**: Remove the guard (or raise it to a duration-based sanity limit).

#### E7-04: `skip_existing=False` neither updates nor re-adds existing tracks, yet reports them as "added"
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/batch_processor.py:113-117, 166-172`; `auralis/library/repositories/track_repository_lifecycle.py:111-121` (`add` returns the existing row); API field `auralis-web/backend/schemas/library.py:18`, forwarded at `auralis-web/backend/routers/library_scan.py:155`
- **Status**: NEW
- **Description**: With `skip_existing=False`, `existing_track` is forced to `None`, so the code takes the "new track" branch and calls `tracks_repo.add(track_info)`. `add()` finds the row by `filepath_key`, logs "Track already exists" and returns it unchanged. The scanner then counts it as `'added'`, puts it in `added_tracks`, and never calls `update_by_filepath`. The request field is documented as "Skip files already in library" (so `false` should reprocess them).
- **Evidence**: Probe: scan a 1 s WAV; replace it with a 2 s WAV (mtime advanced); `scan_directories([music], skip_existing=False)` -> `files_added=1, files_updated=0`, track duration still 1.0; a normal scan afterwards -> `files_updated=1`, duration 2.0.
- **Impact**: A "rescan everything" request through the API is a silent no-op that lies about its result and re-enqueues every already-fingerprinted track for fingerprinting. The bundled frontend always sends `true`, so only API clients are affected.
- **Siblings**: none.
- **Suggested Fix**: When `skip_existing=False`, still look up the existing row and take the update branch (ignoring the mtime watermark), or drop the parameter.

#### E7-05: `SidecarManager.is_valid()` / `get_fingerprint()` raise `AttributeError` on valid-JSON-but-wrong-shape `.25d` files, permanently blocking fingerprinting of that track
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/sidecar_manager.py:98-112, 125-139, 207-232`; `auralis/library/sidecar_validation.py:26, 40-45`; callers `auralis/services/fingerprint_extractor.py:128-133, 261`
- **Status**: NEW (#4910 hardened numeric values; #4638 made writes atomic; neither validates the container type)
- **Description**: `is_valid` catches only `json.JSONDecodeError`/`OSError`. `json.load` can return a list, string or `null`; `sidecar_matches_audio` then calls `data.get(...)` (and `audio_meta.get(...)` when `audio_file` is `null`). `SidecarManager.read()` types the result `dict | None` without checking, and `get_fingerprint` calls `data.get` as well.
- **Evidence**: Probe: sidecar contents `[]`, `null`, `"str"` -> `is_valid()` raises `AttributeError: 'list'/'NoneType'/'str' object has no attribute 'get'`. In `extract_and_store` the exception lands in the outer `except Exception` and returns `False` (so the 'analyze fresh' fallback and the sidecar rewrite never run); in `extract_batch` (`fingerprint_extractor.py:261`) the `is_valid` call is outside any `try`, so one bad sidecar aborts the whole batch.
- **Impact**: A foreign, hand-edited or otherwise corrupted-but-parseable `.25d` file beside an audio file leaves that track unfingerprintable (every retry hits the same exception) and can abort a batch. Sidecars live next to user files, so this input is not fully under Auralis' control.
- **Siblings**: `SidecarManager.read()` and `get_fingerprint()` share the unchecked `dict` assumption.
- **Suggested Fix**: In `read()`/`is_valid()` reject non-dict top-level JSON and a non-dict `audio_file`/`fingerprint` and return `None`/`False`; also catch `(AttributeError, TypeError, ValueError)` in `is_valid`.

#### E7-06: Untagged files get their full filename (with extension) as title; tagged-but-untitled files get the stem
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/metadata_extractor.py:192-210`; `auralis/library/scanner/batch_processor.py:140-144`
- **Status**: NEW
- **Description**: `audio_info_to_track_info` defaults `title` to `audio_info.filename` and only switches to `Path(...).stem` inside `if audio_info.metadata:`. `extract_metadata` returns `{}` for a file with no recognised tags, and `batch_processor` assigns metadata only `if metadata:`, so the stem fallback is unreachable for exactly the files that need it.
- **Evidence**: Probe: untagged `a.wav` -> stored title `'a.wav'`; `b.wav` with only a TPE1 tag -> title `'b'`.
- **Impact**: Library lists show "a.wav" for untagged tracks while tagged-without-title tracks show "b"; the title also flips when a user adds an unrelated tag and the file is rescanned.
- **Siblings**: none.
- **Suggested Fix**: Make the default `Path(audio_info.filepath).stem` unconditionally.

#### E7-07: Scan path reservation matches exact strings only, so a parent and child directory (or a symlink alias) can be scanned concurrently (default `max_concurrent_scans = 4`)
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scan_coordinator.py:77-97`; `auralis/library/scanner/scan_stages.py:51-52`; default at `auralis/library/models/settings.py` (`max_concurrent_scans` default 4)
- **Status**: NEW (slot/path accounting itself is correct; #5802 guard verified present, see below)
- **Description**: `try_reserve_scan_paths` rejects a path only if the identical `normpath(abspath(...))` string is already reserved. `/Music` and `/Music/Rock` (or a symlink to either) are both granted, so two scans walk and insert the same files at once.
- **Evidence**: Code path: `clashing = [p for p in paths if p in self._active_scan_paths]`. The loser of each per-file insert race gets an `IntegrityError` in `TrackRepository.add` -> rollback -> `None` -> recorded as a failed file ("Database insert failed"); the artist/genre/album get-or-create savepoints are the ones reported broken under pysqlite in #5717. Within a single call, nested `scan_folders` are also walked twice and `files_found`/`total_expected` double count them.
- **Impact**: Spurious "failed" entries and orphan rows when a manual scan overlaps the auto-scanner on nested folders. Not data-corrupting.
- **Siblings**: none.
- **Suggested Fix**: Treat a reservation as clashing when either path is an ancestor of the other (compare `os.path.realpath` with a separator-aware prefix check), and de-duplicate nested roots inside one call.

#### E7-08: `TrackRepository.get_by_paths()` keys its result by the stored path, not the requested one, defeating the `filepath_key` matching it performs
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_lookup.py:69-86`; sole caller `auralis-web/backend/services/queue_enrichment.py:117-122`
- **Status**: NEW
- **Description**: The query matches on `filepath_key IN (make_filepath_key(p) ...)` (normalised, case-folded on Windows/macOS), but `result[track.filepath] = track` uses the row's stored spelling. The caller then does `found[fp] = ...` for the returned keys and later `by_fp.get(fp)` with the engine's original spelling, which misses whenever the spellings differ (different case on a case-insensitive platform, `a//b` or `./` forms, `\` vs `/`).
- **Evidence**: Code reading only (the lookup and the caller are both unambiguous); on Linux the two spellings normally coincide because queue entries come from `Track.filepath`.
- **Impact**: Queue entries whose path differs in spelling from the stored one are enriched as `None` (blank rows). Latent: needs a path produced outside the DB.
- **Siblings**: none.
- **Suggested Fix**: Return a mapping keyed by the requested path (map each requested path to its `filepath_key`, then back).

#### E7-09: `LibraryDatabase._delete_lock` is a dead lock with a misleading comment (#3771 was closed without being fixed)
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/database.py:114-115`
- **Status**: Regression of #3771 (closed; the field survived the `LibraryManager` -> `LibraryDatabase` move in `b02c8543`/`44af56d8`)
- **Description**: `self._delete_lock = threading.RLock()` is created under the comment "Thread-safe locking for delete operations (prevents race conditions)". `grep -rn _delete_lock` finds only this line; no delete path acquires it, and `delete_tracks_by_ids`/`cleanup_missing_files` rely on the transaction instead.
- **Evidence**: single occurrence in the whole tree.
- **Impact**: Misleads readers into believing deletes are serialized; no runtime effect.
- **Siblings**: none.
- **Suggested Fix**: Delete the field and the comment (the issue's acceptance criterion).

## Relationships

- **Silent-success family: E2-01, E1-02, E6-10, E6-07 (with open #5712 and #5191).** In each case the analysis or guard layer degrades to a quiet default, such as `{}`, all-zero audio, a 0.0-coerced dimension or a sentinel inside a median, without raising. The documented fail-fast in `HybridProcessor` (`repair=False`) and the pipeline's unprocessed-audio fallback therefore never fire. One policy would close all four: non-finite or failed analysis raises, or returns an explicit "unavailable" marker that the job and stream layers surface.
- **Whole-file analysis cost: E6-03 with E2-09 and E6-08.** Whole-file adaptive and hybrid jobs fingerprint and quality-gate the entire decoded file. Hybrid jobs run `analyze_content` twice (E2-09). Its genre features look at only the first 93 ms (E6-08). Fixing E6-03 by routing through the shared windowed pipeline (`crop_preloaded_windows`) also gives E6-08 and E6-09 a representative window.
- **Fingerprint integrity: E6-01, E6-02, E6-10 with open #5697.** All of these change persisted fingerprint values. The fixes should land together with one `FINGERPRINT_ALGORITHM_VERSION` bump. #5697 must be fixed first, or stale `.25d` sidecars get re-stamped as current.
- **Final-chunk geometry in the offline loop: E5-05, E2-04 with open #5736 and #5737.** All of these come from rendering a tiny remainder as its own chunk. Folding a remainder of at most `crossfade_samples` into the previous chunk removes the E5-05 seam residual and the #5736 crash, and keeps the E2-04 fallback unreachable. E2-04 should still be fixed (`on_too_short="zeros"`).
- **Continuous-space steps: E2-02, E2-05, E2-03.** All three are hard thresholds or selectors that the #4860/#5108/#5578 `smooth_gate` conversions missed. Each can be fixed the same way, with a `smooth_gate` knee or a continuous combination.
- **Realtime player chain: E1-01, E1-03, E3-01, E3-03 with open #5707, #5721 and #5729.** All live behind the dormant `get_audio_chunk()` path. Fix this chain as one unit when the realtime path is revived, or delete it with #5708.
- **Library scale and ordering: E7-01, E7-02.** Both are index or collation gaps that need a schema v24 migration. They can share it: association-table indexes plus `COLLATE NOCASE` ordering, so the existing NOCASE indexes get used.
- **Scanner robustness: E7-03, E7-06, E4-03, E4-04 with open #5732, #5567 and #5594.** All four sit on the scan ingest path. E4-03 (ID3 multi-value) and #5732 (Vorbis multi-value) should share one list-aware tag reader.
- **Tag editor: E4-01, E4-02.** Both are per-format writer gaps in `metadata_editor/writers.py`. A per-format round-trip test over every key in `TAG_MAPPINGS` would have caught both.
- **Fingerprint worker lifecycle: E6-04, E6-05, E6-06 with open #5756.** All four are in the batch fingerprint pool's start/stop and sizing logic.

## Prioritized Fix Order

1. **E7-01** (HIGH): add the association-table and `albums.artist_id` indexes in a v24 migration. Also stop calling `find_similar` on every track load. This is the only finding with a user-visible multi-second stall on the shipped path, and the fix is mechanical.
2. **E2-01, then E1-02**: make fingerprint failure and non-finite output loud. Add a startup check that `auralis_dsp` imports. Today a missing wheel ships unmastered audio as "complete", which also hides every other DSP bug from users and testers.
3. **E7-03**: per-entry `try/except` in `_walk_directory`. One line of structure stops silent, partial library scans.
4. **E4-02, E4-01**: the M4A save failure blocks every edit on iTunes-tagged files, and MP3/WAV fields are silently dropped. Both are small writer fixes plus one round-trip test.
5. **E6-01, E6-02, E6-10, E6-07**: a fingerprint-correctness batch with one algorithm-version bump, after #5697.
6. **E6-03 (+ E2-09)**: bound whole-file job analysis to the windowed pipeline and drop or window the quality gate. This is a memory risk on long files.
7. **E2-02, E2-05, E2-03**: replace the continuous-space steps with smooth gates.
8. **E7-02**: NOCASE ordering and Unicode-aware search. It can share the v24 migration from item 1.
9. Remaining LOW items, grouped by the Relationships above: the offline CLI (E5-01..05, E2-04), the realtime player chain (E1-01, E1-03, E3-*), the fingerprint pool lifecycle (E6-04..06, E6-11), and config/dead-code hygiene (E2-06..08, E2-10, E7-09).

## Known/Existing (re-confirmed, not re-filed)

The dimension sub-audits re-checked these open issues against the live tree. They are not new findings.

- **Sample integrity / DSP**: #5187, #5191, #5558, #5576, #5695, #5699, #5700, #5701, #5702, #5703, #5704, #5712 (re-verified: `KeyError` on chunks of 4096 samples or fewer), #5721, #5722, #5723, #5724, #5736, #5858, #5098
- **Player**: #5460, #5563, #5564, #5686, #5705 (re-confirmed by probe), #5706, #5707, #5708, #5725, #5726, #5727, #5728, #5729. **#5565** no longer reproduces in code (the prebuffer match now goes through `_entries_match`). It looks closeable after verification.
- **Audio I/O**: #5266, #5566, #5567, #5709, #5711, #5713, #5730, #5731, #5732, #5733, #5734, #5735, #5739
- **Chunked mastering (offline)**: #5694 (re-confirmed: a 0.5-peak input clips 4595 samples), #5696, #5710 (re-confirmed), #5736, #5737, #5738 (no Python caller has appeared), #5739, #5740
- **Analysis**: #5244, #5593 (measured +2–3 LU on 40–45 Hz sub-bass tones, against the issue's ~1 dB), #5697, #5711, #5713, #5714, #5716, #5741, #5742, #5743, #5744, #5745, #5746, #5756
- **Library**: #5594, #5595, #5596, #5597, #5698, #5717, #5718, #5719, #5720, #5747, #5748, #5749, #5750, #5751, #5752, #5753, #5754, #5755, #5851
- **Closed fixes verified still in place**: #4981 (accepted: no dither), #5505, #5531, #5568, #5570, #5589, #5802 (no `except AttributeError` around the scan guard), #5339, #4966, #5109, #5569, #5592, #4494 and others listed per dimension below.

**Observation, not filed** (Library sub-audit): `migration_v022_to_v023.sql` runs `UPDATE user_settings`, but no migration creates that table; it comes only from `create_all`, which runs after migration. A pre-Oct-2025 DB that never ran an app with `UserSettings` could fail that step. Verify before filing.

**Checklist note**: the Dimension 6 item "batch vs streaming analyzers (`fingerprint/analyzers/`)" is stale. That package no longer exists, and there is one Rust fingerprint implementation. The next `/audit-sync` should update it.

## Appendix: Checked, No Issue (per dimension)

#### Dimension 1: Sample Integrity

- `len(output) == len(input)`: probe on lengths 1024, 1025, 1500, 2047, 2048, 4095, 4097, 10001, 44101, 88207 for 1 and 2 channels, fixed-target path: shape and dtype held everywhere (quality gate disabled to avoid the known #5712). `HybridProcessor._process_*` raise `RuntimeError` on mismatch, `AudioProcessingPipeline.apply_enhancement` re-checks, offline loop checks `processed_chunk.shape[1] != chunk.shape[1]` and `write_region.shape[1] != core_samples`. WOLA EQ (`eq_processor`) buffer is `original_length + chunk_size` and trimmed, coverage verified.
- Copy-before-modify: `ContinuousMode.process`, `AdaptiveMode.process`, every `CompressionStrategies/ExpansionStrategies` entry, `amplify`, `SafetyLimiter`, `PeakNormalizer`, `stages/no_op`, `soft_clip`, `BrickWallLimiter`, `AdaptiveCompressor`, `LookaheadBuffer`, WOLA frame copies. Probe: input not mutated for float32/float64, mono 1-D, `(N,1)`, 6-channel, read-only, Fortran-order, strided, negative-stride, big-endian arrays, and in reference/hybrid modes. `to_mono` returns the input uncopied for 1-D by documented contract.
- dtype: float32 in/out held through ContinuousMode, EQ (vectorized and plain), limiter, stereo-width multiband (cast at the end), `sosfiltfilt_safe`, `ParallelEQUtilities`, offline stages, level matcher, gain smoother, `AdaptiveCompressor`. float64 in/out also held. Only gap: E1-04.
- Clipping: ContinuousMode final normalization peak clamp (-0.3 dBFS) + `BrickWallLimiter` (-0.3 dBFS, verified `gain[i] <= target[i]` for every branch, window includes sample i); probe on 0 dBFS square, 6x over-range, full-scale noise, impulses: peak <= 0.9661 in every case. The limiter's one-sample attack step is open #5699.
- NaN/Inf: input NaN raises `ModuleError` (above MIN_SAMPLES); reference-mode NaN reference raises; `saver.save` repairs then clips; `WAVEncoder` rejects non-finite. Fingerprint source guards (#5505/#5531) present. Gap: E1-02 (downstream masking).
- Mono/stereo: 1-D -> `(N,2)`; `(N,1)` processed as mono (stereo stage skipped, loudness meter handles it, #5550 verified); 6-channel passes through (loader downmixes 6/8 channels and routes others through FFmpeg; no producer of >2 channels reaches `get_audio_chunk`). Gap: E1-05 for layout/dtype validation.
- Bit depth: `io/results.py` only describes the target (no transform). `saver.save` casts to float32, repairs NaN, clips to [-1, 1] before `sf.write`. Probe with libsndfile 1.2.2: +1.0 -> 32767/8388607, -1.0 -> -32768/-8388608, 1.7 and -1.7 clip to the same, NaN/Inf -> 0, no overflow wrap. libsndfile floors rather than rounds (mean error about -0.5 LSB, max 1 LSB over 200k random PCM_16 samples); this is the known undithered-truncation trade-off documented in `results.py` (closed #4981), not re-filed. `PCM_32` job exports carry at most 24 effective bits because the pipeline and `save()` are float32 (inherent).
- Offline CLI (rated as offline-tool weight): every stage bypass copies; `apply_true_peak_guard` and `ContinuousMasteringBranch` file-level gains are Python floats (no promotion); crossfade ramps are built in the chunk dtype; `read_chunk` transposes unconditionally (square-array bug #2292 stays fixed); chunk-count short-render guard present.
- `EnvelopeFollower` refactor of 2026-10-22 (`d93e3990`) and the `SpectrumGainsMixin` move (`7cfa8e04`): behaviour-preserving for sample handling (kernel allocates with `zeros_like`, state now stored from the float32 output; mixin is a verbatim move).
- `HybridProcessor` limiter/EQ cross-call state: serialized by `_process_lock`; reset hooks present (`reset_limiter`, `reset_psychoacoustic_eq`).

#### Dimension 2: DSP Pipeline

- Chain order: the only stage sequence is `ContinuousStagesMixin._apply_dsp_stages` (input gain -> EQ -> dynamics -> stereo width -> normalization, then the brick-wall limiter in `HybridProcessor`); nothing runs a stage outside the list. `_stage_input_gain` can never fire because `ProcessingParameters` has no `input_gain` (already in #5576).
- Stage independence: stages have no try/except by design (#4972); a failure aborts the call. `PipelineJournal` is per call; `PsychoacousticEQ.current_gains` and `BrickWallLimiter.current_gain` persist across calls, but the shipped geometry trims 5 s of context and the final normalization clamps to the limiter threshold, so the leak is inaudible.
- WOLA / windowing: fixed 50% hop, full-Hann synthesis, window-weight normalization (frame 0 and the tail handled); `apply_eq_gains` is un-windowed, analysis FFT is Hann with coherent-gain compensation; band map is by center frequency; no double-windowing; bins above the last Bark edge clamp to the top band.
- Phase coherence: `adjust_stereo_width_multiband` and the tilt correction use zero-phase `sosfiltfilt` in parallel (difference added to the dry signal); the shared 2 kHz edge is amplitude-complementary (pinned by #4505 test).
- Continuity of the live chain: guard gates are `smooth_gate` knees; `delta_eq` tanh caps are C1 at 0; `derive_target` is smooth in distance. Numeric sweeps of the generator over crest, LUFS and band fractions found no plateaus except the clamp at `target_lufs` -28 for inputs below about -37 LUFS, and non-monotonicity only in the documented bells (`compression`, `eq_blend`).
- Coordinate derivation: every axis goes through `_smooth_unit` (NaN -> 0.5, +/-Inf saturates, tanh bounded); `log` argument guarded; sanitize_non_finite replaces NaN dimensions before the mapper.
- Optimizer wrapper: preserves return value, exceptions, sample count; thread-safe (RLock, double-checked singleton); idempotent.
- Rust boundary: `py_bindings.rs` copies the buffer before `py.detach`, catches panics with `catch_unwind`, validates channels/sample rate; `Cargo.toml` has no `panic = "abort"`; rayon only inside `chroma.rs`; no mutable statics. `rust_fingerprint_to_schema` returns exactly 25 schema keys with correct renames and units.
- Preset tables: `PreferenceVector.from_preset_name`, `get_preset_profile` (returns None) and `get_genre_profile` all degrade for unknown names without raising; no engine table still defines a removed preset.
- Fixed-target chunk seams: a 65 s synthetic with changing spectral balance, rendered in backend geometry (15 s chunks, 5 s context, 10 s emission), shows seam level steps within +0.82 dB of the input steps with the guards on and +0.69 dB with them off (the residual is the peak clamp already in #5701); the guards add at most about 0.3 dB.

#### Dimension 3: Player State

- Lock graph (U=`update_lock`, A=`_audio_lock`, P=`PlaybackController._lock`, Q=`QueueManager._lock`, L=`_position_lock`, F=`_fingerprint_lock`, R=`RealtimeProcessor.lock`): the only nestings are U->A->P, A->P, A->Q (`has_next_track` in `get_audio_chunk`), L->A, L->P and F->R->(auto_master/level_matcher locks). No inversion found. The queue change listener runs after Q is released, `_materialise_track` runs before L, and the library session is never opened under a player lock (Player -> Library order holds).
- play/pause/stop state transitions are atomic under `PlaybackController._lock`. Enumerated stop/play and pause/play interleavings (including `_stop_requested`/`_pause_requested` set-first discipline from #3669/#5588) always end in a consistent state/flag pair.
- Position invariant: `seek()` and the `position` setter hold `_audio_lock` across read-total and seek; `read_and_advance_position` clamps (#5114); `on_swap` resets position inside the swap lock; `_get_position_seconds` clamps to duration.
- Queue bounds on skip/previous/remove/insert/reorder/move: all mutators take Q for the whole read-modify-write. `rollback_index` clamps to live bounds, `remove_tracks` sorts descending, `reorder`/`move` re-find the current entry by identity. `load_playlist`/`set_queue` clamp `current_index` under Q (#4098, #5355). (Repeat-wrap rollback gap is Existing #5705.)
- Gapless prebuffer vs load/play: `advance_with_prebuffer` peeks, decodes outside all locks (#5105), commits through `advance_if_next_matches`, then swaps under U->A with `on_swap` in the same section. Match rule `_entries_match` requires non-None id or path on both sides (the #5565 scenario is fixed in code; the issue is still open).
- Callbacks outside locks: `defer_notifications()` correctly wraps every mutator that runs under `_audio_lock` (`seek`, `position` setter, `load_file`, `load_track_from_library`, `next_track` `on_swap`). `IntegrationManager._notify_callbacks` and `PlaybackController._dispatch_callbacks` snapshot the list and invoke outside their locks.
- stop() resource cleanup: stop() deliberately keeps the decoded buffer (resume restarts at 0); no file handles are held (decode is whole-file in memory). Prebuffer worker and loader threads are shut down by `gapless.cleanup()` through `_shutdown` (#2075, #4631).
- Real-time processor lifecycle: there is no start/stop. `process_chunk` is stateless apart from the level matcher/auto-master state, and effect flags are snapshotted under `R` (#3784). `reset_all_effects()` runs only at `cleanup()`. Processor locks are consistently ordered; `process_chunk` preserves length and dtype and repairs non-finite output.
- Mixin composition: every mixin method that mutates shared state takes its host's lock (`QueueLockedStateMixin` through Q, `QueueLoadingMixin` under Q, `ShuffleMixin`/`QueueNavigationMixin` under Q, `PrebufferMixin` under U/`_thread_lock`, `LibraryLoadingMixin` outside any player lock, `PlaybackReportingMixin` under L then A/P). `PlayerPropertiesMixin` reads and writes under `_audio_lock`/`_position_lock`.
- Backend seek input validation: `SeekRequest` rejects NaN, Inf and negatives. Only the huge-finite case leaks through (E3-06).

#### Dimension 4: Audio I/O

- Format coverage: `.mp3` is covered by `tests/input_media`; `.m4a/.aac/.ogg/.opus/.wma` by `tests/auralis/io/test_ffmpeg_format_roundtrips_5336.py`; WAV/FLAC/AIFF/AU by `test_unified_loader.py` and `tests/regression/test_format_consistency_and_rf64.py`. The format registry is single-sourced in `formats.py`.
- Corrupt headers: random bytes named .mp3/.flac/.wav/.opus/.m4a/.ogg/.aac, a truncated M4A without moov, a 100-byte WAV and a forged RIFF header all raise `ModuleError` with meaningful codes (ERROR_CORRUPTED, ERROR_LOADING, ERROR_TRUNCATED_FILE) and leave no temp WAV behind. Truncated MP3 or mid-stream corruption decodes with a warning.
- Large files: pre-decode caps via ffprobe or `sf.info` (`MAX_DURATION_SECONDS` plus `oversize_decode_detail`), a size-implied fallback when duration is missing (#4128), a post-decode backstop, float32 reads (#3748), allocation-free peak (#5591). The remaining weaknesses (RAM-backed temp WAV, 4 GiB RF64, full decode) are already open as #5734, #5566 and #5739.
- Sample rate always comes from metadata (`-ar` from ffprobe; `sf.read` returns the file rate; a failed probe raises, with no 44100 fallback). The `44100` defaults elsewhere are constructor defaults overwritten by `file_manager.sample_rate = loaded_sample_rate`. The reference-audio rate is dropped in `AudioFileManager.load_reference`, but `LevelMatcher` is rate-independent.
- Downmix: FFmpeg `-ac 2` only when channels > 2 (mono preserved, #4611). Native BS.775 downmix is limited to 6/8 channels; other counts are routed to FFmpeg (#5242). Peak-renormalisation, dtype preservation and the LFE drop behave as documented. The 7.1 side-channel fold is the known #5735.
- FFmpeg process supervision: `subprocess.run(timeout=...)` kills on timeout. The cancellable `Popen` path drains pipes through repeated `communicate(timeout)`, so there is no unread-stderr deadlock. Cancellation calls terminate then kill then wait, and temp WAV cleanup is in `finally` (CancelledError is a BaseException, so it still runs). No other `subprocess` use exists outside `auralis/io`.
- Path safety: `reject_protocol_path` regex, `-protocol_whitelist file` on both ffmpeg and ffprobe, a shared `ffprobe_command` with `--` (verified that `ffprobe -- -dash.m4a` works), `is_file()` rejects FIFOs/devices in `_validate_input`, and the scanner pre-filters with `is_file`. Leading-`-` names are safe for `-i`.
- stderr handling: UTF-8 `errors='replace'` (#5555), last-line redaction with the known path stripped (#4806).
- Output side: `saver.save` repairs NaN/Inf then clips to [-1,1]; `Result` validates subtype and directory up front.
- Tag extraction robustness: `MetadataExtractor` swallows the mutagen ValueError for MP4-style keys on Vorbis files; an untagged MP3, FLAC, WAV or Opus file returns an empty dict or None without raising; a corrupt ID3 header returns None; `'abc'` track and `(17)` genre are normalised; year is `[:4]`-bounded.
- Editor write path: backup, lock and restore-on-failure work (#5307). Track/disc totals are preserved (#5506). OPUS and WAV dispatch is fixed (#4130). ASF names are fixed (#5536).
- Closed-issue spot checks still in place: #4834, #4826, #5326, #5555, #4496, #2074, #4875, #5312, #5104, #4128, #5317, #3743, #5242, #4611, #4131, #4112, #5589, #5590, #4117.

#### Dimension 5: Chunked Mastering

- Chunk independence: `read_chunk` returns a fresh float32 copy (`astype` copies), `process_chunk` starts with `audio.copy()`, `ContinuousMasteringBranch.apply` copies again; carried `prev_tail` is `.copy()`ed. Probed all 12 stage delegates at float32/float64, 1000 and 44100 samples: shape, dtype, no aliasing, input not mutated, finite output.
- Seam settling: only the transient shaper (one-poles, tau 5/50 ms) and `BrickWallLimiter` (60 ms release) carry per-chunk state; both are in the `__post_init__` check (3 s >= 5x4x60 ms = 1.2 s). Other stages are stateless zero-phase `sosfiltfilt` (edge effects fall where crossfade weight is ~0), and no stage measures the audio. Mid-file seam: chunked vs whole-file residual -96.7 dB (r = 5 s case), no step.
- Crossfade shape: `sin^2`/`cos^2` equal-gain over `linspace(0, pi/2, head_len)` (weights 0->1 / 1->0, sum exactly 1); no equal-power regression (#4966). Weight is 0 on the cold head and 0 on the edge-affected tail end.
- Off-by-one arithmetic: `overlap_after = min(crossfade, total - read_pos - core)` always makes tail length equal the next chunk's usable head; exact-multiple files (last chunk = full `chunk_size`), remainder < crossfade, remainder == crossfade and `head_len == 0` all reassemble to exactly `total_frames` (probed shapes equal). Non-last write regions are guarded by the `core_samples` RuntimeError (#2515); first/last-chunk regions are correct by construction.
- Reassembly order: strictly sequential index order from `read_pos`; end-of-render `chunks_processed != total_chunks` check raises instead of publishing a short file (a truncated FLAC raises inside libsndfile; OGG reports true frame count, so a silent-short last chunk was not reproducible).
- Partial failure: no per-chunk try/except by design; any raise aborts, the stage directory (`TemporaryDirectory`, same filesystem) is removed on every exception including KeyboardInterrupt, `os.replace` publishes only after `fsync`, the previous master is untouched; `prev_tail` is committed only after `write` succeeds. Output is 24-bit (`PCM_24`), clipped to [-1, 1] before write, created with umask-respecting 0666 (#5592 still fixed). Mono input renders 2-channel (#4494).
- Analysis scope: stage parameters come from the file-level fingerprint, the file-level `_source_lufs`/`_source_crest_db` (middle 30 s window, a documented representative-window heuristic) and the whole-song `_song_peak_db`; the only per-chunk measurement is Stage 1 `peak_db` clip prevention, which is deliberate (#2402) and only touches samples above the threshold.
- Last-chunk handling: never zero-padded, never dropped (probed 50 ms to 5 s remainders; output shape == input shape). Only the 1-15 sample case fails, already #5736.
- Sample-rate handling: `_process` renders at 8 k, 11.025 k, 16 k, 22.05 k, 32 k, 48 k, 96 k and 192 kHz without error.
- `mastering_notch_context.py`, `mastering_diagnostics.py`: pure scaling/printing, no chunk coupling (`brilliance_pct` row can never fire because notches are limited to 150-1200 Hz).
- #5839 refactor (`1a6f666a`) is behaviour-equivalent to the inline code it replaced.
- Verified-fixed and still in place: #5109 (staged atomic write), #5339 (ratio guard exists), #4966 (equal-gain), #4970 (constant true-peak gain — but see #5694 for its premise), #5569 (pre-downmix), #5592, #5512/#5511/#5533, #2429, #2157, #2292, #2515, #3660, #3700, #4494.

#### Dimension 6: Analysis

- **Determinism**: Rust path has no RNG; the only rayon use (`chroma.rs` `par_iter` over CQT bins) collects per-bin sequential results, so reduction order is fixed; two runs of `compute_fingerprint_schema` on the same buffer are identical; the ffmpeg vs librosa loader is chosen by extension, so a given file always takes the same branch; `window_offset_s` is pure.
- **Pathological input, windowed path**: bounded on all three loaders (ffprobe duration, then bounded decode with 1 s pre-roll; soundfile header duration + offset/duration; crop-before-resample for pre-loaded). Probed through the real Rust build: silence, DC, white/pink noise, 0.5 s, 1000 samples, 2 samples, 1 sample, odd-length stereo, +-inf, NaN: no panic, no hang (all under 0.11 s at 10 s of audio); the PyO3 wrapper uses `py.detach` + `catch_unwind`; rate range [8k, 384k] enforced in Rust and the Python adapter resamples everything to 22.05 kHz first.
- **Band split, #5570 fix**: pink noise band fractions are level-independent (band floor gone); `compute_bass_mid_ratio` and `estimate_transient_density` scopes match the 30 s / whole-window analysis.
- **Schema mapping** (`rust_fingerprint_to_schema`): 7 band keys, 13 pass-through dims, centroid/10 kHz rolloff normalisation, DRV half-response curve, bass/mid log-ratio and `loudness_variation` rename all match `schema.py`; missing key raises KeyError (fail loud). `prepare_rust_audio` interleaves C-order (#5556 fix in place).
- **Batch vs streaming parity**: single implementation; windowed path and `ContinuousMode.analyze` share the Rust engine and the analyzer's validation/sanitize step.
- **ML lifecycle**: `create_ml_genre_classifier` is an `lru_cache(maxsize=1)` singleton; filterbank is built once; `classify` is stateless (read-only weights), so concurrent use is safe. Weights are deterministic.
- **K-weighting / gating**: stage-2 shelf coefficients match BS.1770-4 (`f0` 1681.97 Hz, +3.9998 dB); absolute (-70) and relative (-10 LU) gating, unbounded `integrated_buffer` vs bounded short-term buffer, partial trailing block (#3677), per-call meter in `calculate_loudness_units` (no shared filter state) are all correct. Known deviations are #5593 (Butterworth RLB; my probe: about +0.1 LU on pink noise but +2-3 LU on a 40-45 Hz sub-bass tone, so the issue's "~1 dB" understates it for bass-heavy electronic material) and #5741 (LRA).
- **Dynamic range**: `_calculate_dr_value` follows the TT-DR algorithm (3 s blocks, top 20 %, second peak); Hilbert paths are capped at 30 s (#4214 fix in place).
- **Quality scoring**: NaN and -inf inputs score 0 via `range_based_score`/`linear_scale_score` guards; `threshold_score` sign fix in place.
- **Thread safety**: no module-level mutable caches in `auralis/analysis` or `auralis/services`; `AudioFingerprintAnalyzer` is stateless; `QualityMetrics`/`SpectrumAnalyzer`/`DynamicRangeAnalyzer` state is guarded by `HybridProcessor._process_lock`; `FingerprintNormalizer.fit` publishes a complete dict (#5243) and `FingerprintSimilarity.fit` holds `_fit_lock`; `ResizableSemaphore` acquire/release/resize/over-release logic is correct.
- **KeyboardInterrupt**: no bare `except:` or `except KeyboardInterrupt` in `auralis/analysis`, `auralis/services`; the single `except BaseException` (`fingerprint_worker._extract_bounded._run`) re-raises on the caller thread; `windowed_compute`/analyzer catch `Exception` only.
- **Fingerprint worker design**: `_extract_bounded` abandons a hung daemon thread (documented, #4837), semaphore released in `finally`, per-track attempts capped (#5308), claim/drain bookkeeping uses real thread count (#4596); sidecar validation checks algorithm version, size+mtime and finite numeric dims (#4910 fix in place).
- **Retired/offline weighting**: `mastering_*` offline CLI items were not re-filed.

#### Dimension 7: Library & Database

- Repository pattern: no raw SQL outside `repositories/` and `migrations/`; the only `text()` outside repositories is `PRAGMA` in `database.py`/`database_engine.py`. In-repository `text()` (playlist `INSERT OR IGNORE ... SELECT`, fingerprint upserts with whitelisted column names via `_validate_fingerprint_columns`, scheduler claim) is parameterised/validated.
- Detached ORM instances: every Track read path carries `_track_eager_options()` (genres always selectin); Album/Artist/Playlist/Genre detail options verified; all `to_dict()` use `_safe_collection`/`_safe_scalar`; the `refresh()` sites (`Track.add`, `update_artwork_path`, `GenreRepository.create/update`, `PlaylistCrudMixin.create`) re-load or touch the relationship while attached. Only dead `get_tracks_by_genre` misses (#5754).
- `BaseRepository._session_scope()`: all repositories use it; rolls back on any escaping exception. No repository catches a failure and returns an attached object. Only `RepositoryFactory.reset_library` hand-rolls a session (correct rollback/close, not a repository class).
- SQLite config: `check_same_thread=False`, `pool_pre_ping=True`, `foreign_keys=ON`, WAL, `synchronous=NORMAL`, `busy_timeout` and connect timeout from shared constants, identical contract in the migration engine and `FingerprintService._make_engine`. (Cosmetic: the `max_page_count=1073741823` comment says "~4GB"; at 4 KiB pages it is 4 TiB.)
- Engine disposal: `LibraryDatabase.shutdown()` does TRUNCATE checkpoint, `PRAGMA optimize`, `engine.dispose()`, clears `self.engine` in `finally`; `MigrationManager.close()`/context manager and `FingerprintService.close()` dispose their engines.
- Concurrent scans: `ScanCoordinator` slot counter and exclusive flag share one lock; claim/release are paired in `claim_scan`/`scan_directories.finally`; `LibraryScanner` calls the guard directly with no `except AttributeError` (#5802 fix present, `grep AttributeError auralis/library/` shows only the comment).
- `cleanup_missing_files`: id-cursor batching of 1000, bounded memory, batched recheck, per-batch commit, association rows and playlist positions handled by `delete_tracks_by_ids`. (Unreadable-folder data loss is Known #5698.)
- Migration safety: file lock plus same-process `threading.Lock` in `migration_lock` (never unlinked), double-checked version after lock, pre-migration backup with the SQLite online backup API, restore on failure (probe confirmed a failed step restored the backup), DDL + version row in one transaction, `DROP TABLE` gate with explicit `@ALLOW_DROP_TABLE` (only v015 child-table rebuild and v020 retirement use it), migration chain v001..v023 contiguous and `__db_schema_version__ = 23`. Observation (not filed): `migration_v022_to_v023.sql` runs `UPDATE user_settings` although no migration ever creates that table (only `create_all`, which runs after migration), so a pre-Oct-2025 DB that never ran an app with `UserSettings` would fail that step.
- Pagination determinism: probed `get_popular`, `get_all` (title/year/play_count), `get_recent` and artists-by-track_count with heavy ties over 12 pages of 50 -> no duplicates or skips and page-concatenation equal to one large page, so the missing `Track.id` tiebreaker (unlike `search`, #4796) is not reproducible on this SQLite; not filed.
- Duplicate association rows from repeated artists/genres in one `add()`: SQLAlchemy de-duplicates the collection (probe: one `track_artist` row, one `track_genre` row).
- `escape_like` + `escape='\\'` used by every search; `order_by` columns whitelisted; `track_deletion.delete_tracks_by_ids` clears association tables before `tracks` (FK ON); `reset_library` order respects FKs and relies on `ON DELETE CASCADE` for fingerprints/similarity edges.
- Scanner: depth cap (`MAX_SCAN_DEPTH=50`), directory-inode cycle detection, hidden/skip dirs, per-file exception isolation, bounded failure list with path redaction; symlinked directory cycles handled (the ELOOP gap is E7-03).
- Settings repository: class-level RLock serialises all read-modify-write on the singleton row; field allowlist enforced.
- `hasattr`/`getattr` on `TrackFingerprint` in `get_by_multi_dimension_range` and `setattr` loops are reachable only with internal callers; no SQL injection path.
