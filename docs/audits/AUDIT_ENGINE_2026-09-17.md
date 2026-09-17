# Audio Engine Audit — 2026-09-17

**Scope**: `auralis/core/`, `auralis/dsp/`, `auralis/player/`, `auralis/io/`, `auralis/analysis/`, `auralis/services/`, `auralis/library/`, `auralis/optimization/`, `vendor/auralis-dsp/`
**Depth**: deep | **Dimensions**: all 7 | **HEAD**: `a59e77de`
**Method**: one agent per dimension, at most 3 at a time. The orchestrator re-checked every CRITICAL, HIGH and MEDIUM claim against the source and reproduced the CRITICAL end to end. Deduplicated against the last 2,000 issues and the 2026-09-16 engine report.

This audit deliberately targets the last 24 hours, in which the engine changed more than in the preceding weeks: pyo3/numpy 0.23 → 0.29 (`acd42e3e`), librosa 0.11 → 1.0 (`61948c73`), the #5505 fingerprint sanitizer, the #5507 saver guard, the #5506 metadata writers, the #5508 queue change listener, and two cleanup commits from a parallel session (`e5e2cd05`, `a59e77de`) that fixed most of #5509–#5513 in code while leaving those issues open.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH     | 1 |
| MEDIUM   | 1 |
| LOW      | 9 |
| **Total**| **12** |

**Severity changes and merges made by the orchestrator**
- **ENG-D2-01: HIGH → LOW.** The claim needs a negative or zero `low_energy`, which cannot happen: the band `*_pct` values are power ratios from a summed PSD. A probe on noise, digital silence and DC gave minimum values of 0.0045, 0.0036 and 0.020, each set summing to 1.0000. Before #5505 the same input raised `ValueError`, so the guard improved matters rather than regressing them.
- **ENG-D2-02 merged into ENG-D5-01.** Two dimensions reported the same `e5e2cd05` stage-aggregation code.

**Both of the serious findings are incomplete fixes from the last 24 hours**, and one of them is this session's own:
1. **ENG-D7-01 (CRITICAL)**: no fresh install can persist a fingerprint. The `track_fingerprints` columns `is_reference`, `reference_weight` and `fingerprint_version` are `NOT NULL` with Python-side defaults only. A migrated database got real SQL defaults from its `ALTER TABLE` migrations, but a fresh database is built by `create_all()` and gets none. Both raw-SQL `INSERT`s omit the columns, so every write raises `IntegrityError`, is caught, rolled back and logged. Reproduced: `upsert()` returned `None` and the table stayed empty.
2. **ENG-D6-01 (HIGH)**: the #5505 sanitizer covers `AudioFingerprintAnalyzer.analyze()`, but two backend producers call `compute_fingerprint_schema()` directly and are still unguarded. That fix's completeness check confirmed the guard was wired into `analyze()` and never grepped the Rust helper's other callers.

**Key themes**
1. **A fix that lands in one place and misses its siblings.** #5505 (ENG-D6-01), #5507 (ENG-D1-02), #5511 (ENG-D1-01), #5513 (ENG-D3-01), #4130 (ENG-D4-02) all follow this shape. The pattern is strong enough to be worth a habit: after each fix, grep for the *callee*, not only the fixed call site.
2. **Fresh-install versus migrated database drift.** ENG-D7-01 is the second instance after #5321 (missing indexes on fresh databases). The schema has two construction paths and only one is exercised in practice.
3. **Docs and comments left behind by yesterday's cleanups** (ENG-D5-01, ENG-D5-02, ENG-D6-02).
4. **The two big dependency upgrades came through clean.** Dimension 4 rebuilt real fixtures in every format and confirmed no librosa 1.0 decode regression; dimensions 1, 2 and 6 probed the pyo3 0.29 boundary and found GIL release, panic mapping, dict keys, dtypes and determinism all unchanged. Chunk-seam continuity, reassembly length, the queue listener's lock ordering (340k mutations, no deadlock) and the #5507 saver repair were all verified by probe.

**Issues fixed in code but still open** (the parallel session did not close them): #5509, #5510, #5511, #5512 and #5513 are all confirmed fixed except the two stress-test call sites in ENG-D3-01. They should be closed after a check.

---

## Findings

### CRITICAL

#### ENG-D7-01: Every fresh-install fingerprint write fails silently — `is_reference`/`reference_weight` are NOT NULL with no SQL-level default, and both raw-SQL `INSERT`s in `fingerprint_upsert_mixin.py` omit them
- **Severity**: CRITICAL
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_upsert_mixin.py:76-103` (`upsert()`), `auralis/library/repositories/fingerprint_upsert_mixin.py:156-188` (`store_fingerprint()`); root cause columns `auralis/library/models/fingerprint.py:87,93` (`is_reference`, `reference_weight` — Python-side `default=` only); fresh-DB path `auralis/library/migration_manager.py:142-167` (`initialize_fresh_database` → `Base.metadata.create_all`)
- **Status**: NEW
- **Description**: `TrackFingerprint.is_reference` and `.reference_weight` are declared `nullable=False` with a Python-side `default=False` / `default=0.0` (`mapped_column(..., default=...)`, not `server_default=...`). SQLAlchemy only applies a bare `default=` during an ORM flush; it does not emit a DDL `DEFAULT` clause. On a **migrated** database these two columns exist instead via `ALTER TABLE track_fingerprints ADD COLUMN is_reference INTEGER NOT NULL DEFAULT 0` (`migration_v014_to_v015.sql`) and `... reference_weight REAL NOT NULL DEFAULT 0.0` (`migration_v016_to_v017.sql`) — a real SQL-level default, so SQLite fills them in when a raw `INSERT` omits them. On a **fresh** install, `MigrationManager.initialize_fresh_database()` builds the schema purely from `Base.metadata.create_all()` and never runs the incremental `ALTER TABLE` steps, so the generated columns are `is_reference BOOLEAN NOT NULL` / `reference_weight FLOAT NOT NULL` with **no DEFAULT at all** (confirmed by dumping the actual DDL SQLite produced — see Evidence). Both `upsert()`'s and `store_fingerprint()`'s raw `INSERT INTO track_fingerprints (...)` statements list only `track_id`, the 25 float dimensions, and (for `store_fingerprint`) `fingerprint_blob`/`fingerprint_version` — neither lists `is_reference` nor `reference_weight`. On a fresh database, the `INSERT` therefore always raises `sqlite3.IntegrityError: NOT NULL constraint failed: track_fingerprints.is_reference`, which both methods catch, roll back, log as an `error()`, and swallow by returning `None`.
- **Evidence**:
  ```
  $ sqlite3 /tmp/audit_probe_db/test.db ".schema track_fingerprints"
  CREATE TABLE track_fingerprints (
      ...
      fingerprint_version INTEGER NOT NULL,
      is_reference BOOLEAN NOT NULL,          -- no DEFAULT
      reference_weight FLOAT NOT NULL,        -- no DEFAULT
      fingerprint_blob BLOB,
      ...
  );
  ```
  Live probe against a brand-new `LibraryDatabase(tmp_path)` (scratch `HOME`, never touching the real library):
  ```python
  result = repo.upsert(track_id=track_id, fingerprint_data=fp)   # the actual production call
  print(result)  # -> None
  # DB row for that track_id: None (row was never created)
  ```
  Direct replay of `store_fingerprint()`'s SQL reproduces the same exception:
  `sqlite3.IntegrityError: NOT NULL constraint failed: track_fingerprints.is_reference`.
  Both production callers already defensively check the return value and only log-and-skip: `auralis/services/fingerprint_extractor.py:141` (`if not self.fingerprint_repo.upsert(...): error(...); return False`) and `auralis/analysis/fingerprint/fingerprint_service.py:275` (`return self._fingerprint_repo.upsert(...) is not None`) — so nothing crashes, but nothing is ever stored either.
- **Impact**: On every fresh install (a new user, or any user who follows the project's own documented recovery step "delete `~/.auralis/library.db`" from the Troubleshooting table), **no track fingerprint is ever persisted**, permanently — this is not a one-time race, it is a schema-level defect that reproduces on every single call. `fingerprint_extractor.extract_and_store()` returns `False` and logs `"Failed to store fingerprint for track {id}"` for every track, forever; the fingerprint queue/status subsystem sees perpetual failures; similarity search and "find similar tracks" have nothing to query; and `auralis/learning/reference_seeder.py`'s reference-cloud selection (`select_and_seed_references` → `repository.set_reference_weights(weights)`) has zero fingerprint rows to score, so the reference cloud stays permanently empty. `auralis/core/processing/target_derivation.py`'s soft k-NN reference-weighted target refinement therefore never engages for any fresh-install user — mastering silently falls back to its non-reference-informed default target for the life of the install. The failure is completely silent to the end user (only an `error()`-level log line, no user-facing surface), and there is no workaround short of a schema fix — deleting and recreating the database reproduces the exact same broken schema.
- **Siblings**: None — a repo-wide grep for `INSERT INTO` under `auralis/library/repositories/` found exactly these two call sites, both in this file.
- **Suggested Fix**: Add `is_reference` and `reference_weight` to both `INSERT` column lists (with literal `0`/`0.0`, mirroring how `fingerprint_version` is already special-cased as "supplied on INSERT, absent from the UPDATE clause" for the same reason) — do **not** add them to `update_clause`, so an existing reference flag/weight is never clobbered by a routine dimension refresh. Longer-term: add a regression test that builds a database via `Base.metadata.create_all()` only (no migrations) and asserts `upsert()` succeeds, so fresh-vs-migrated schema drift on this table (already the root cause of closed #5321) cannot silently reappear a third time.
- **Orchestrator note**: CRITICAL confirmed by the orchestrator, reproduced end to end. On a brand-new `LibraryDatabase` file, `RepositoryFactory.fingerprints.upsert(track_id, dims)` returned `None` and `select count(*) from track_fingerprints` stayed at 0. Dumping the fresh DDL shows `is_reference`, `reference_weight` and `fingerprint_version` all `NOT NULL` with no `DEFAULT`.

### HIGH

#### ENG-D6-01: Two backend fingerprint producers bypass the #5505/#5103 sanitizer, the shared windowed pipeline's duration cap, and its batch/streaming parity guarantee
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis-web/backend/core/mastering_target_service.py:216-284`, `auralis-web/backend/analysis/fingerprint_generator.py:139-196,291-346`
- **Status**: NEW (sibling gap the #5505 and #5103 fixes never covered — not a regression, since neither fix ever touched these files)
- **Description**: `sanitize_non_finite()`'s own docstring claims it "runs at the end of `AudioFingerprintAnalyzer.analyze`, which every producer calls." That's false for two production call paths that go straight to `compute_fingerprint_schema()` (the raw, unsanitized Rust→schema glue in `rust_fingerprint.py`) instead of through `AudioFingerprintAnalyzer.analyze()`:
  1. `MasteringTargetService.extract_fingerprint_from_audio()` (Tier-3, "extract from audio" — the path used the first time a track is mastered before it has a cached fingerprint) calls `compute_fingerprint_schema()` directly at `mastering_target_service.py:247` in its primary (non-exception) branch, then immediately feeds the raw result into `generate_targets_from_fingerprint()` (`mastering_target_service.py:277`, itself unguarded — `target_lufs = current_lufs * 0.4 + streaming_target * 0.6` propagates a NaN `lufs` straight into the mastering targets) and persists it unsanitized to both the `.25d` sidecar (`FingerprintStorage.save()`, line 282) and, via the caller chain, the DB.
  2. `FingerprintGenerator._compute_fingerprint_in_thread()` (`fingerprint_generator.py:169-196`, invoked from `get_or_generate()` → `_generate_via_rust()`, used by `stream_fingerprint.py` on stream start and by `analysis/fingerprint_queue.py`'s background worker) also calls `compute_fingerprint_schema()` directly and writes the unsanitized result straight to the database via `fingerprint_repo.add(track_id, fingerprint_data)` (`fingerprint_generator.py:284`) with no validation in `FingerprintCrudMixin.add()` either.

  Additionally, both paths independently re-implement the load→fingerprint sequence instead of calling the shared `compute_windowed_fingerprint()` that `services/fingerprint_extractor.py` and `fingerprint_service.py` already use: they call `load_audio(filepath)` (`mastering_target_service.py:227`, `fingerprint_generator.py:150`) with **no duration cap** — `auralis/io/unified_loader.py:load_audio()` has no offset/duration parameter at all — so a multi-hour podcast/DJ-mix/audiobook is fully decoded into memory just to fingerprint it, the same OOM class #4116 fixed for `mastering_fingerprint.py` and that `windowed_compute.py`'s 90s body + 2×30s-probe strategy and `fingerprint_extractor.py`'s `MAX_FINGERPRINT_FILE_SIZE_MB` guard exist to prevent. They also skip the body+probe LUFS/crest bias correction (#4595's validated fix for systematic LUFS error on tracks with a quiet intro), so a fingerprint computed via these two paths will differ from the same track's batch-scan fingerprint — the exact "whichever wrote the DB row first wins, and the two paths silently disagree" bug class #4595 was written to eliminate for good.

  Once a NaN/Inf-poisoned fingerprint reaches storage this way, nothing re-validates it on read: `fingerprint_service._load_from_database()`/`_load_from_file_cache()` and `mastering_target_service.load_fingerprint_from_database()`/`load_fingerprint_from_file()` only re-check `_band_pct_valid()` (the 7 frequency-band fractions summing to ~1), which does not cover `lufs`, `crest_db`, or any of the other 18 dimensions — so a poisoned `lufs` persists across every future mastering pass for that track until it is manually re-fingerprinted.
- **Evidence**: Live probe (monkeypatching a NaN `lufs` into the Rust result) confirms the divergence:
  ```
  AudioFingerprintAnalyzer.analyze() lufs -> 0.0   (sanitized: True)
  _compute_fingerprint_in_thread() lufs   -> nan   (sanitized: False)
  ```
  `rust_fingerprint.py:135-138` (`compute_fingerprint_schema`) performs no sanitization itself — it is a thin, deliberately unguarded glue layer; sanitization is the caller's job, and `AudioFingerprintAnalyzer.analyze()` is the only caller that does it (`audio_fingerprint_analyzer.py:103-106`).
  Commit `2136d0da` (#5505)'s diff touched only `audio_fingerprint_analyzer.py`, `windowed_compute.py`, `continuous_space.py`, `fingerprint_quantizer.py` and two test files — it never touched `mastering_target_service.py` or `fingerprint_generator.py`.
- **Impact**: Reachable in normal use — every first-time playback/mastering of a track without a cached fingerprint goes through `MasteringTargetService`'s Tier-3 path, and every on-demand/queue-driven fingerprint generation goes through `FingerprintGenerator`. A degenerate input (silence, a corrupt decode region, an extreme-content file that pushes the Rust engine's math to a NaN/Inf edge — the same trigger #5103/#5505 were written for) reaching either path produces: (a) mastering targets computed from NaN/Inf, feeding the same "all-NaN buffer → zeroed track reported as success" failure mode #5505 fixed for the `ContinuousMode` path; (b) a permanently poisoned DB row / `.25d` file that every subsequent read serves as valid, since no read-time check catches it; (c) `FingerprintNormalizer.fit()` (`normalizer.py:172-173`, `np.asarray([fp.to_vector() for fp in batch])` then `np.percentile`/`np.mean`/`np.std` per column) has its statistics for that dimension turned to NaN for the **entire library**, not just the poisoned track — `normalize()`'s `range_val > 1e-6` check happens to fail safe on NaN (comparisons with NaN are always False, so it falls into the zero-variance 0.5 branch) rather than propagating NaN further, but every track's similarity score on that dimension silently degrades to "no information" until a clean refit; (d) fingerprints computed via these two paths systematically disagree with the same track's batch-scan fingerprint (no bias-correction, no windowing), undermining fingerprint-based similarity/dedup between a freshly-streamed track and its later library-scanned self.
- **Siblings**: None beyond the two listed — every other fingerprint producer (`services/fingerprint_extractor.py`, `fingerprint_service.py`, `core/recording_type_detector.py`, `core/processing/continuous_mode.py`, `core/analysis/content_analyzer.py`) goes through `AudioFingerprintAnalyzer.analyze()` directly or via `compute_windowed_fingerprint()`, both of which sanitize.
- **Suggested Fix**: Route both call sites through `compute_windowed_fingerprint()` (or, at minimum, through `AudioFingerprintAnalyzer.analyze()` plus the existing 90s/probe-bounded loader) instead of calling `compute_fingerprint_schema()`/`load_audio()` directly — this is the same fix in the same shape #4595 already applied to the other two producers, and it closes the sanitization gap, the duration-cap gap, and the batch/streaming-parity gap in one change since all three live in the shared function.
- **Orchestrator note**: Confirmed: `grep -rn compute_fingerprint_schema` shows exactly two callers outside the analyzer, `auralis-web/backend/analysis/fingerprint_generator.py:192-193` and `auralis-web/backend/core/mastering_target_service.py:223,247`, and `rust_fingerprint.compute_fingerprint_schema` contains no finiteness check of its own. This is an incomplete-fix gap in #5505 (this session's own fix): its completeness check verified the guard was wired into `analyze()`, but never grepped the Rust helper's other callers. The call sites are in the backend, which this audit nominally excludes, but the broken contract is the engine's.

### MEDIUM

#### ENG-D1-02: FFmpeg-decoded audio is written to a temp WAV via a bare `sf.write()` with no clip and no NaN/Inf repair — sibling of the #5507 saver.py fix
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/simple_mastering.py:184-185`
- **Status**: NEW (sibling pattern of Existing/fixed #5507)
- **Description**: When `SimpleMasteringPipeline._master_file_impl()` (the offline CLI mastering entry point, reached only via `auto_master.py` — "nothing in the Electron app reaches" this subsystem per that script's own docstring, #4873) processes an FFmpeg-only format (mp3/m4a/aac/…), it decodes via `load_with_ffmpeg()` and immediately re-encodes the raw result to a temporary WAV with a direct `sf.write()` call — bypassing `auralis/io/saver.py::save()` entirely, and therefore both the `#5507` NaN/Inf repair *and* the `[-1, 1]` clip that `saver.save()` applies. `load_with_ffmpeg()` itself (`auralis/io/loaders/ffmpeg_loader.py`) has no finiteness or range guard (`grep` for `isfinite`/`isnan`/`clip` in that file: no hits). If a malformed/corrupt source file makes FFmpeg emit a non-finite or out-of-range sample, it round-trips through this PCM_24 write with `sf.write`'s behavior for a non-finite input sample being implementation-/build-dependent — exactly the failure mode #5507 fixed for the final-output writer. Worse, once quantized into fixed-point PCM_24, the NaN no longer *is* NaN, so it also slips past the fail-fast `validate_audio_finite(repair=False)` check in `mastering_process_chunk.py:88` that re-reads this temp file's chunks — that check only catches literal NaN/Inf, not the finite-but-garbage value libsndfile may have substituted.
- **Evidence**:
  ```python
  # auralis/core/simple_mastering.py:181-186
  from ..io.loaders import load_with_ffmpeg
  _tmp_dir = _tempfile.TemporaryDirectory()
  _tmp_wav = Path(_tmp_dir.name) / (orig_path.stem + "_dec.wav")
  _raw, _raw_sr = load_with_ffmpeg(orig_path, _tmp_dir.name)
  sf.write(str(_tmp_wav), _raw, _raw_sr, subtype="PCM_24")   # no clip, no NaN guard
  resolved_input_path = _tmp_wav
  ```
  Confirmed no guard exists anywhere upstream: `grep -n "isfinite\|isnan\|validate_audio_finite\|np.clip" auralis/io/loaders/ffmpeg_loader.py` → no matches.
- **Impact**: Narrow blast radius — this path is exercised only by the standalone `auto_master.py` CLI tool on FFmpeg-routed formats (mp3/m4a/aac/ogg/wma), not by the live backend or desktop app, and only triggers when FFmpeg's own decode of a malformed/corrupt file produces a non-finite or out-of-range sample. When it does trigger, the corrupted sample(s) propagate through the entire chunked mastering pass (not just one output file) because this temp WAV becomes the DSP pipeline's input, and the downstream fail-fast NaN check cannot catch it once PCM quantization has turned NaN into some other finite value. Rated MEDIUM, consistent with #5507 (same bug class, same "undefined value with nothing logged" mechanism), not HIGH, given the narrower reach (CLI-only, requires a corrupt source decode) versus #5507's live backend export-job blast radius.
- **Siblings**: None — grepped every `load_with_ffmpeg` call site (`unified_loader.py`, `loader.py`, `windowed_compute.py`, `mastering_fingerprint.py`); only `simple_mastering.py:185` re-encodes the decoded buffer back to a WAV file. The others keep it in memory and never call `sf.write` on it.
- **Suggested Fix**: Route this write through `auralis.io.saver.save()` instead of a bare `sf.write()` (it already handles the float32 cast, NaN/Inf repair, and clip for any subtype), or at minimum call `validate_audio_finite(_raw, context="ffmpeg pre-transcode", repair=True)` and `np.clip(_raw, -1.0, 1.0)` before this `sf.write`.
- **Orchestrator note**: Confirmed: `simple_mastering.py:185` calls `sf.write(..., subtype='PCM_24')` directly on the FFmpeg-decoded buffer, bypassing `auralis/io/saver.py::save()` and its #5507 repair.

### LOW

#### ENG-D1-01: Sample-count invariant checks in the non-chunked mastering paths are bare `assert`s, stripped under `python -O` — sibling gap left by #5511's own completeness check
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/hybrid_processor.py:274`, `auralis/core/hybrid_processor.py:301`, `auralis/core/hybrid_stage_dispatch.py:120`, `auralis/core/processing/hf_aware_limiter.py:117`
- **Status**: NEW (sibling of Existing #5511)
- **Description**: `e5e2cd05` fixed the two sample-count `assert`s in `auralis/core/mastering_chunk_loop.py` (issue #5511) by converting them to `if ...: raise RuntimeError(...)`. #5511's own body included an explicit, unchecked "Completeness Checks" item: *"CONSISTENCY: `grep -rn \"^\s*assert \" auralis/core/ auralis/dsp/` to find other production invariants that rely on `assert`. Fix them too, or list them as out of scope."* That grep was not (re-)run as part of the fix — it still finds four more post-limiter/post-filter shape invariant checks written as bare `assert`s: the adaptive-mode and hybrid-mode post-limiter checks in `hybrid_processor.py` (lines 274, 301), the reference-mode post-limiter check in `hybrid_stage_dispatch.py` (line 120), and the HF-aware limiter's shape-preservation check in `processing/hf_aware_limiter.py` (line 117). Under `python -O`/`PYTHONOPTIMIZE`, all four are compiled out, silently removing the last-line-of-defense check that the brick-wall limiter / HF-aware limiter didn't change the sample count.
- **Evidence**:
  ```python
  # auralis/core/hybrid_processor.py:272-277
  processed = self.brick_wall_limiter.process(processed)
  # Sample-count invariant: limiter must preserve length (fixes #2519)
  assert processed.shape == target_audio.shape, (
      f"Sample count mismatch after limiter (adaptive): "
      f"expected {target_audio.shape}, got {processed.shape}"
  )
  ```
  Same pattern at `hybrid_processor.py:301` (hybrid mode) and `hybrid_stage_dispatch.py:120` (reference mode); `hf_aware_limiter.py:117` guards `restored.shape == in_shape` after re-splitting a possibly-limited composite.
- **Impact**: No behavior change today — no launcher in this repo runs Python with `-O`. If one ever did (or `PYTHONOPTIMIZE=1` is set in an environment), a future DSP regression in the limiter/HF-aware-limiter path would silently truncate or pad the output instead of raising, corrupting the chunk/track downstream with no diagnostic. Same class and severity as #5511, which the project already rated LOW for the identical reasoning ("Only when Python runs with -O and a DSP bug also occurs").
- **Siblings**: None beyond the four listed (full `grep -rn "^\s*assert " auralis/core/ auralis/dsp/` sweep run; the remaining hits are parameter-range validations in `auralis/core/config/settings.py` and `unified_config.py`, a different category — config-construction validation, not a per-stage sample-count/shape invariant — and two `assert result is not None` liveness checks in `hybrid_processor_singleton.py`).
- **Suggested Fix**: Convert all four to `if <violated>: raise RuntimeError(...)`, matching the pattern `e5e2cd05` already applied to `mastering_chunk_loop.py`; close out #5511's outstanding completeness checkbox referencing this location.
- **Orchestrator note**: Confirmed: `grep -rn '^\s*assert ' auralis/core/ auralis/dsp/` shows the four shape asserts (`hybrid_processor.py:274,301`, `hybrid_stage_dispatch.py:120`, `processing/hf_aware_limiter.py:117`), plus unrelated config/singleton asserts.

#### ENG-D2-01: `_calculate_spectral_balance`'s post-#5505 ratio guard creates a discontinuity — and a `ZeroDivisionError` — exactly at the boundary it's meant to protect

- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_space.py:209-230` (`ProcessingSpaceMapper._calculate_spectral_balance`), guard added by `2136d0da` (#5505)
- **Status**: NEW (related to #5505 — the original NaN-propagation bug #5505 fixed is still fixed; this is a new defect introduced by that fix)
- **Description**:
  `#5505` added a guard so a non-finite `ratio` degrades to `_smooth_unit`'s
  neutral midpoint instead of propagating `nan` into every downstream
  parameter:
  ```python
  ratio = (high_energy + self._ENERGY_EPSILON) / (low_energy + self._ENERGY_EPSILON)
  log_high_low = (
      math.log(ratio) if math.isfinite(ratio) and ratio > 0 else math.nan
  )
  ```
  Two problems:
  1. **The division itself is unguarded.** If `low_energy == -self._ENERGY_EPSILON`
     exactly, the denominator is `0.0` and Python's plain-float division raises
     `ZeroDivisionError` *before* the `isfinite`/`ratio > 0` check ever runs.
     Nothing between here and `HybridProcessor._process_adaptive_mode` catches
     it — `continuous_mode.py::process()` → `_resolve_parameters()` →
     `ProcessingSpaceMapper.map_fingerprint_to_space()` has no intervening
     `try/except` — so this one uncaught exception aborts the whole mastering
     call for that chunk/track.
  2. **The fallback is discontinuous, not neutral.** `low_energy`/`high_energy`
     are sums of `*_pct` fingerprint dimensions (`rust_fingerprint.py` docs
     them as "already 0-1 fractions"), and unlike `spectral_centroid`/
     `spectral_rolloff` in that same adapter, the band fractions are **not**
     clamped to `[0, 1]` (no `_clip01`) before reaching this code — only
     `sanitize_non_finite()` runs on them, which strips NaN/Inf but not a
     small negative value. As `low_energy` (or symmetrically `high_energy`)
     crosses zero from the positive side, the *correct* continuous behavior
     (visible on the positive side of the sweep below) is for
     `spectral_balance` to saturate smoothly toward its asymptote. Instead,
     the instant the denominator goes negative, the code abandons the
     mathematically well-defined (if extreme) ratio and substitutes the flat
     neutral `0.5`, producing a hard jump rather than a continuation of the
     saturating curve.
- **Evidence** (probe against the live module, `low_energy` swept with
  `high_energy` fixed at 10, `spectral_centroid` fixed):
  ```
  low_energy= 0.01          spectral_balance=0.854374
  low_energy= 1e-08         spectral_balance=0.854374
  low_energy= 0.0           spectral_balance=0.854374
  low_energy=-1e-08         EXCEPTION: ZeroDivisionError: division by zero
  low_energy=-1e-06         spectral_balance=0.504374   <-- jump of 0.35
  low_energy=-0.01          spectral_balance=0.504374
  low_energy=-50            spectral_balance=0.504374
  ```
  The symmetric case (`high_energy` swept negative, `low_energy` fixed at 10)
  shows the same ~0.35 jump (0.154 → 0.504) without hitting the
  `ZeroDivisionError` path (a zero *numerator* is not a crash, only a zero
  *denominator* is).
  A related, lower-reachability instance of the same root cause: `_smooth_unit`
  (line 18-27) now maps a literal `+inf`/`-inf` input to the neutral `0.5`
  (`if not math.isfinite(value): return 0.5` catches Inf as well as NaN),
  whereas the original `tanh`-only implementation handled `±inf` correctly by
  saturating to `1.0`/`0.0` — the same value large-but-finite inputs already
  saturate to (`smooth_unit(1e10) == 1.0`, but `smooth_unit(inf) == 0.5`).
  This path is currently hard to reach in production because
  `sanitize_non_finite()` already zeroes any non-finite fingerprint dimension
  before `continuous_space.py` sees it, and `log_high_low`'s own non-finite
  case is force-set to `math.nan` rather than an infinity — but it means the
  fix conflated "NaN" (genuinely needs a neutral fallback) with "Inf" (already
  handled correctly by `tanh`) into one branch.
- **Impact**: Two fingerprints that differ by a fraction of a percent in
  low-frequency or high-frequency energy — exactly the "differ slightly" case
  the Dimension 2 checklist calls out — can receive a `spectral_balance`
  coordinate that differs by ~0.35 out of the full 0-1 range, i.e. a
  dramatically different EQ/spectral-tilt decision for two audibly
  indistinguishable inputs. Content genuinely low in bass energy (thin
  recordings, heavily high-pass-filtered material, high-pitched test tones)
  is the most likely to land near this boundary, where ordinary
  floating-point noise in the upstream band-energy sum decides which side of
  the jump a given track falls on. In the narrower case where the sum lands
  exactly on `-_ENERGY_EPSILON`, mastering fails outright with an unhandled
  `ZeroDivisionError` instead of producing a master or a clean error.
- **Siblings**: None outside this function — `_ENERGY_EPSILON`/`high_energy`/
  `low_energy` are local to `_calculate_spectral_balance`; `_smooth_unit` is
  shared by all three coordinate axes (`_calculate_dynamic_range`,
  `_calculate_energy_level`) but the crash and the ~0.35 jump both need the
  `log_high_low` ratio-sign flip specific to this method, not just any
  `_smooth_unit` call — the other two axes' finite domains (crest_db, lufs,
  loudness_variation) don't hit an internally-computed division.
- **Suggested Fix**: Compute the ratio defensively (e.g. clamp `low_energy`/
  `high_energy` to `max(0.0, value)` before adding the epsilon, which both
  removes the zero-denominator case and keeps the curve continuous through
  zero), and drop `Inf` from `_smooth_unit`'s "map to neutral" branch — handle
  it the way plain `tanh` already does (saturate to 0/1) and reserve the
  neutral-midpoint fallback for `NaN` only, which is the actual failure mode
  #5505 was fixing.
- **Orchestrator note**: HIGH → LOW. The premise (a negative or zero `low_energy`) is unreachable: the band `*_pct` values are power ratios from a summed PSD, so they are non-negative by construction — a probe on noise, digital silence and DC gave min values of 0.0045, 0.0036 and 0.020, each set summing to 1.0000 — and `sanitize_non_finite()` replaces a non-finite dimension with 0.0, never a negative. Before #5505 the same input raised `ValueError` from `math.log`, so the guard strictly improved the behavior rather than introducing a regression. Worth hardening (guard the denominator, and let `_smooth_unit` saturate on ±Inf instead of returning neutral), but it is defence in depth.

#### ENG-D3-01: Two stress tests still call the `QueueController.clear()` alias `e5e2cd05` deleted
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `tests/stress/test_processing_stress.py:128`, `tests/stress/test_large_library.py:502` (class `TestLongRunningOperations`, method `test_1000_track_queue`)
- **Status**: Existing: #5513 (fix incomplete)
- **Description**: #5513 (filed earlier the same day, `docs/audits/AUDIT_DEPRECATION_2026-09-17.md` finding DEP-INT-01) asked to delete `QueueController.clear()` and enumerated every caller that needed updating first: the backend production caller (`queue_edit_mixin.py:203`) and five test call sites. `e5e2cd05` did the deletion (`auralis/player/queue_controller.py`, removing the `clear()` alias) and correctly fixed the production caller and three of the five listed test files (`tests/auralis/player/test_enhanced_player.py`, `test_queue_controller.py` — renamed `test_clear_alias_works` to `test_clear_queue_works`, `test_queue_change_invalidates_prebuffer_5508.py` — dropped the `("clear", ...)` mutation row). The other two test files #5513 explicitly listed, `tests/stress/test_processing_stress.py:128` and `tests/stress/test_large_library.py:502`, were not touched and still call `player.queue.clear()` on a live `QueueController` instance.
- **Evidence**: `hasattr(QueueController, "clear")` is `False` (confirmed live: `QueueController(lambda: None).clear()` raises `AttributeError: 'QueueController' object has no attribute 'clear'`). `grep -rn "\.clear()" auralis/player/ auralis-web/backend/services/` shows zero remaining production callers; `grep -rn "player\.queue\.clear(" tests/` shows exactly these two hits. In practice both tests currently fail one line *earlier* than the `.clear()` call, at `player = AudioPlayer()` (`enhanced_audio_player.py:84`, `ValueError: get_repository_factory is required` — a pre-existing, unrelated constructor requirement neither cleanup commit touched), confirmed by running both tests directly with `-m ""` to bypass the `slow` marker filter. `test_processing_queue_overflow` is already listed in `pytest-baseline.json`; `test_1000_track_queue` is `@pytest.mark.slow`-marked and therefore never collected into the baseline at all (CI runs `-m "not slow"`), so it is invisible to the ratchet either way.
- **Impact**: None today — both tests are already broken before reaching the deleted method, so this doesn't newly fail CI. But it leaves #5513's own "no `QueueController.clear()` caller may remain anywhere in the repo" completeness check unmet, and the moment the unrelated `AudioPlayer()` constructor bug is fixed, both tests will start failing with `AttributeError` instead of passing, silently reintroducing the exact problem #5513 was filed to close.
- **Siblings**: None — these are the only two remaining `.clear()` calls on a `QueueController`/`AudioPlayer.queue` anywhere in `auralis/`, `auralis-web/`, or `tests/`.
- **Suggested Fix**: Change both call sites to `player.queue.clear_queue()`, matching the three test files `e5e2cd05` already fixed the same way, and check `#5513`'s remaining completeness/acceptance boxes as done.
- **Orchestrator note**: Confirmed: `hasattr(QueueController, 'clear')` is False, and `tests/stress/test_processing_stress.py:128` and `tests/stress/test_large_library.py:502` still call `player.queue.clear()`.

#### ENG-D4-01: `scripts/rate_track.py` calls `librosa.load()` directly with no `FFMPEG_FORMATS` gate — breaks on M4A/AAC/WMA under librosa 1.0
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `scripts/rate_track.py:19,64-69`
- **Status**: NEW
- **Description**: Every production fingerprint entry point (`mastering_fingerprint.py`,
  `windowed_compute.py`) checks `Path(file).suffix.lower() in FFMPEG_FORMATS` and routes
  through `auralis.io.loaders.load_with_ffmpeg` before ever calling `librosa.load()`. This
  dev script skips that gate entirely — `librosa.load(str(audio_path), sr=44100, mono=False)`
  is called on whatever path the user passes, unconditionally. Under librosa 0.x this fell
  through to the `audioread` backend for formats libsndfile can't open (M4A/AAC/WMA);
  librosa 1.0 (`61948c73`) removed that backend, so `librosa.load()` now raises instead.
- **Evidence**: Probed directly — `librosa.load('test.m4a', sr=44100, mono=False, duration=90.0)`
  and the same for `.wma` both raise `LibsndfileError: Format not recognised` under the
  installed librosa 1.0.0 / soundfile 0.14.0. MP3/OGG/OPUS/FLAC/WAV all still succeed via
  libsndfile's own native decoders, so the breakage is specific to M4A/AAC/WMA, not all
  FFmpeg-routed formats.
- **Impact**: `./scripts/rate_track.py song.m4a --rating 4` (or `.wma`/bare `.aac`) now prints
  `✗ Could not load audio: ...` and exits cleanly (the call is wrapped in
  `try/except Exception` at line 67-69) — no crash, no data corruption, but the script's one
  job (capture a fingerprint + rating) silently produces nothing for those three formats.
  Not reachable from any production/backend/frontend path — grepped for other callers, none
  found; this is a standalone CLI tool.
- **Siblings**: None — the two production fingerprint paths already gate correctly (see
  "Passed" above); this is the one caller that doesn't.
- **Suggested Fix**: Route through `auralis.io.unified_loader.load_audio()` (or gate on
  `FFMPEG_FORMATS` + `load_with_ffmpeg`, matching `mastering_fingerprint.py`) instead of
  calling `librosa.load()` directly.

#### ENG-D4-02: WMA metadata falls through to the no-op generic writer/reader — same bug class as #4130 (OPUS/WAV), but WMA was never added to the dispatch table
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/library/metadata_editor/metadata_editor.py:110-127,174-190`, `auralis/library/metadata_editor/readers.py:117-131`, `auralis/library/metadata_editor/writers.py:210-227`
- **Status**: NEW
- **Description**: `.wma` has been a fully scanned/supported audio format since `030831e4`
  (2026-06-02, same day as #4109/#4112) — it's in `FFMPEG_FORMAT_NAMES` and therefore in
  `AUDIO_EXTENSIONS`/`SUPPORTED_FORMATS`, so the library scanner ingests `.wma` tracks and
  the metadata-edit endpoint (`auralis-web/backend/routers/metadata.py`) has no
  format allowlist stopping a WMA track from reaching `MetadataEditor.write_metadata()`.
  But `metadata_editor.py`'s read/write dispatch (`isinstance(..., FLAC/MP4/OggOpus/OggVorbis/WAVE)`
  or `ext in (...)`) has no branch for ASF/WMA, so it falls to
  `writers.write_generic_metadata()` / `readers.read_generic_metadata()` — exactly the class
  of bug #4130 fixed for OPUS and WAV (both of which *were* added to the dispatch table that
  day; WMA was not, despite already being a live format).
  `write_generic_metadata()` assigns raw field names (`audio_file['track'] = ...`,
  `audio_file['title'] = ...`) directly as ASF attribute keys instead of the real ASF/WMA tag
  names (`Title`, `Author`, `WM/AlbumTitle`, `WM/Genre`, `WM/TrackNumber`, `WM/PartOfSet`,
  etc.), and none of `_with_existing_total()`'s track/disc total-preservation logic (#5506)
  applies to this path either, since it never runs for WMA.
- **Evidence**: Reproduced directly — copied a real `.wma` fixture, called
  `MetadataEditor().write_metadata(path, {'title': 'My Title', 'track': 5, 'artist': 'Some Artist'})`,
  got `ok=True` (reported success), then re-opened the file with mutagen directly:
  `{'track': [ASFUnicodeAttribute('5')], 'title': [ASFUnicodeAttribute('My Title')], 'artist': [ASFUnicodeAttribute('Some Artist')]}`
  — lowercase, non-standard keys with no `WM/` prefix, not the ASF-recognized `Title`/`Author`/`WM/TrackNumber`.
  A real WMA player (Windows Media Player, VLC, foobar2000, ffprobe's own tag reader) will not
  display these as title/artist/track — the edit is invisible to everything except this app's
  own `read_generic_metadata()`, which happens to lowercase-match `'Title'`→`'title'` by
  coincidence but would miss `'Author'`→`'author'` (not `'artist'`) and every `WM/*`-prefixed
  standard field entirely. `MetadataEditor.get_editable_fields()` also compounds this: for a
  `.wma` path it returns the FLAC field list (`get_format_key()` defaults unknown extensions
  to `'flac'`), implying the FLAC/Vorbis tag scheme applies, when the actual write dispatch
  uses the generic path instead — the two disagree about which tag scheme a WMA edit uses.
- **Impact**: A user editing title/artist/album/track/disc/etc. on a `.wma` library track
  via the metadata dialog gets a reported success, but the edit is functionally lost from the
  perspective of any other software, and pre-existing standard WMA tags on a real-world file
  (ripped by other tools) are neither read into the app's fields nor overwritten — they sit
  alongside the new bogus keys. No audio corruption, no crash; bounded to metadata
  correctness on one less-common format.
- **Siblings**: `get_supported_formats()` (`metadata_editor.py:66-68`) is stale in the same
  direction — it lists `['mp3', 'flac', 'm4a', 'aac', 'ogg', 'wav']`, omitting both `opus`
  (which #4130 gave a real branch to) and `wma`.
- **Suggested Fix**: Add an explicit ASF/WMA branch using `mutagen.asf.ASF` with a proper
  `TAG_MAPPINGS['wma']` table (`Title`, `Author`, `WM/AlbumTitle`, `WM/AlbumArtist`,
  `WM/Genre`, `WM/TrackNumber`, `WM/PartOfSet`, ...), reusing `_with_existing_total()` for
  track/disc, matching the #4130 pattern already used for OPUS/WAV. Update
  `get_supported_formats()` to match the real dispatch table.
- **Orchestrator note**: Confirmed: the writer dispatch in `metadata_editor.py:171-190` has no `wma`/ASF branch, so WMA falls through to `write_generic_metadata`.

#### ENG-D5-01: #5512's fix landed correctly in substance, but its own docstring and code comment now describe the wrong behavior
- **Severity**: LOW
- **Dimension**: Chunked Mastering Loop
- **Location**: `auralis/core/mastering_chunk_loop.py:42-49` (docstring), `auralis/core/mastering_chunk_loop.py:224-233` (comment + merge logic)
- **Status**: Existing: #5512 (fix landed, incomplete polish)
- **Description**: `e5e2cd05` correctly changed the chunk loop to merge every
  chunk's `stages` list into `info['stages']` (deduped by exact dict equality,
  first-occurrence order) instead of only ever using chunk 0's `info`. Two
  things were not updated to match:
  1. `process_chunks()`'s own docstring (lines 46-48) still says: *"info is
     the processing-stages dict from the first chunk (matches original
     behavior: info is only updated once, from chunk 0)"* — this is exactly
     the behavior #5512 was filed against and is no longer true; the docstring
     now documents the bug the commit fixed, not the fix.
  2. The new comment (lines 224-227) claims stages are "de-duplicated ... so a
     stage run on several chunks is still represented once." That holds for
     every mastering-branch stage in `mastering_branches/continuous.py`
     (`makeup_gain`, `soft_clip`, `normalize`, bass/mid/presence/air/etc.)
     because their inputs (whole-track fingerprint, whole-song peak,
     `effective_intensity`) are constant across chunks, so their stage dicts
     really are byte-identical and the `in` check collapses them to one entry.
     It does **not** hold for Stage 1's `peak_reduction`
     (`mastering_process_chunk.py:115`), whose `target`/`result` are derived
     from each chunk's own `peak_db` and will differ chunk to chunk on
     realistic loud material — every chunk where it fires appends a *new*,
     non-duplicate entry, so a long, dynamically loud track can end up with
     one `peak_reduction` entry per chunk that triggered it (worst case,
     `total_chunks` entries at 30 s/chunk — hours-long files could produce
     hundreds).
- **Evidence**:
  ```python
  # lines 46-48, still describing the pre-fix behavior:
  #   (info, chunks_processed) — info is the processing-stages dict from
  #   the first chunk (matches original behavior: info is only updated
  #   once, from chunk 0).

  # lines 224-233:
  if chunks_processed == 0:
      info = chunk_info
  else:
      for stage in chunk_info.get('stages', []):
          if stage not in info['stages']:   # dict equality — only collapses
              info['stages'].append(stage)  # stages whose values are identical
  ```
  `mastering_process_chunk.py:115`: `info['stages'].append({'stage':
  'peak_reduction', 'target': target_peak, 'result': peak_db})` — `target_peak`
  and `peak_db` are chunk-local.
- **Impact**: Diagnostics-only (`result['processing']` returned by
  `master_file()`, consumed by `auto_master.py`/callers/tests for reporting,
  not by the audio path) — no audio correctness impact. A future maintainer
  reading the docstring would wrongly assume `info` still reflects only chunk
  0; a maintainer relying on the comment's "represented once" guarantee could
  be surprised by a `stages` list that grows with `peak_reduction` entries on
  long, dynamic tracks. No test currently asserts either the aggregation
  behavior or its docstring, so this can drift again silently.
- **Siblings**: None — the other five per-chunk stage-info dicts genuinely are
  whole-track-derived and dedupe correctly; only `peak_reduction` is
  legitimately per-chunk.
- **Suggested Fix**: Update the `process_chunks()` docstring to describe the
  actual behavior (info aggregates every distinct stage-info dict across
  chunks, first-occurrence order). Either soften the inline comment to note
  the `peak_reduction` exception, or key the dedup on `stage_info.get('stage')`
  plus chunk-invariant fields instead of full dict equality if a single
  representative `peak_reduction` entry is actually desired.
- **Orchestrator note**: merged with ENG-D2-02 (dimension 2 reported the same `e5e2cd05` stage-aggregation code). Both parts belong to one fix: the whole-dict `not in` comparison almost never de-duplicates, and the docstring plus comment still describe the pre-fix chunk-0-only behavior.

#### ENG-D5-02: Rust `auralis_dsp.process_chunks` / `ChunkProcessor` remains entirely dead code — zero production callers anywhere
- **Severity**: LOW
- **Dimension**: Chunked Mastering Loop
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs:747-809` (`process_chunks_wrapper`), `vendor/auralis-dsp/src/chunk_processor.rs` (`ChunkProcessor::process_chunks`)
- **Status**: NEW (informational — corroborates the "unreachable" note already on record in #4989's commit message, but no open issue tracks the dead-code cleanup itself)
- **Description**: The engine's actual chunked-mastering loop
  (`auralis/core/mastering_chunk_loop.py`) is a same-named but entirely
  separate Python function; it never calls into the Rust `process_chunks`
  PyO3 binding. A repo-wide grep for `auralis_dsp.process_chunks` /
  `.process_chunks(` finds exactly one caller in the whole tree —
  `tests/test_pyo3_channel_axis_guards_4502.py`, a PyO3-boundary/axis-guard
  smoke test, not a mastering path. This was already noted in passing by the
  `c1da0a2d` (#4989) commit message ("Currently unreachable in production —
  `auralis_dsp.process_chunks` has zero Python callers"); I re-verified it is
  still true today and that #4989's own fix (the crossfade-region
  double-counting bug, `chunk_processor.rs:84-122`) is still present and
  correct — no regression. Separately, the wrapper's docstring
  (`py_bindings.rs:756-757`) says it "Returns: Dictionary with 'peaks' (list
  of peak values per chunk)" but the actual returned dict has keys `output`,
  `chunk_size`, `overlap` — no `'peaks'` key exists. If this function is ever
  wired up, its GIL handling is correct (`py.detach(...)` since `acd42e3e`)
  and its channel-axis guard (1-2 channels, `(channels, samples)` layout)
  matches the Python engine's convention — but its accepted dtype is `f64`
  (`PyReadonlyArray2<'_, f64>`) while the Python engine works in `f32`
  throughout the chunk loop, so a caller would need an explicit cast.
- **Evidence**: `grep -rn "auralis_dsp\.process_chunks\|\.process_chunks(" --include="*.py" .` → only `tests/test_pyo3_channel_axis_guards_4502.py`. `py_bindings.rs:756-757` vs `804-806` (actual dict keys `output`/`chunk_size`/`overlap`, no `peaks`).
- **Impact**: None on the shipped path — purely a maintenance/documentation
  liability. Anyone auditing or extending the Rust DSP surface could
  reasonably (and wrongly) assume this is a live streaming/chunking
  implementation; its stale docstring would mislead a future integration
  attempt.
- **Siblings**: None.
- **Suggested Fix**: Either delete `process_chunks`/`ChunkProcessor` and its
  Python-visible binding as unreachable (matching the precedent set by
  `auralis/optimization/parallel_processor.py` in #4565), or, if it is meant
  to be wired up eventually, fix the docstring to match the actual return
  dict and track "wire up or remove" as its own tracked deferred item rather
  than leaving it silently dead.

#### ENG-D6-02: `FingerprintQuantizer`'s module docstring still claims 0-100 percentage bounds after `e5e2cd05` changed them to 0-1
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/library/fingerprint_quantizer.py:13-16`
- **Status**: NEW
- **Description**: `e5e2cd05` correctly fixed `DIMENSION_BOUNDS` for the 7 band-pct dimensions from `(0.0, 100.0)` to `(0.0, 1.0)` and updated the class docstring (`fingerprint_quantizer.py:36`, "Frequency-distribution dimensions (0-1 fractions)"), but left the module-level docstring's "Accuracy Guarantees" section unchanged: `"Percentage dimensions (0-100): <0.4% max error (100/255)"` (line 14). That line now describes bounds that no longer exist in the code below it.
- **Evidence**: `fingerprint_quantizer.py:7-16` vs. `fingerprint_quantizer.py:47-55`.
- **Impact**: Documentation-only; the quantization math itself is correct (verified in ENG-D6 pass-through checks above). Risk is purely that a future edit trusts the stale module docstring over the correct class docstring/`DIMENSION_BOUNDS` and reintroduces the 0-100 bug #5509 just fixed.
- **Siblings**: None.
- **Suggested Fix**: Update the module docstring's "Accuracy Guarantees" line to match the class docstring ("Frequency-distribution dimensions (0-1 fractions)").

#### ENG-D7-02: `store_fingerprint()`/`upsert()` return a transient `TrackFingerprint` that is missing `fingerprint_blob`, `fingerprint_version`, `id`, and both timestamps
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_upsert_mixin.py:94-96` (`upsert`), `:179-181` (`store_fingerprint`)
- **Status**: NEW
- **Description**: Both methods perform the actual write via raw SQL (`session.execute(text(...))`), then construct `TrackFingerprint(track_id=track_id, **fingerprint_dict)` purely as the return value — this object is never added to the session, so its constructor only populates the keys it was given. `fingerprint_dict` carries the 25 float dimensions but not `fingerprint_blob`, `fingerprint_version`, `is_reference`, `reference_weight`, `id`, `created_at`, or `updated_at`, even though `store_fingerprint()` computes and persists a real `fingerprint_blob` in the same call. A caller reading `result.fingerprint_blob` (or `.fingerprint_version`, `.id`) off the returned object gets `None`/unset, not what was actually written to the row. This is unrelated to and not covered by #5509's two bugs (return-`None`-on-success and the 0–100 bounds), which are both otherwise correctly fixed — see "Skipped as existing" below.
- **Evidence**: Live probe (tmp-file DB) — after a *successful* `store_fingerprint()` call (once ENG-D7-01 is patched so the INSERT succeeds), `result.fingerprint_blob` is `None` while the actual DB row's `fingerprint_blob` column holds the real 25-byte quantized blob; `result.fingerprint_version` is `None` while the DB row holds `FINGERPRINT_ALGORITHM_VERSION`.
- **Impact**: None today — `store_fingerprint()` has zero production callers (only two test files call it directly, confirmed by grep), and the two production callers of `upsert()` (`fingerprint_extractor.py`, `fingerprint_service.py`) only check truthiness of the return value, never read its attributes. The added regression test (`test_returns_fingerprint_on_success`) only asserts `fingerprint is not None` and `.track_id`, so it doesn't catch this gap either.
- **Siblings**: None beyond the two methods above (same pattern, same file).
- **Suggested Fix**: Either drop the misleading return value down to what's true (return `True`/`None` for success/failure, as most other repository write paths do) or build the returned object from the actual `params` dict (which does include `fingerprint_blob`/`fp_version`) so it reflects what was persisted.

---

---

## Relationships

- **ENG-D7-01 and ENG-D6-01** both concern fingerprints reaching the database. Fix the schema first: until writes succeed on a fresh install, the sanitizer gap is invisible there, and fixing the sanitizer alone leaves fresh installs with no fingerprints at all.
- **ENG-D7-01 and #5321** are the same root cause, a fresh `create_all()` database drifting from a migrated one. A schema-parity test that builds both and diffs the DDL would have caught both, and is worth adding with the fix.
- **ENG-D1-01, ENG-D1-02, ENG-D3-01, ENG-D6-01** are all incomplete-fix siblings of changes made in the last day. Each one's parent issue carried a completeness check that was not run.
- **ENG-D5-01, ENG-D5-02, ENG-D6-02** are documentation drift from the same cleanup commits and can be fixed together in one pass.

## Prioritized Fix Order

1. **ENG-D7-01** — no fresh install can store a fingerprint, so similarity, the reference cloud and mastering-target refinement are all dead for new users, silently. Add SQL-level defaults (or include the columns in both `INSERT`s), plus a fresh-versus-migrated DDL parity test.
2. **ENG-D6-01** — route the two backend producers through `compute_windowed_fingerprint()` so they get the sanitizer, the duration cap and windowing parity.
3. **ENG-D1-02** — send the FFmpeg temp-WAV write through `saver.save()`.
4. **ENG-D3-01** and closing #5509–#5513 — finish yesterday's cleanups.
5. **ENG-D1-01, ENG-D2-01** — defensive hardening (asserts that survive `-O`, a guarded denominator).
6. **ENG-D4-01, ENG-D4-02, ENG-D5-02, ENG-D7-02** — dev-script and dead-code cleanup, plus the WMA writer gap.
7. **ENG-D5-01, ENG-D6-02** — stale docstrings and the stage de-duplication that does not de-duplicate.
