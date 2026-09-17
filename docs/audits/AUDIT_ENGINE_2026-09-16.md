# Audio Engine Audit — 2026-09-16

**Scope**: `auralis/core/`, `auralis/dsp/`, `auralis/player/`, `auralis/io/`, `auralis/analysis/`, `auralis/services/`, `auralis/library/`, `auralis/optimization/`, `vendor/auralis-dsp/`
**Depth**: deep | **Dimensions**: all 7 | **HEAD**: `ebea9e3b` (171 commits since the 2026-09-13 audit)
**Method**: a fresh read of the live tree, with one dimension agent per area. The orchestrator then re-checked every HIGH and MEDIUM claim against the source. Findings were deduplicated against the last 2,000 GitHub issues (112 open) and against the 2026-09-13 report.

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 1 |
| MEDIUM   | 2 |
| LOW      | 5 |
| **Total**| **8** |

| Dimension | H | M | L |
|---|---|---|---|
| 1 Sample Integrity | 0 | 1 | 0 |
| 2 DSP Pipeline | 1 | 0 | 1 |
| 3 Player State | 0 | 0 | 1 |
| 4 Audio I/O | 0 | 1 | 0 |
| 5 Chunked Mastering | 0 | 0 | 2 |
| 6 Analysis / 7 Library (merged) | 0 | 0 | 1 |

**Severity changes and merges made by the orchestrator** (each re-checked against the code):
- **ENG-D1-01: HIGH → MEDIUM.** On the normal path, `HybridProcessor` already raises on non-finite output before calling `save()`. A NaN can reach the saver only through the short-buffer bypass that open #5191 already tracks.
- **ENG-D3-04: HIGH → LOW.** The agent's impact claim ("the user hears dead air") is wrong for this app. The backend `AudioPlayer` does not open an audio device: nothing under `auralis/` or `auralis-web/backend/` imports `sounddevice`/`pyaudio`, and no backend code calls `get_audio_chunk()`. The browser plays the WebSocket stream. A stale prebuffer therefore wastes one decode and makes the `next_track` REST call load the file synchronously. No one hears a gap.
- **ENG-D4-01: HIGH → MEDIUM, and widened.** The loss affects tag metadata, not audio. The agent said the defect was unique to MP4. The orchestrator confirmed the MP3 writer has the same problem: it writes `TRCK`/`TPOS` as `str(value)`, so an ID3 `"3/12"` that the frontend round-trips as `3` is rewritten as `"3"`.
- **ENG-D5-04: MEDIUM → LOW.** No launcher, build script or packaging config in the repo runs Python with `-O` or `PYTHONOPTIMIZE`, and the module is the offline CLI path. The risk is latent.
- **ENG-D6-05 + ENG-D7-04 merged into ENG-D7-04 (LOW).** Both are latent bugs on the same dead write path. `store_fingerprint()` has no production caller (orchestrator grep), and it is the only caller of `FingerprintQuantizer.quantize()`.

**Key themes**
1. **Non-finite guards sit at the wrong layer.** Both the #5103 fingerprint sanitizer and the #4672 encode-boundary guard were added to *one* wrapper. Sibling entry points still pass values through unguarded: `AudioFingerprintAnalyzer.analyze()` feeds the live mastering path (ENG-D2-01), and `auralis/io/saver.py` is used by the export job (ENG-D1-01). The fix pattern is to move each guard down to the lowest shared function.
2. **Capabilities stop at a facade.** Prebuffer invalidation exists only on `AudioPlayer`'s own wrappers. The backend bypasses them (ENG-D3-04).
3. **Metadata edits resend every field.** The metadata dialog resends every field and converts track and disc numbers to ints. That silently strips the total tracks/discs value from the tag (ENG-D4-01).
4. **Areas that remain well hardened.** Every 2026-09-13 finding in this scope was re-verified: each is either fixed with the fix still in place (#5306, #5307, #5308, #5309, #5310, #5313, #5315, #5317, #5321, #5329, #5331, #5343, #5350, #5358) or still open and not re-reported (#5116, #4970, #5339, #5325, #5336, #5368). The following also passed re-verification with no findings: WOLA/COLA, EQ band-by-frequency mapping, monotonicity sweeps, the Rust PyO3 boundary (`allow_threads` + `catch_unwind`), chunk-loop reassembly and seam continuity (empirical probe), loader corrupt-file handling (probe), FFmpeg lifecycle and path safety, fingerprint determinism (probe), LUFS K-weighting at any sample rate, and migration locking and backup.

---

## Findings

### HIGH

### ENG-D2-01: The #5103 NaN/Inf fingerprint guard does not cover the live mastering path; a single non-finite dimension turns the whole track into silence
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:36-100` (`analyze`, no finiteness check); `auralis/core/processing/continuous_mode.py:250-262` (`_resolve_parameters`); `auralis/core/hybrid_setup.py:47,99-100`; `auralis/core/processing/continuous_space.py:18-20` (`_smooth_unit`); `auralis/core/processing/base/compression_expansion.py:107-133`; `auralis/core/processing/continuous_dsp_ops.py:188`
- **Status**: NEW. It is a scope gap in closed #5103, whose guard lives only in `windowed_compute.py`.
- **Description**: #5103 added `_sanitize_non_finite()` inside `windowed_compute.compute_windowed_fingerprint()`. Only `services/fingerprint_extractor.py` and `analysis/fingerprint/fingerprint_service.py` call that function (the scan and storage paths). The mastering path builds `AudioFingerprintAnalyzer()` directly in `hybrid_setup.build_hybrid_components()` and hands it to `ContinuousMode`. `ContinuousMode._resolve_parameters()` then calls `self.fingerprint_analyzer.analyze(...)`. That method checks only for empty audio and a non-positive `sr`, and it returns the Rust schema dict unchanged. #5103 already showed that the Rust engine can emit NaN/Inf. A NaN dimension survives `_smooth_unit()`, because `tanh(nan)` is `nan`, and so becomes a NaN coordinate. From there it spreads into `target_lufs` and into the compression, expansion and limiter parameters. In `apply_clip_blend_compression`, the line `audio * (1 - amount) + compressed * amount` with `amount = NaN` turns the whole buffer into NaN. `_apply_final_normalization`'s `validate_audio_finite(..., repair=True)` then zeroes every sample and logs only a warning.
- **Evidence**: Agent probe: `ProcessingSpaceMapper().map_fingerprint_to_space({... 'crest_db': nan ...})` returns `dynamic=nan`, and `ContinuousParameterGenerator().generate_parameters(coords)` then returns `target_lufs=nan` and all-NaN compression, expansion and limiter parameters. The orchestrator confirmed that `analyze()` has no `isfinite` check and that `compute_windowed_fingerprint` has exactly the two callers above.
- **Impact**: A degenerate source file is mastered to complete digital silence, and `HybridProcessor.process()` still reports success. This affects export jobs and any streaming render that goes through fingerprint extraction rather than fixed `.25d` targets.
- **Siblings**: `auralis/core/mastering_branches/continuous.py:120` (offline CLI; it has its own `_assert_finite` calls, so it fails loudly instead). `ContinuousMode.derive_album_target()` (`continuous_mode.py:180-186`) calls the same unguarded `analyze()`.
- **Suggested Fix**: Move `_sanitize_non_finite` into `AudioFingerprintAnalyzer.analyze()` so that every caller gets it, or call it in `_resolve_parameters` before `map_fingerprint_to_space`. Also make `_smooth_unit` return the neutral 0.5 for non-finite input as defence in depth. Add a regression test that injects a NaN dimension and asserts the output is not silent.

### MEDIUM

### ENG-D1-01: `auralis/io/saver.py::save()` has no NaN guard; `np.clip` passes NaN into the PCM encoder
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/io/saver.py:30-47`; caller `auralis-web/backend/core/job_execution.py:49` (whole-track export)
- **Status**: NEW. It is a sibling of closed #4672, whose fix did not cover this module. The known way to reach it is open #5191.
- **Description**: `save()` casts to float32 and calls `np.clip(audio, -1, 1)` before `sf.write`. `np.clip` leaves NaN unchanged, and `save()` never calls `validate_audio_finite`. `WAVEncoder.encode_and_save` guards before it delegates here, but the export job calls `save()` directly. `HybridProcessor` normally raises on non-finite output. However, `hybrid_stage_dispatch.validate_and_normalize_input()`'s `MIN_SAMPLES` short-circuit (#5191) returns short buffers without that check.
- **Evidence**: Agent probe: a NaN survives `np.clip`, and `sf.write(..., 'PCM_16')` writes it as `-1.0` with no log. The orchestrator read `saver.py` and confirmed there is no finiteness check.
- **Impact**: A permanent exported file can contain an undefined sample value whose exact value depends on the libsndfile build, and nothing is logged. The window is narrow today.
- **Siblings**: `auralis-web/backend/core/encoding/wav_encoder.py:162-163` already guards correctly and is the pattern to copy.
- **Suggested Fix**: Call `validate_audio_finite(audio_data, context="saver.save", repair=True)` after the dtype cast in `save()`.

### ENG-D4-01: Editing any field in the metadata dialog strips the total tracks/discs value from the tag (MP4 `trkn`/`disk` → `N/0`; MP3 `TRCK`/`TPOS` → `N`)
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/library/metadata_editor/writers.py:147-153` (MP4), `auralis/library/metadata_editor/writers.py:89-92` (MP3); the trigger is `auralis-web/frontend/src/components/library/EditMetadataDialog/useMetadataForm.ts:110-142`, together with `track`/`disc` typed as `int | None` in the backend update request
- **Status**: NEW
- **Description**: The dialog re-sends every field it loaded, not only the fields the user changed, and converts `track`/`disc` with `parseInt(String(value), 10)`. The GET response carries `"3/12"` (MP4 readers format it that way, and ID3 `TRCK` commonly stores it that way), so the PUT sends `3`. `write_mp4_metadata` writes a bare number as `[(3, 0)]`, which zeroes the total. `write_mp3_metadata` writes `TRCK(text="3")`, which drops `/12`. The write succeeds and the backup file is cleaned up, so nothing can be recovered.
- **Evidence**: Agent live probe on an ffmpeg-generated M4A file: the tag reads `'3/12'`, and after `write_metadata(..., {'title': 'Edited Title', 'track': 3})` it reads `'3/0'`. The orchestrator read both writer branches (MP4 `else: [(int(parts[0]), 0)]`, MP3 `TRCK(encoding=3, text=str(value))`).
- **Impact**: Every title-only edit silently loses the total tracks/discs value, and other players and taggers then see it. No audio is affected.
- **Siblings**: FLAC/OGG `TRACKNUMBER` when a file stores it as `"N/M"`. Verify this during the fix.
- **Suggested Fix**: In the writers, keep the existing total when the incoming value has none (MP4: take the existing tuple's `[1]`; ID3: keep the existing `/M` suffix). In the frontend, send only the fields that changed. A longer-term option is separate `track_total`/`disc_total` fields.

### LOW

### ENG-D3-04: Backend queue-edit services bypass `AudioPlayer`'s prebuffer invalidation
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis-web/backend/services/queue_edit_mixin.py`, `queue_order_mixin.py`, `queue_set_mixin.py` (remove, clear, reorder, move, shuffle, unshuffle, set_queue); compare `auralis/player/player_queue_navigation_mixin.py:250` and `auralis/player/player_callbacks_mixin.py:109-121`
- **Status**: NEW
- **Description**: `AudioPlayer.clear_queue()`, `set_shuffle()` and `set_repeat()` call `gapless.invalidate_prebuffer()`. The backend services instead mutate `audio_player.queue` directly, and `QueueController` has no reference to the gapless engine. `advance_with_prebuffer()` re-checks the prebuffered track's id and path, so the wrong track is never used. After a queue edit, though, the prebuffer is always stale, and the advance falls back to a synchronous load.
- **Evidence**: `grep -rn "invalidate_prebuffer\|\.gapless\b" auralis-web/backend/services/` returns nothing.
- **Impact**: A wasted background decode, plus extra latency on the `next_track` call after a queue edit. There is no audible effect, because the backend player does not render audio (see the severity note above).
- **Suggested Fix**: Add invalidating wrappers on `AudioPlayer` (or give `QueueController` an invalidation callback) and route the backend services through them.

### ENG-D2-02: `UnifiedConfig.processing_sample_rate` has no reader, and its default triggers a warning on every construction
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/config/unified_config.py:41,76-80`
- **Status**: NEW. The #5302 sweep covered only `AdaptiveConfig`, so this field was missed.
- **Description**: The field is documented as "downsample for faster processing", and the constructor validates and stores it. A repo-wide grep finds no reader outside the constructor and one round-trip test. Its default is 48000, above the 44100 `internal_sample_rate` default, so the "processing_sample_rate > internal_sample_rate" warning branch fires on every construction that leaves `internal_sample_rate` at its default.
- **Impact**: Dead config and log noise. A developer who sets this field gets no effect.
- **Suggested Fix**: Delete the field, its validation and the warning, following the #5302 pattern.

### ENG-D7-04: Two latent bugs on the dead `store_fingerprint()` / `FingerprintQuantizer.quantize()` write path (merged from ENG-D6-05 and ENG-D7-04)
- **Severity**: LOW
- **Dimension**: Library & Database / Analysis
- **Location**: `auralis/library/repositories/fingerprint_upsert_mixin.py:115-187`; `auralis/library/fingerprint_quantizer.py:46-52`
- **Status**: NEW. The #5350 and #5471 commit messages both mention the quantizer scale bug as out of scope, but no issue was ever filed for it.
- **Description**: (a) `store_fingerprint()` returns `None` on both the success and the failure path, although its docstring promises a `TrackFingerprint` on success, as the sibling `upsert()` returns. (b) `FingerprintQuantizer.DIMENSION_BOUNDS` declares the seven `*_pct` band dimensions as `(0, 100)`, but every producer emits fractions from 0 to 1. The quantized bytes therefore collapse: a probe round-trips `sub_bass_pct` 0.10 to 0.0 and `bass_pct` 0.25 to 0.39. Nothing in production calls `store_fingerprint()` (orchestrator grep), it is the only caller of `quantize()`, and `fingerprint_blob` is never read anywhere.
- **Impact**: None today. Both bugs would take effect the moment the path is connected to a real write.
- **Suggested Fix**: Delete `store_fingerprint()`, the quantizer and the unused `fingerprint_blob` write path, in line with the project's delete-unreachable-code practice. If the path is kept, fix both bugs and add a return-value assertion to the two tests that call it.

### ENG-D5-04: The chunk loop's sample-count invariants are bare `assert`s, which `python -O` strips
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:218-221`, `auralis/core/mastering_chunk_loop.py:274-277`
- **Status**: NEW. It is the same pattern #2735 fixed in the backend stream paths.
- **Description**: The per-chunk "DSP preserved sample count" check and the "write_region == core_samples" check are both `assert` statements. `-O`/`PYTHONOPTIMIZE` removes them, as the agent's probe confirmed. The final `chunks_processed != total_chunks` check is a real `raise`, but it does not detect drift in the length of an individual chunk.
- **Impact**: Latent. Nothing in the repo runs Python with `-O`, and this is the offline CLI path.
- **Suggested Fix**: Replace both with `if ...: raise RuntimeError(...)`, as #2735 did.

### ENG-D5-05: `master_file()`'s `processing.stages` reports only chunk 0
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:223-225`; consumer `auralis/player/player_callbacks_mixin.py:99`
- **Status**: NEW
- **Description**: `info` is captured only from the first chunk. Some stages run conditionally per chunk; for example, peak reduction depends on each chunk's own peak (#2402). If such a stage runs only in later chunks, it never appears in the reported stages.
- **Impact**: Diagnostics only. The audio output is correct.
- **Suggested Fix**: Merge the stage lists from all chunks, or document that the field reflects only the first chunk.

---

## Relationships

- **ENG-D2-01 and ENG-D1-01** have the same root cause: the non-finite guard was added to a wrapper instead of the lowest shared function. With ENG-D2-01 fixed, the repair zeroing in `_apply_final_normalization` stops being the only barrier. With ENG-D1-01 fixed, the export file is protected whatever the upstream behaviour. Both should land alongside #5191 (the `MIN_SAMPLES` bypass), which is the remaining way to reach ENG-D1-01.
- **ENG-D4-01** spans the engine writers and the frontend form. Fixing only the writers (keeping the existing total) is enough to stop the data loss. Fixing only the frontend is not enough, because any API client can still send a bare integer.
- **ENG-D7-04** is the same "dead code with latent defects" pattern as #4989 (the Rust `process_chunks`) and #5325 (the unused optimizer surface). Deleting the code is cheaper than keeping it correct.
- **ENG-D3-04** would become an audible bug if the backend ever renders audio itself. Fix it before any such feature is added.

## Prioritized Fix Order

1. **ENG-D2-01**: the only finding that can silently wreck a user's output (a silent master). The fix is small and local.
2. **ENG-D4-01**: user-visible, irreversible tag loss on an everyday action. Fix the writers first.
3. **ENG-D1-01**, together with open **#5191**: closes the remaining way for a NaN to reach an exported file.
4. **ENG-D7-04**: delete the dead fingerprint write path.
5. **ENG-D3-04**, **ENG-D5-04**, **ENG-D2-02**, **ENG-D5-05**: cleanup and defence in depth.

## Documentation Note

Dimension 7 reports that all 13 repositories now use `BaseRepository._session_scope()`. The note in `audit-engine.md` that "most call sites still hand-roll session lifecycle" is out of date and should be removed on the next edit of that skill.
