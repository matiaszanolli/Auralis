# Core Audio Engine Audit — 2026-10-21

**Scope**: `auralis/` engine (sample integrity, DSP pipeline, player, audio I/O, chunked mastering, analysis, library) plus the backend call sites that feed it.
**Depth**: deep, 7 dimension agents (Sonnet), read-only. Most HIGH/MEDIUM findings were confirmed by reading the cited lines and by small probes on synthetic audio or temp-file SQLite databases; any finding resting on code reading alone says so in its Evidence.
**Baseline**: HEAD `98a709f5`. Dedup was run against 121 open issues, the 300 most recent issues of all states, `docs/audits/AUDIT_ENGINE_2026-09-1*.md` and `AUDIT_ENGINE_2026-10-16.md`, and `.claude/issues/`.

## Executive Summary

| Severity | Findings | NEW | Regression | Existing |
|---|---|---|---|---|
| CRITICAL | 0 | 0 | 0 | 0 |
| HIGH | 5 | 4 | 1 | 0 |
| MEDIUM | 28 | 21 | 1 | 6 |
| LOW | 44 | 34 | 3 | 7 |
| **Total** | **77** | **59** | **5** | **13** |

**Publish-time validation (2026-10-21)**: of the 64 NEW/Regression findings, 63 were confirmed against current code and filed as #5694–#5756; ENG-D5-02 was found stale (see its entry), which also removes it from the "closed without a fix" claim in theme 1 above (#5592 was fixed).

The 77 findings are after folding 6 cross-dimension duplicates (83 raw), listed under "Merged duplicates". The 13 Existing ones are already tracked by open issues and are kept for completeness; do not re-publish them. The 5 Regressions are closed issues whose fix is missing or incomplete in the live code.

**Key themes**

1. **Recent fixes are the main source of new defects.** The fix for #5559 made the offline CLI hard-clip quiet sources (ENG-D2-01). The fix for #5569 shipped an `except _sf.error` that raises `AttributeError` (ENG-D4-02). #5562 moved the limiter window but not the attack (ENG-D1-03). #5554 fixed units but the fixed-target EQ still tilts every track (ENG-D2-02). #5116, #5512 and #5582 were closed with part of the fix missing (ENG-D5-03, -08, ENG-D3-01).
2. **Destructive paths act on a bad assumption.** The offline CLI deletes its output folder unconditionally, so `-o` equal to the input folder deletes the source music (ENG-D5-01). `cleanup_missing_files()` treats "cannot see the file" as "file deleted" and removes tracks with their playlist rows, favourites and play counts (ENG-D7-01).
3. **The fingerprint pipeline can keep serving stale or wrong data.** An unversioned central `.25d` cache is promoted to the current algorithm version and never recomputed (ENG-D6-01). A rescanned, modified file keeps its old fingerprint (ENG-D7-04). Migrated databases lack `fingerprint_blob` (ENG-D7-03). The similarity prefilter returns arbitrary rows (ENG-D6-05).
4. **Chunk-local gain handling still shapes levels.** A whole-chunk peak clamp varies the track-level gain by up to ~8 dB per chunk (ENG-D2-04), a post-limiter boost exceeds the ceiling (ENG-D1-04, open #5558), and the loudness target and measurement use different scales (ENG-D2-03).
5. **A large part of the player's real-time path is dormant in the shipped backend.** `get_audio_chunk` has no caller outside `tests/`, so ENG-D1-05, ENG-D3-03 and ENG-D3-11 are latent. They were rated down for it, and the alternative is to delete the path.
6. **Multichannel handling is inconsistent across I/O, analysis and streaming.** Stream start advertises the native channel count while the audio is downmixed (ENG-D4-01), fingerprinting reads "first two channels" (ENG-D4-03), and 7.1 folds side channels into both outputs (ENG-D4-12).

**Most impactful**

- ENG-D5-01 and ENG-D7-01 — user data loss, the first through a flag that is easy to mistype.
- ENG-D2-01 — hard clipping of quiet sources in the offline CLI, introduced by the last fix.
- ENG-D6-01 — wrong fingerprints are stamped current, so they are never recomputed (3206 unversioned cache files exist on the audit machine).
- ENG-D2-02 — a content-independent EQ tilt on every track in the shipped streaming path.

**Verified fixed since the 2026-10-16 report** (not re-reported): ENG-D1-01..03 and -04 of that report's D1/D2 set, the fingerprint stereo interleave (`order='F'`), band-floor level dependence, `transient_density` scope, quantizer bounds, the mono enhanced-stream failure, the bulk-delete association tables, the on-demand fingerprint version stamp, scanner change detection by `updated_at`, and most of the player queue-shape findings except the two still open as #5563 and #5564.

**Caveats**

- ENG-D5-07 and ENG-D4-08 rest on code reading only (a memory probe hit the tmpfs quota; `-nostdin` was not probed at runtime).
- Dimension 6 did not cover `adaptive_mastering_engine.py`, `mastering_profile.py` or the numerics of `rhythm.rs`, `variation_analysis.rs` and `spectral_features.rs` beyond black-box probes.
- The Dimension 7 agent was interrupted once and resumed; it wrote its report after the resume.

**Housekeeping found along the way**

- Open **#5565** is already fixed in code (`_entries_match` in the player queue code) and can be closed.
- **#5592** was reported as closed without a fix (ENG-D5-02), but commit `95d71a27` fixed it; the finding was withdrawn at publish time.
- The audit skills (`_audit-common.md`, `audit-engine.md`) say the optimizer wrapper "wraps `AdaptiveMode.process`" and "sits on every real mastering call". Dimension 2 confirmed this is false: the live path is `ContinuousMode.process` (`use_continuous_space` defaults to True), `AdaptiveMode.process` is reached only by `mode="hybrid"` jobs and the legacy `use_continuous_space=False` branch, the wrapper is profiling-only since #5325, and the optimizer's cache and memory pool are constructed but never used. This should be corrected on the next `/audit-sync`.

## Findings

### HIGH

#### ENG-D2-01: Offline CLI file-level final gain is derived from the INPUT peak, so any source quieter than about -2.5 dBFS is hard-clipped (regression introduced by the #5559 fix)
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/mastering_branches/continuous.py:221-258`; `auralis/core/mastering_chunk_loop.py:219-232`
- **Status**: NEW (introduced by c7687a98, the fix for closed #5559; not a regression of #5559's original symptom)
- **Description**: #5559 replaced the per-chunk `normalize(processed, adapted_peak)` with a constant `file_gain = adapted_peak / song_peak_linear`, where `song_peak_linear` is the peak of the INPUT file measured by `prepare_file` (`mastering_prepare.py:213-223`). That is only a valid output-peak cap if the stages in between preserve the peak. They do not: makeup gain, EQ shelves, the harmonic exciter, the soft clipper and above all the loudness maximizer (push gain into a limiter whose ceiling is near 0 dBFS) all change it. For a quiet input the chain already lifts the peak toward the limiter ceiling, and `file_gain` (up to `0.89/0.05`) is applied on top. The old per-chunk normalize bounded the peak by construction. The only remaining protection is the `np.clip(write_region, -1, 1)` before the PCM_24 write (`mastering_chunk_loop.py`), which turns the overshoot into hard clipping. The true-peak guard added by #4970 is keyed to the same input peak (`_tp_gain = ceiling / (input_song_peak * overshoot)`), so it never sees the processed signal and is also inert for quiet inputs.
- **Evidence**: `SimpleMasteringPipeline().master_file()` on a 20 s synthetic stereo track (pink noise + 55 Hz kicks), scaled to input peak P. Pre-clip max |x| measured by wrapping the `np.clip` in `mastering_chunk_loop`:
  `P=0.9 -> 0.86` (fine), `P=0.8 -> 0.90`, `P=0.7 -> 1.08`, `P=0.5 -> 1.59`, `P=0.3 -> 1.77`, `P=0.05 -> 1.88`. Written files: 0.8% (P=0.3) and 1.1% (P=0.05) of samples sit at full scale. Call path: `_render_to_sink` -> `pipeline._process` -> `ContinuousMasteringBranch.apply` (`processed * file_gain`).
- **Impact**: `auto_master.py` outputs audible hard clipping for any source with a peak below roughly -2.5 dBFS (most unmastered material, classical, quiet transfers), i.e. exactly the material that benefits most from the tool. Offline-CLI only (#4873), but audible distortion on output.
- **Siblings**: `mastering_chunk_loop.py:228-232` (true-peak guard keyed to the input peak, same wrong quantity). `mastering_process_chunk.py:117-124` passes the same input peak to the makeup-gain headroom clamp, which is correct there (pre-chain).
- **Suggested Fix**: Derive the file gain from the measured post-chain peak (two-pass, or accumulate per-chunk output peaks and apply the gain in a second streaming pass), or keep a constant gain but follow it with a real limiter so the ceiling holds. Add a regression test with a -20 dBFS-peak input asserting `max(|out|) <= 1.0` before the write clamp.
- **Also reported as**: ENG-D1-01 — Offline CLI hard-clips sources whose peak is below roughly -3.5 to -4 dBFS: the new file-level normalize gain (#5559) and true-peak guard (#4970) both scale by the SOURCE peak (`HIGH`; location: `auralis/core/mastering_branches/continuous.py:228-258` (`file_gain = adapted_peak / song_peak_linear`), `auralis/core/mastering_chunk_loop.py:226-236` (`_tp_gain = _tp_ceiling / (_song_peak_linear * _tp_overshoot)`), `auralis/core/mastering_prepare.py:196-222` (`_song_peak_db` is the peak of the unprocessed source)). Folded here; its evidence is consistent with the above.

#### ENG-D2-02: Fixed-target EQ still tilts every track (about -4 dB bass, +2..+3.6 dB treble on real music): #5554 fixed the units but not the uncalibrated "ideal" band shares
- **Severity**: HIGH
- **Dimension**: DSP Pipeline (config reachability / calibration)
- **Location**: `auralis-web/backend/core/mastering_target_service.py:424-448,465-488`; consumed by `auralis/core/processing/fixed_target_params.py:35-55`
- **Status**: Regression of #5554 (closed after a unit-only fix; the content-independent tilt it reported is still present)
- **Description**: #5554 changed the arithmetic to fraction units (`diff * 100 * 0.5`) but kept the "ideal" energy shares (sub 0.05, bass 0.15, low-mid 0.18, mid 0.22, upper-mid 0.20, presence 0.13, air 0.07). Those are not what the fingerprint's band fractions look like: they are energy shares, and energy falls steeply with frequency. The 512-track corpus medians that `parameter_generator_eq.py:63-70,169-171` already uses are bass 0.456, low-mid 0.101, mid 0.198, upper-mid+presence 0.103, air 0.0063. Against the service's ideals a median track gets bass -6 dB (clamp), upper-mid +6, presence about +4.5, air +3.2. `convert_targets_to_parameters` then SUMS bands into the shelves (`low_shelf = sub_bass + bass`, `high_shelf = presence + air`), so shelves reach -10 dB and +9.5 dB before the 0.7 blend and the per-band perceptual weights.
- **Evidence**: Real stems from `~/Music` (instrumental mixes, 15-30 s): `generate_targets_from_fingerprint` -> `convert_targets_to_parameters` gives `low_shelf_gain -9.5 / -10.2`, `high_shelf_gain +9.5 / +7.9`, `high_mid_gain +6.0`. End to end through `HybridProcessor` (fixed targets from the service vs the same targets with empty `eq_adjustments_db`), level-removed band deltas for 20-60 / 60-250 / 250-500 / 0.5-2k / 2-4k / 4-6k / 6-20k Hz: `[-3.4 -4.3 -1.3 +0.9 +2.0 +3.6 +2.4]` and `[-3.5 -4.8 +0.5 +1.8 +2.1 +2.4 +1.5]` dB. The fingerprint (per-chunk) path for the same material produces near-neutral shelves because `generate_eq_curve` uses the corpus centers, so the two paths for one track disagree by up to about 7 dB across the spectrum.
- **Impact**: The primary streaming path (every track with a cached fingerprint or `.25d` sidecar) is bass-cut and treble-boosted by a roughly constant amount whatever the track is, contradicting the project's HF-overdrive tuning. Playback sounds different depending on whether the fingerprint was cached.
- **Siblings**: `target_crest_db` produced at the same place is never read (dead, #5576).
- **Suggested Fix**: Replace the hand-set ideals with the corpus centers already in `parameter_generator_eq.py` (single source of truth), or route fixed-target EQ through `delta_eq.compute_delta_eq` with a target derived from the cloud. Add a test: median-corpus fingerprint -> all shelves within about 1 dB of 0.

#### ENG-D5-01: `auto_master.py` folder mode `rmtree`s the output folder unconditionally, so `-o` equal to (or an ancestor of) the input folder deletes the source music
- **Severity**: HIGH
- **Dimension**: Chunked Mastering
- **Location**: `auto_master.py:67-73` (`master_folder`); default output folder at `auto_master.py:186`
- **Status**: NEW
- **Description**: Before any file is processed, `master_folder` removes the output folder if it exists, with no containment check against `input_folder`, no confirmation and no "is this folder empty or ours" test. If the user passes the input folder (or any ancestor of it) as `-o`, the originals are deleted, the "no audio files found" branch then returns, and nothing is mastered. Because the default output is the relative path `output`, running the CLI from a directory that already holds a user folder called `output` also wipes it.
- **Evidence**:
  ```python
  if output_path.exists():
      ...print("🧹 Cleaning up existing output folder...")
      shutil.rmtree(output_path)
  output_path.mkdir(parents=True, exist_ok=True)
  # only AFTER this does it rglob input_path for audio
  ```
  Live probe in a scratch dir with one WAV in `musicdir/sub/a.wav`: `python auto_master.py musicdir -o musicdir -q` printed `No audio files found in musicdir` and `musicdir` was empty afterwards (the file and the subfolder were gone).
- **Impact**: Irreversible loss of the user's source audio from a one-argument mistake ("master this folder in place" is a natural thing to type). It is CLI-only, so HIGH rather than CRITICAL, but the damage is permanent.
- **Siblings**: Single-file mode (`auto_master.py:168`) with `-o` equal to the input path also replaces the original in place via the staged `os.replace` with no warning. This is lower severity because the user names a file. The `-o` mp3 case fails only after the fingerprint and pre-scan.
- **Suggested Fix**: Resolve both paths and refuse (non-zero exit) when `output` equals, contains or is contained by `input`. Only delete an output folder after explicit confirmation or a `--clean` flag, or write into it without wiping.

#### ENG-D6-01: `FingerprintService` tier-2 serves unversioned/stale central `.25d` fingerprints and `upsert()` then stamps them with the current algorithm version
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/fingerprint_service.py:158-163,230-245`; `auralis/analysis/fingerprint/fingerprint_storage.py:165-167`; `auralis/library/repositories/fingerprint_upsert_mixin.py:85-99`
- **Status**: NEW (interaction between the #5572 fix and the unversioned central cache; the ENG-D6-01/-02/-03 re-fingerprint plan depends on this)
- **Description**: The centralized sidecar cache `~/.auralis/fingerprints/<md5(path+mtime+size)>.25d` is validated only by its *file-format* version (`"2.0"`), the cache key and the band-sum check. Neither the key nor the load path knows `FINGERPRINT_ALGORITHM_VERSION`, and `FingerprintService.get_or_compute` writes these files without a `fingerprint_version` key. `FingerprintService.get_or_compute` tier 1 (DB) correctly rejects rows with `fingerprint_version < 10`, but tier 2 (`_load_from_file_cache`) then returns whatever an older algorithm wrote, as long as the 7 bands sum to ~1, and calls `_save_to_database` -> `upsert()`. Since #5572, `upsert()` writes `fp_version = FINGERPRINT_ALGORITHM_VERSION` unconditionally, so the stale values are persisted as a **current** row and the outdated-row sweep (`claim_next_outdated_fingerprint`) never revisits them. The backend path (`MasteringTargetService.load_fingerprint_from_file`) does reject unversioned sidecars (#5556), but the player (`fingerprint_loader_mixin.py:83`) and offline mastering (`mastering_prepare.py:108`) go through `FingerprintService`.
- **Evidence**: Probe (scratch HOME): `FingerprintStorage.save(wav, stale_fp_with_lufs=-99, {})` then `FingerprintService(db_path=<missing>).get_or_compute(wav)` returned the stale dict (`fp['lufs'] == -99`) with no recompute. The user's real cache holds 3206 `.25d` files, none containing `fingerprint_version`; many are from 2026-08/09 (before the order='F' fix, the band-floor fix and the v10 bump on 2026-10-20).
- **Impact**: The "existing persisted fingerprints need to be regenerated" step of the 2026-10-16 fixes is defeated for every file that has a central sidecar: wrong/level-dependent fingerprints keep driving mastering targets, `ProcessingCoordinates` and similarity, and (via `upsert`) are re-labelled as current so they are never recomputed.
- **Siblings**: `FingerprintStorage.load` is also used by `MasteringTargetService.load_fingerprint_from_file` (version-aware there). `SidecarManager` (adjacent sidecars) is version-aware (`sidecar_manager.py:118`); only the central store is not.
- **Suggested Fix**: Stamp `fingerprint_version` when `FingerprintService` saves, and reject (or `FingerprintStorage.load` itself reject) sidecars whose version is missing or `< FINGERPRINT_ALGORITHM_VERSION`; optionally fold the algorithm version into the cache key. One shared check should serve both loaders.

#### ENG-D7-01: `cleanup_missing_files()` treats any `Path.exists() == False` as "file deleted", so an unsearchable folder or an empty mount point wipes tracks plus their playlist rows, favourites and play counts
- **Severity**: HIGH
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_maintenance.py:126-190` (checks at `:162`, `:165`); callers `auralis-web/backend/services/missing_tracks.py:28-37`, `routers/library_scan.py:371`, `services/library_auto_scanner.py:358`
- **Status**: NEW
- **Description**: After every scan (manual and auto) the whole library is pruned. A row is deleted when `Path(filepath).exists()` is False and `parent.exists()` is True. `Path.exists()` swallows every `OSError` (EACCES, EPERM, EIO, ESTALE ...), not only ENOENT. The #2525 unmounted-volume guard only inspects the immediate parent. Two realistic cases defeat it: (a) a directory the process cannot search (permissions changed, macOS privacy/TCC revocation, sandbox): `parent.exists()` stats it through its own parent and succeeds, `file.exists()` fails with EACCES; (b) tracks sitting directly in a mount point that is currently unmounted (`/mnt/usb/x.flac`): the empty mount-point directory exists, the file does not. The recheck at `:176-181` repeats the same ambiguous test, so it cannot catch either.
- **Evidence**: Probe `p8.py` (fresh DB, track in `music/`, added to a playlist, favourited, played; `chmod 0 music/`): `cleanup_missing_files()` returned `1`; afterwards `get_by_id` is None and `len(playlists.get_by_id(pl).tracks) == 0`. `delete_tracks_by_ids` removes `track_playlist` rows deliberately.
- **Impact**: Silent, unrecoverable loss of user data (playlist membership, favourite flag, play counts, fingerprints) for every affected track, triggered by an environmental condition and executed with no confirmation. Backups are only taken at schema migrations, so there is nothing to restore.
- **Siblings**: `remove_tracks_under_folder` (same file) is unaffected (no existence test). Any other `Path.exists()` used to decide deletion: grep found none in `auralis/library`.
- **Suggested Fix**: Decide "missing" with `os.stat` and treat only `FileNotFoundError`/`NotADirectoryError` as missing (skip on any other `OSError`). Additionally require the owning scan root (or a few ancestors) to exist and be non-empty, or skip pruning for roots that discovery could not read.

### MEDIUM

#### ENG-D1-03: BrickWallLimiter attack is still a one-sample gain step (now 87 samples before the peak): the #5562 fix moved the window but did not smooth the attack
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/dynamics/brick_wall_limiter.py:137-169` (window + `target_gains`), `:171-239` (`_release_envelope`: `if tg < prev_gain: prev_gain = tg  # attack: instant`)
- **Status**: NEW (incomplete fix of #5562, closed 2026-10-20 by `5946f621`; the issue's proposed fix asked for a ramped attack, the commit only corrected the `maximum_filter1d` origin)
- **Description**: The look-ahead window now correctly covers `[i, i + lookahead)`, so the per-sample ceiling holds. But `_release_envelope` still drops the gain to `threshold / peak` instantly, so the gain steps down in a single sample at `peak_index - (lookahead - 1)` instead of ramping over the look-ahead. A step in a multiplicative gain is a waveform discontinuity of `delta_gain * x[n]` (broadband click). The class docstring still promises "smooth gain reduction envelope (no clicks/pops)".
- **Evidence**: Probe: 0.5-amplitude 200 Hz stereo sine plus one 1.8 sample at index 20000, `create_brick_wall_limiter(44100, threshold_db=-0.3)`: largest single-sample change of the effective gain is 0.463 (1.0 -> 0.537, -5.4 dB) at index 19912 (= 20000 - 88); output peak 0.96605 (ceiling holds). Splitting the call at an arbitrary index changes the output by 3e-8, so cross-call state is fine.
- **Impact**: Every limiting event is an audible tick when it fires. Reach is small in the shipped chain (ContinuousMode already pins the chunk peak at -0.3 dBFS, so the limiter engages by fractions of a dB, but see ENG-D1-02), but the limiter is the real peak control in reference/hybrid job modes and in the offline CLI `loudness_maximizer`, where a push gain makes it engage constantly.
- **Siblings**: `auralis/core/stages/loudness_maximizer.py:80` (fresh limiter per chunk, so state is also cold at each 30 s chunk); `auralis/core/hybrid_setup.py:77`.
- **Suggested Fix**: Smooth `target_gains` after the min-over-window: for example take the sliding minimum of the gain over `lookahead` samples and then low-pass it with a `lookahead`-long linear/Hann ramp (`uniform_filter1d`) so the gain reaches the target by the time the peak arrives, then keep the ceiling check. Add a test that no single-sample gain step exceeds a small bound.
- **Also reported as**: ENG-D2-08 — The #5562 limiter fix moved the look-ahead window but the gain still steps instantaneously, so every limited peak produces a hard gain step 87 samples earlier (`LOW`; location: `auralis/dsp/dynamics/brick_wall_limiter.py:122-147,176-225`). Folded here; its evidence is consistent with the above.

#### ENG-D1-04: LevelManager boosts a chunk after the limiter with no peak check (re-verified live)
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis-web/backend/core/level_manager.py:205-239` (boost branch), `auralis-web/backend/core/chunk_render.py:295` (`_smooth_level_transition`), `auralis-web/backend/core/stream_protocol.py:172` (unclamped float32 on the wire)
- **Status**: Existing: #5558 (open)
- **Description**: Unchanged since the 2026-10-16 report; still no ceiling check after `chunk * env`.
- **Evidence**: Re-run today: previous chunk RMS about -12 dB, next chunk RMS about -22 dB with 0.966 peaks -> gain +8.47 dB, output peak 2.56. Chunks served from cache are clipped to +/-1.0 by `saver.save`, the first play is not, so first play and replay differ.
- **Impact**: As in #5558. ENG-D1-02 makes the triggering condition (a chunk pulled down by the whole-buffer peak clamp next to an unpulled one) more frequent.
- **Siblings**: none new.
- **Suggested Fix**: As in #5558: cap the boost by `ceiling / chunk_peak` or run a final limiter after `smooth_transition`.

#### ENG-D2-03: Per-chunk loudness normalization compares a target built on the fingerprint's unweighted-RMS "LUFS" with a BS.1770 K-weighted measurement, so the lift is under-applied by about 3-4 dB and loud sources are attenuated
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/parameter_generator_dynamics.py:43-64` (target) vs `auralis/core/processing/continuous_dsp_ops.py:184-217` (measurement); `auralis/dsp/utils/adaptive.py:87-135`
- **Status**: NEW (related to closed #5221 and #4123; the "both sides share a scale" claim in #5221's comments is false)
- **Description**: `calculate_target_lufs` builds `target = fp['lufs'] + gain`, with gain >= 0 by construction (softplus). `fp['lufs']` is the Rust/Python fingerprint proxy `20*log10(rms of the MONO mean) - 0.7`, deliberately not BS.1770 (#4123, `dsp_math.rs:18-38`). `_normalize_chunk_loudness` then moves the chunk's K-weighted, channel-SUMMED loudness (`calculate_loudness_units`) to that target. A K-weighted stereo measurement sits above the mono-mean RMS proxy by 3 dB for any correlated stereo plus a spectral term, so the realised gain is `lift - (K - fp)`. The comments at `adaptive.py:101-113` and `continuous_dsp_ops.py:233-238` state the two now share a scale; they do not.
- **Evidence**: Real stems (15 s, `HybridProcessor`, fingerprint path): `fp_lufs -15.7, K_in -12.8 (K-fp +3.0), intended lift +3.5, realised -0.6 dB`; `fp -13.2, K -9.5 (+3.7), lift +1.3, realised -2.4 dB`; `fp -18.8, K -15.1 (+3.7), lift +5.4, realised +1.2 dB`. Synthetic sweep (constant +3.5 dB offset): sources at fp -30.9 / -24.9 / -18.9 / -14.9 get intended lifts 7.9 / 7.4 / 5.6 / 2.8 and realised 4.4 / 3.9 / 2.1 / -0.7 dB. The fixed-target path (`gain = target - source_lufs`, both proxy-scale) is self-consistent, so the same track lands at a different loudness depending on which path rendered it.
- **Impact**: Loud masters are turned down although the generator's contract is "never attenuate"; quiet material gets about half the intended lift; paths disagree. Loudness is within a few dB, so not a catastrophic defect, but the whole loudness model is miscalibrated by a source-dependent constant.
- **Siblings**: `adaptive_mode.py:188-190` (K-scale LUFS fed into `tanh` centred on the corpus proxy-scale -14.3887/2.7732); `mastering_branches/continuous.py:68-72` and `adaptive_mode.py:255-267` (`AdaptiveLoudnessControl` thresholds -12/-14/TARGET -11 are "true LUFS" values but are fed `unpacker.lufs`/proxy on the offline path).
- **Suggested Fix**: Calibrate once. Either express `target_lufs` on the K scale (target = K-measured loudness of the chunk + lift, using the same meter), or convert the fingerprint value with a measured offset. Do not mix scales across `calculate_target_lufs`, `_normalize_chunk_loudness` and the corpus `_LUFS_CENTER`.

#### ENG-D2-04: In the fixed-target path the whole-buffer peak clamp re-introduces a per-chunk gain, so adjacent chunks (tiled without crossfade) land on different levels
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline (chunk-seam continuity)
- **Location**: `auralis/core/processing/continuous_dsp_ops.py:262-278` (Step 2); interacts with `:242-258` (constant gain)
- **Status**: NEW (residual after #5552; see also ENG-D2-09 of the 2026-10-16 report, now removed Step 3)
- **Description**: #5552 made the loudness step a constant track-level gain so chunks keep their relative levels. Step 2 then clamps the chunk's peak to -0.3 dBFS with `amplify(audio, SAFE_CEILING_DB - current_peak_db)`: a gain applied to the whole buffer (15 s plus context) that depends on that buffer's single loudest sample. Two renderings of the same overlapped audio therefore differ whenever a transient exists in one window and not the other. The backend trims each rendering to a non-overlapping segment and tiles them with no crossfade, so the difference becomes a level step at the seam. `LevelManager.smooth_transition` only acts when the RMS step exceeds 1.5 dB.
- **Evidence**: Synthetic: one brief transient in window A only, constant +9 dB track gain, overlap region [10,15) s rendered by chunk A and chunk B: RMS differs by 4.14 dB (peaks 0.966 vs 0.815). Real stem (`07-te-para-tres ... instrum`, windows at 10 s hops, fixed targets with a +1.3 dB track gain): seam steps between consecutive chunk renderings of the shared region `0.00, -0.80, -0.45, 0.00, +0.91 dB` (a hot master hits the clamp on every chunk with a different amount).
- **Impact**: Audible sub-1.5 dB level steps every 10 s that nothing smooths, strongest on hot or high-gain tracks, which is the opposite of what the constant gain intended.
- **Siblings**: the same Step 2 whole-buffer clamp serves the fingerprint path (there the per-chunk LUFS normalization is already chunk-local by design).
- **Suggested Fix**: Make peak control a limiter (or carry the clamp gain as a track-level constant like `source_lufs`, computed from the whole-track peak and applied to all chunks) rather than a per-buffer scalar.
- **Also reported as**: ENG-D1-02 — Final-normalization "emergency" peak clamp is a whole-chunk gain, so the constant track-level gain of the fixed-targets path (#5552) still varies by up to ~8 dB per chunk with that chunk's crest (`MEDIUM`; location: `auralis/core/processing/continuous_dsp_ops.py:269-282` (Step 2, `peak_adjustment = min(SAFE_CEILING_DB - current_peak_db, 0.0)`; `amplify(audio, peak_adjustment)`), preceded by the constant gain at `:243-254`). Folded here; its evidence is consistent with the above.

#### ENG-D2-05: Soft k-NN target derivation hands about half of the total weight to references BEYOND rank k (live since #5560 wired the cloud)
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/target_derivation.py:153-188` (tail loop at `:166-176`)
- **Status**: NEW (introduced by b8e533db / #5113; became reachable with b84609fc / #5560)
- **Description**: #5113 "softens the hard rank-k cutoff" by re-admitting every reference past rank k with weight `softmax([d, d_k])[0] * exp(-rank/(k/4))`. The two-way softmax is about 0.5, whereas the in-k weights come from a k-way softmax and average 0.1. The comment promises a tail "that starts at about 50% of its softmax weight" but the code starts it at about 5x the k-th neighbour's weight. The loop never breaks (`exp` is always positive), so the whole cloud participates. The tail also skips `_apply_reference_weights`, so references the seeder scored 0 are not suppressed in the tail while the same references inside k would be.
- **Evidence**: Synthetic clouds, k=10, nearest neighbour first: `N=15: in-k weight 0.551, tail 0.449; N=30: 0.503 / 0.497; N=100: 0.500 / 0.500`. Largest in-k weight 0.058-0.069 versus the first tail reference 0.166-0.174. With 20 of 30 references at `reference_weight=0`, refs that should be suppressed carry 11% of the total.
- **Impact**: The "k nearest" target regresses toward the cloud mean: the nearest references are diluted to half weight, the EQ target loses its content specificity, and zero-weighted references leak in. Affects every non-fixed-target chunk once the cloud is non-empty (and `derive_album_target`, which averages these targets).
- **Siblings**: `album_target.py` (consumes `derive_target`).
- **Suggested Fix**: Scale the tail by the k-th neighbour's actual (reference-weighted) weight instead of a fresh two-way softmax, bound the tail to a few ranks (taper threshold), and apply the same `reference_weight` factor. Add a test that in-k mass >= 90%.

#### ENG-D2-06: Psychoacoustic EQ halves every band's gain whenever the band's mean level is 20 dB under its own peak, so tonal frames get half the EQ of noisy frames
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline (parameter-space continuity / spectral masking)
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:272-285`; threshold from `auralis/dsp/eq/masking.py:49-60`
- **Status**: NEW
- **Description**: `_calculate_target_gains` multiplies `required_gain` by 0.5 when `band_energies[i] < masking_thresholds[i]`. `band_energies[i]` is the MEAN of the band's FFT magnitudes in dB; `masking_thresholds[i]` is that SAME band's PEAK magnitude in dB minus 20. The test is therefore "does this band contain a partial more than 20 dB above its own average", i.e. tonality/peakiness, not masking by a neighbour. It is a hard x0.5 step per band per frame, and with `adaptation_speed = adaptation_strength = 0.8` the one-pole smoothing passes it nearly unattenuated.
- **Evidence**: `analyze_spectrum` on a 4096-sample frame: white noise -> 0 of 25 bands halved; three sine partials + noise -> bands 0, 8, 18 halved; harmonic series on 110 Hz + noise -> 16 of 25 bands (1-16) halved.
- **Impact**: The same generated EQ curve is applied at full strength on noisy/percussive frames and at half strength on tonal frames, flipping frame to frame (46 ms hop) on mixed material: spectral flutter and an EQ amount that depends on texture rather than on the continuous mastering coordinates.
- **Siblings**: none found; `calculate_simultaneous_masking`/`calculate_temporal_masking` are dead.
- **Suggested Fix**: Compute masking from neighbouring bands (spreading function) or drop the halving; if kept, make it a smooth function of (threshold - level).

#### ENG-D2-07: `AdaptiveLoudnessControl.calculate_adaptive_gain` is a step function of loudness and crest, and its bass-aware reduction branch is unreachable (same family: stereo width dead-band)
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline (parameter-space continuity)
- **Location**: `auralis/dsp/utils/adaptive_loudness.py:56-141`; `auralis/core/processing/base/stereo_width_processor.py:105`
- **Status**: NEW (the 2026-10-16 report, ENG-D6-03, cites this consumer's "up to ~1.6 dB" reduction, which can never fire)
- **Description**: (1) The gain is a lookup over three LUFS buckets (`> -12` returns 0, `> -14` is `0.5*(TARGET-lufs)`, else `intensity*(TARGET-lufs)`) and three crest buckets (`max_gain` 4/5/6 at 15/12 dB). Inputs 0.02 apart on a threshold get different makeup gain: that is the categorical bucketing the continuous design forbids. (2) In the final `else` branch (`source_lufs <= -14`) the code tests `if source_lufs < -13.0: pass`, which is always true there, so the `elif bass_pct ... transient_density ...` reduction and the bass-only fallback are dead; the "bass-aware gain" logged by `AdaptiveMode` and used by the offline branch never changes anything. (3) `StereoWidthProcessor.apply_stereo_width_safe` skips the width change entirely when `|target_width - 0.5| <= 0.1` and applies it in full above, so a target of 0.60 vs 0.61 is 0 dB vs about +1.7 dB side gain.
- **Evidence**: `calculate_adaptive_gain(lufs)`: `-11.99 -> 0.0`, `-12.01 -> 0.5`; `-13.99 -> 1.5`, `-14.01 -> 3.01`; crest at -18 LUFS: `11.99 -> 6.0`, `12.01 -> 5.0`, `14.99 -> 5.0`, `15.01 -> 4.0`. Scan over lufs -40..-11, bass 0.2/0.4/0.7, transients 0/0.5/0.9: 0 combinations where passing `bass_pct`/`transient_density` changes the result.
- **Impact**: Live in `mode="hybrid"` jobs (`AdaptiveMode._apply_final_normalization`) and in the offline CLI (`mastering_branches/continuous.py:68-72`): neighbouring tracks get up to 1.5 dB different makeup, and the documented bass/kick protection does not exist.
- **Siblings**: `adaptive_mode.py:190-190` loudness coordinate uses smooth tanh (fine); `air_enhancement/mid_warmth/presence_enhancement/clarity_boost` minimum-boost gates (`boost_db < 0.3`, `darkness_factor < 0.4`, `body_content >= 0.25`) and `transient_shaper` (`boost_db < 0.5`, `bass_pct >= 0.05`) are the same pattern at smaller magnitude.
- **Suggested Fix**: Replace the bucket chain with softplus/`smooth_gate` blends (the pattern `loudness_maximizer` already uses) and either fix or delete the dead bass branch.

#### ENG-D3-01: `previous_track()` rollback never applies when the move wrapped (repeat on, first track), leaving the queue pointer on a track that was not loaded
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/player_queue_navigation_mixin.py:165-201`; `auralis/player/components/queue_manager.py:200-224`
- **Status**: Regression of #5582
- **Description**: The #5582 fix made `rollback_index()` a compare-and-set and passes `expected_current=saved_index - 1`. That is only the index `previous_track()` moved to when it did not wrap. With `repeat_enabled` at index 0 (or -1), `QueueManager.previous_track()` jumps to `len(tracks) - 1`, so `current_index != expected_current` and the rollback is silently skipped. The load failed (or the entry has no path), the loaded audio is still the old track, but the queue now points at the last track. Because of #5563 (production entries carry `filepath`, not `file_path`) the "no path" branch is taken for every real queue, so this triggers on every Previous press at the first track with repeat on.
- **Evidence**: Probe: queue `[a(ok), missing, missing]`, `load_file(a)`, `set_repeat(True)`, `play()`, `previous_track()` -> returns `False`, `queue.current_index == 2`, `current_file == a.wav`, `state == ERROR`. The bad value is `expected_current=saved_index - 1` at line 201; the real moved-to index is whatever `QueueManager.previous_track()` set (line 178).
- **Impact**: Queue/now-playing pointer (`get_queue_info()['current_index']`, `current_track`) describes a track other than the loaded audio; the next Next press wraps to track 0 and reloads the track the user was already on. Combined with ENG-D3-07 the player is also wedged in ERROR.
- **Siblings**: none (only caller of `rollback_index`).
- **Suggested Fix**: Have `QueueManager.previous_track()` return/record the index it moved to (or read `snapshot_index()` immediately after the move under the same lock) and pass that as `expected_current`; add a repeat-wrap test.

#### ENG-D3-02: Auto-advance retries forever when `next_track()` returns False: one thread per audio callback, state stays PLAYING
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/player_streaming_mixin.py:96-117,146-185`
- **Status**: NEW
- **Description**: `_auto_advance_next` calls `self.next_track()` and ignores its return value. Only an exception stops playback (#2441). `next_track()` returns `False` for a missing/undecodable next file or an entry with no recognised path key, without moving the queue. The `finally` clears `_auto_advancing`, and the next `get_audio_chunk()` call (position is clamped at `total_samples`, so `end_of_track` is still true and `has_next_track()` is still true) spawns another advance thread. This repeats at the audio callback rate, each attempt doing `Path.exists()` plus a full decode attempt for a corrupt file, with `_advance_thread` overwritten each time so `cleanup()` only joins the last one.
- **Evidence**: Probe: queue `[a(ok), '/nonexistent/x.wav']`, `seek(0.99)`, 1 s of `get_audio_chunk(1024)` calls -> 813 `next_track` attempts, `state == PLAYING` throughout. With production-shaped entries (`{'filepath': ...}`, #5563) the same loop starts at the first track boundary (reproduced: after the end of track 1 the state stayed PLAYING and no advance ever happened).
- **Impact**: Thread/CPU storm and log spam at every track boundary whose successor cannot be loaded; playback never finishes or reports an error (the #5584 fix only covers "no next track"). Dormant in the shipped backend (no `get_audio_chunk` caller), live for any engine consumer.
- **Siblings**: none.
- **Suggested Fix**: Treat a `False` return like the exception path (stop and emit an error/`playback_finished` once), or advance past/skip the unloadable entry; add a test that the spawn count is bounded.

#### ENG-D3-03: `RealtimeLevelMatcher` starts at `current_target_rms = 0`, so the first track played fades in from about -34 dB over ~7 s
- **Severity**: MEDIUM (audible artifact; downgraded from HIGH because the real-time chain has no production caller of `get_audio_chunk`)
- **Dimension**: Player State
- **Location**: `auralis/player/realtime/level_matcher.py:23-30,66-92`
- **Status**: NEW
- **Description**: `current_target_rms` is initialised to `0.0` and moves toward `reference_rms` by `alpha = 0.01` per chunk. `gain = current_target_rms / current_rms`, so the very first chunks get gain ~0.01 and the target only reaches the reference after hundreds of chunks. `set_reference_audio()` and `reset()` never seed or reset it (`reset()` rebuilds the gain smoother but leaves `current_target_rms` stale, so the fade-in happens once per process, not per track). Since #5585 the auto-selected reference does enable the matcher, so this is now reachable for any library load.
- **Evidence**: Probe: reference RMS equal to the input RMS (ideal gain 0 dB), 1024-sample chunks -> output/input RMS: chunk 0 -10.1 dB, chunk 1 -34.2 dB, 5 -24.8, 20 -14.4, 50 -7.9, 100 -4.0, 200 -1.2, 300 -0.4 dB.
- **Impact**: The first track after the matcher is enabled starts nearly silent and swells for ~7 s; later reference changes then glide correctly, so it is easy to miss in manual testing.
- **Siblings**: none. (Design note: the matcher also normalises every 23 ms chunk to the whole-reference RMS, which flattens dynamics; that is a DSP-design question for Dimension 2, not filed here.)
- **Suggested Fix**: Seed `current_target_rms = reference_rms` in `set_reference_audio()` (and in `reset()`); add a test asserting the first chunk's gain is ~1 for equal RMS.

#### ENG-D3-04: Every production `load_file()` decodes the whole track into RAM, prebuffers the next one and computes a fingerprint, none of which anything consumes
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis-web/backend/services/queue_set_mixin.py:154-157`, `auralis-web/backend/services/queue_edit_mixin.py:145-148`; `auralis/player/player_file_loading_mixin.py:51-88`; `auralis/player/queue_controller.py:42-62`; `auralis/player/fingerprint_loader_mixin.py:41-122`; `auralis-web/backend/config/startup/components.py:182-189`
- **Status**: NEW
- **Description**: Audio reaches the client through the backend `ChunkedProcessor` stream, not through the engine: `grep` finds no caller of `AudioPlayer.get_audio_chunk` outside `tests/`, `audio_data` is never read by the backend, and the shipped `PlayerConfig` sets `enable_auto_mastering=False`, so `RealtimeProcessor.set_fingerprint()` returns immediately and `_current_fingerprint` is write-only. Yet each `set_queue` and each remove-current awaits `audio_player.load_file(...)`, which (a) decodes the entire file to float32 stereo (42 MB per 2 min; a 1 h mix is ~1.3 GB), (b) calls `gapless.start_prebuffering()`, decoding the next track the same way (and every queue edit re-arms it through `on_queue_changed`, #5583), and (c) spawns a `fingerprint-loader` thread that runs `get_or_compute()`, which on a cache miss decodes the file again and runs the 25D analysis (tier-3 compute) and can write the library DB concurrently with the backend fingerprint queue. Threads are uncapped: rapid skipping stacks one analysis per load, each discarded only after it finishes.
- **Evidence**: `queue_set_mixin.py:154` `await asyncio.to_thread(self.audio_player.load_file, current_track.filepath)` is awaited before `play()` and before the endpoint returns; `components.py:187` `enable_auto_mastering=False`; `fingerprint_loader_mixin.py:100` writes `_current_fingerprint`, which has no reader (`grep _current_fingerprint` -> only this mixin and `__init__`). Probe: `AudioFileManager.load_file` on a 120 s FLAC took 0.34 s and held 42 MB.
- **Impact**: Latency on every play-from-library (decode time of the full file before the engine call returns), 2x track-size resident memory (loaded + prebuffered) for no output, duplicate fingerprint work competing with the real queue. Grows with file length.
- **Siblings**: reference decode in `IntegrationManager._auto_select_reference` (only on `load_track_from_library`, not the frontend path); `on_queue_changed` prebuffer re-arm triggers the same unused decode on every edit when nothing is playing.
- **Suggested Fix**: Decide the engine's role. If the engine is state-only in production, make the load lazy (metadata only) and gate prebuffer/fingerprint on a config flag; if a native output is planned, gate them on "an audio consumer attached". Cap or serialise the fingerprint loader and skip it when `auto_master is None`.

#### ENG-D3-05: Engine next/previous/gapless read `file_path`/`path`; production queue entries use `filepath` or carry no path
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/gapless_playback_engine.py:143,294,452-453`; `auralis/player/player_queue_navigation_mixin.py:168`; `auralis/player/components/queue_manager.py:22-23`; producer `auralis/player/queue_controller.py:441`
- **Status**: Existing: #5563
- **Description**: Re-verified against live code: unchanged (`next_track.get('file_path') or next_track.get('path')` at all five sites, while `set_queue` wraps strings as `{'filepath': ...}`). It is also the trigger that makes ENG-D3-01 and ENG-D3-02 hit on every real queue.
- **Evidence**: see #5563; ENG-D3-02 probe with `{'filepath': ...}` entries.
- **Impact**: see #5563.
- **Siblings**: `add_to_queue` (`player_queue_navigation_mixin.py:227`) is the only reader that accepts both keys.
- **Suggested Fix**: see #5563 (single `entry_filepath()` helper).

#### ENG-D3-06: `shuffle()`/`unshuffle()` identify the current track by `id` only
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/components/queue_manager.py:391-423`
- **Status**: Existing: #5564
- **Description**: Re-verified: unchanged; idless entries (the `set_queue` shape) lose the current pointer on shuffle and `unshuffle` restores a stale index.
- **Evidence**: see #5564.
- **Impact**: see #5564.
- **Siblings**: duplicate ids resolve to the first match.
- **Suggested Fix**: see #5564 (identity like `reorder_tracks`).

#### ENG-D4-01: Enhanced/seek stream start advertises the file's native channel count, but >2-channel FFmpeg-routed files are streamed downmixed to stereo
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/unified_loader.py:304-312` (probe reports native channels) vs `auralis/io/loaders/ffmpeg_loader.py:475,495` (decode forces `-ac 2`); consumers `auralis-web/backend/core/chunk_metadata.py:86`, `chunked_processor.py:234`, `stream_enhanced.py:222`, `stream_seek.py:220`
- **Status**: NEW
- **Description**: `get_audio_info()`/`_get_info_with_ffprobe` returns the container's channel count, and `load_audio_metadata()` stores it as `processor.channels`. For `.m4a/.aac/.wma` libsndfile cannot open the file, so `SeekableSource.resolve()` converts it once via `load_audio()`, which downmixes any >2-channel source to stereo (`-ac 2`). Chunks are therefore 2-channel, but `audio_stream_start.channels` is still the native count. `send_pcm_chunk` flattens the real array (2-ch interleaved), and the frontend sizes `PCMStreamBuffer` and the playback worklet (`setChannels`, `outputChannelCount`) from the stream-start `channels`. The same probe/decode disagreement was already fixed for mono in #4611/#4597; the >2-channel case was not.
- **Evidence**: probe on a 1 s 6-channel AAC `.m4a`: `get_audio_info -> channels=6`, `load_audio -> shape (22528, 2)`, `load_audio_metadata -> AudioMetadata(channels=6, ...)`, `convert_to_temp_wav -> sf.info(wav).channels == 2`. Client: `useEnhancedStreamStart.ts:120 buffer.initialize(sample_rate, message.data.channels)`, `BufferScheduler.ts:232-239`.
- **Impact**: A 5.1 M4A/AAC/WMA track played in enhanced mode is deinterleaved as 6-channel from 2-channel data: garbled audio at roughly 3x speed with wrong duration. Normal-mode streaming is not affected (it reads the converted WAV's own channel count, `stream_normal.py:142`), so enhanced and normal disagree for the same file. Native >2-channel WAV/FLAC/OGG is self-consistent (6 and 6) but never downmixed (see D4-03 siblings).
- **Siblings**: `stream_seek.py:220` (same field); `chunk_metadata.py:106` full-decode fallback reports `audio.shape[1]` (already post-downmix, so that one is right).
- **Suggested Fix**: Report the post-decode channel count: in `load_audio_metadata` clamp to `min(channels, 2)` whenever `can_seek_natively()` is false (or derive it from the resolved seekable WAV via `sf.info`), rather than trusting the probe. Add a test with a 6-channel `.m4a` fixture.

#### ENG-D4-02: `master_file()` multichannel pre-check catches `_sf.error`, which does not exist, so every failure in that block becomes `AttributeError`
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/core/simple_mastering.py:203-214` (also the temp-dir placement at `:179-186`)
- **Status**: NEW (introduced by the #5569 fix, `39cf2cc4`, today; #5569 is closed)
- **Description**: The new block does `try: ... _sf.info(...).channels > 2 ... except _sf.error: pass  # not a libsndfile-readable file`. soundfile 0.14.0 has no `error` attribute (it has `LibsndfileError`/`SoundFileError`). When the try body raises, Python evaluates `_sf.error` to match the handler and raises `AttributeError: module 'soundfile' has no attribute 'error'`, chained on the real exception. The intended "fall through and let the chunk loop report it" never happens, and a `ModuleError` from `load_with_soundfile` (severely truncated or over-budget 5.1 file) is also masked.
- **Evidence**: `SimpleMasteringPipeline().master_file('bad.wav', 'out.wav')` with 2000 random bytes -> `AttributeError module 'soundfile' has no attribute 'error'`, `__context__` = `LibsndfileError: Format not recognised`. `hasattr(soundfile, 'error') == False`. No test references `sf.error`.
- **Impact**: Every unreadable or corrupt WAV/FLAC/AIFF/AU given to `auto_master.py` / `master_file` reports a misleading `AttributeError` instead of a meaningful corrupt-file error; `ModuleError` codes (`ERROR_TRUNCATED_FILE`, `ERROR_CORRUPTED`) are lost for multichannel inputs. The job still fails, so no data loss.
- **Siblings**: Same function, FFmpeg branch (`:183-190`): `_tmp_dir = TemporaryDirectory()` is created before the `try/finally` that cleans it (`:215/:285`), so a `load_with_ffmpeg` or `save_audio` failure (common for corrupt MP3/M4A) leaves cleanup to the GC finalizer with a `ResourceWarning`; same for the multichannel branch.
- **Suggested Fix**: Catch `_sf.LibsndfileError` (or `sf.SoundFileError`) and let `ModuleError` propagate; move the temp-dir creation inside the `try` that has the `finally: cleanup()`. Add a corrupt-WAV test for `master_file`.
- **Also reported as**: ENG-D5-04 — `except _sf.error` in the new #5569 pre-downmix block is an AttributeError (`soundfile` has no `error`), so any unreadable input fails with the wrong message and leaks the temp dir (`LOW`; location: `auralis/core/simple_mastering.py:203-214`). Folded here; its evidence is consistent with the above.

#### ENG-D4-03: Fingerprint windowing reads native multichannel files as "first two channels", while probes average all channels and the FFmpeg path uses a real downmix
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/analysis/fingerprint/windowed_compute.py:245-262` (libsndfile branch, `librosa.load`), `:315-316` (`audio = audio[:2, :]`)
- **Status**: NEW (same defect class as closed #5569/#3743; different code path)
- **Description**: For WAV/FLAC/AIFF/AU the body window is loaded with `mono=False` and any `>2`-channel array is truncated to channels 0 and 1 (L+R), dropping Center/LFE/surround (the comment calls this "sufficient", which is exactly what #3743/#5569 retired). The two 30 s probe windows use `mono=True` (equal-weight mean of all channels including LFE), so the LUFS/crest median at `:326-345` mixes an L+R estimate with an all-channel estimate. The FFmpeg-routed branch of the same function gets a proper `-ac 2` downmix, so the same 5.1 mix fingerprints differently as FLAC than as M4A. The fingerprint drives mastering targets (`master_file` fingerprints the original path, not the downmixed temp WAV).
- **Evidence**: `if audio.ndim == 2 and audio.shape[0] > 2: audio = audio[:2, :]` (`:315-316`); `librosa.load(..., mono=True, ...)` (`:255-257`); FFmpeg branch decodes through `load_with_ffmpeg` (downmix) at `:183`.
- **Impact**: Centre-heavy surround masters (vocals/dialogue in C) get spectral/dynamic dimensions computed without their main content, skewing mastering targets. Only affects >2-channel lossless sources (rare), degradation not failure.
- **Siblings**: Backend streaming reads native-seekable files raw: `chunk_operations.py:138-151` returns `(N, 6)` for a 6-channel WAV (probed), `HybridProcessor.process` accepts and returns 6 channels, no downmix anywhere on that path (consequence downstream not verified).
- **Suggested Fix**: Decode the window through one shared helper that applies `downmix_to_stereo`/`requires_layout_aware_downmix` (or route >2-channel native files through `load_with_ffmpeg` windows), and make the probes use the same stereo downmix before mono-folding.

#### ENG-D4-04: FFmpeg intermediate WAV is not RF64-capable; decodes over 4 GiB truncate
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:476-500` (no `-rf64 auto`)
- **Status**: Existing: #5566
- **Description**: Still true: the command has no `-rf64`. The f32 intermediate (#5317) makes the 4 GiB ceiling reachable at the 6 GiB `MAX_DECODED_BYTES` budget (e.g. 96 kHz stereo, > ~1 h 33 min).
- **Evidence**: `ffmpeg_cmd` built at `:476-500`, output `str(temp_wav)` with `.wav` suffix.
- **Impact**: See #5566.
- **Siblings**: `seekable_source.py:96` (`sf.write(..., format="WAV", subtype="FLOAT")`) and `simple_mastering.py:190,210` (`save_audio(..., "PCM_24")` temp WAV) write whole decoded tracks into plain WAV containers with the same 4 GiB limit (not probed; sizes would need > 4 GiB).
- **Suggested Fix**: See #5566; apply the same container choice to the sibling writers.

#### ENG-D4-05: Library scan ingests undecodable files as zero-duration tracks
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/library/scanner/audio_analyzer.py:58-99`, `batch_processor.py:135-139`
- **Status**: Existing: #5567
- **Description**: Re-verified live: `AudioAnalyzer().extract_audio_info()` on 3000 random bytes named `.mp3` returns `(None, None, None, 'MP3')`; the "unreadable" branch in the batch processor cannot trigger.
- **Evidence**: probe output `(None, None, None, 'MP3')`.
- **Impact**: See #5567.
- **Siblings**: none new.
- **Suggested Fix**: See #5567.

#### ENG-D4-06: M4A track/disc numbers dropped, WMA tags not read
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/library/scanner/metadata_extractor.py:41-51,132-157`
- **Status**: Existing: #5568
- **Description**: Re-verified: the M4A probe returned no `track`/`disc` keys (`trkn`/`disk` tuples fail `int()`), MP3/OGG/Opus returned them.
- **Evidence**: `m4a {'title':..., 'date': 2020, ...}` with `track="3/12"` set; no `track`.
- **Impact**: See #5568.
- **Siblings**: see ENG-D4-09 for other tag-parsing gaps.
- **Suggested Fix**: See #5568.

#### ENG-D6-02: Continuous-mode quality gate raises an uncaught `KeyError` on 1024-8191-sample chunks and burns ~2 s of CPU per gated chunk for a result nothing reads
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/core/processing/continuous_quality.py:42-77`; `auralis/analysis/base_spectrum_analyzer.py:243-262`; `auralis/analysis/quality/quality_metrics.py:149-153`
- **Status**: NEW
- **Description**: `_record_quality_measurements` runs `QualityMetrics.compare_quality` on the first call and then every 5th call (`quality_gate_enabled=True`, interval 5) and catches only `(ValueError, RuntimeError)`. `HybridProcessor` lets audio of at least `MIN_SAMPLES = 1024` through, but `SpectrumAnalyzer.analyze_file` uses `fft_size=8192` and returns `{}` when `len(audio) < 8192`; `FrequencyResponseAssessor.assess` then does `spectrum_result['spectrum']` and raises `KeyError`, which escapes the mastering call. Separately, the result is dead: `last_quality_comparison` / `last_mastering_measurements` are read only by a test.
- **Evidence**: With fixed targets (the streaming fast path), `HybridProcessor(UnifiedConfig())` with `current_targets` set, `process(noise(2000..8191, 2))` raises `KeyError: 'spectrum'` from `frequency_assessment.py:65` via `quality_metrics.py:153` (9000 samples passes). `_record_quality_measurements` on a 15 s stereo chunk takes 2.1 s wall (two full `assess_quality` runs: 128-band Python loops per FFT frame, Hilbert, Welch, find_peaks).
- **Impact**: A short final chunk (or a very short file) that lands on a gated call index (always the first call of a fresh `ContinuousMode`, then 1 in 5) aborts mastering of that chunk with an exception instead of returning audio of the same length; the invariant `len(output) == len(input)` is lost for that call. For every other gated chunk the playback worker spends ~2 s extra for a debug log line.
- **Siblings**: `QualityMetrics.assess_quality` itself fails the same way for any window under 8192 samples; `evaluate_mastering_files` only guards at 0.4 s (17 640 samples at 44.1 kHz, so it is safe there, but not at 8-16 kHz sample rates).
- **Suggested Fix**: Skip the gate when the chunk is shorter than the analyzer FFT (and make `analyze_file` of a too-short input pad rather than return `{}`). Preferably remove the gate from the real-time path (no consumer) or run it off the audio path / only when a diagnostics flag is on.

#### ENG-D6-03: `MasteringFingerprint.from_audio_file` decodes and resamples the entire file for every FFmpeg-routed format before cropping to 90 s
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/mastering_fingerprint.py:105-127`
- **Status**: NEW (same class as the #5110 fix applied to `windowed_compute.py`; this sibling was missed)
- **Description**: For `.mp3 .m4a .aac .ogg .wma .opus` the code calls `load_with_ffmpeg(audio_path, tmp)` with no `offset`/`duration`, resamples every channel of the full buffer with librosa, and only then slices `raw_audio[..., :int(sr * 90.0)]`. The comment claims the 90 s cap bounds peak memory (#4116), which is only true for the libsndfile branch (`librosa.load(..., duration=90.0)`). `load_with_ffmpeg` supports `duration=` (#5110) and `windowed_compute` already uses it.
- **Evidence**: Call path `GET /api/enhancement/.../mastering-recommendation` (`routers/enhancement.py:682`) -> `ChunkedAudioProcessor.get_mastering_recommendation` -> `chunk_mastering.compute_mastering_recommendation` (`chunk_mastering.py:62`) -> `MasteringFingerprint.from_audio_file(filepath)`. `adaptive_mastering_engine.py:344` and `analyze_album()` use the same entry point.
- **Impact**: A multi-hour MP3/M4A (podcast, DJ mix, audiobook) is fully transcoded to a temp WAV, loaded into RAM (GBs) and resampled just to read 90 s, on a REST request path. CPU/memory and latency grow with file length; OOM risk on the desktop process.
- **Siblings**: None other found in `auralis/analysis`, `auralis/services`, `auralis/learning` (`grep load_with_ffmpeg(`).
- **Suggested Fix**: Pass `duration=90.0` to `load_with_ffmpeg` (resample after the bounded decode), mirroring `windowed_compute._decode_window`.

#### ENG-D6-04: Distortion/noise assessors measure the signal, not distortion or noise, and the "noise floor" scales 1:1 with level, so a louder master always scores worse
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/quality_assessors/utilities/estimation_ops.py:22-95` (`estimate_thd`), `:117-148` (`estimate_noise_floor`); `auralis/analysis/quality/distortion_assessment.py:38-62`; weight 0.25 in `quality_metrics.py:160-170`
- **Status**: NEW
- **Description**: `estimate_thd` takes the largest FFT bin of the middle half of the track (excluding the first 10 bins) as "the fundamental" and reports sqrt(power at bins 2f..5f / power at f). For music there is no single fundamental, so this is the ratio of four arbitrary bins to the strongest bin. `estimate_noise_floor` is the mean of the lowest 10 % of `|x|` samples, i.e. the near-zero-crossing part of the amplitude distribution of the programme itself (about rms - 24 dB for Gaussian-like material), not a noise measurement. The two feed 70 % of `DistortionAssessor` (0.4 THD, 0.3 noise) and `detailed_analysis` sets `excessive_distortion` / `high_noise`.
- **Evidence**: Probes (`QualityMetrics.assess_quality`, 44.1 kHz stereo): white Gaussian noise (no harmonics at all) -> `thd = 0.21`, `excessive_distortion=True`; pink noise scaled -40/-30/-20/-14/-10/-6 dBFS rms -> `noise_floor_db` -65.2/-55.2/-45.2/-39.2/-35.2/-31.2 and distortion score 52.6/49.3/45.8/43.7/18.9/10.9 with identical spectrum shape; a clean synthetic chord with -54 dBFS noise reports `noise_floor_db = -45.1`, `thd = 0.68`, `high_noise=True`.
- **Impact**: The before/after `MasteringEvaluationReport` (`simple_mastering.py:250-265`, `continuous_quality.py`) systematically scores a loudness-raised master lower on "distortion" and flags healthy music as noisy/distorted, so the advisory verdict printed to the user for a mastering engine is biased against its own main operation. Overall score is 25 % distortion.
- **Siblings**: `detect_excessive_noise` / `detect_excessive_distortion` in the same file reuse both estimators.
- **Suggested Fix**: Either drop the two estimators from the overall score, or measure noise from a spectral/frame-RMS floor (e.g. 5th-percentile frame RMS over gated frames, relative to the programme) and replace THD with a tonal-peak test that only reports when a dominant harmonic series exists.

#### ENG-D6-05: Similarity prefilter returns the first `n*10` rows of the range box with no `ORDER BY`, not the nearest candidates
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/library/repositories/fingerprint_similarity_mixin.py:223-228`; consumer `auralis/analysis/fingerprint/similarity.py:325-342`
- **Status**: NEW
- **Description**: `find_similar` pre-filters by a rigid box (lufs +-3, crest +-2, bass_pct +-0.08, tempo +-15 BPM) via `get_by_multi_dimension_range(ranges, limit=n*prefilter_factor)`. The statement is `select(TrackFingerprint).where(...).limit(limit)` without ordering, so for `n=10` the candidates are 100 arbitrary rows (in practice lowest rowid = oldest fingerprints) and the 25-D distance only ranks within them. For libraries where the box holds more than 100 tracks, the true nearest neighbours are dropped depending on insertion order. The tempo constraint is also applied on the estimator that makes octave errors (ENG-D6-08), which silently excludes true neighbours.
- **Evidence**: Code: no `order_by` in the statement; `_get_prefiltered_candidates(target_fp, max_candidates=n * prefilter_factor)`. The K-NN graph builder (`knn_graph.py:121-126`) uses the same `find_similar` for every track, so the persisted graph inherits it.
- **Impact**: "Similar tracks" and the K-NN graph degrade with library size; recommendations are biased to the oldest-fingerprinted tracks. No crash.
- **Siblings**: `knn_graph.update_graph` and `build_graph` via `find_similar`.
- **Suggested Fix**: Order the box query by a cheap L1 distance on the same four dimensions (or fetch the whole box, bounded at e.g. 5000, and rank in numpy) before applying the limit.

#### ENG-D6-06: `FingerprintNormalizer.fit` gates on an unfiltered row count but fits on filtered rows, and the similarity fit is once-per-process
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/normalizer.py:151-153,164-176`; `auralis/library/repositories/fingerprint_query_mixin.py:152-160` (`get_count`) vs `:80-115` (`get_all`); `auralis/analysis/fingerprint/similarity.py:106-110`
- **Status**: NEW
- **Description**: `min_samples` (default 10) is checked against `get_count()`, which counts every `track_fingerprints` row including claim placeholders and stale-version rows. `get_all()` (used to build the vectors) excludes both (#4822). Right after an algorithm bump (as of today, v10) the table is mostly stale: `get_count()` is large, `get_all()` returns a handful or none, and `fit()` publishes `DimensionStats` computed from, say, 3 vectors (5th/95th percentiles of 3 samples), `fitted=True`. `FingerprintSimilarity.fit` returns `True` immediately on later calls (`if self.fitted`), and the startup auto-fit worker runs once, so the statistics are never refreshed as the library re-fingerprints.
- **Evidence**: `fit`: `total = fingerprint_repository.get_count(); if total < min_samples: ...` then `batch = fingerprint_repository.get_all(limit=batch_size, offset=offset)`; `get_count` is `select(func.count()).select_from(TrackFingerprint)`.
- **Impact**: Normalised distances (and the K-NN graph built from them, `autofit_worker._run`) use ranges from a tiny, possibly unrepresentative sample after each version bump or on young libraries; dimensions with a degenerate range collapse to 0.5. Similarity quality is wrong until a restart with a mature library or a manual refit.
- **Siblings**: `KNNGraphBuilder` is constructed only after a successful fit.
- **Suggested Fix**: Count with the same `_current_fingerprint_clause()` as `get_all`, and allow `fit()` to re-run (or refit when the current-row count has grown by some factor).

#### ENG-D7-02: `begin_nested()` on the default pysqlite driver commits the get-or-create work immediately, so a failed `add()` / `update*()` leaves orphan artists, genres and albums
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_lifecycle.py:73`, `:91`, `:110` (`_get_or_create_artists/_genres/_album`); engine config `auralis/library/database.py:138-145`
- **Status**: NEW (compounds Existing #5596)
- **Description**: The engine uses pysqlite's legacy transaction mode with no `begin` event hook that emits `BEGIN`. SQLAlchemy documents that SAVEPOINT is unreliable there: `SAVEPOINT` opens the SQLite transaction itself, and the outermost `RELEASE` commits it. The savepoint-wrapped inserts are therefore durable even if the surrounding session later rolls back. `add()` resolves artists, genres and album first and inserts the `Track` last, so any later failure (IntegrityError, lock timeout, vanished row) rolls back the track but not its parents. The "scoped rollback" comment on these blocks is not true on this driver.
- **Evidence**: Probe `p11.py`: (1) `_get_or_create_artists(['Ghost Artist'])` + `_get_or_create_genres(['Ghost Genre'])` inside a session, then `session.rollback()` -> `artists=1 genres=1`. (2) `add()` for a path whose `filepath` collides with an existing row -> returns `None` but leaves `artists 2, genres 2, albums 1, tracks 1`.
- **Impact**: Zero-track artists/albums/genres appear in the Artists/Albums/Genres views and statistics after any failed ingest; the sweep that would remove them does not exist (#5596). Any partial-failure invariant in `add()` is weaker than its code suggests.
- **Siblings**: `update_by_filepath`, `update`, `_assign_album` (same helpers, `track_repository_mutation.py:41-60`).
- **Suggested Fix**: Install the standard SQLAlchemy pysqlite fix (`connect` sets `isolation_level=None`, `begin` event executes `BEGIN`) on the engine, or drop the savepoints and resolve get-or-create with `INSERT ... ON CONFLICT DO NOTHING` + re-select. Add a test that rolls back after `add()` fails.

#### ENG-D7-03: `track_fingerprints.fingerprint_blob` is in the model but no migration ever adds it, so every fingerprint read fails on databases migrated from before 2025-12-11
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/models/fingerprint.py:101`; `auralis/library/migrations/` (no `ADD COLUMN fingerprint_blob`); `auralis/library/database.py:184-194` (only `create_all` + index repair)
- **Status**: NEW
- **Description**: `fingerprint_blob` was added to the ORM in 31dfe0c7 (2025-12-11, Phase 3A) with no migration; v003->v004 creates `track_fingerprints` without it and v014/v016 only add `is_reference`/`reference_weight`. `create_all` never alters existing tables, and `create_missing_declared_indexes` repairs indexes only. Any library whose `track_fingerprints` table predates that commit and was upgraded through the SQL migrations has no such column, yet every `select(TrackFingerprint)` and both raw upserts reference it.
- **Evidence**: Probe `p1.py/p3.py`: v1 schema migrated to v22 through `check_and_migrate_database` (success), opened with `LibraryDatabase`; `db.fingerprints.get_by_track_id(1)` -> `OperationalError: no such column: track_fingerprints.fingerprint_blob`. Schema diff (`p2.py`) shows that column as the only one missing; the owner's current DB is fine (it has the column).
- **Impact**: For affected upgrades the fingerprint cache, the background queue, similarity and the reference cloud all fail permanently; callers swallow the error and recompute, so it presents as "fingerprints never stick". Nothing repairs it.
- **Siblings**: `user_settings` has no migration at all (only `create_all`); any column added to it after a user's table was created hits the same wall. Unverified for columns added later because the file history was lost in the models split.
- **Suggested Fix**: Add a v22->v23 migration `ALTER TABLE track_fingerprints ADD COLUMN fingerprint_blob BLOB` (the runner already tolerates "duplicate column"), and add a CI test that migrates a v1 schema and diffs it against `create_all` for column presence.

#### ENG-D7-04: A rescan that detects a replaced/modified file updates the track row but leaves its `track_fingerprints` row current, so the new audio keeps the old file's fingerprint
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/batch_processor.py:140-146`; `auralis/library/repositories/track_repository_mutation.py:63-104` (`update_by_filepath`); read side `auralis-web/backend/analysis/fingerprint_generator.py:218-224`, `auralis/analysis/fingerprint/fingerprint_service.py:_load_from_database`
- **Status**: NEW
- **Description**: The `.25d` caches and the chunk cache key on size+mtime and self-invalidate, but the DB fingerprint row is keyed on `track_id` only and `get_by_track_id` filters on algorithm version, never on the file. `update_by_filepath` neither deletes nor flags the fingerprint, and the scan only enqueues `added_tracks` for fingerprinting. A re-ripped, remastered or re-encoded file at the same path therefore stays tied to the fingerprint of the previous audio indefinitely.
- **Evidence**: Code path above; no reference to `fingerprint` anywhere in `update_by_filepath` / `process_single_file`.
- **Impact**: Mastering targets, `ProcessingCoordinates`, similarity and the reference cloud are computed from another recording's analysis, exactly for the "remaster in place" case the #5574 watermark was introduced to catch. Persistent until the DB is reset.
- **Siblings**: `TrackRepository.update_metadata` is tag-only and unaffected.
- **Suggested Fix**: In the scanner's 'updated' branch, when `filesize`/`duration` or mtime changed, delete the fingerprint row via `FingerprintRepository.delete()` and enqueue the track.

#### ENG-D7-05: Artist-name heuristics split real band names and merge symbol-only names into one artist
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/utils/artist_normalizer.py:48-99` (`normalize_artist_name`), `:101-180` (`parse_featured_artists`, `PRESERVED_DUOS` at `:31`, short-name rule `:174-177`); use `track_repository_lifecycle.py:63-82`, `scanner/metadata_extractor.py:195-207`
- **Status**: NEW
- **Description**: (1) `normalize_artist_name` keeps only alphanumerics, so names made of symbols normalise to `''`. `_get_or_create_artists` matches on `normalized_name`, so every such artist collapses onto the first one stored. (2) `parse_featured_artists` splits any `A & B` / `A and B` whose parts are <= 3 words and do not start with "the", unless the full name is in a 13-entry hard-coded list. The scanner applies it to every artist tag, so a single-artist tag becomes several artists.
- **Evidence**: Probe `p9.py`: tracks tagged `!!!` and `+/-` both land on artist 1 (`name='!!!'`, `normalized_name=''`, titles `t0,t1`); `Iron & Wine` becomes artists `Iron` and `Wine`; `Mumford & Sons` becomes `Mumford` and `Sons`. Parser output also splits `Belle and Sebastian`, `Coheed and Cambria`, `Tegan and Sara`, `Of Monsters and Men`, `Simon and Garfunkel` (list only has the `&` spelling).
- **Impact**: Wrong artist pages, track counts and search results for such libraries; no per-file workaround because the DB value is derived from the tag at every rescan.
- **Siblings**: ENG-D4-09 (multi-value tags) touches the same input path.
- **Suggested Fix**: Do not split a name that is the whole artist tag unless the tag has an explicit feat/ft/vs marker or multiple tag values; prefer ALBUMARTIST. Make the normalised key fall back to the casefolded raw name when it is empty.

### LOW

#### ENG-D1-05: Real-time chain scales the whole chunk by a peak-derived gain, stepping the gain at every chunk boundary (zipper clicks)
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/player/realtime/processor.py:165-170` (safety peak), `auralis/player/realtime/level_matcher.py:104-109` (`processed *= limiter_gain`), `auralis/player/realtime/auto_master.py:185-190` (adaptive peak ceiling)
- **Status**: NEW
- **Description**: All three limiters compute `target_peak / max(|chunk|)` over the current buffer and multiply the entire buffer by it. The gain is constant inside a chunk and independent between chunks, so it steps at each buffer boundary whenever one buffer exceeds the ceiling and its neighbour does not.
- **Evidence**: Probe: `RealtimeProcessor.process_chunk` on a continuous 200 Hz sine, 1024-sample buffers, one buffer at 1.3 peak: `|out|/|in|` is 1.000 on the sample before the hot buffer and 0.728 on its first sample, and 0.728 -> 1.000 on leaving it (-2.8 dB step each side).
- **Impact**: Audible clicks on any over-ceiling material, but `AudioPlayer.get_audio_chunk` has no production consumer in the backend (the desktop app streams via the WebSocket chunk pipeline; no `sounddevice`/output stream exists in the tree), so this is latent.
- **Siblings**: the three locations above.
- **Suggested Fix**: Route all three through one smoothed-gain helper (attack ramp, per-sample envelope carried across calls, like `AdaptiveGainSmoother`) or delete the unused real-time output path.

#### ENG-D1-06: HybridProcessor returns buffers shorter than 1024 samples before any finite-value check
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/hybrid_stage_dispatch.py:80-90` (MIN_SAMPLES return precedes `validate_audio_finite` at `:97`)
- **Status**: Existing: #5191 (open); re-verified in the live code.
- **Description / Evidence**: The too-short branch returns `target_audio.copy()` unprocessed and unvalidated, so NaN/Inf in a sub-1024-sample buffer is passed straight through, while every longer buffer fails fast.
- **Impact**: At most the last <23 ms of a track; downstream `WAVEncoder` rejects non-finite audio, which turns it into a chunk failure rather than silence.
- **Siblings**: none.
- **Suggested Fix**: Move the finite check above the early returns.

#### ENG-D1-07: No DC-offset removal anywhere in the shipped chain
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/hybrid_processor.py` / `auralis/core/processing/continuous_mode.py` (absent)
- **Status**: Existing: #5187 (open)
- **Description / Evidence**: Re-probed: a stereo signal with +0.3 DC offset leaves `HybridProcessor.process` with the DC intact and its peak pinned at 0.9661, so the offset eats headroom and is re-amplified by the track gain.
- **Impact**: Reduced headroom/loudness on sources with DC; no corruption.
- **Siblings**: none.
- **Suggested Fix**: As in #5187 (a gentle 5-20 Hz high-pass or per-chunk mean removal at the input).

#### ENG-D2-09: `ContinuousMode` caches the reference cloud per processor forever (an empty first read is permanent), and the engine now imports the backend `config.globals` to find the repository
- **Severity**: LOW
- **Dimension**: DSP Pipeline (config reachability)
- **Location**: `auralis/core/processing/continuous_mode.py:129-155`; `auralis/core/hybrid_setup.py:97-124`
- **Status**: NEW (follow-up to #5560)
- **Description**: `_reference_context` sets `self._reference_cloud = []` when the first `get_reference_cloud()` returns nothing (or raises) and never reloads, because the guard is `is None`. The backend refreshes the cloud asynchronously (`_init_reference_cloud_refresh`, fingerprint-queue drain callback, post-scan hook) while processors live in an LRU of 32 (`ProcessorFactory`). A processor created before the first refresh keeps the legacy deficit EQ for its lifetime, and one created before a later refresh keeps a stale cloud, so which EQ algorithm a track gets depends on processor age. Separately, the engine package does `from config.globals import get_component_registry` (a backend top-level module name), which only resolves when `auralis-web/backend` is on `sys.path`.
- **Evidence**: code: `if self._reference_cloud is None: ... self._reference_cloud = []` then `if not self._reference_cloud: return None`.
- **Impact**: Inconsistent EQ across tracks/sessions; small per track. The import is a layering inversion that silently degrades to "no repository" when the path differs.
- **Siblings**: `_distance_stats` is cached with the cloud.
- **Suggested Fix**: Expire the cache (version/timestamp from the repository or a short TTL) and treat an empty cloud as "retry next call"; inject the repository through `ProcessorFactory`/`build_hybrid_components` instead of importing the backend registry.
- **Also reported as**: ENG-D7-10 — `refresh_cloud()` is not atomic, and the continuous-mode processor caches an empty cloud for its lifetime (`LOW`; location: `auralis/learning/reference_seeder.py:186-232`; `auralis/library/repositories/fingerprint_similarity_mixin.py:56-100`; consumer `auralis/core/processing/continuous_mode.py:137-150`). Folded here; its evidence is consistent with the above.

#### ENG-D2-10: Cross-dimensional guards decide on the first 2 seconds of the first channel only, which for chunks 1+ is trimmed context
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/stage_snapshot.py:46-77` (consumers `continuous_stages.py:159-185,195-219`)
- **Status**: NEW
- **Description**: `_compute_3band_energy` and `_compute_phase_correlation` truncate to `sample_rate * 2` samples from the START of the buffer, and the 3-band split uses channel 0 only. The tilt-correction guard (up to +-2 dB over the whole buffer) and the phase-blend guard are therefore decided by the first 2 s of a 15 s buffer. In the backend, chunks 1+ are loaded with leading context and the first 5 s of their emitted audio are skipped (`chunk_boundaries.py:emitted_chunk_start`), so the measured window is audio that is discarded, and two renderings of the same overlap can take different decisions.
- **Evidence**: code: `max_samples = min(len(signal), sample_rate * 2); signal = signal[:max_samples]`.
- **Impact**: Guard corrections are noisy estimates applied to the whole chunk; adds to seam variability (ENG-D2-04). Low magnitude.
- **Siblings**: none.
- **Suggested Fix**: Measure on a strided or centre-weighted sample of the kept region, using both channels (mid).

#### ENG-D2-11: Offline `stereo_expansion` width curve is discontinuous at fingerprint widths 0.15 and 0.30 (about 3x jump)
- **Severity**: LOW
- **Dimension**: DSP Pipeline (offline CLI subsystem, #4873)
- **Location**: `auralis/core/stages/stereo_expansion.py:61-76`
- **Status**: NEW
- **Description**: The three branches of `narrowness_factor` do not meet: at 0.15 the first branch ends at 0.6 and the Gaussian branch starts at 0.195; at 0.30 the Gaussian ends at 0.195 and the third branch starts at 0.3. The module is documented as using smooth curves.
- **Evidence**: `apply(..., current_width, intensity=1.0, ...)` `width_factor - 0.5`: width 0.1499 -> 0.0780; 0.1501 -> 0.0254; 0.2999 -> 0.0254; 0.3001 -> 0.0390.
- **Impact**: Two tracks 0.0002 apart in measured width get side gain +2.6 dB vs +0.9 dB. Offline CLI only.
- **Siblings**: ENG-D2-07's minimum-gain gates in the other named stages.
- **Suggested Fix**: Use one continuous bell/smoothstep over the width axis.

#### ENG-D2-13: Compression stage is level-dependent and its generated threshold/attack/release are ignored (verified still true)
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/base/compression_expansion.py:94-123`
- **Status**: Existing: #5576
- **Description**: `apply_clip_blend_compression` still reads only `ratio` and `amount` and uses an absolute soft-clip threshold `0.8 - (ratio-1)*0.1`. No change needed to the issue.
- **Evidence**: unchanged code.
- **Impact**: see #5576.
- **Siblings**: see #5576.
- **Suggested Fix**: see #5576.

#### ENG-D3-07: A failed load forces a healthy player into the terminal ERROR state, and nothing but another successful load leaves it
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/player_file_loading_mixin.py:86-88,150-152`; `auralis/player/playback_controller.py:149-153,189-196,284-292`; `auralis/player/integration_manager.py:256-292`
- **Status**: NEW
- **Description**: `load_file()`/`load_track_from_library()` call `playback.set_error()` on any failure, even though a failed `AudioFileManager.load_file` leaves the previous audio and position untouched. In ERROR, `play()` is rejected ("load a new file first") and `stop()` returns False (it only handles PLAYING/PAUSED), and a successful `next_track()` swap does not resume because `was_playing` is False. `next_track()` failure, by contrast, does not set ERROR, so the two navigation paths disagree. In `IntegrationManager.load_track_from_library` the broad `except` also covers `repos.tracks.record_play()` and the final notify, i.e. it can return False (and set ERROR) after the audio was already swapped and `current_track` set.
- **Evidence**: Probe: `previous_track()` onto a missing file -> `state == ERROR`, `play()` -> False. Backend: `queue_set_mixin.py:154-163` ignores the `load_file` result and `play()` result and still broadcasts `set_playing(True)`.
- **Impact**: After a transient failure (moved file, DB lock in `record_play`) the engine reports ERROR and ignores play/stop while the backend state manager says "playing"; recovery needs a lucky successful load.
- **Siblings**: `load_file` (:86), `load_track_from_library` (:150).
- **Suggested Fix**: Only enter ERROR when no audio is loaded (or let `stop()`/`play()` recover from ERROR when audio is loaded); move `record_play` after the success return or guard it separately.

#### ENG-D3-08: `current_track` metadata goes stale after any queue-driven advance (`next_track()`/`previous_track()`/auto-advance)
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/player_queue_navigation_mixin.py:57-151,153-193`; `auralis/player/integration_manager.py:218-239,269-274`; `auralis/player/player_streaming_mixin.py:133-138`
- **Status**: NEW
- **Description**: `integration.set_current_track()` is called only from `load_track_from_library`. The gapless `next_track()` path and `previous_track()` (which uses `load_file`) never update it, so `_current_track_dict` keeps describing whichever track was last loaded from the library. Every playback state dict (`'current_track'`), `get_playback_info()['library']['current_track']` and the new #5584 `playback_finished` event read that dict.
- **Evidence**: Probe: queue `[A, B]`, `current_track = A`, `next_track()` (file is now `b.wav`) -> `library.current_track == {'title': 'A'}`; playing B to its end emits `playback_finished` with `track.title == 'A'`.
- **Impact**: Consumers of the engine callback surface attribute events to the wrong track. No in-repo production consumer today (`add_callback` is never called by the backend).
- **Siblings**: `file_loaded`/`track_completed` events carry no track at all.
- **Suggested Fix**: Resolve and set the current track in the advance paths (or derive it from `queue.get_current_track()` at notify time).

#### ENG-D3-09: Loading by path/`add_to_queue` never syncs the queue pointer, so an empty-queue `add_to_queue` plays the same track twice
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/player_queue_navigation_mixin.py:204-233`; `auralis/player/components/queue_manager.py:52-56,91-110`
- **Status**: NEW
- **Description**: `add_to_queue()` appends and loads the track when nothing is loaded, but `QueueManager.add_track` leaves `current_index == -1` on an empty queue. The loaded track therefore is not "current" (`get_current_track()` is None) and `peek_next()` returns that same track (index 0), so `has_next_track()` is True. `load_file`/`load_track_from_library` never touch the pointer either.
- **Evidence**: Probe: `add_to_queue({'file_path': a})`, `play()`, run to end -> `peek_next` == the playing track, auto-advance reloaded it (`queue idx 0`, `tracks_played == 1`) before stopping at the second end.
- **Impact**: The first track added to an empty queue plays twice; now-playing info for the engine queue is empty while audio is loaded. Reached via the backend `POST /api/player/load` (no frontend consumer today).
- **Siblings**: `AudioPlayer.load_playlist` is fine (it sets the index).
- **Suggested Fix**: When `add_to_queue` triggers the load into an empty queue, also set `current_index = 0` (or sync the pointer in the load paths).

#### ENG-D3-10: `shuffle_enabled` survives `set_queue()`/`clear_queue()` while the order is no longer shuffled
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/queue_controller.py:300-304,332-340,427-448`; `auralis/player/components/queue_manager.py:226-231`
- **Status**: NEW
- **Description**: `set_queue()`, `load_playlist()` and `clear()` drop the shuffle snapshot but leave the `shuffle_enabled` flag set, so `get_queue_info()` reports shuffle on over an unshuffled queue, and `set_shuffle(True)` is then a no-op because of the #5315 `already_enabled` guard.
- **Evidence**: Probe: shuffle, then `set_queue(8 new tracks)` -> `shuffle_enabled == True`, order `[0..7]`, `_pre_shuffle_tracks is None`; `set_shuffle(True)` leaves the order unchanged; `clear_queue()` keeps the flag True.
- **Impact**: Shuffle indicator wrong after starting a new queue; a programmatic `set_shuffle(True)` cannot re-shuffle. The REST shuffle path (`controller.shuffle()`) is unaffected.
- **Siblings**: `QueueManager.clear()`.
- **Suggested Fix**: Either reset the flag where the snapshot is dropped, or re-apply `shuffle()` after a repopulating `set_queue` when the flag is on; make `set_shuffle` compare against "is the snapshot held" instead of the flag.

#### ENG-D3-11: Real-time chain is built for `config.sample_rate` and never told the track's actual rate
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/player_streaming_mixin.py:142`; `auralis/player/realtime/processor.py:108,190`; `auralis/player/realtime/auto_master.py:54,58`
- **Status**: NEW
- **Description**: `AudioFileManager.sample_rate` follows the loaded file (no resampling), but `get_audio_chunk` calls `process_chunk(chunk)` without `sample_rate`, `AdaptiveCompressor` and `LowMidTransientEnhancer` are constructed once with `config.sample_rate`, and the performance monitor divides by `config.sample_rate`. For a 48/96 kHz file the compressor attack/release (20/200 ms) and the 50 ms transient window are scaled wrongly and CPU-usage stats are off by the rate ratio. The `AudioFileManager` docstring still claims "auto-resampling to target sample rate".
- **Evidence**: grep: `process_chunk(chunk)` is the only call; `AdaptiveCompressor(comp_settings, config.sample_rate)` is built in `AutoMasterProcessor.__init__`.
- **Impact**: Wrong dynamics timing for non-44.1 kHz material when auto-mastering is on (off in the shipped config, so currently dormant).
- **Siblings**: none.
- **Suggested Fix**: Pass `file_manager.sample_rate` into `process_chunk` and reconfigure (or rebuild) the compressor/enhancer on a rate change; fix the stale docstring.

#### ENG-D4-07: Non-canonical multichannel WAV/FLAC/AIFF silently re-enter FFmpeg, ignoring the caller's `cancel_event` and `temp_folder`
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/soundfile_loader.py:86-98`; contract text at `auralis/io/unified_loader.py:46-51`
- **Status**: NEW
- **Description**: `load_with_soundfile` routes 3/4/5/7/9+ channel files to `load_with_ffmpeg(file_path)` with no `temp_folder` and no `cancel_event`. `load_audio`'s docstring says `cancel_event` is "ignored for natively-decodable formats (no subprocess to cancel)", which is false for these files, and the job's private temp folder is bypassed (temp WAV goes to the system temp root).
- **Evidence**: `return load_with_ffmpeg(file_path)` (`:98`); probe: 3/4/5-channel `.wav` through `load_audio` decode correctly via FFmpeg (shape `(N, 2)`).
- **Impact**: Cancelling a processing job on a quad/5.0/3-channel WAV cannot terminate the FFmpeg child (up to the 300 s timeout), and its temp output lands outside the job directory that job cleanup manages.
- **Siblings**: `loader.py:load()` has the same unthreaded call; `simple_mastering.py:208-210` calls `load_with_soundfile` directly.
- **Suggested Fix**: Add `temp_folder`/`cancel_event` parameters to `load_with_soundfile` and forward them to the FFmpeg fallback; correct the docstring.

#### ENG-D4-08: FFmpeg is run without `-nostdin` and at default log level
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:476-500` (and `_run_ffmpeg_cancellable`, `:162-180`)
- **Status**: NEW
- **Description**: The decode argv has `-y` but not `-nostdin`, and the child inherits the backend's stdin (no `stdin=` argument anywhere in `auralis/io`). By FFmpeg's documented behaviour, interaction on stdin is on unless disabled, so when the backend runs from a terminal (`python main.py --dev`) keystrokes ('q') abort an in-flight decode into a "truncated" result, and when stdin is a pipe FFmpeg may consume bytes meant for the parent. No `-hide_banner`/`-loglevel error` either, so stderr (captured in memory) carries banner and progress for every decode.
- **Evidence**: `grep -rn "nostdin\|stdin=\|DEVNULL" auralis auralis-web/backend` finds nothing; only ffprobe has `-v error`.
- **Impact**: Dev-mode flakiness (decode ends early, reported as truncation) and unbounded stderr growth on noisy corrupt streams; not probed at runtime (the clips decode too fast to type into).
- **Siblings**: ffprobe calls (`:102-115`, `unified_loader._get_info_with_ffprobe`) also inherit stdin.
- **Suggested Fix**: Add `-nostdin -hide_banner -loglevel error` to the ffmpeg argv and pass `stdin=subprocess.DEVNULL` in both runners.

#### ENG-D4-09: Free-form tags are not bounded or multi-value aware, so a malformed track number blocks ingest and extra artists/genres are dropped
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/library/scanner/metadata_extractor.py:119-127,132-157`
- **Status**: NEW
- **Description**: (a) `_normalize_field_value` returns unbounded Python ints for `track`/`disc`. (b) `if isinstance(value, list) and value: value = value[0]` keeps only the first of repeated Vorbis `ARTIST`/`GENRE` values, so `audio_info_to_track_info`'s list branches (`:190-215`) are dead and multi-artist FLAC/OGG files get one artist.
- **Evidence**: FLAC with `TRACKNUMBER=99999999999999999999` -> extractor yields `track: 99999999999999999999`; `TrackRepository.add()` with that value returns `None` (control with `track_number=5` adds fine), so the scanner reports only "Database insert failed" for an otherwise decodable file. FLAC with `ARTIST=['Artist One','Artist Two']`, `GENRE=['Rock','Pop']` -> `{'artist': 'Artist One', 'genre': 'Rock'}`.
- **Impact**: A file with one absurd tag is never imported (reason hidden); multi-valued artist/genre tags are silently truncated.
- **Siblings**: `year` is safe (`[:4]`); `_validate_and_normalize_track_info` (`track_repository_lifecycle.py:42`) does not range-check `track_number`/`disc_number`.
- **Suggested Fix**: Reject (return `None`) numeric track/disc/year outside a sane range in `_normalize_field_value`, and keep the full list for `artist`/`genre` instead of `value[0]`.

#### ENG-D4-10: Relative filenames of the form `Word: ...` are rejected as FFmpeg protocol URLs
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:47-58`; callers `auto_master.py:156-168`, `simple_mastering.py:185`
- **Status**: NEW
- **Description**: `_PROTOCOL_PREFIX_RE` matches any leading `[A-Za-z][A-Za-z0-9+.-]+:`. The CLI passes `Path(args.input)` unresolved, so a bare relative file such as `Live: Concert.mp3` is refused with "URL/protocol inputs are not allowed". Absolute and `./`-prefixed paths are fine.
- **Evidence**: `reject_protocol_path('Live: Concert.mp3')` and `'AC-DC: Live.mp3'` raise; `'/abs/Live: x.mp3'`, `'./Live: x.mp3'`, `'Track 01: Intro.mp3'` pass. Library scans use absolute paths and are unaffected.
- **Impact**: CLI/offline mastering of an MP3/M4A in the working directory with a colon in its name fails with a misleading error.
- **Siblings**: `ffprobe_command` uses the same guard.
- **Suggested Fix**: Resolve to an absolute path (or prefix `./`) before the guard and before passing to FFmpeg, which also removes the need for the heuristic on relative paths.

#### ENG-D4-11: FFmpeg decode temp lives in the system temp root: not swept after a hard kill, and its size is outside the decode budget
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:445-455`; sweep at `auralis-web/backend/config/startup/tempfiles.py:57-125`
- **Status**: NEW
- **Description**: With no `temp_folder`, the intermediate is `mkstemp(prefix='auralis_', suffix='.wav', dir=gettempdir())` (player `loader.load()`, `windowed_compute`'s own `tmpXXXX` dirs, etc.). The `finally` cleans on normal exits, but a SIGKILL/OOM mid-decode (and the orphaned ffmpeg child, which keeps writing) leaves the file behind; the startup sweep only globs `auralis_stream_*` and `auralis_seekable_*`, so these are never reclaimed. Separately `MAX_DECODED_BYTES` (6 GiB) budgets the numpy array only; the f32 temp WAV adds a second copy of the same size, and on a tmpfs `/tmp` (this machine: `tmpfs 30G`) both are RAM.
- **Evidence**: `fd, temp_wav_str = tempfile.mkstemp(suffix='.wav', dir=str(temp_dir), prefix='auralis_')`; `#3671` comment in the same function already notes "/tmp (RAM-backed on Linux)".
- **Impact**: Slow RAM/disk leak after crashes (one full decoded track each); worst-case decode footprint is about 2x the documented budget.
- **Siblings**: `windowed_compute.py:214`, `mastering_fingerprint.py:113`, `simple_mastering.py:183,208` (`TemporaryDirectory()` in the system temp root).
- **Suggested Fix**: Use a single `auralis_`-prefixed temp root for all decode scratch (so the startup sweep and `SEEKABLE_TEMP_PREFIX`-style reclaim cover it), and count the temp WAV against the budget (halve the effective limit or decode directly to a memory-mapped array).

#### ENG-D4-12: Native 7.1 downmix folds side-surround channels into both outputs
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/processing.py:222-229`
- **Status**: NEW
- **Description**: For 8-channel input the matrix treats indices 4/5 (back L/R) as Ls/Rs but sums indices 6/7 (side L/R) into BOTH L and R (`extra = audio[:, 6:].sum(axis=1); L_out += 0.707*extra; R_out += 0.707*extra`). FFmpeg's own 7.1 downmix (used for the same content in M4A/AAC) places side-left only in L and side-right only in R, so identical material downmixes differently depending on container. Documented as a deliberate "don't invent placement", but it collapses hard-panned side content toward centre.
- **Evidence**: code above; `load_audio` of an 8-channel WAV returns peak 0.300 (renormalised to input peak), no test compares it to `ffmpeg -ac 2`.
- **Impact**: Minor stereo-image difference for 7.1 lossless files; no clipping (peak renormalised).
- **Siblings**: none.
- **Suggested Fix**: Route 8-channel layouts through the same FFmpeg `-ac 2` matrix (drop 8 from `_NATIVE_DOWNMIX_CHANNELS`) or map SL->L, SR->R explicitly.

#### ENG-D5-02 (STALE — withdrawn at publish time): Staged render file is created by `mkstemp` (mode 0600), so every published master is owner-only (`#5592` closed without a fix)
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:97-113`
- **Status**: STALE — withdrawn at publish time (2026-10-21). Commit `95d71a27` (2026-10-17, in HEAD) fixed #5592: the stage file is created with `os.open(..., 0o666)` inside a private temp directory, and `tests/auralis/core/test_mastering_stage_mode_5592.py` pins it. The audit agent's "closed with no fix" claim was wrong; no issue was filed. Original status: Regression of #5592 (closed COMPLETED 2026-10-17, no commit references it, code unchanged)
- **Description**: `tempfile.mkstemp` creates the staged `.part` file with 0600, `sf.SoundFile(mode='w')` reuses the inode, and `os.replace` publishes it, so the master keeps 0600 instead of the umask default. There is also no `fsync` before the rename (the stated model, `core/encoding/atomic_io.py`, has the fsync).
- **Evidence**: Live: `stat -c %a` on masters written by `master_file` gives `600` (input `664`, umask `002`), for both the stereo case and the 6-channel case. `grep -n "chmod\|umask\|fsync" mastering_chunk_loop.py` returns nothing.
- **Impact**: Masters written into a shared or served folder (NAS, media server, another user's library) are unreadable to other users and services. The cause is not obvious. Without the fsync, power loss right after the rename can leave a short file under the final name.
- **Siblings**: `auralis/utils/atomic_write.py` (JSON only, `NamedTemporaryFile` also 0600, but its targets are private sidecars). `core/encoding/atomic_io.py` writes backend-private caches, which is fine.
- **Suggested Fix**: Before `os.replace`, `os.chmod(tmp_path, 0o666 & ~umask)` (or copy the mode of an existing destination) and `os.fsync` the sink. Add a mode assertion to `tests/auralis/core/test_mastering_atomic_output_5109.py`.

#### ENG-D5-03: #5116's `sosfiltfilt_safe` fix left raw `sosfiltfilt` in the live chunk path, so a final chunk of at most about 12 samples still fails the whole render
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/dsp/resonance_notcher.py:214`, `auralis/core/dsp/transient_shaper.py:108`, `auralis/core/dsp/harmonic_exciter.py:135,147`; the chunk loop that produces the tiny chunk is `mastering_chunk_loop.py:157-170`
- **Status**: Regression of #5116 (CLOSED by `01848a75`, which converted only `parallel_eq.py`, `sub_bass_control.py` and `dsp/utils/stereo.py`)
- **Description**: When `total_frames % (30 s * sr)` is 1 to about 12 samples, the final chunk is processed alone (`core_samples` = the remainder, no left context). The first raw `sosfiltfilt` raises `ValueError: The length of the input vector x must be greater than padlen`, the staged file is deleted, and `master_file` fails. Those samples are already contained in the previous chunk's overlap tail, so the extra chunk is redundant.
- **Evidence**: `master_file` on a file of `30*sr + k` frames: k=1,2,5,9,12 FAIL (padlen 9 or 15); k=16,20,30,60,200 OK. Direct `_process` on a (2,5) and (2,12) array: failures raised at `resonance_notcher.py:214` and `transient_shaper.py:108`.
- **Impact**: About 1 in 10^5 track lengths fails to master, with a scipy error text that gives no hint. Batch mode records it as a failed file.
- **Siblings**: `auralis/core/processing/continuous_guards.py:78` and `core/processing/hf_aware_limiter.py:138` are also raw (HybridProcessor path; short-length behaviour not probed).
- **Suggested Fix**: Fix it once in the loop: fold a final remainder shorter than a safe minimum (for example the crossfade length) into the previous chunk. Alternatively route the four remaining sites through `sosfiltfilt_safe`.
- **Also reported as**: ENG-D2-12 — Unguarded `sosfiltfilt` in the remaining stage DSP and in the live tilt guard: a final chunk of 15 samples or fewer aborts the file (#5116 siblings) (`LOW`; location: `auralis/core/dsp/transient_shaper.py:108`, `auralis/core/dsp/harmonic_exciter.py:135,147`, `auralis/core/dsp/resonance_notcher.py:214`, `auralis/core/processing/continuous_guards.py:78`, `auralis/core/processing/hf_aware_limiter.py:138` (unwired)). Folded here; its evidence is consistent with the above.

#### ENG-D5-05: The chunk-seam guard added for #5339 is an `assert` (stripped under `-O`) and checks only the lower bound
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_config.py:87-102` (`SimpleMasteringConfig.__post_init__`)
- **Status**: NEW (the guard is from `3edbd9f2`, #5339; the lower-bound ratio itself is fine and verified)
- **Description**: The project convention, enforced by #5511 and #5533, is that chunk-loop invariants are real `raise`s because asserts vanish under `python -O`. This `assert` is the only one left in the mastering modules. It also checks only `CROSSFADE >= 20 * slowest_tau`. It does not check that the crossfade is shorter than `CHUNK_DURATION_SEC`, and the fields stay mutable after `__post_init__`.
- **Evidence**: `python -O -c "SimpleMasteringConfig(CROSSFADE_DURATION_SEC=0.01)"` is accepted. Without `-O`, `CROSSFADE_DURATION_SEC=35.0` (chunk 30 s) constructs fine and then fails mid-render with `RuntimeError: Crossfade write_region mismatch: expected 1323000 samples, got 1543500`, after rendering chunk 0.
- **Impact**: Latent. Default values are safe, and measured whole-vs-chunked seams are clean (-90 dB or better), so only custom configs or optimized runs are affected. The failure mode for a too-long crossfade is a late, confusing abort.
- **Siblings**: none in mastering modules.
- **Suggested Fix**: Raise `ValueError` for both bounds (`settle_floor <= crossfade < CHUNK_DURATION_SEC`).

#### ENG-D5-06: Rust `process_chunks` is still dead code and still returns silent all-zero output (or aborts the interpreter) for `overlap >= chunk_size`
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs:772-819`, `vendor/auralis-dsp/src/chunk_processor.rs:47-60`
- **Status**: NEW (#5537 closed on 2026-09-17 with a docstring correction only; the ENG-D5-07 claim in the 2026-10-16 report is now probed and confirmed)
- **Description**: The binding validates only the channel count. `let hop_size = chunk_size - overlap;` is unchecked `usize` arithmetic and the release profile has overflow checks off. `ChunkProcessor::new` allocates `(channels, overlap)` zeros eagerly. Nothing calls it: `grep` over `auralis/` and `auralis-web/backend/` finds no use of `auralis_dsp.process_chunks` or `ChunkProcessor`. The Python `mastering_chunk_loop.process_chunks` is an unrelated function with the same name.
- **Evidence**: Probed on `np.ones((2,10000))`:
  - `process_chunks(a, 4096, 1024)` returns all 1.0 (ok).
  - `(4096, 5000)` and `(1000, 2205)` return the right shape, **all zeros**, no error.
  - `(4096, 4096)` raises `RuntimeError: ... attempt to divide by zero` (panic caught).
  - `(4096, 2**40)` aborts the process (`memory allocation of 17592186044416 bytes failed`, rc 134; `catch_unwind` cannot catch alloc failure). `(4096, 2**62)` raises `PanicException` (shape overflow).
- **Impact**: None on shipped paths today. If anyone wires it in, bad parameters produce silent total data loss or a hard process abort. The function also differs from the Python path (f64 only, fixed 2205-sample linear crossfade, identity `process_fn`).
- **Siblings**: none.
- **Suggested Fix**: Delete the binding (nothing uses it). If it is kept, validate `0 < chunk_size`, `overlap < chunk_size` and a sane upper bound before constructing the processor.

#### ENG-D5-07: FFmpeg-format inputs are fully decoded into RAM before the "memory-efficient" chunked render
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/simple_mastering.py:180-192`; `master_file` docstring at `:133`
- **Status**: NEW (related: Existing #5566 for the same intermediate WAV's 4 GiB limit)
- **Description**: `master_file` claims to process "in chunks instead of loading entire file". For mp3/m4a/aac/ogg/wma/opus it calls `load_with_ffmpeg(...)`, which decodes to a temp `pcm_f32le` WAV and then returns the whole decode as one ndarray (`load_with_soundfile`). It then pushes that array through `save_audio` into a second PCM_24 WAV. The file the loader already wrote could have been read in place.
- **Evidence**: Code read only (the memory probe was lost to the tmpfs quota): `load_with_ffmpeg` returns `tuple[np.ndarray, int]`; float32 stereo at 44.1 kHz is about 0.35 MB per second, so roughly 2.5 GB for a 2 h file before `save_audio` makes its copies.
- **Impact**: Long podcasts or DJ mixes in compressed formats can exhaust memory in the CLI. Normal songs are fine, so the impact is small.
- **Siblings**: the multichannel pre-downmix block at `simple_mastering.py:203-212` does the same with `load_with_soundfile`.
- **Suggested Fix**: Stream ffmpeg directly to the temp WAV (`-ac 2 -acodec pcm_f32le`) and hand that path to the chunk loop. The loader already writes this file, so skip the read-back-and-resave step.

#### ENG-D5-08: Stage-info merge reports one `peak_reduction` entry per triggering chunk, contradicting the "de-duplicated" docstring
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:256-265` (dedup via `stage not in info['stages']`), docstring at `:51-55`
- **Status**: Regression of #5512 (closed; the merge works, the de-dup claim does not)
- **Description**: Dedup compares whole dicts. `peak_reduction` carries per-chunk `target` and `result` floats (`mastering_process_chunk.py:114`), so each chunk where it triggers adds a new entry.
- **Evidence**: Live `master_file` on a 100 s file returned two distinct `peak_reduction` entries (`-0.5003/-0.4847` and `-0.5018/-0.4643`) in `processing['stages']`. Other stages carry constant values and do collapse.
- **Impact**: Diagnostics only. A long loud track would list one entry per chunk.
- **Siblings**: none.
- **Suggested Fix**: Dedup on `stage['stage']`, or collapse the per-chunk fields (min/max).

#### ENG-D6-07: `LoudnessMeter` "loudness range" is not EBU R128 LRA (400 ms blocks, -10 LU relative gate)
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/loudness_meter.py:341-353`; scored in `auralis/analysis/quality/loudness_assessment.py:49-53` against `TARGET_LOUDNESS_RANGE_LU = (7, 20)`
- **Status**: NEW (the K-weighting accuracy itself is Existing #5593)
- **Description**: LRA per EBU Tech 3342 is the 10th-95th percentile spread of *3 s short-term* loudness gated at -20 LU relative to the ungated short-term mean. The meter takes the percentile spread of the *400 ms* block loudnesses, after the integrated-loudness gate at -10 LU. Block-to-block fluctuation from the beat is counted as range.
- **Evidence**: 90 s stereo noise with a 2 Hz pulse envelope: ffmpeg `ebur128` reports LRA 0.1 LU, `LoudnessMeter` 2.71 LU; same signal with 8 dB section steps every 15 s: ffmpeg 8.0 LU, meter 10.56 LU. Integrated loudness agrees (-21.2 vs -21.3, -23.6 vs -23.7).
- **Impact**: `loudness_range` in `detailed_metrics` and the 30 % LRA term of the loudness score are inflated by several LU for rhythmic material.
- **Siblings**: none.
- **Suggested Fix**: Compute LRA from 3 s sliding short-term windows (1 s hop) with the -20 LU relative gate, or rename/stop scoring the value.

#### ENG-D6-08: Tempo estimator uses un-normalised autocorrelation, producing octave errors (120 -> 60, 140 -> 70, 180 -> 60 BPM) and ~199 BPM for noise
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `vendor/auralis-dsp/src/fingerprint_compute.rs:394-420` (`estimate_tempo`)
- **Status**: NEW
- **Description**: The onset envelope's autocorrelation `sum(env[i]*env[i+lag])` over `lag in [60..200 BPM]` is taken with `argmax`, without dividing by the number of terms or applying a tempo prior, and with no octave disambiguation. Accented-downbeat patterns therefore flip between the beat period and multiples of it; featureless input prefers the shortest lag.
- **Evidence**: 60 s of noise clicks at a steady tempo with every 4th click accented: 60->60.1, 90->89.1, 100->99.4, 110->112.3, 120->**60.1**, 128->129.2, 140->**69.8**, 150->152.0, 180->**60.1**. White noise: 198.8.
- **Impact**: `tempo_bpm` carries weight 0.08 in the similarity distance and drives the +-15 BPM prefilter, so rhythmically identical tracks look different. Not used in mastering decisions (`target_generator.py:321` discards it).
- **Siblings**: none.
- **Suggested Fix**: Normalise by `n - lag`, optionally fold candidates with a log-Gaussian prior around 120 BPM; bump the algorithm version.

#### ENG-D6-09: `phase_correlation` uses `abs(mean(exp(i*dphi)))`, so a polarity-inverted stereo pair scores a perfect 1.0, and the stereo assessor adds 20 % of the score from it
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/phase_correlation.py:111-134`; consumed at `auralis/analysis/quality/stereo_assessment.py:45`
- **Status**: NEW
- **Description**: A constant phase offset of pi has `|mean(e^{i*pi})| = 1`. The `np.unwrap` before `np.exp` does nothing (exp is 2*pi periodic). The metric is the circular concentration of the phase difference, not its sign, but it is named and scored (`phase_score = phase_correlation * 100`) as "higher = better phase".
- **Evidence**: 5 s noise, `L = x`, `R = -x`: `correlation = -1.0`, `phase_correlation = 1.0`, `mono_compatibility = 0.0`, stereo score 20.0; `R = -0.8x + noise`: `phase_correlation = 0.931`. Uncorrelated L/R gives 0.003.
- **Impact**: The 20 % phase term rewards the worst case and the width term is also 0 for L = -R (mid = 0), so the damage is limited, but the dictionary value is misleading for any consumer.
- **Siblings**: none.
- **Suggested Fix**: Use the real part (`np.real(np.mean(np.exp(1j*dphi)))`), or drop the term.

#### ENG-D6-10: `DynamicRangeAnalyzer`: stereo is raveled (units become interleaved samples), short inputs crash, and silence yields a NaN crest factor that `band_score` maps to 100
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/dynamic_range.py:47-51,111-165,260-293`; `auralis/analysis/quality_assessors/utilities/scoring_ops.py:259-282` (`band_score`)
- **Status**: NEW (DR algorithm itself fixed in #5222; this is the edge/unit behaviour the previous audit did not check)
- **Description**: (1) For 2-D input `audio_data.ravel()` interleaves L/R, so every sample-denominated constant is halved in time: the TT-style 3 s DR block is 1.5 s, the 50 ms RMS window is 25 ms, `peak_density` is halved and `estimated_attack_time_ms` is doubled. (2) `_estimate_compression_ratio` calls `signal.filtfilt` (needs more than 300 samples) before its own `len < 1000` guard, and `np.max` on an empty array crashes `_calculate_peak_level`. (3) For silence, `peak = rms = -inf`, `crest_factor = nan`; `band_score(nan, ...)` falls through every comparison and returns the top-band score (100). Also the 30 s Hilbert cap makes `input_variation` (whole file) and `envelope_variation` (first 30 s) disagree for long audio.
- **Evidence**: `analyze_dynamic_range` raises `ValueError` for lengths 1, 100, 300 and for 0 samples. A 20 s dual-mono signal gives `dr_value` 12.25 vs 13.49 mono, `peak_density` 107.5 vs 215.0; mono 2.5 s -> `dr_value = 0.0` ("Very Poor"), same signal as stereo -> 10.49. Digital silence through `QualityMetrics.assess_quality` returns overall 40.7 "Fair" (crest NaN -> 100 on that term, distortion score 100).
- **Impact**: Advisory metrics only (`evaluate_mastering_files` windows are 8 s): inconsistent DR/timing numbers between mono and stereo and "Fair" for silent windows (e.g. a quiet intro window) in the evaluation.
- **Siblings**: `base_assessor._interpolate_score` has the same NaN-to-top-score behaviour.
- **Suggested Fix**: Analyse per channel (or a mono mix) instead of `ravel()`, guard short/empty input at the top of `analyze_dynamic_range`, return `crest_factor = 0.0` for non-finite levels, and make `band_score` return 0 for NaN.

#### ENG-D6-11: `FrequencyResponseAssessor` compares a max-normalised, A-weighted spectrum against a flat 0 dB reference, and 15 of 128 bands have no FFT bin
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/quality/frequency_assessment.py:34-49,65-76`; `auralis/analysis/spectrum_operations.py:200-217`; `auralis/analysis/quality/quality_metrics.py:55-61`
- **Status**: NEW
- **Description**: `map_to_bands` returns dB relative to the loudest band (`rms_to_db` with `ref=max`) *after* mean-magnitude averaging, then the analyzer adds the A-weighting curve; the assessor scores `|spectrum - reference|` against a reference of 0 dB across 50 Hz-16 kHz. So "flat" means every band as loud as the loudest band, plus the A-weighting offset (-39 dB at 31 Hz) is counted as deviation. With `fft_size=8192` at 44.1 kHz (5.4 Hz bins) the lowest 15 of 128 log bands (up to ~92 Hz) contain no FFT bin, read as the `top_db` floor and add ~114 dB of deviation each.
- **Evidence**: White noise: 15 empty bands, mean deviation 26.7 dB of which empty bands ~114 dB each (13 dB of the mean); `frequency_response_score` 56.1 (white), 32.4 (pink, level-independent), 0.0 for a harmonic chord. Even a perfect input cannot exceed ~74.
- **Impact**: 25 % of the overall quality score has a structural ceiling and scores white noise above pink noise; before/after comparisons are dominated by spectral tilt rather than response quality.
- **Siblings**: `identify_frequency_issues` uses the same `deviation`.
- **Suggested Fix**: Skip empty bands (or compute bands from octave-spaced integrated power), remove the double A-weighting, and define the reference relative to a pink/typical-music tilt.

#### ENG-D6-12: `FeatureExtractor.extract_features` assumes channels-first, so the genre classifier sees 2 samples of zero-padded audio for the canonical `(samples, 2)` input
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/ml/feature_extractor.py:58-77`; caller `auralis/core/analysis/content_analyzer.py:259` (`_classify_genre_advanced(audio)`)
- **Status**: NEW
- **Description**: `np.mean(audio, axis=0)` is documented as "(channels, samples)" but the pipeline passes `(samples, channels)`. For `(N, 2)` the mean over axis 0 is a 2-element array that is then zero-padded to 1 s, so every feature (rms, centroid, tempo...) describes silence.
- **Evidence**: 8 s 220 Hz tone + noise: `(N,2)` -> `rms 4.9e-8, centroid 11025.0, tempo 120.0`, mono -> `rms 0.213, centroid 7714.8, tempo 200.0`; `classify()` returns `classical 0.995` for the stereo input.
- **Impact**: `genre_info["primary"]` is constant for stereo input and feeds `EQProcessor._apply_content_adjustments` (+-20-30 % band scaling) on the legacy `AdaptiveMode`/`HybridMode` paths. The default continuous-space path does not use it, hence LOW.
- **Siblings**: `content_analyzer._classify_genre_rule_based` handles the axis correctly (`axis=1`).
- **Suggested Fix**: Accept samples-first like the rest of the engine (mean over `axis=1` when `shape[1] <= 8`), with a test on a stereo array.

#### ENG-D6-13: `KNNGraphBuilder.build_graph` pages with OFFSET over a non-unique `created_at` ordering and wipes the graph before rebuilding
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/knn_graph.py:108,116,166`; `auralis/library/repositories/fingerprint_query_mixin.py:98-114`
- **Status**: NEW
- **Description**: The comment says "cursor pagination", but the loop is `get_all(limit, offset)` ordered by `created_at DESC` only. A background fingerprint queue inserting rows during a long build shifts the offsets (duplicated and skipped tracks), and ties on `created_at` have no secondary key. `clear_all()` runs first, so readers see an empty graph until the build ends.
- **Evidence**: Code only (no probe).
- **Impact**: Incomplete/duplicated edges after a build run during fingerprinting; empty neighbour results during the rebuild.
- **Siblings**: `normalizer.fit` uses the same offset loop.
- **Suggested Fix**: Add a unique tie-breaker (`id`) to the ordering and use keyset pagination; build into a staging table or delete per batch.

#### ENG-D7-06: Scanner change detection is one-directional (`mtime <= watermark`) and never uses the file size it stores
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/batch_processor.py:128-131`; `auralis/library/migrations/migration_v021_to_v022.sql:15-17` (comment)
- **Status**: NEW
- **Description**: A file is skipped when its mtime is not newer than the stored watermark. A file replaced by one with an older or identical mtime (restore from backup, `rsync -t`, `cp -p`, a swapped-in earlier master) is never re-read. The migration comment says the scanner "now also compares [filesize] as a cheap secondary signal", but `filesize` is only written (`track_info.setdefault('filesize', ...)`), never compared.
- **Evidence**: Code: only `Path(file_path).stat().st_mtime <= scanner_watermark` gates the skip.
- **Impact**: Stale duration, sample rate, tags (and, per ENG-D7-04, fingerprint) for replaced files.
- **Siblings**: none.
- **Suggested Fix**: Skip only when `mtime == watermark` and `st_size == existing_track.filesize`; otherwise re-read.

#### ENG-D7-07: Files whose names are not valid UTF-8 fail at the first DB bind and never enter the library
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/file_discovery.py:139-170` (yields `os.fsdecode`d paths with surrogate escapes); first DB use `scanner/batch_processor.py:~100` (`get_by_path`) and `track_repository_lifecycle.py` (`add`)
- **Status**: NEW
- **Description**: On Linux a latin-1 / mis-charset filename decodes to a `str` with lone surrogates (`\udce9`). `soundfile`/mutagen open it fine, but binding it to SQLite raises `UnicodeEncodeError`.
- **Evidence**: Probe `p10.py`: 3 files (accented, CJK, latin-1 byte name) -> `2 added, 1 failed`, reason `'utf-8' codec can't encode character '\udce9' ... surrogates not allowed`.
- **Impact**: Those tracks are silently unreachable (they are reported as failures with an opaque message); same for any later API that round-trips the path through JSON.
- **Siblings**: `Track.filepath` consumers that JSON-encode paths.
- **Suggested Fix**: Detect surrogate-escaped names during discovery and either skip them with a clear failure reason, or store a lossless encoding (`os.fsencode(...).decode('utf-8','backslashreplace')` key) alongside the real path.

#### ENG-D7-08: Pre-migration backups are full DB copies in the data directory and are never pruned
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/migration_backup.py:27-77`; `auralis/library/migration_manager.py:296-306`
- **Status**: NEW
- **Description**: Each migration run writes `library.backup_<timestamp>.db` next to the DB and nothing ever deletes old ones. A failed backup aborts the migration and therefore the app start (`LibraryDatabase` raises `MigrationError`), so a full disk caused by accumulated backups blocks the next upgrade.
- **Evidence**: `~/.auralis` on the dev machine holds 465 `library.backup_*.db` files, 9.2 GB (22 MB each for the current DB; many are one second apart, consistent with test runs booting against the real library, see the known test-isolation hazard).
- **Impact**: Unbounded disk growth that scales with library size times migrations; the dev-machine count is inflated by test churn but production has no cap either.
- **Siblings**: none.
- **Suggested Fix**: Keep the newest N (e.g. 3) backups, delete older ones after a successful migration; make tests point `HOME` at a temp dir.

#### ENG-D7-09: Artwork and fingerprint cache directories are hard-coded to `~/.auralis` regardless of `database_path`
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/album_repository.py:83`; `auralis/analysis/fingerprint/fingerprint_storage.py:40`
- **Status**: NEW
- **Description**: `LibraryDatabase(database_path=...)` relocates the DB but `AlbumRepository` and `FingerprintStorage` still write to the real home directory. Album ids are per-database, so artwork named `album_<id>_<hash>` from different databases mixes in one directory, and nothing removes artwork when its album disappears (no album delete path exists).
- **Evidence**: `ls ~/.auralis/artwork | wc -l` = 8,933 files (1.9 GB) for 4,075 distinct album ids, while the live DB currently has 0 albums.
- **Impact**: Disk bloat, cross-library artwork collisions, and test/alt-library runs polluting the real profile.
- **Siblings**: `ENG-D7-08`'s test-isolation cause.
- **Suggested Fix**: Derive both directories from the database's parent directory (or inject them) and have the orphan sweep from #5596 also delete the album's artwork file.

#### ENG-D7-11: `get_reference_cloud()` and `get_by_dimension_range()` skip `_current_fingerprint_clause()`
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_similarity_mixin.py:42-54`, `:142-183`
- **Status**: NEW
- **Description**: #4822 made every other fingerprint read exclude claim placeholders (`lufs == -100`) and stale-algorithm rows; the docstring of `get_by_multi_dimension_range` says "same as every other read". These two do not. A reference-flagged row that is mid-re-extraction (`fingerprint_version = 0` claim) or outdated is returned to the target derivation. `get_by_dimension_range` also accepts any attribute name via `hasattr(TrackFingerprint, dimension)` (relationships, methods).
- **Evidence**: Code only.
- **Impact**: Mixed-version points in the reference manifold for the window between an algorithm bump and the next `refresh_cloud`; currently no caller of `get_by_dimension_range`.
- **Siblings**: `fingerprint_query_mixin.get_count` counts every row (placeholders included).
- **Suggested Fix**: Add the clause to both reads and validate `dimension` against `_FINGERPRINT_WRITABLE_COLS`.

#### ENG-D7-12: Fresh installs (`create_all`) and migrated databases still differ in ways raw SQL and ordering notice
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/models/base.py:66-69`, `models/track.py` (`filepath_key`, ids), `repositories/fingerprint_upsert_mixin.py:94-102`; `auralis/library/migrations/migration_v017_to_v018.sql`
- **Status**: NEW (sibling of fixed #5530/#5321)
- **Description**: Probe `p2.py` diffs. (1) `track_fingerprints.created_at/updated_at` have no server default on fresh installs, so the raw `INSERT ... ON CONFLICT` upserts leave them NULL (verified: `(None, None, None)`), while `get_all()`/`get_all_with_track_stats()` order by `created_at DESC` and the reference seeder relies on that to take "the most recent slice" (`reference_seeder.py:211`); see also ENG-D6-13. (2) `ix_tracks_filepath_key` is UNIQUE on fresh installs, plain on migrated ones. (3) Migrated tables use `AUTOINCREMENT`, fresh ones reuse rowids, so ids of deleted tail rows are reissued (caches keyed on `/api/albums/{id}/artwork` or track id can then show another item). (4) `tracks.fingerprint_hash` exists only on migrated DBs.
- **Evidence**: `p2.py` output; `p6.py` `select created_at, updated_at` on a fresh DB.
- **Impact**: Behaviour depends on how the DB was born; ordering by `created_at` is degenerate on fresh installs.
- **Siblings**: ENG-D7-03 is the worst case of the same class.
- **Suggested Fix**: Give `created_at`/`updated_at` `server_default=func.current_timestamp()` (or set them in the raw INSERT), and add a test that diffs migrated vs `create_all` schemas.

#### ENG-D7-13: `GenreRepository.get_tracks_by_genre()` does not eager-load `Track.genres` (dead method, latent #4500 regression)
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/genre_repository.py:126-170`
- **Status**: NEW
- **Description**: Uses its own `joinedload(Track.album), joinedload(Track.artists)` instead of `_track_eager_options()`; the expunged tracks then report `genres: []` via `_safe_collection` plus a WARNING.
- **Evidence**: Probe `p7.py` over ~40 read paths: only `g.tracks` warned (`Track.genres could not be loaded`). The method has no production caller.
- **Impact**: None today; wrong output the moment a route uses it.
- **Siblings**: `_ARTIST_DETAIL_OPTIONS` also omits `Track.artists` (not reported by any current serializer).
- **Suggested Fix**: Use `_track_eager_options(collections_via_selectin=True)` or delete the method.

#### ENG-D7-14: Scanner computes and the schema carries data nothing uses
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/audio_analyzer.py:88-130`, `scan_models.py:88`; `models/track.py` (`bitrate`, `bit_depth`, `peak_level`, `rms_level`, `lufs_level`, `fingerprint_status`, `fingerprint_computed_at`, `fingerprint_error_message`, `fingerprint_vector`, indexes `idx_tracks_fingerprint_*`); `models/statistics.py` (`LibraryStats`)
- **Status**: NEW
- **Description**: `file_hash` is computed for every file (two extra reads) but never persisted or read. The scanner never fills `bitrate`/`bit_depth`/level columns, so they are always NULL. `update_status()` has no production caller, so `fingerprint_status` is always `'pending'` and `computed_at/error_message/vector` are never written, yet three indexes on them are maintained on every track write. `LibraryStats` is not used (StatsRepository computes live).
- **Evidence**: grep for `file_hash`, `update_status(`, `fingerprint_vector` outside definitions: none.
- **Impact**: Wasted I/O on network shares, write amplification, misleading API fields.
- **Siblings**: none.
- **Suggested Fix**: Drop the hash, populate or remove the columns, and drop the dead indexes in a migration.

#### ENG-D7-15: `AdaptiveResourceMonitor` invokes its callbacks while holding its own lock
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/resource_monitor.py:116-190` (callbacks at `:154`, `:184`); consumers `auralis/services/fingerprint_queue_scaling.py:119-160`
- **Status**: NEW
- **Description**: `on_worker_count_change` / `on_semaphore_change` run inside `with self._lock`. They take `stats_lock` and `ResizableSemaphore`'s internal lock, so the order is monitor lock -> consumer locks. I found no reverse nesting (`stop_resource_monitor` calls `get_stats()` outside `stats_lock`), so there is no live deadlock; it is a latent lock-ordering hazard by construction.
- **Evidence**: Code and grep of both callers.
- **Impact**: None now; a future consumer calling `get_stats()` under its own lock deadlocks the monitor thread.
- **Siblings**: none.
- **Suggested Fix**: Compute under the lock, collect the callbacks, invoke them after releasing it.

#### ENG-D7-16: `FileDiscovery.should_skip_path` rejects every file when the scan root sits under a hidden directory
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/file_discovery.py:185-209`
- **Status**: Existing: #5594
- **Description**: Still true (probe: `/home/u/.local/share/music/a.flac` -> skipped).
- **Evidence**: `should_skip_path(Path('/home/u/.local/share/music/a.flac')) == True`.
- **Impact**: Empty scans for such roots.
- **Siblings**: none.
- **Suggested Fix**: See #5594.

#### ENG-D7-17: `TrackRepository.add()` mis-assigns albums for artist-less tracks; album race guard cannot fire
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_lifecycle.py:102-117`
- **Status**: Existing: #5595
- **Description**: Still true (probe `p5.py`: an artist-less track tagged album "Al" attached to the other artist's album 1). `max_concurrent_scans` defaults to 4 in `UserSettings`, so the duplicate-album race is reachable.
- **Evidence**: `p5.py` output `artistless track album_id 1 same as owned album? True`.
- **Impact**: See #5595.
- **Siblings**: `_assign_album` in the mutation mixin.
- **Suggested Fix**: See #5595.

#### ENG-D7-18: No orphan sweep for albums, artists and genres
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/album_repository.py`, `artist_repository.py`, `genre_repository.py`, `track_deletion.py`
- **Status**: Existing: #5596
- **Description**: Still true; `delete_tracks_by_ids` removes association rows only. Now also fed by ENG-D7-02 (failed ingests create orphans) and ENG-D7-09 (artwork files orphaned).
- **Evidence**: No prune method in the three repositories.
- **Impact**: See #5596.
- **Siblings**: ENG-D7-02, ENG-D7-09.
- **Suggested Fix**: See #5596.

#### ENG-D7-19: `MigrationManager.get_current_version()` maps any exception to version 0
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/migration_manager.py:97-101`
- **Status**: Existing: #5597
- **Description**: Unchanged (`except Exception: return 0` -> `initialize_fresh_database()`).
- **Evidence**: Code.
- **Impact**: See #5597.
- **Siblings**: none.
- **Suggested Fix**: See #5597.

## Merged duplicates

| Kept | Absorbed | Note |
|---|---|---|
| ENG-D2-01 | ENG-D1-01 | Same offline-CLI clipping; the two probes put the threshold at -2.5 and about -4 dBFS source peak. |
| ENG-D2-04 | ENG-D1-02 | Same whole-chunk peak clamp. |
| ENG-D1-03 | ENG-D2-08 | Same limiter attack step. Dimension 1 rated it MEDIUM, Dimension 2 LOW; MEDIUM kept because the limiter is the real peak control in reference/hybrid jobs and the CLI maximizer. |
| ENG-D4-02 | ENG-D5-04 | Same `except _sf.error`. Dimension 4 rated it MEDIUM, Dimension 5 LOW; MEDIUM kept because it is a regression shipped by a fix and it also leaks the temp dir. |
| ENG-D5-03 | ENG-D2-12 | Same unguarded `sosfiltfilt` family (#5116); both file lists are in the kept finding. |
| ENG-D2-09 | ENG-D7-10 | Same cached/empty reference cloud and its non-atomic refresh. |

## Relationships

- **Level-chain cluster** — ENG-D2-01, ENG-D2-04, ENG-D1-03, ENG-D1-04 (#5558) and ENG-D2-03 are one problem seen at different stages: gain is decided from a local peak or a mis-scaled loudness, and nothing owns a track-level ceiling. The whole-chunk clamp (ENG-D2-04) pulls one chunk down, the level manager then boosts its neighbour past the ceiling (ENG-D1-04), and a one-sample limiter attack (ENG-D1-03) makes every limited peak audible. Fix them against one design: a track-level gain cap plus a smoothed limiter, not three local patches.
- **`except _sf.error`** (ENG-D4-02) sits in the same block as the temp-dir placement that ENG-D4-11 and ENG-D5-07 describe; fix them together.
- **Fingerprint trust chain** — ENG-D6-01 → ENG-D7-04 → ENG-D7-03 → ENG-D6-05/06 → ENG-D2-05: wrong or stale rows are kept (D6-01, D7-04), some databases cannot read them at all (D7-03), the prefilter then picks arbitrary candidates (D6-05), and the normalizer fits on the wrong row set (D6-06). The reference cloud used for the soft k-NN targets (ENG-D2-05, ENG-D2-09) reads the same rows.
- **Destructive-action pair** — ENG-D5-01 and ENG-D7-01 share a cause: no check that the thing being deleted is what the code thinks it is. ENG-D7-18 (no orphan sweep) and ENG-D7-02 (orphans created by failed adds) are the opposite pressure on the same tables.
- **FFmpeg decode family** — ENG-D4-04 (4 GiB truncation), ENG-D4-07, ENG-D4-08, ENG-D4-10, ENG-D4-11, ENG-D5-07 and ENG-D6-03 all come from the FFmpeg intermediate WAV and how callers reach it.
- **Dormant real-time path** — ENG-D1-05, ENG-D3-02, ENG-D3-03, ENG-D3-04 and ENG-D3-11 live in `AudioPlayer.get_audio_chunk` and the real-time chain. Deleting the unused path closes them at once; fixing them one by one is wasted effort if the path stays unused.
- **Queue shape** — ENG-D3-05 (#5563), ENG-D3-06 (#5564) and ENG-D3-09 share the cause the 2026-10-16 report described: queue entries have no stable shape.

## Prioritized Fix Order

1. **ENG-D5-01** — refuse `-o` equal to, inside, or an ancestor of the input folder, and never `rmtree` a folder the tool did not create. Small change, prevents data loss.
2. **ENG-D7-01** — in `cleanup_missing_files()` require the parent directory to be readable and non-empty/mounted before treating a missing file as deleted; soft-delete or ask before removing playlist rows and favourites.
3. **ENG-D2-01** — cap the CLI's file-level gain by the processed peak (or run a final true-peak limiter) and add the -10 dBFS-peak regression test the finding names.
4. **ENG-D6-01** — version or drop the central `.25d` cache so `upsert()` cannot stamp old values current; recompute the 3206 existing files.
5. **ENG-D2-02** — calibrate the fixed-target "ideal" band shares so the EQ is content-dependent again; ENG-D2-03 and ENG-D2-05 touch the same target derivation, do them in one pass.
6. **ENG-D4-02** — replace `_sf.error` with the real exception type (`sf.LibsndfileError` / `RuntimeError`), and clean the temp dir on failure. Regression shipped today.
7. **ENG-D7-03 and ENG-D7-04** — add the missing `fingerprint_blob` migration and invalidate a track's fingerprint when its file changes.
8. **Level chain** — ENG-D2-04, ENG-D1-04 (#5558), ENG-D1-03 together, as described under Relationships.
9. **ENG-D4-01** — make stream start report the channel count of the audio actually sent.
10. **ENG-D3-01, ENG-D7-02, ENG-D7-05, ENG-D6-02, ENG-D6-05, ENG-D6-06, ENG-D2-06, ENG-D2-07, ENG-D4-03** — the remaining MEDIUM items, each independent.
11. **Decision, not a fix**: delete or wire up the dormant real-time output path, and the Rust `process_chunks` (ENG-D5-06), which is dead code that returns silence or aborts.
12. LOW findings in batches by file; the Existing ones are already tracked.

## Appendix: Verified Correct and Tracker Notes

Sections the dimension agents recorded after their findings: what was checked and held, and notes about existing issues. They are not findings.

**Dimension 3**

##### Existing / stale-tracker notes (not new findings)
- **#5565** (prebuffer match treats two missing ids as equal) is OPEN but already fixed in code by `_entries_match()` (`gapless_playback_engine.py:441-454`, #5583 commit `99ee1809`): ids compared only when non-None, path branch requires non-None on both sides. It can be closed after a regression test confirms.
- **#5686** (duplicate `get_track_count`/`get_queue_size`) still true at `queue_controller.py:362-368`.
- **#5460** (queue edits never update `PlayerStateManager.state`) is backend-side; not re-examined here.
- `NavigationService.jump_to_track` calling a non-existent `set_current_index` is recorded in AUDIT_CONCURRENCY_2026-09-13 and has no router caller; not re-filed.

##### Verified correct (no finding)
Lock ordering and callback dispatch (all notifications are queued by `defer_notifications()` or fired after the lock is released); position clamp on seek/steady state/last chunk; `play()`/`stop()`/`pause()` flag ordering; `advance_with_prebuffer` peek-load-commit retry and `advance_if_next_matches` atomicity; `cleanup()` ordering and thread joins; `remove_*`, `insert_track`, `reorder_tracks`, `move_track` index maintenance; `set_queue`/`load_playlist` atomicity; fingerprint generation/staleness guard.

**Dimension 6**

##### Verified OK / no finding
- **Fixed since 2026-10-16**: order='F' interleave (`prepare_rust_audio`, #5556), band-floor level dependence and transient_density/bass_mid_ratio scope (8bd83648: pink noise bands identical across 30 dB; transient_density 0 for pure sines, 0.23/0.45/0.77 for 2/4/8 kicks per second, independent of level), quantizer bounds (f97ca622), mono/>2-channel K-weighting (e2249990).
- **Determinism**: two successive `compute_fingerprint_schema` runs are equal; the genre-weight init is seeded; Rust path has no RNG.
- **Resource bounds**: windowed fingerprint is bounded on all three branches; the only unbounded decode is ENG-D6-03. `QualityMetrics` is only fed 8 s windows or processing chunks.
- **ML lifecycle / threading**: classifier built once (`lru_cache`), `LoudnessMeter` created per call where shared, `FingerprintNormalizer.fit` publishes atomically (#5243). KeyboardInterrupt: `windowed_compute` / analyzer catch `Exception` only.
- **Existing**: K-weighting filter vs BS.1770 RLB is Existing #5593 (LOW); `FingerprintQuantizer` docstring Existing #5538.

## Coverage Notes

These are the dimension agents' own notes. Finding IDs in them that are not marked "below" (for example the lists of fixes verified since 2026-10-16) use the numbering of the 2026-10-16 report, not this one. References to ENG-D1-01, -02, -03, ENG-D2-08, ENG-D5-04 and ENG-D2-12 point to findings merged under the kept IDs in "Merged duplicates".

**Dimension 1 — Sample Integrity**: Traced HybridProcessor -> ContinuousMode (all 5 stages, fixed-target and per-chunk paths), BrickWallLimiter, EQ/WOLA, stereo width, LevelManager, backend chunk load/render/extract/encode/wire path, saver/loader boundaries, reference/hybrid job modes, realtime chain, and the offline CLI chunk loop; probed mono (N,1), 3/6-channel, 8 kHz-192 kHz, float64, read-only/F-ordered inputs, NaN/1e30 poisoning, odd chunk lengths (sample count and dtype held everywhere; the #5550/#5551/#5552/#5575 fixes verified live). Also re-checked fresh fixes landed 2026-10-17..20 for new defects (that is where findings 01-03 come from). Not covered: Rust DSP internals, analysis/fingerprint numerics, player gapless/queue logic, library/DB (other dimensions); I/O decode correctness beyond the sample-integrity boundary.

**Dimension 2 — DSP Pipeline**: **Coverage.** Read the live chain end to end: `HybridProcessor` -> `ContinuousMode` (+ `continuous_stages/_dsp_ops/_guards`, `fixed_target_params`, `parameter_generator*`, `continuous_space`, `delta_eq`, `target_derivation`, `album_target`), `EQProcessor` + `PsychoacousticEQ` (WOLA, masking, band map), `BrickWallLimiter`, `stage_snapshot`, the backend `mastering_target_service` that feeds the fixed-target path, plus `AdaptiveMode`/`HybridMode`/`reference_mode`, the offline CLI chain (`mastering_process_chunk`, `mastering_branches/continuous`, `mastering_chunk_loop`, 13 `stages/`, `core/dsp/`) and the Rust PyO3 boundary (`py_bindings.rs`: every wrapper uses `py.detach` + `catch_unwind`; only `compute_fingerprint` has a production Python caller). Probes ran on synthetic audio and on ~15-30 s excerpts of the user's `~/Music` stems (read-only). Not covered in depth: `auralis/analysis/*` fingerprint internals (Dim 6), the backend `LevelManager` (backend audit), `core/analysis/spectrum_mapper` and `target_generator` (only reached by the hybrid/legacy `AdaptiveMode`). **Fixes since 2026-10-16 verified in live code (not re-reported):** ENG-D2-01 (#5552, `source_lufs` constant gain; residual in ENG-D2-04 below), -02 (#5553, `WIDTH_FACTOR_UNITY`), -05 (#5560, wired; follow-ups in ENG-D2-05/-09 below), -06 (#5561, stage removed), -07 (#5562, direction fixed; step remains, ENG-D2-08), -09 (#5577), -10 (#5578, `smooth_gate` ramp), -11 (#5579), -13 (#5580), D1-06 (#5575). ENG-D2-03 (#5554) is only partly fixed: see ENG-D2-02. **Optimizer wrapper truth (needed to correct the skill text).** The claim "wraps `AdaptiveMode.process` and sits on every real mastering call" is FALSE. `HybridProcessor._process_adaptive_mode` (`hybrid_processor.py:240-257`) calls `ContinuousMode.process` whenever `config.use_continuous_space` is true, which is the default and the only value the app sets (`unified_config.py:88`). The wrapped method `AdaptiveMode.process` is reached only by (a) `HybridMode.process` (`hybrid_mode.py:68,101`), i.e. processing jobs submitted with `mode="hybrid"` (`job_config.py:64`), and (b) the `use_continuous_space=False` branch (`hybrid_processor.py:261`). Streaming/chunked playback, default adaptive jobs and `reference` mode (`apply_reference_matching`, a pure RMS gain) never touch it. What `apply_module_optimizations()` installs after #5325 is a profiling-only `time_function` decorator (`hybrid_setup.py:150-185`). Audited where live: it preserves the return value, exceptions (`try/finally`) and sample count, uses `functools.wraps`, records under an `RLock`, is idempotent via `AdaptiveMode._optimized`, and the singleton uses a double-checked lock. No correctness defect. `SmartCache`/`MemoryPool` are constructed but have no production apply-point (only `get_optimization_stats()` reports them; its only caller is `HybridProcessor.get_performance_stats`, which nothing in the backend calls). Suggested skill wording: "a profiling-only decorator on `AdaptiveMode.process`, which is live only for hybrid-mode jobs and the legacy `use_continuous_space=False` path; the `PerformanceOptimizer` singleton itself is constructed by every `HybridProcessor` but is statistics-only".

**Dimension 3 — Player State**: Read in full: every file under `auralis/player/` (AudioPlayer + its six mixins, PlaybackController, QueueController, QueueManager, GaplessPlaybackEngine, AudioFileManager, IntegrationManager, `realtime/`), the backend call sites that drive the engine (`navigation_service`, `queue_set_mixin`, `queue_edit_mixin`, `playback_service`), and the 2026-10-16 report's D3 findings. Lock graph traced (U=`update_lock`, A=`_audio_lock`, P=`PlaybackController._lock`, Q=`QueueManager._lock`, L=`_position_lock`): the only nestings are U->A->P, A->P, A->Q, L->A; no inversion or callback-under-lock found. Seven probes (scratch dir, HOME isolated, deleted afterwards) confirmed the MEDIUM findings. **Fixed since 2026-10-16 (verified in live code, not re-reported)**: D3-04 (#5581 swap+reset in one section), D3-05 (#5582 CAS, but see ENG-D3-01), D3-06 (#5583 re-arm), D3-07 (#5584 end-of-queue stop), D3-08 (#5585), D3-09 (#5586), D3-10 (#5587), D3-11 (#5588). Still true: D3-01/02/03 (open #5563/#5564/#5565, listed below). Not checked: audio-device output (none exists in production: `get_audio_chunk` has no caller outside `tests/`, which lowers the real-world reach of the real-time findings and is stated per finding).

**Dimension 4 — Audio I/O**: Read all of `auralis/io/` (unified_loader, loader, loaders/ffmpeg_loader + soundfile_loader, processing, saver, results, formats) and traced every engine/backend consumer: scanner `audio_analyzer` + `metadata_extractor`, `simple_mastering` pre-transcode, `windowed_compute`/`mastering_fingerprint`, player `audio_file_manager`, backend `chunk_metadata`/`seekable_source`/`chunk_operations`/stream-start. Runtime probes on 1-3 s synthetic clips (all 7 formats, 3/4/5/6/8-channel WAV, truncated FLAC, garbage mp3/m4a, tags in mp3/m4a/ogg/opus/flac); scratch deleted. **Verified fixed since 2026-10-16** (not re-reported): ENG-D4-01 stderr UnicodeDecodeError (#5555), D4-05 `loader.load()` validation (#5589), D4-06 ffprobe `-v quiet` (#5590), D4-07 validate_audio temporary (#5591). Still open and still true: #5566, #5567, #5568 (listed briefly below). Not covered: the Rust DSP, the frontend worklet beyond the one channel-count check, Windows/macOS ffmpeg behaviour.

**Dimension 5 — Chunked Mastering**: Read the whole offline chunk path (`mastering_chunk_loop.py`, `mastering_process_chunk.py`, `mastering_prepare.py`, `mastering_notch_context.py`, `simple_mastering.py`, `mastering_config.py`, `mastering_branches/continuous.py`, `stages/loudness_maximizer.py`) and the Rust `process_chunks` binding. Probed on synthetic 100 s stereo (normal, hot/clipped, quiet, drum bursts straddling boundaries): chunked `master_file` output vs the same pipeline run whole-file. The residual is -90 to -130 dB everywhere, the seam region included, with no level step, so there is no seam-discontinuity finding. Final chunks of 20 ms to 2 s also match the whole-file render to -40 dB or better. Reassembly order, sample count, last-chunk handling, partial-failure staging, mono and 6-channel input, and the Rust `process_chunks` edge cases were probed live. **Not covered**: the backend concurrent chunk processor (`/audit-backend`), and the offline CLI clipping, `BrickWallLimiter` attack, `LevelManager` and per-chunk peak clamp (Dimension 1; ENG-D1-01 already covers the new source-peak `file_gain` and true-peak gain). Verified-fixed since the 2026-10-16 report and not re-reported: #4970 (constant true-peak gain), #5339 (ratio guard exists, see ENG-D5-05), #5569 (pre-downmix works end to end, see ENG-D5-04), #5512 (stage merge), #5511/#5533. Probe artifacts were removed. The shared tmpfs hit its quota during the run (other agents' files); my large files were deleted at once.

**Dimension 6 — Analysis**: Re-verified the 2026-10-16 Dim 6 items against live code (D6-01 order='F' is fixed by 99ea1d83/`prepare_rust_audio`, D6-02/-03 band floor and transient_density fixed by 8bd83648 with `FINGERPRINT_ALGORITHM_VERSION` 10, D6-04 quantizer bounds fixed by f97ca622; D6-05 K-weighting is Existing #5593). Probed the Rust fingerprint after the rebuild, then read the fingerprint cache and similarity stack, the `quality/` assessors and `quality_assessors/` constants, `dynamic_range.py`, `loudness_meter.py`, `phase_correlation.py`, `spectrum_operations.py`, `mastering_fingerprint.py` and `ml/`, with probes on synthetic audio. **Not covered**: `adaptive_mastering_engine.py` and `mastering_profile.py` internals beyond a skim, `rhythm.rs`/`variation_analysis.rs`/`spectral_features.rs` numerics (only black-box probes), and fingerprint queue/worker concurrency (belongs to the services/library dimension).

**Dimension 7 — Library & Database**: Read all of `auralis/library/` (database, base/track/playlist/fingerprint/scheduler/stats/settings/genre/album/artist repositories, scanner package, models, migrations + manager/steps/lock/backup, sidecar_manager, resource_monitor, artist_normalizer) plus the backend prune/scan/reset callers. Ran 11 runtime probes (temp-file SQLite, scratch HOME, real `~/.auralis` untouched): fresh-vs-migrated schema diff, delete/cascade/prune, savepoint atomicity, EACCES prune, pagination stability, detached-instance sweep over ~40 read paths, non-UTF-8 filenames, artist parsing. **Verified fixed since 2026-10-16 (not re-reported)**: bulk-delete FK failure (a8a0897d, `track_deletion.py`), fingerprint_version stamping (c340250e), playlist position contiguity (1cb22f1c), scanner `file_mtime` watermark (c1e600d0), queue-history `DetachedInstanceError` (feature retired). Dropped as disproved: unstable LIMIT/OFFSET ties (stable in practice, 3000-row probe), genre dedup in association rows, LUFS -100 sentinel collision (Rust clamps at -120). Cross-dim: stale `.25d` cache promoted to current by `upsert()` is ENG-D6-01; undecodable-file ingest and M4A tags are ENG-D4-05/-06; not repeated here.
