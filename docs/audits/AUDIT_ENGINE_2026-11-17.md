# Audio Engine Audit - 2026-11-17

Fresh audit of the current tree (`auralis/`, `vendor/auralis-dsp/`), run by `/audit-engine` as part of the comprehensive suite. Seven dimension agents, depth `deep`, no `--limit`. Dedup baseline: all 6090 GitHub issues (highest #6346, verified not truncated). No prior report was read or reused.

## Executive Summary

| Severity | NEW | Existing (open issue) | Total |
|----------|-----|-----------------------|-------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 16 | 3 | 19 |
| LOW | 31 | 3 | 34 |
| **Total** | **47** | **6** | **53** |

One cross-dimension duplicate (D3-08, the gapless zero-pad, same as D1-05 / #6109) was removed in the merge. No regressions of closed issues were found: every checklist fix pinned by a closed issue (#5731, #5734, #5739, #6315, #6316, #6318, #5701, #5721, #5694, #6127, #6336 and others) was re-verified in place, and the pinned regression test files pass. Sample count, copy-before-modify, dtype, clip ceilings, chunk-seam continuity (whole vs chunked render differ by at most 6e-6), migrations, scan coordination and detached-instance handling all held up.

### Key themes

1. **Unbounded gain on near-silent input.** Hybrid mode (D1-01) and the offline `file_gain` (D5-03) have no floor and lift a noise-floor file to near full scale. The adaptive path already has the floor; these are siblings of closed #5551.
2. **Fingerprint measurement fidelity.** The Rust engine accumulates whole-track sums in f32 (D6-01), measures centroid/rolloff over one whole-track window (D6-02), and measures `lufs` on the mono sum (D1-03). Fixes need a `FINGERPRINT_ALGORITHM_VERSION` bump to 17. The `fingerprint_preloaded` path skips the memory gate (D6-03).
3. **Analysis scope vs mastering scope.** The offline loudness maximizer is driven by a 30 s middle window (D5-01), the same design class as closed #6341 and open #6346.
4. **Audio I/O container edge cases.** WAV past 4 GiB written as plain RIFF (D4-01), FLAC with total_samples=0 refused (D4-02), RIFF size placeholders rejected (D4-03), decoder overshoot hard-clipped on the FFmpeg route only (D4-04).
5. **Library data integrity.** A rescan/retag that creates a new album loses artwork (D7-01), a deleted album folder leaves ghost rows forever (D7-02), and combining-mark stripping merges distinct non-Latin artists (D7-03).
6. **Dormant realtime path.** `AudioPlayer.get_audio_chunk` and the realtime chain have no production caller (open #5708), so player-state and realtime findings (D1-02, D2-02, D3-x) are rated at dormant weight.

### Most impactful

D1-01 / D5-03 (noise lifted to full scale), D1-03 (wrong master gain for out-of-phase stereo, up to -24 dB / +24 dB), D6-01 + D6-02 (systematically wrong fingerprint dimensions on real tracks), D7-01 and D7-02 (user-visible library damage), D4-01 (silently unreadable >4 GiB output).


## CRITICAL Findings
None.

## HIGH Findings
None.

## MEDIUM Findings
### D1-01: Hybrid mode peak-normalises with unbounded gain, so a noise-floor file is mastered to full-scale noise
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/hybrid_mode.py:109-110`, `auralis/dsp/basic.py:22-43`; offline sibling `auralis/core/mastering_branches/continuous.py:263-285`
- **Status**: NEW
- **Description**: `HybridMode._apply_hybrid_processing` ends with `normalize(blended_audio, 0.9886)`. `normalize()` scales to the target peak
  for any `peak > 0` with no gain cap and no silence floor. `validate_and_normalize_input` only short-circuits exact digital silence
  (`np.allclose(..., atol=1e-10)`), so a file that holds only dither / room noise reaches this line. The continuous path was given a floor and
  a cap for exactly this class (#5551: `SILENCE_FLOOR_LUFS`, `MAX_NORMALIZATION_GAIN_DB = 24`) and `PeakNormalizer.normalize_to_target` has
  a `peak > 0.001` guard; hybrid mode (still reachable: `POST /api/processing` accepts `mode: "hybrid"` with a reference, `job_execution.py`)
  bypassed both. The offline CLI has the same shape: `file_gain = adapted_peak / song_peak_linear` in `ContinuousMasteringBranch.apply` is uncapped
  (`song_peak_db` is floored at -96 dB only for exact zeros).
- **Evidence**: Measured on `HybridProcessor(mode=...)`, 3 s of Gaussian noise, reference = 0.3 RMS noise:
  `noise peak -46 dBFS: adaptive -46.2 dBFS | hybrid -0.3 dBFS (rms 0.23) | reference -25.9 dBFS`;
  `-86 dBFS: adaptive -86.4 | hybrid -0.3 dBFS (rms 0.21) | reference -66.4`; `-126 dBFS: adaptive -126.1 | hybrid -0.3 dBFS (rms 0.21)`.
  Offline: `SimpleMasteringPipeline.master_file` on a 15 s file peaking at -86 dBFS wrote a master peaking at -0.5 dBFS / -14.2 dBFS RMS (+86 dB); -45 dBFS in -> -0.5 dBFS out.
- **Impact**: A near-silent or dither-only input (a "silent" bonus track, a failed rip, a track with only a noise floor) is turned into loud full-scale noise
  in a REST job with no warning. Offline CLI is lower weight (auto_master tool only).
- **Suggested Fix**: Route the hybrid blend through the shared bounded path (the `SILENCE_FLOOR_LUFS` / `MAX_NORMALIZATION_GAIN_DB` logic of
  `_normalize_chunk_loudness`, or `PeakNormalizer.normalize_to_target`'s `peak > 0.001` guard) instead of a raw `normalize()`; cap `file_gain` in the offline branch the same way.

### D1-02: One Inf sample permanently poisons the realtime `AdaptiveCompressor`, and nothing ever resets it
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/dynamics/compressor.py:103-135`, `auralis/dsp/dynamics/envelope.py:25-39,85-93`, `auralis/player/realtime/auto_master.py:51,95,180`
- **Status**: NEW (residual of the #5313 class; #5313 is CLOSED and only added the output repair)
- **Description**: `AdaptiveCompressor.process` converts the per-sample peak to dB and feeds `-gain_reduction` to the stateful `EnvelopeFollower`. A NaN
  sample is harmless (the `>=` / `>` masks are False, so gain reduction stays 0), but an `+/-Inf` sample gives `gain_reduction = -inf`; the follower evaluates
  `input + (env - input) * coeff` = `inf - inf` = NaN, stores it in `self.envelope = float(output[-1])`, and `input > NaN` is False so every later call
  returns NaN. `StreamingPeakCeiling` deliberately ignores non-finite samples ("Non-finite samples do not drive the gain"); the compressor in front of it has no such
  guard. The state is never cleared: `AdaptiveCompressor.reset()` has no caller, `AutoMasterProcessor` never calls it on track load / seek / `clear_fingerprint`,
  and `RealtimeProcessor.reset_all_effects` only disables auto-master. Only a sample-rate change (which rebuilds the compressor) recovers it.
- **Evidence**: `RealtimeProcessor` with auto-mastering enabled, 1024-sample float32 stereo chunks of 0.3 RMS noise: clean chunks fine (peak <= 0.95);
  one chunk with `c[100,0] = np.inf` -> output finite only because `validate_audio_finite(repair=True)` zeroed it; then three clean chunks:
  `after inf 0..2: finite True, peak 0.0, zero fraction 1.0, compressor envelope = nan`. Control: the same with a NaN sample recovers on the next chunk.
- **Impact**: Permanent silence from the auto-master chain until app restart or a sample-rate change, from a single non-finite sample. Practically mitigated:
  `io/processing.validate_audio` sanitises every decode, so Inf has to arise inside the chain; hence MEDIUM rather than HIGH. It is a defence-in-depth gap with a
  severe, unrecoverable failure mode, and the same file already contains the correct pattern (`peak_ceiling.py`).
- **Suggested Fix**: Mask non-finite samples to 0 before the dB conversion in `AdaptiveCompressor.process` (as `StreamingPeakCeiling` does) and/or guard `EnvelopeFollower.process_buffer`
  against a non-finite envelope; call `compressor.reset()` / `peak_ceiling.reset()` from `AutoMasterProcessor.set_fingerprint` / `clear_fingerprint`.

### D1-03: A strongly anti-correlated (out-of-phase) stereo track gets the wrong master gain: the fingerprint loudness is measured on the mono sum
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity (cross-dimension: primary home is Dim 2 / Dim 6, parameter derivation; reported here because it sets the sample gain of the output)
- **Location**: `vendor/auralis-dsp/src/fingerprint_compute.rs:206-223` (lufs on `(L+R)/2`), `auralis/dsp/utils/adaptive.py:90,169-192` (offset clamp +-10 dB), `auralis/core/processing/continuous_mode.py:244-252`, `auralis-web/backend/core/mastering_target_generation.py:99-143` (`plan_level`, correlation clamped to [0, 1])
- **Status**: NEW (related: #5700 OPEN, per-chunk proxy-vs-K scale; #6337 CLOSED, fixed only the peak half of the mono-mix problem; #4123 RMS proxy is intentional)
- **Description**: The 25D `lufs` is an RMS proxy of the mono mix. As inter-channel correlation goes to -1 the mix cancels and `lufs` collapses (to -120 at exact anti-phase) although the K-weighted loudness of the stereo signal is unchanged.
  Both render paths trust it: the whole-file job path (`ContinuousMode._resolve_parameters`) derives `target_lufs` from it and the proxy-to-K correction is clamped to +-10 dB,
  so the final normalisation chases a target near -100 LUFS and attenuates by up to `MAX_NORMALIZATION_GAIN_DB` (24 dB); the streaming path (`plan_level`) sees a -120 LUFS "very quiet"
  track and plans the maximum +24 dB lift, which the limiter then flattens. `channel_peak_offset_db` clamps rho to [0, 1], so negative correlation is treated as uncorrelated.
- **Evidence**: Same loudness material (K-LUFS about -8.5 in), right channel = rho * left + sqrt(1 - rho^2) * independent noise.
  Whole-file path (`HybridProcessor.process`, no fixed targets): rho 1.0 -> +1.8 dB, 0.0 -> +2.2, -0.5 -> +1.1, -0.8 -> **-2.9**, -0.95 -> **-9.3**, -1.0 -> **-23.8 dB** (fingerprint lufs -120, `target_lufs` -101.8).
  Streaming path (`generate_targets_from_fingerprint` -> `set_fixed_mastering_targets`): planned lift 0.9 dB at rho 1.0, 4.9 at -0.5, 8.9 at -0.8, 12.8 at -0.95, **24.0 at -1.0**; at rho -1.0 the crest falls 16.3 -> 8.8 dB (in-phase control: 16.3 -> 12.5) and RMS rises 4 dB.
- **Impact**: A polarity-inverted channel (a real defect in transfers and rips) or heavily out-of-phase material is attenuated by up to 24 dB in a processing job or driven 24 dB into the limiter while streaming. Rare input, but the failure is large in both directions.
- **Suggested Fix**: Measure the fingerprint `lufs` / `crest_db` on a power sum of the channels (or a K-weighted stereo loudness) instead of `(L+R)/2`, or at minimum treat `lufs <= -100` / negative `phase_correlation` as "proxy unusable" and fall back to the measured K-weighted loudness in both `_resolve_parameters` and `plan_level`.

### D1-05: Last chunk is zero-padded to `chunk_size` before auto-advance, so every gapless transition carries up to one buffer of silence
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/player/audio_file_manager.py:147-159`, `auralis/player/player_streaming_mixin.py:100-124`
- **Status**: Existing: #6109
- **Description**: Re-verified present: `get_audio_chunk` pads the final short chunk with `np.zeros` up to `chunk_size`, and `get_audio_chunk` in the streaming mixin spawns the advance thread on the same call, so the next track starts after the padding.
- **Evidence**: `chunk = np.vstack([chunk, padding])` (`audio_file_manager.py:158-159`); default `buffer_size` 1024 = 23 ms at 44.1 kHz, above the 1 ms gapless threshold.
- **Impact**: Audible gap at every auto-advance (tracked).
- **Suggested Fix**: See #6109.

### D2-01: Reference-cloud EQ path (delta_eq) reintroduces an air-band correction and a second band-to-gain law
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline Correctness
- **Location**: `auralis/core/processing/delta_eq.py:138-142`, `auralis/core/processing/parameter_generator_eq.py:130-153` (vs `:45-74`, `:91-99`), `auralis/core/processing/parameter_generator.py:71-75`, `auralis/core/processing/fixed_target_params.py:84-90`
- **Status**: NEW
- **Description**: The checklist invariant is that `eq_curve_from_fingerprint` is the single derivation of the five EQ gains and that the air band yields no correction (`_band_gains` pins `'high_shelf_gain': 0.0` because the 22.05 kHz fingerprint measures air only up to 11 kHz, and on six reference masters air was "the cause of every remaining bench miss", commit `a0a2b6565`). `ContinuousParameterGenerator.generate_parameters` only uses that law when no reference cloud is available. As soon as `_derive_target_spectrum` returns a target (the app registers the fingerprint repository at startup, `config/startup/components.py:52-58`, and `refresh_cloud` seeds `is_reference` rows after every scan/fingerprint-queue drain), the EQ comes from `delta_eq.compute_delta_eq`, a second band-to-gain table: `high_shelf = (presence + air) / 2` (so the air share drives half the high shelf), `low_shelf = (sub_bass + bass) / 2` (the law keys on bass alone), `high_mid = (2*upper_mid + presence) / 3`, with different per-band caps. The streaming path (fixed targets from `mastering_target_generation.py`) uses the first law and always has `eq_blend = 0.7` (`fixed_target_params.py:90`), while whole-file jobs (`job_execution.py` -> `HybridProcessor.process`, no fixed targets) use the second law and a computed `eq_blend` (0.35-0.9), so the same track is toned differently when streamed and when exported.
- **Evidence**: Corpus-median fingerprint with the air share 3x its centre, target = corpus centres:
  `eq_curve_from_fingerprint(src)` -> all five gains 0.00 dB;
  `to_eq_curve(compute_delta_eq(src, tgt))` -> `high_shelf_gain = -0.98 dB` (from air alone), other bands 0.
  Call path: `processing_engine` job -> `HybridProcessor.process` -> `mode_dispatch.process_adaptive_mode` (`current_targets is None`) -> `ContinuousMode._resolve_parameters` -> `_derive_target_spectrum` -> `generate_eq_curve_from_target` -> `delta_eq`.
- **Impact**: Up to about +-1 dB (air share alone: +-2 dB cap x gate x 0.5) of high-shelf EQ that was deliberately removed from the other path, plus different low/high-mid gains; streaming and export of one track disagree tonally whenever the library has a reference cloud. Not a crash or integrity issue.
- **Suggested Fix**: Make `delta_eq` produce only per-band deltas and route the five EQ gains through one function (drop the air share from `high_shelf`, key `low_shelf` on bass), or retire `delta_eq` for EQ gain derivation; at minimum align the fixed-target `eq_blend` with the per-chunk one.

### D3-09: RealtimeLevelMatcher is a per-buffer AGC with a per-sample smoother
- **Severity**: MEDIUM
- **Dimension**: Player State Machine
- **Location**: `auralis/player/realtime/level_matcher.py:108-140`, `auralis/player/realtime/gain_smoother.py:14-62`
- **Status**: Existing: #6106
- **Description**: Re-verified: gain is recomputed per 1024-sample buffer from that buffer's RMS and smoothed with per-sample alphas (0.02 / 0.005, about 50 / 200 sample time constants), clamped at 10x (+20 dB). Unchanged.
- **Evidence**: `level_matcher.py:115-129`, `gain_smoother.py:28,52-57`.
- **Impact**: See #6106.
- **Suggested Fix**: See #6106.

### D3-10: Production load_file() decodes, prebuffers and fingerprints tracks that nothing consumes
- **Severity**: MEDIUM
- **Dimension**: Player State Machine
- **Location**: `auralis/player/player_file_loading_mixin.py:71-84`, `auralis/player/queue_controller.py:56-63`, `auralis/player/gapless_prebuffer.py:225-242`
- **Status**: Existing: #5708
- **Description**: Re-verified: the fingerprint thread is now skipped when `auto_master is None` (`fingerprint_loader_mixin.py:67-73`), but `load_file` still decodes the whole file, `start_prebuffering()` decodes the next one, and every queue edit that changes the next track re-arms a full decode via `on_queue_changed`.
- **Evidence**: `player_file_loading_mixin.py:72-79`.
- **Impact**: See #5708 (two resident decoded tracks plus a reference decode on library loads, latency on set_queue).
- **Suggested Fix**: See #5708.

### D4-01: WAV output past 4 GiB is written as plain RIFF, so the tail is unreadable (saver, wav_sanitize rewrite, CLI sink, seekable temp WAV)
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/saver.py:64`; `auralis/io/wav_sanitize.py:44-50`; siblings `auralis/core/mastering_chunk_loop.py:95-97,157-163` (offline CLI), `auralis-web/backend/core/seekable_source.py:170`
- **Status**: NEW (same defect class as closed #5566, whose `-rf64 auto` fix covers only FFmpeg's own intermediate WAV)
- **Description**: Every libsndfile WAV writer in the codebase uses the plain `WAV` container. libsndfile does not promote to RF64 on its own: it writes `RIFF` with size 0xFFFFFFFF and a data size clamped to 32 bits, and stops the readable frame count at 2^32/bytes-per-frame - 1. The samples are on disk but no reader (libsndfile included) sees them. `saver.save()` and `sanitize_wav_in_place()` never pass `format="RF64"` when the output will exceed 4 GiB.
- **Evidence**: `save('out.wav', zeros((540_000_000, 2), float32), 48000, 'PCM_32')` wrote 4,320,000,044 bytes; `sf.info` then reports `WAV PCM_32 frames=536870911` (expected 540,000,000) and the header starts `RIFF\xff\xff\xff\xffWAVE`. Likewise `sanitize_wav_in_place` on a 4.8 GB RF64 float WAV holding one NaN rewrote it and the result read back as `WAV FLOAT frames=536870911` (11,184.8 s of 12,500 s). Forcing `format='RF64'` writes a valid file.
- **Impact**: Silent loss of the last part of a long hi-res render. Reachable through (a) processing jobs with `bit_depth` 32 (or 24 near the 6 GiB input budget) on 96 kHz+ material of about 90 minutes or more, (b) the offline CLI, which has no duration cap (PCM_24 stereo passes 4 GiB at about 2 h at 96 kHz or 4.1 h at 48 kHz), (c) the sanitize rewrite of any decode over 4 GiB that needs repair (overshoot above 1.0 triggers it, so mostly theoretical), and (d) the libsndfile branch of `convert_to_temp_wav`. Narrow trigger, but the failure is silent and no sample-count check runs afterwards.
- **Suggested Fix**: Add one helper in `auralis/io` that returns `format='RF64'` when `frames * channels * bytes_per_sample` exceeds roughly 4 GiB (and `soundfile_format_name` says WAV), and use it in `saver.save`, `sanitize_wav_in_place`, `mastering_chunk_loop` and `seekable_source`. Add a read-back frame-count assertion after close.

### D4-02: FLAC with an unknown total sample count (STREAMINFO = 0) is refused with a bogus "exceeds maximum duration" error
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/soundfile_loader.py:84-98`; `auralis/io/audio_probe.py:97-112`; `auralis/library/scanner/audio_analyzer.py:65-73,86-91`
- **Status**: NEW
- **Description**: A FLAC written to a non-seekable sink (`ffmpeg -f flac - > x.flac`, `flac` reading stdin, stream recorders) carries `total_samples = 0`. libsndfile then reports `frames = INT64_MAX` (`sf.info`: 9223372036854775807 frames, 209146758205323 s), and `sf.read` cannot allocate. The loader compares that duration to `MAX_DURATION_SECONDS` and raises, so the user sees a nonsensical "exceeds maximum duration (209146758205324s > 7200s)". FFmpeg decodes the same file with exit code 0.
- **Evidence**: `ffmpeg -i s.wav -f flac - > piped.flac`; `load_audio('piped.flac')` gives `Corrupted or unsupported audio file: Audio file exceeds maximum duration (209146758205324s > 7200s)`; `get_audio_info` returns the same in `error`; `AudioAnalyzer().extract_audio_info` logs "Refusing piped.flac at scan time" and returns None, so the track is never ingested.
- **Impact**: A decodable file is dropped from the library with a misleading diagnosis. Workaround: re-encode with `flac`. This is an edge-case file class, hence MEDIUM rather than HIGH.
- **Suggested Fix**: Treat `frames == INT64_MAX` (or any frame count that implies a size far above the file's own byte length) as "length unknown" and route the file to FFmpeg/ffprobe, which can decode and measure it. The existing FFmpeg re-route in `load_with_soundfile` is the natural place.

### D4-03: WAV with a RIFF size placeholder other than 0xFFFFFFFF is rejected as "severely truncated"
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/soundfile_loader.py:23-44,63-72`
- **Status**: NEW (sibling of closed #4112, which special-cased only 0xFFFFFFFF)
- **Description**: `_get_wav_declared_size` trusts the RIFF size field. Streaming writers that cannot seek back (for example ALSA `arecord` to a pipe writes 0x7FFFFFDC, other recorders use 0x7FFFFFFF) leave a large placeholder. libsndfile reads such files fine (it uses the real file length), but the size check computes 0.0% completeness and raises `ERROR_TRUNCATED_FILE`.
- **Evidence**: Copy a valid 704 kB WAV and patch bytes 4-8 to 0x7FFFFFFF or 0x7FFFFFDC: `sf.read` returns all 176,400 frames, `load_audio` raises `Truncated audio file: File is severely truncated (0.0% complete)`. 0xFFFFFFFF and 0 pass. The scanner (`sf.info`) accepts the same file into the library, so it scans fine and then fails to play.
- **Impact**: Valid, complete recordings cannot be played, processed or fingerprinted. Workaround: re-save the file.
- **Suggested Fix**: Skip the declared-size check when the declared size is far above any plausible value (at least 0x7FFFFF00) or exceeds what the format could hold, or cross-check against the `data` chunk length. Only warn on partial truncation when the declared size is coherent with the file.

### D4-04: `sanitize_wav_in_place` hard-clips decoder overshoot, so the FFmpeg decode route differs from the in-memory route and from #6316
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/wav_sanitize.py:5-8,25-26,50`; callers `auralis/core/simple_mastering.py:174-177`, `auralis-web/backend/core/seekable_source.py:161-165`
- **Status**: NEW
- **Description**: `_needs_repair` flags any sample with `|x| > 1.0` and the rewrite clips it to [-1, 1]. The module docstring says this is "exactly as `saver.save()` does", but since #6316 `saver.save()` deliberately does not clip float subtypes ("an intermediate file must not clip what the engine's headroom stages would have handled"). The same track therefore has different samples depending on the route: `load_audio()` keeps the overshoot (`validate_audio` only warns), natively readable MP3/OGG/Opus keep it, while every FFmpeg-decoded M4A/AAC/WMA that goes through `decode_to_wav` plus sanitize (offline CLI, and the seekable temp WAV the streaming path reads) is clipped at decode time.
- **Evidence**: A 128 kbps AAC of loud noise: `load_audio` peak 1.326 (379 samples above 1.0); after `decode_to_wav` + `sanitize_wav_in_place` the peak is 1.0, rewritten=True, max abs diff 0.326. Same for MP3 (peak 1.16, 14 samples; clipped to 1.0). The existing test `test_out_of_range_decode_is_clipped` pins the old #5532 CLI behaviour and so predates #6316.
- **Impact**: Hard clipping of codec overshoot samples before DSP for AAC/WMA sources, which also forces a full second copy of the decode on disk (2x the temp space that `require_decode_space` budgets). The quantity per track is small, but it is an avoidable, route-dependent alteration of source samples and it contradicts the stated #6316 intent.
- **Suggested Fix**: Make `_needs_repair` and the rewrite handle only non-finite samples (leave finite out-of-range values alone, as the FLOAT saver does), and update the docstring and the #5532 test. If a clip is still wanted for the PCM output, do it at the output boundary only.

### D5-01: Whole-file loudness maximizer is driven by a 30 s middle-window LUFS/crest, not the whole track
- **Severity**: MEDIUM (offline-tool weight; up to the 4 dB push cap)
- **Dimension**: Chunked Mastering Loop
- **Location**: `auralis/core/mastering_prepare.py:139-163` (window read + `measure_window_loudness`), consumed at `auralis/core/mastering_branches/continuous.py:234-242` and `auralis/core/stages/loudness_maximizer.py:50-79`
- **Status**: NEW (related design theme to open #6346, but a different code path: #6346 is `MasteringFingerprint`'s 90 s window; this is the offline `_source_lufs`/`_source_crest_db`)
- **Description**: `prepare_file` measures "per-file accurate ITU-R BS.1770 loudness" and crest on `notch_sample`, which is only the middle `min(total, 30 s)` slice. `_source_lufs`/`_source_crest_db` then set `push_db` for every chunk of the file. The pre-scan loop at `:215-226` already streams the entire file for the peak, so a whole-file measurement was available at no extra I/O. The 25D fingerprint is whole-track, and the project rule is "analysis whole-track, mastering chunked". The offline chain therefore mixes a whole-track fingerprint (intensity, makeup gain) with a 30 s-slice loudness for the maximizer.
- **Evidence**: Probe: 120 s track, a loud section with the middle 30 s at -26 dB relative.
  ```
  quiet_middle  window LUFS/crest (-43.2, 19.8)  whole (-17.3, 16.7)
    maximizer push_db 3.99 (level_gap 28.7, source_lufs -43.2)
  uniform       window (-17.2, 15.4)  whole (-17.2, 15.5)
    maximizer push_db 1.32
  ```
  The same music gets about 2.7 dB more push into the -1 dB brick-wall limiter purely because of what lies at the file's midpoint. A loud track with a quiet bridge at the centre is pushed to the 4 dB cap and its crest is reduced, and a quiet-centre-loud-ends case is the same.
- **Impact**: Output loudness and crest for dynamic tracks (a bridge, a long intro or outro, a live track with a breakdown) depend on an arbitrary slice. The error is bounded at about 4 dB by `LOUDNESS_MAX_CREST_REDUCTION_DB`. It also makes the same song's master vary between a whole-track and a middle-window view.
- **Suggested Fix**: Fold the BS.1770 integrated-LUFS and crest measurement into the existing whole-file pre-scan loop in `prepare_file`. `LoudnessMeter.measure_chunk`/`finalize_measurement` already stream block by block. Keep the 30 s window only for resonance-notch detection.

### D6-01: Whole-track Rust fingerprint accumulates 20M-sample sums in f32, so spectral rolloff/centroid (and RMS, crest, phase correlation) drift with track length
- **Severity**: MEDIUM
- **Dimension**: Analysis Subsystem
- **Location**: `vendor/auralis-dsp/src/spectral_features.rs:16-62` (`compute_spectral_centroid`, `compute_spectral_rolloff`: `psd.iter().sum::<f32>()`, `let mut cumulative = 0.0` as f32 over 2^23-2^24 bins), `vendor/auralis-dsp/src/dsp_math.rs:11-17` (`compute_rms`: `let sum_sq: f32 = ...sum()`), `vendor/auralis-dsp/src/stereo_analysis.rs:20-27, 71-110` (`compute_energy`, `compute_phase_correlation`, `normalize_signal`)
- **Status**: NEW
- **Description**: Since algorithm v13 the engine receives the whole track (up to 900 s = 19.8M samples at 22.05 kHz) instead of a 90 s window, but several reductions stayed single-precision sequential sums. A float32 accumulator stops absorbing small terms once its running value is large (ulp/2 exceeds the increment), so late samples/bins are partly lost. The v14/v15 work (#6341) moved the band shares and `bass_mid_ratio` to f64 accumulators for exactly this reason; the centroid/rolloff/RMS/stereo reductions were not converted. The error grows with duration and is not a property of the audio.
- **Evidence**: Same algorithm in float64 (numpy, identical Hann window and FFT size) vs the installed `auralis_dsp.compute_fingerprint`:
  - Pink noise, spectral_rolloff Hz (Rust / float64 truth): 120 s 3094/3220, 240 s 2929/3181, 420 s 2563/3217, 600 s 2156/3192, 900 s 1522/3188; centroid at 900 s 1500/1359.
  - Real tracks (mono 22.05 kHz, rolloff Rust/truth Hz): 231 s 811/886, 576 s 1174/1529, 576 s 2472/2744, 803 s 1747/2048. `lufs` reads 0.07-0.16 dB low (e.g. -16.17 vs -16.01), `crest_db` correspondingly high.
  - Stereo Laplacian noise, 900 s: `phase_correlation` 0.9026 vs 0.8823 truth (60 s: 0.8833 vs 0.8824).
  - 60 s inputs are accurate to <0.5%, so the defect is invisible to the old 90 s-window tests.
- **Impact**: Every track longer than about 4 minutes gets a systematically wrong `spectral_rolloff` (8-50% low), `spectral_centroid` (up to +10%), `lufs`/`crest_db` (~0.1-0.2 dB) and a biased `phase_correlation`; the error differs between two renders of the same material at different lengths. `spectral_rolloff`/`spectral_centroid` are `TARGET_FEATURES` of the reference-cloud EQ target (`core/processing/target_derivation.py:75`) and the centroid is 30% of the `spectral_balance` coordinate (`continuous_space.py:132-137`); both also carry similarity weights (`dimension_weights.py`).
- **Suggested Fix**: Accumulate these reductions in f64 (or compute centroid/rolloff from the per-frame f64 PSD accumulation the band shares already use, see D6-02); add a long-input regression test (>= 8 min) comparing against an f64 reference; bump `FINGERPRINT_ALGORITHM_VERSION` to 17 so stored rows are recomputed.

### D6-02: Spectral centroid/rolloff come from one whole-track Hann-windowed 2^N FFT, so they describe the middle of the track and disagree in scope with the band shares
- **Severity**: MEDIUM
- **Dimension**: Analysis Subsystem
- **Location**: `vendor/auralis-dsp/src/spectral_features.rs:158-203` (`audio_to_freq_domain`: one FFT of `next_pow2(len)` points, Hann over the whole length), `vendor/auralis-dsp/src/fingerprint_compute.rs:240-243`
- **Status**: NEW (the same class as closed #6341 / v14: "dimensions of one fingerprint must not describe different parts of the track"; the centroid/rolloff were left out of that fix)
- **Description**: A single Hann window spanning the whole track weights audio by w(t)^2: the first and last ~10% carry ~1% of the weight, the first/last 25% ~25%. The 7 band shares, `bass_mid_ratio`, `loudness_variation` etc. weigh the whole track uniformly (3 s frames), so one fingerprint holds a brightness measure for the middle half and band shares for the whole. It also allocates a 2^25-point complex FFT (268 MB) plus 134 MB PSD, 67 MB freqs and a 67 MB copy for a 900 s track.
- **Evidence**: 120 s signals, Rust `spectral_centroid` vs unwindowed whole-track centroid: bright first 25% then dark: 1534 Hz vs 2396 Hz; dark then bright last 25%: 1515 vs 2395; bright middle 50%: 5208 vs 3440. The band shares of the same inputs (`air` 0.120, `presence` 0.180) correctly reflect the whole track.
- **Impact**: A track with a bright intro/outro (or a long quiet or bass-only coda) fingerprints with a centroid/rolloff that ignores it while the band shares include it; brightness-derived mastering coordinates and similarity then disagree with the spectrum the EQ is built from. Also the largest single allocation of the analyzer.
- **Suggested Fix**: Derive centroid and rolloff from the same frame-accumulated f64 PSD as the band shares (also removes the 2^25 FFT); bump the algorithm version together with D6-01.

### D6-03: `fingerprint_preloaded` runs whole-track analysis without the `analysis_budget` gate
- **Severity**: MEDIUM
- **Dimension**: Analysis Subsystem
- **Location**: `auralis/analysis/fingerprint/preloaded_fingerprint.py:18-30`; callers `auralis/core/processing/continuous_mode.py:213`, `auralis/core/analysis/content_analyzer.py:147`; contradicted claim at `auralis/analysis/fingerprint/analysis_budget.py:108`
- **Status**: NEW
- **Description**: `analysis_budget` is documented as "the process-wide gate every fingerprint computation goes through", and only `compute_windowed_fingerprint` reserves from it. `fingerprint_preloaded` (the #6114 path) analyses a decoded buffer of up to `FINGERPRINT_FULL_TRACK_MAX_S` in full by calling `analyzer.analyze` directly. Whole-file jobs (`core/job_execution.py` -> `HybridProcessor.process(audio)` -> `ContinuousMode._resolve_parameters` with no fixed params) take this path for every track under 15 minutes. The analyzer's transient footprint (~77 MB per minute, measured) is therefore added to the gated library queue's and the interactive stream's analyses with nothing bounding the sum.
- **Evidence**: `rg "analysis_budget"` shows `reserve()` only in `windowed_compute.py:119`. Measured `analyze()` peak for a 900 s stereo buffer: +1148 MB over baseline.
- **Impact**: The 40-minute (~3.4 GB) cap holds only for file-based extraction; concurrent processing jobs and library fingerprinting can together exceed it (the OOM scenario #6336/#6338 were written to prevent), and jobs cannot be cancelled while waiting.
- **Suggested Fix**: Wrap the whole-track branch of `fingerprint_preloaded` in `analysis_budget.reserve(minutes)` (interactive for jobs), keep the windowed branch ungated.

### D6-04: ML genre feature extraction is degenerate (onset rate pinned to the frame rate, tempo pinned to 200 BPM), so the classifier returns "metal" or "classical" for almost everything
- **Severity**: MEDIUM
- **Dimension**: Analysis Subsystem
- **Location**: `auralis/analysis/ml/feature_extractor_temporal.py:45-65` (`_onset_rate`), `auralis/dsp/utils/spectral.py:262-295` (`_tempo_estimate_python`), `auralis/dsp/utils/spectral.py:52-80` (`spectral_centroid`), `auralis/analysis/ml/genre_classifier.py:104-124`
- **Status**: NEW (the #6142 fix, spreading frames for the averaged-magnitude features, is in place; these three features were not part of it)
- **Description**: (1) `_onset_rate` compares `flux = np.sum(max(spectrum - prev, 0))` (a sum over ~1024 bins) with `np.mean(spectrum) * 0.1` (a per-bin mean), a factor-of-N scale mismatch, so every frame is an onset and the feature is always `sr / hop` (86.1 at 44.1 kHz) whatever the audio. (2) `tempo_estimate` takes the mean spacing of flux peaks above mean+0.5 sigma (a few frames apart) and clips to 60-200, so it saturates at 200. (3) `spectral_centroid` analyses a single 4096-sample frame at the 25% mark, not frames spread over the track. With two of the strongest weighted features constant, the linear scores are decided by `rms`/`crest` alone.
- **Evidence**: 22 random real clips (30 s from the library, 44.1 kHz) through `create_ml_genre_classifier().classify`: `onset_rate` 86.0 (46.4-46.7 on three) and `tempo` 200 for 22/22; primary genre "metal" for 17, "classical" for 5 (confidence ~1.0), including Miles Davis, Pink Floyd, Eric Clapton, Talking Heads and The Prodigy as "metal". 25-clip run: 21 metal, 4 classical.
- **Impact**: `genre_info` feeds `EQProcessor._apply_content_adjustments`, `TargetGenerator.generate_targets` (genre profile) and the job summary for the adaptive/hybrid mode path (`AdaptiveMode`, reached by `mode=hybrid` jobs); output is effectively two classes keyed to loudness. Off the default ContinuousMode path (which ignores genre), so not user-facing for the standard stream.
- **Suggested Fix**: Normalise the flux comparison per bin (or use a median/peak-pick onset detector shared with the Rust tempo), reuse a real tempo estimator, spread the centroid over `_frame_offsets`; add a test asserting `onset_rate`/`tempo` vary across distinct synthetic inputs.

### D7-01: A rescan/retag that creates a new album never extracts its artwork, and the prune deletes the old album's artwork file
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_mutation.py:67-73,85-156,158-202`; `auralis/library/repositories/orphan_pruning.py:51-82`; `auralis/library/repositories/track_repository_lifecycle.py:231-243` (the only extraction site); `auralis/library/scanner/batch_processor.py:195-209`
- **Status**: NEW
- **Description**: Embedded/folder artwork is extracted only inside `TrackRepository.add()` ("if album and album_repository and not album.artwork_path"). The update paths (`update_by_filepath`, `update`) call `_assign_album` -> `_get_or_create_album`, which can create a brand-new `Album` row (album tag changed, ALBUMARTIST tag added, any compilation after the v30->v31 rescan, a retagged/renamed album) but never extract artwork for it. `_prune_after_relation_change` then deletes the emptied old album(s) and queues unlinking of THEIR artwork files after commit. Nothing else re-extracts: `POST /api/albums/{id}/artwork/extract` has no frontend caller (only an MSW mock).
- **Evidence**: Reproduced. Two FLACs with embedded front cover, no albumartist -> scan: albums 1 and 2 both have `artwork_path`. Add `albumartist=Various Artists` to both files, rescan: tracks re-pointed to new album id 3, `albums` = `[(3, 'Comp', 3, '')]` (empty artwork_path), the artwork directory is empty (old files unlinked, none written for album 3). Call path: `BatchProcessor.process_single_file` -> `update_by_filepath(..., replace_tags=True)` -> `_assign_album` -> `_prune_after_relation_change` -> `prune_orphans` -> `_unlink_artwork_after_commit`.
- **Impact**: Cover art silently disappears for every album touched by a retag, and for every compilation/soundtrack/guest-first album on the first rescan after the v31 migration (the migration clears `file_mtime` precisely to force that rescan). The user-visible grid shows placeholders until the albums are deleted and re-added; the UI exposes no way to re-extract.
- **Suggested Fix**: Make artwork extraction part of album resolution rather than of `add()` only: after `_assign_album` (both update paths), if the resolved album has no `artwork_path` and a file path is known, run the same extract-and-commit step `add()` uses (share one helper), before the prune.

### D7-02: Deleting a track's whole folder leaves its rows in the library forever
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_missing_files.py:50-63` (`_track_file_is_missing`), used by `_confirmed_missing_ids` (`:66-83`) and `track_repository_maintenance.py:124-167`; caller `auralis-web/backend/services/missing_tracks.py:24-45`
- **Status**: NEW (deliberate trade-off from #2525 / #5698 whose other side is untreated; not covered by any open or closed issue)
- **Description**: The prune treats "the track's parent directory is itself ENOENT" as "volume probably unmounted" and skips the track. That is also exactly what `rm -rf Album/` (or deleting an artist folder, or the album folder after a rename that did not match a relocation) looks like, so those rows can never be pruned: the only rows `cleanup_missing_files` can ever remove are tracks whose file vanished from a folder that still exists. Context that would tell the two cases apart is available to the caller (the configured scan roots and `ScanResult.walk_complete`) but the repository method takes none.
- **Evidence**: Reproduced. Scan two folders, `shutil.rmtree(lib/'Solo')`, run `tracks.cleanup_missing_files()` -> `0` removed; the `Solo` track row (and its album and artist) are still in the DB. Deleting a single file inside a surviving folder is pruned correctly (`1` removed). `relocate_missing_track` documents the opposite treatment ("a gone parent directory still counts") so the two halves disagree.
- **Impact**: Deleted albums stay browsable and queueable but unplayable indefinitely, inflate every library count, keep their artwork file, and each ghost costs the fingerprint worker up to 3 failed extraction attempts per process start (`MAX_EXTRACTION_ATTEMPTS`). Only "reset library" clears them.
- **Suggested Fix**: Pass the scan roots into the prune: treat a missing parent as gone when the track lies under a configured scan root that was walked this cycle (`walk_complete` and the root itself readable and non-empty), and keep the skip only for tracks outside any walked root.

### D7-03: `normalize_artist_name` strips combining marks, so distinct non-Latin artists collapse into one row
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/utils/artist_normalizer.py:97-101` (used by `track_repository_lifecycle.py:93-115` and the unique-by-normalized-name lookup)
- **Status**: NEW
- **Description**: The key keeps only characters for which `str.isalnum()` or `isspace()` is true. Unicode combining vowel signs and diacritics (categories Mc/Mn: Devanagari matras, Thai above/below vowels, Arabic harakat, Hebrew points, and any accent that NFC cannot precompose) are neither, so they are deleted. `_get_or_create` then resolves a second artist whose name differs only in those marks to the first artist's row.
- **Evidence**: Executed: `normalize_artist_name('शिव') == normalize_artist_name('शव') == 'शव'`; `'कुमार'` and `'कमर'` both -> `'कमर'`; Arabic `'الحُب'` and `'الحب'` -> `'الحب'`. `_get_or_create_artists` selects `Artist.normalized_name == normalized` first, so the second name is attributed to the first artist's row and its own name is never stored.
- **Impact**: Tracks of different artists are silently merged under one artist (irreversible short of retagging and a rescan after deletion); artist counts/pages wrong for libraries in these scripts. The Latin-script behaviour the docstring describes is unaffected.
- **Suggested Fix**: Keep characters whose category starts with `M` (marks) as well as alnum when building the key (and apply NFC/NFKC before filtering), so only punctuation/symbols are dropped.


## LOW Findings
### D1-04: Input contract accepts any `np.floating` dtype, so float16 / longdouble fail late inside the limiter
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/hybrid_stage_dispatch.py:70-71`, failing at `auralis/dsp/dynamics/brick_wall_limiter.py:137`
- **Status**: NEW
- **Description**: `validate_and_normalize_input` checks `np.issubdtype(dtype, np.floating)`, which admits float16 and float128. The stages run (DC removal, fingerprint, EQ, dynamics, normalisation) and the first call that
  rejects the dtype is `scipy.ndimage.maximum_filter1d` in the final limiter: `RuntimeError: array type dtype('float16') not supported`. The work is wasted and the error is not a contract error.
- **Evidence**: `HybridProcessor.process((44100,2) float16)` and `np.longdouble` -> `RuntimeError array type dtype('float16'/'float128') not supported` at `scipy/ndimage/_filters.py:1733` after the whole chain ran.
- **Impact**: Loud (no corruption), only a diagnostics / wasted-compute issue; nothing in the app produces these dtypes.
- **Suggested Fix**: Restrict the contract to `dtype in (np.float32, np.float64)` and raise the same `ValueError` as the other contract checks.

### D2-02: AutoMasterProcessor's makeup-gain headroom cap is a per-buffer peak-derived gain (fourth site of the #5721 pattern)
- **Severity**: LOW (dormant path: `enable_auto_mastering=False`, `AudioPlayer.get_audio_chunk` has no production consumer)
- **Dimension**: DSP Pipeline Correctness
- **Location**: `auralis/player/realtime/auto_master.py:194-211`
- **Status**: NEW (sibling of closed #5721, which moved the three other per-buffer peak scalars onto `StreamingPeakCeiling` but left this one)
- **Description**: After compression the makeup gain is capped so the CURRENT buffer's peak stays under 0.98: `max_safe_gain_db = 20*log10(0.98 / processed_peak)`. The cap is recomputed from each buffer's own peak, so the gain is constant inside a buffer and unrelated between buffers - it steps at every boundary where the peak changes.
- **Evidence**: probe with the shipped class (fingerprint lufs -22 / crest 14 -> makeup 5.0 dB, 1024-sample buffers of a 200 Hz sine, transient enhancer off): input buffer peaks 0.20, 0.20, 0.85, 0.85, 0.20 gave effective peak gains +4.92, +3.96, +0.50, +0.50, +1.20 dB: a 3.5-4.4 dB step at the 0.20 -> 0.85 boundary.
- **Impact**: Audible zipper/AGC steps on the real-time chain if it is ever wired to an output (it is not today).
- **Suggested Fix**: Apply the makeup gain through the same carried per-sample envelope (`StreamingPeakCeiling`/`AdaptiveGainSmoother`) rather than a per-buffer scalar, or delete the unwired real-time output path (the decision #5721 left open).

### D2-03: Legacy AdaptiveMode (hybrid-mode adaptive half) derives EQ/dynamics/level with hard-threshold steps
- **Severity**: LOW (legacy path; reached only by `mode=hybrid` jobs with a reference file; blended at 40%)
- **Dimension**: DSP Pipeline Correctness (parameter-space continuity)
- **Location**: `auralis/core/analysis/target_fingerprint_adjustments.py:54-67, 75-88, 94-100, 116-126`; `auralis/core/processing/eq_processor.py:126-159`; `auralis/core/processing/adaptive_normalization.py:75-79, 102`; `auralis/dsp/utils/spectral.py:71-80`
- **Status**: NEW
- **Description**: `AdaptiveMode` (kept for the hybrid mode) still builds its targets from categorical `if` thresholds, exactly the class the continuous space and #4860/#5578/#5704/#6303 removed: band-share tails add/subtract fixed EQ amounts (bass +1.5 / -1.0 dB at 0.28 / 0.58, mid +1.2 / -0.8 dB, treble +1.8 / -1.2 dB), `crest_db > 16` / `< 8` switch the compression ratio, `lufs > -10` / `< -25` shift the target by 2 dB, `EQProcessor._apply_content_adjustments` multiplies gains by 0.7/0.8/1.2/1.3 on centroid / genre / dynamic-range classes, and `apply_final_normalization` gates the makeup gain on `expansion_amount < 0.1` and the peak normalization on `peak < target - 1.5 dB`. The centroid feeding those classes is one 4096-sample frame (about 93 ms) taken at the 1/4 point of the buffer (`spectral_centroid`).
- **Evidence**: `apply_fingerprint_enhancements` with `bass_pct` 0.2799 -> 0.2801: `bass_boost_db` 1.5 -> 0.0; `mid_pct` 0.0999 -> 0.1001: `midrange_clarity_db` 1.2 -> 0.0; `crest_db` 15.99 -> 16.01: `compression_ratio` 2.5 -> 1.5. (`ContinuousMode` is not affected: its `content_profile` carries none of the keys these class tests read, so they stay at their neutral defaults.)
- **Impact**: Two near-identical tracks (or two chunks of one track) can be mastered 1-2 dB differently in the hybrid mode's adaptive half.
- **Suggested Fix**: Replace the thresholds with `smooth_gate` knees as in the continuous path, or retire the adaptive half of hybrid mode in favour of `ContinuousMode`.

### D2-04: Offline harmonic exciter adds a linear +1-4 dB boost to 3-8 kHz because its high-pass overlaps the donor band
- **Severity**: LOW (offline CLI only, `auto_master.py`)
- **Dimension**: DSP Pipeline Correctness
- **Location**: `auralis/core/mastering_config.py:230-239, 263-269`; `auralis/core/dsp/harmonic_exciter.py:114-161`; `auralis/core/stages/harmonic_exciter.py:74-99`
- **Status**: NEW
- **Description**: The exciter is documented as pure harmonic generation ("the HP still rejects the original donor band, only newly generated harmonics pass"). But `EXCITER_DONOR_HIGH_HZ` (5500) is above `EXCITER_HP_CUTOFF_HZ` (4500), and the cascade donor 3000-8000 Hz is above its 8000 Hz HP, so the saturator's linear (fundamental) component in 4.5-5.5 kHz (and the skirt of the order-2 zero-phase HP below it) is added back at `drive x wet` gain: the stage is partly a 3-8 kHz shelf boost that does not go through `hf_budget` accounting as one.
- **Evidence**: `harmonic_exciter.apply` stage, sine at the fundamental, gain at the fundamental frequency: intensity 1.0 / hf_lift 1.0 (wet -12 dB): +1.59 dB @ 3 kHz, +4.10 dB @ 4.8 kHz, +3.15 dB @ 7 kHz (level independent: same at -50 and -12 dBFS); intensity 0.6 / 0.6: +0.33 / +0.95 / +0.72 dB.
- **Impact**: Up to +4 dB of uncounted presence boost on HF-poor sources in the offline tool, stacked on top of the clarity/presence/air shelves the HF budget is meant to bound.
- **Suggested Fix**: Move the HP cutoff above the donor band (or band-limit the donor below it) and remove the linear (fundamental) component from the wet path so only generated harmonics are added; fix the docstring either way.

### D2-05: Offline mastering carries its own band-target tables, diverging from `CORPUS_BAND_CENTERS`
- **Severity**: LOW (offline CLI only)
- **Dimension**: DSP Pipeline Correctness
- **Location**: `auralis/core/mastering_notch_context.py:47-56`; `auralis/core/mastering_config.py:213` (`BASS_TARGET_PCT`); `auralis/core/analysis/target_fingerprint_adjustments.py:25` (`BAND_SHARE_TAILS`)
- **Status**: NEW
- **Description**: `contextualize_notches` keeps a hand-typed band table calibrated on "n=27 reference tracks" that disagrees with the 508-track `CORPUS_BAND_CENTERS` that #5695 made the single source (sub_bass 0.087 vs 0.1354, low_mid 0.136 vs 0.1009, mid 0.171 vs 0.1983, upper_mid 0.055 vs 0.0733, presence 0.015 vs 0.0297, air 0.001 vs 0.0063), and one row keys on `brilliance_pct`, which is not a fingerprint dimension (it silently falls back to its own default). `BASS_TARGET_PCT` retypes the bass centre as a literal. Notches are only detected in 150-1200 Hz, so the stale rows beyond bass/low-mid/mid are unreachable and the divergent ones only change notch depth scaling.
- **Evidence**: `BAND_LOOKUP` vs `auralis/dsp/constants.py::CORPUS_BAND_CENTERS`; `grep brilliance_pct auralis` hits only this table.
- **Impact**: Notch depth is scaled against an outdated health target; tuning the corpus centres will not move it.
- **Suggested Fix**: Build `BAND_LOOKUP` from `CORPUS_BAND_CENTERS` (drop the `brilliance` row) and import the bass centre instead of retyping it.

### D2-06: A reference-mode processor given no reference fails with "Invalid processing mode: reference"
- **Severity**: LOW
- **Dimension**: DSP Pipeline Correctness
- **Location**: `auralis/core/hybrid_processor.py:196-203`
- **Status**: NEW
- **Description**: `_process_impl` dispatches `if is_reference_mode() and reference is not None` / `elif is_adaptive_mode()` / `elif is_hybrid_mode()` / `else: raise ValueError("Invalid processing mode: ...")`. For `mode == "reference"` and `reference is None` no branch matches, so the valid mode is reported as invalid. The router rejects this at request time (#4735), so only direct callers see it.
- **Evidence**: `c.set_processing_mode('reference'); HybridProcessor(c).process(x)` -> `ValueError: Invalid processing mode: reference`.
- **Impact**: Misleading error; no audio effect.
- **Suggested Fix**: Raise `ValueError("reference mode requires a reference array")` when the mode is reference and `reference is None`.

### D2-07: Album-consistency target derivation is unwired; stale comments describe deleted state
- **Severity**: LOW
- **Dimension**: DSP Pipeline Correctness (config reachability)
- **Location**: `auralis/core/processing/album_target.py` (whole module), `auralis/core/processing/continuous_mode.py:83-85`, `auralis/core/processing/continuous_dsp_ops.py:87-99`
- **Status**: Existing: #3481 (open, "Per-album mastering consistency mode"); the stale-comment part is NEW
- **Description**: `derive_album_target` / `average_targets` have no production caller (only tests), and `ContinuousMode.__init__` keeps a comment announcing an "album-consistency override ... When set, every process() call uses this one target" with no attribute behind it. #5560 (closed) fixed the reference-cloud reachability but not this part. Separately, the `_apply_dynamics` docstring explains the design by contrast with `HybridProcessor.dynamics_processor` / `DynamicsProcessor`, both deleted in #6201.
- **Evidence**: `grep -rn "album_target\|derive_album_target\|average_targets" auralis auralis-web/backend` -> only the module itself.
- **Impact**: Doc rot / dead surface; no audio effect.
- **Suggested Fix**: Keep tracked under #3481 (wire it or delete the module); delete the orphan comment and rewrite the `_apply_dynamics` docstring without the removed class.

### D3-01: stop() then play() does not cancel an auto-advance already inside its decode
- **Severity**: LOW
- **Dimension**: Player State Machine
- **Location**: `auralis/player/player_streaming_mixin.py:171-201`, `auralis/player/enhanced_audio_player.py:143-177`, `auralis/player/gapless_playback_engine.py:173-174`
- **Status**: NEW (the #3296 / #6127 fixes cover only "stop before the thread starts" and "cleanup")
- **Description**: `_auto_advance_next` consults `_stop_requested` once, at line 174, before `next_track(completed=True)`. The only mid-flight cancellation is the `abort=self._cleanup_in_progress.is_set` predicate, which `stop()` does not trip. `play()` clears `_stop_requested`. So a stop() followed by play() while the advance thread is in the blocking fallback decode (no ready prebuffer) lets the stale advance commit afterwards: it advances the queue, swaps in the next track and resets position, replacing the track the user just restarted.
- **Evidence**: harness (prebuffer off, `_load_audio` slowed to 0.6 s): final chunk of A spawns the advance thread; 0.1 s later `stop()` then `play()` -> `stop True STOPPED`, `replay True PLAYING a.wav pos 0`; 1 s later `file b.wav qidx 1 state PLAYING pos 0`. Path: `get_audio_chunk` end_of_track -> `_auto_advance_next` -> `next_track` -> `advance_with_prebuffer` (`abort` only polls `_cleanup_in_progress`) -> `advance_if_next_matches` -> `_on_swap`.
- **Impact**: User-visible only for an engine consumer that drives `get_audio_chunk` (dormant in the shipped backend) and only when the fallback decode is slow; the restarted track is replaced by the next one and the queue skips a track. Also `stop()` clearing `_auto_advancing` defeats the single-flight guard for that window.
- **Suggested Fix**: Bump `_advance_generation` under `_audio_lock` in `stop()` (and `play()`), capture the generation in `_auto_advance_next`, and pass `abort=lambda: cleanup_set or generation != self._advance_generation` into `next_track`/`advance_with_prebuffer`.

### D3-02: A successful gapless next_track() does not leave the terminal ERROR state
- **Severity**: LOW
- **Dimension**: Player State Machine
- **Location**: `auralis/player/playback_controller.py:88-94,120-138,209-229`, `auralis/player/player_queue_navigation_mixin.py:99-117,153-158`, `auralis/player/player_file_loading_mixin.py:90-100`
- **Status**: NEW (adjacent to closed #5725, which only narrowed when ERROR is entered)
- **Description**: ERROR is entered when a load fails with nothing loaded (#5725) and is left only by `load_and_stop()` (reached through `load_file` / `load_track_from_library` / `previous_track`). `next_track()` installs audio via `advance_with_prebuffer` and `_on_swap` only calls `playback.seek`, which does not touch state, and `was_playing` is False in ERROR so no `play()` is attempted. `play()` and `stop()` both reject ERROR.
- **Evidence**: harness: `set_queue([bad, a, b])`, `load_file(bad)` -> `False`, state ERROR; `next_track()` -> `True`, state still ERROR, `is_loaded()` True; `play()` -> `False` ("play() rejected: player is in ERROR state"). Production trigger: `QueueService.set_queue` whose start track is missing/undecodable (`queue_set_mixin.py` logs "queue set but not playing"), then the user skips forward.
- **Impact**: Engine reports a loaded, healthy track but refuses to play or stop until some other `load_file` succeeds. Today the backend ignores the `play()` return value (and the engine state is not what the client hears), so the visible effect is a wedged engine state, not silence.
- **Suggested Fix**: In `_on_swap` (or after a successful advance) recover from ERROR the way `load_and_stop` does, e.g. add a `PlaybackController` method that moves ERROR -> STOPPED atomically and call it inside the swap hook.

### D3-03: load_track_from_library() reports failure after the audio was already swapped in
- **Severity**: LOW
- **Dimension**: Player State Machine
- **Location**: `auralis/player/integration_library.py:47-83`, `auralis/player/player_file_loading_mixin.py:121-164`
- **Status**: NEW
- **Description**: The method's single `try/except Exception -> return False` wraps both the real load (`file_manager.load_file(..., on_loaded=)`, which swaps audio and resets the position via the hook) and post-load bookkeeping (`set_current_track`, `repos.tracks.record_play`, `_auto_select_reference`'s caller, `track.to_dict()` for the notify). If `record_play` raises (for example "database is locked" while a scan writes), the player is already on the new track in STOPPED state but the call returns False. The wrapper then skips `_schedule_fingerprint_load` and `gapless.start_prebuffering()`, `_note_failed_load` sees audio loaded and does nothing, and `AudioPlayer.add_to_queue` skips `select_if_unselected`.
- **Evidence**: harness with a repo whose `record_play` raises: `returned False | loaded True a.wav | state STOPPED | current_track True`, and `play()` then succeeds; `add_to_queue({'filepath', 'id'})` leaves `queue.current_index == -1` (the #5727 double-play condition) while the file is loaded. The backend route `load_track` (`routers/player_playback.py:117-143`) answers 400 "Failed to load track" and skips the `track_loaded` broadcast although the engine holds the track.
- **Impact**: A transient DB error in a statistics write turns a successful load into a reported failure with inconsistent engine state (loaded audio, unselected queue, no prebuffer or fingerprint scheduled, caller told it failed).
- **Suggested Fix**: Keep only the decode inside the failure scope; run `record_play` / reference selection / notification in their own try blocks that log and continue, so the return value means "audio is loaded".

### D3-04: load_playlist() accepts a negative start_index and writes an out-of-range queue index
- **Severity**: LOW
- **Dimension**: Player State Machine
- **Location**: `auralis/player/queue_loading.py:92-94` (sibling guard at `:126-128`), `auralis/player/queue_locked_state.py:30-34`
- **Status**: NEW (#4098 / #5355 fixed atomicity, not the lower bound)
- **Description**: `set_queue` writes `current_index` only when `start_index >= 0`; `load_playlist` writes `min(start_index, track_count - 1)` with no lower clamp, so `start_index=-5` stores -5. `QueueController.current_index`'s setter also stores any value. Python negative indexing then makes `peek_next()` return a wrapped element, `advance_if_next_matches` mutates the index and returns None (read by `advance_with_prebuffer` as a lost race), and `get_current_track()` returns None.
- **Evidence**: `q.current_index = -5` on a 5-track `QueueManager`: `peek_next()` -> `{'id': 1}`; `advance_if_next_matches(...)` -> `None` with `current_index` now `-4`.
- **Impact**: Queue-bounds invariant broken for any caller passing a negative index. No production caller of `AudioPlayer.load_playlist` exists today, so dormant.
- **Suggested Fix**: Clamp `max(0, min(start_index, track_count - 1))` in `load_playlist` (or reject negatives like `set_queue`) and clamp in the `current_index` setter.

### D3-05: load_file() and the gapless advance bypass the per-track player state the library path sets; the advance event is enriched before it is synced
- **Severity**: LOW
- **Dimension**: Player State Machine
- **Location**: `auralis/player/player_file_loading_mixin.py:51-88`, `auralis/player/player_queue_navigation_mixin.py:113-124`, `auralis/player/integration_library.py:65-72`, `auralis/player/integration_manager.py:203-219`
- **Status**: NEW (#5726 fixed `current_track` for navigation, not for `load_file`)
- **Description**: (a) `AudioPlayer.load_file()` - the call the backend actually makes after `set_queue` and after removing the current track - never calls `set_current_track`, so `current_track` / `get_playback_info()['library']['current_track']` / the `track` of `playback_finished` stay None or describe the previously loaded track. (b) In `next_track()` the deferred state events are flushed at the exit of the `defer_notifications()` block and enriched by `_on_playback_state_change` with `_current_track_dict`, but `_sync_current_track_from_queue()` only runs afterwards; the `seek` event for the swap therefore pairs the new `current_file` / duration with the previous track's metadata on every advance. (c) Sibling: `next_track` / `load_file` also never run `_auto_select_reference`, so the level-matching reference chosen for the previous track keeps driving the new one (only `load_track_from_library` refreshes it).
- **Evidence**: harness: queue [A, B], `load_file(A)`, `play()`, register `integration.add_callback`, `next_track()` -> single event `{'action': 'seek', 'current_file': 'b.wav', 'duration_seconds': 1.5, 'current_track': None}`.
- **Impact**: Inconsistent metadata for any consumer of engine events or `get_playback_info()`; none registers today, so low. Would bite as soon as the engine is the source of now-playing state.
- **Suggested Fix**: Make `load_file` sync `current_track` from the queue entry (as `_sync_current_track_from_queue` does) and move the sync before the deferred flush (do it inside the `defer_notifications()` scope, before it exits), or carry the target track in the event.

### D3-06: PlayerConfig(enable_auto_mastering=True) does not enable the auto-master stage
- **Severity**: LOW
- **Dimension**: Player State Machine
- **Location**: `auralis/player/realtime/processor.py:37-38,59-62,143-162`, `auralis/player/realtime/auto_master.py:39,171-173`
- **Status**: NEW
- **Description**: `RealtimeProcessor` seeds `effects_enabled['auto_mastering'] = config.enable_auto_mastering` and builds an `AutoMasterProcessor`, but that processor starts with `self.enabled = False` and nothing sets it True at construction. `process_chunk` therefore calls `auto_master.process`, which returns the audio untouched, while `effects_enabled` and the log line ("Auto-mastering: Enabled") say it is on. Only an explicit `set_effect_enabled('auto_mastering', True)` activates it, which every test does.
- **Evidence**: harness: `RealtimeProcessor(PlayerConfig(enable_auto_mastering=True, enable_level_matching=False))`, fingerprint set, 0.02-amplitude noise chunk -> `p.effects_enabled == {'auto_mastering': True}`, `auto_master.enabled == False`, max abs difference 0.0; after `set_effect_enabled('auto_mastering', True)` the same chunk changes by 0.0816. `get_processing_info()` shows `enabled_effects.auto_mastering: True` and `effects.auto_mastering.enabled: False` together.
- **Impact**: A config flag that silently does nothing (dormant: the shipped backend passes False). Any future consumer enabling it through the config gets unprocessed audio and contradictory status.
- **Suggested Fix**: Initialise `AutoMasterProcessor.enabled` from `config.enable_auto_mastering` (or call `set_enabled` in `RealtimeProcessor.__init__`).

### D3-07: Dead state in the realtime chain: `compression_ratio` and `performance_mode`
- **Severity**: LOW
- **Dimension**: Player State Machine
- **Location**: `auralis/player/realtime/auto_master.py:147-163`, `auralis/player/realtime/performance_monitor.py:20-53`
- **Status**: NEW
- **Description**: `_generate_adaptive_parameters` computes a fingerprint-derived `compression_ratio` (1.5 / 2.0 / 2.5 by crest) and `reasoning`, but `_process_locked` only reads `makeup_gain_db` and `target_peak`; the compressor is built once with a fixed ratio 1.3 (`_build_compressor`). `PerformanceMonitor` maintains `performance_mode` ("adapts quality") but nothing in `auralis`/`auralis-web` reads it (grep), so sustained overruns change no processing.
- **Evidence**: `grep -rn "compression_ratio\|performance_mode" auralis auralis-web/backend` finds only the producers and `get_stats` output.
- **Impact**: Docstrings and stats promise content-adaptive compression and CPU-adaptive quality that do not happen; dormant path.
- **Suggested Fix**: Either apply the ratio to the compressor (rebuilding on fingerprint change) and gate stages on `performance_mode`, or delete the unused outputs so stats stop implying behaviour.

### D3-11: Engine queue pointer / concurrent track-changing operations (context, not re-filed)
- **Severity**: LOW
- **Dimension**: Player State Machine
- **Location**: `auralis/player/player_file_loading_mixin.py:51-88`, `auralis/player/player_queue_navigation_mixin.py:59-217`
- **Status**: Existing: #5937 (engine queue pointer does not follow `load_file`), #6082 (track-changing operations serialised by four unrelated locks)
- **Description**: Both re-confirmed in the current tree: `load_file` never moves `queue.current_index`, and `load_file` / `next_track` / `previous_track` / `set_queue` share no common lock (also lets a failed concurrent load call `set_error()` after another load succeeded, via the check-then-set in `_note_failed_load`, `player_file_loading_mixin.py:97-100`). The fuzz run exercising these concurrently found no deadlock and no bounds violation, only logical interleavings.
- **Evidence**: see the two issues.
- **Impact**: See the issues.
- **Suggested Fix**: See the issues.

### D4-05: Pre-decode size budget and free-space check use the source channel count, not the 2 channels FFmpeg actually decodes
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:101-108,151-153`; `auralis/io/loaders/ffmpeg_command.py:33`
- **Status**: NEW
- **Description**: `build_ffmpeg_cmd` folds anything above 2 channels with `-ac 2` (`decoded_channel_count`), so the temp WAV and the resulting array are stereo. `_probe_or_fail` and `require_decode_space` still size the decode with the probed native channel count. For the soundfile path using native channels is right (the full multichannel buffer is read before the downmix), but not for FFmpeg.
- **Evidence**: 5.1 AAC M4A, 4 s, 48 kHz, `AURALIS_MAX_DECODED_BYTES=3000000`: rejected with "exceeds maximum decoded size (4s x 48000 Hz x 6ch x 4B)" although the stereo decode is 1.5 MB. At the default 6 GiB budget a 5.1 AAC/ALAC file longer than about 93 minutes (48 kHz) is refused although its stereo decode is a third of that.
- **Impact**: Over-rejection of long multichannel FFmpeg-format files, and a 3x over-reservation of temp space. Rare for music.
- **Suggested Fix**: Pass `decoded_channel_count(source_channels)` to `oversize_decode_detail` and `require_decode_space` in the FFmpeg path (the scanner's `oversize_probe_detail` can keep the native count or use the same helper for FFmpeg formats).

### D4-06: Absolute file paths reach `ModuleError` strings and WARNING logs on the libsndfile paths (sibling of #4806 / #4366)
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/soundfile_loader.py:165-166`; `auralis/io/audio_probe.py:68-70`; `auralis/io/loaders/ffmpeg_loader.py:174-175,214-215`
- **Status**: NEW (the #4806 fix and its test cover only the FFmpeg/ffprobe raise sites)
- **Description**: `ModuleError`'s contract (`logging.py`) is that the path travels in `.path`, never in the string. The `except Exception as e: raise ModuleError(f"{Code.ERROR_LOADING}: {str(e)}")` in `load_with_soundfile` embeds libsndfile's message, which contains the full path (`Error opening '/abs/path/txt.wav': Format not recognised.`). `get_audio_info` stores the same `str(e)` in `info_dict['error']` and logs `warning(f"Could not get audio info for {file_path}: {e}")` at WARNING with the full path, against the "absolute paths at DEBUG only" rule of #4366/#4806.
- **Evidence**: `str(load_audio('/abs/dir/txt.wav'))` includes `/abs/dir/txt.wav`.
- **Impact**: None today: the backend maps errors through `_safe_error_message` and never forwards the string, and the app is localhost-only. It is the exact "one refactor from exposure" state #4806 set out to remove, now only partially removed.
- **Suggested Fix**: Raise `ModuleError(code, path=str(file_path))` with a redacted reason (for example `redact_subprocess_output(str(e), known_path=...)`) and log the path at DEBUG only.

### D4-07: A `temp_folder` that does not exist now raises a raw `FileNotFoundError` instead of being created
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:125-136,150-154`; `auralis/io/loaders/ffmpeg_space.py:28`
- **Status**: NEW
- **Description**: `_temp_wav_path` creates the folder (`temp_dir.mkdir(exist_ok=True)`), but `require_decode_space` (added by #5734/#6166) runs first and calls `shutil.disk_usage(temp_folder)`, which fails on a folder that does not exist yet, so the `mkdir` is never reached. The exception is also outside `_decode_wav`'s `try`, so it is neither a `ModuleError` nor cleaned. (The `mkdir` also lacks `parents=True`.)
- **Evidence**: `load_audio('s.mp3', temp_folder='<existing parent>/newtmp')` raises `FileNotFoundError: [Errno 2] No such file or directory: '.../newtmp'`.
- **Impact**: Public `load_audio(temp_folder=...)` contract regression. No in-tree caller passes a missing directory (all pass `mkdtemp`/`TemporaryDirectory`), so nothing breaks today.
- **Suggested Fix**: Call `_temp_wav_path`'s directory creation (with `parents=True`) before `require_decode_space`, or have `require_decode_space` measure the nearest existing ancestor.

### D5-02: `true_peak_4x` zero-pads each write region, so edge overshoot can set the file's correction gain (sibling of closed #6327)
- **Severity**: LOW
- **Dimension**: Chunked Mastering Loop
- **Location**: `auralis/core/mastering_chunk_assembly.py:104-116`; max accumulation at `auralis/core/mastering_chunk_loop.py:227-229`
- **Status**: NEW (same defect class as closed #6327, fixed only in `analysis/loudness_true_peak.py`)
- **Description**: #6327 fixed the `LoudnessMeter` true peak by reflection-padding each block before `resample_poly` and dropping the context. `true_peak_4x` still calls `resample_poly(write_region, 4, 1, axis=0)` directly. The default zero padding turns a non-zero block edge into a step, so Gibbs ringing overshoots at the first and last ~dozens of samples of every ~30 s write region. The measurement pass keeps the maximum over all regions (the file's first and last regions included) and `two_pass_correction_gain` turns it into the uniform attenuation.
- **Evidence**: Same sample data through both implementations, 3 s regions, 200 trials each:
  ```
  limited noise : bias 0.000 dB mean / 0.000 dB max
  hot sustained tone @0.8 : bias +0.369 dB mean / +1.079 dB max
  ```
  (`true_peak_4x` vs `true_peak_linear` from `loudness_true_peak.py`.) Typical dense music is unaffected. A sustained near-peak tone (synth bass, organ) at a region edge makes the whole master up to about 1 dB quieter than the -0.5 dBTP target needs.
- **Impact**: Up to about 1 dB of needless level loss for material with a sustained tone near peak at a 30 s boundary or the file ends. Conservative direction, so no clipping risk.
- **Suggested Fix**: Make `true_peak_4x` call (or share) `true_peak_linear` from `analysis/loudness_true_peak.py` instead of re-implementing the oversampling. Keep the sample-peak fallback.

### D5-03: `file_gain` has no floor, so near-silent (dither-only) input is mastered to about -9 dBFS RMS
- **Severity**: LOW
- **Dimension**: Chunked Mastering Loop
- **Location**: `auralis/core/mastering_branches/continuous.py:263-269`; pre-scan at `auralis/core/mastering_prepare.py:215-226`
- **Status**: NEW (offline sibling of closed #5551, which fixed this class only in the hybrid normaliser)
- **Description**: `file_gain = adapted_peak / db_to_amplitude(song_peak_db)`. `SILENCE_FLOOR_DB` (-96 dB) is substituted only when the peak is exactly 0. Any non-zero peak, even one LSB of dither, divides 0.87 by an arbitrarily small number. The two-pass correction can only attenuate, so it caps at 0.99 but never prevents the boost.
- **Evidence**: Probe, 20 s of +/-1 LSB-style noise:
  ```
  in peak 3e-05 -> out peak 0.555, rms -9.2 dBFS
  in peak 3e-06 -> out peak 0.514, rms -9.3 dBFS
  in peak 1e-07 -> out peak 0.537, rms -9.3 dBFS
  ```
  That is +80 to +137 dB of gain on noise.
- **Impact**: A "silent" or hidden pre-gap track, or a file whose only content is dither, comes out as loud broadband noise. Exotic in a music library, but a hazard in batch folder mode. The shipped path has a silence early-return; this path does not.
- **Suggested Fix**: When the whole-song peak is below a floor (for example -60 dBFS), use `file_gain = 1.0` or skip processing and copy through. Alternatively clamp `file_gain` to a sane maximum.

### D5-04: Offline loop reads native WAV directly and bypasses the loaders' truncation check, so a truncated stereo WAV masters "successfully" to a short file
- **Severity**: LOW
- **Dimension**: Chunked Mastering Loop
- **Location**: `auralis/core/simple_mastering.py:179-198` (native branch; only the >2-channel case reaches a loader); `auralis/core/mastering_prepare.py:125-131`; `auralis/core/mastering_chunk_assembly.py:67-77`
- **Status**: NEW (sibling of closed #3441/#3313/#5589/#4131, which closed this gap on `loader.py` and `load_with_soundfile`)
- **Description**: `load_with_soundfile` compares the RIFF-declared size against the real file size because libsndfile silently shrinks `frames` to the data that exists. The mastering path opens `sf.SoundFile` directly for 1-2 channel native files. The FFmpeg branch gets `check_truncation_frames`, and the >2-channel branch goes through `load_with_soundfile`. Plain stereo WAV/AIFF gets neither. `total_frames` is taken from the shrunk header, so `chunks_processed == total_chunks`, no error is raised, and the result dict reports success.
- **Evidence**: 80 s stereo WAV cut to 55% and to 80% of its bytes:
  ```
  0.55 info frames 1940395 expected 3528000 -> master OK out frames 1940395 chunks 2
  0.8  info frames 2822397 expected 3528000 -> master OK out frames 2822397 chunks 3
  ```
  (A truncated FLAC does fail loudly: "flac decoder lost sync". Only the WAV/AIFF/AU family is silent.)
- **Impact**: A partially copied or downloaded WAV silently yields a shorter master. The app's loaders warn at <90% and reject at <10%; the CLI does neither.
- **Suggested Fix**: Call the declared-size truncation check (`_get_wav_declared_size` / `get_aiff_au_declared_size` logic) in `prepare_file` before the chunk loop for native-format inputs, and raise or warn the same way as the loaders.

### D5-05: Stage 1 clip-prevention soft-clips over-full-scale input, then `file_gain` divides by the pre-clip peak, so the master is attenuated twice
- **Severity**: LOW
- **Dimension**: Chunked Mastering Loop
- **Location**: `auralis/core/mastering_process_chunk.py:94-114` (Stage 1 keyed on per-chunk input peak); `auralis/core/mastering_branches/continuous.py:263-269` (`file_gain` keyed on the pre-Stage-1 song peak)
- **Status**: NEW (adjacent to closed #6320; its test only goes up to input peak 0.999)
- **Description**: For any chunk whose input peak exceeds -0.5 dBFS, Stage 1 soft-clips the peaks down to -0.5...-2 dB. `file_gain` is then `adapted_peak / input_peak` of the unclipped signal. For an input peak above 1.0 (float sources, and the FLOAT multichannel downmix that #6316 deliberately lets exceed full scale), the peaks are cut non-linearly, then scaled by `0.87/peak` as well. The two-pass correction is attenuate-only, so it cannot recover the headroom.
- **Evidence**: The #5694 fixture (`_music_like`), pipeline defaults otherwise:
  ```
  in peak 0.600 -> out peak 0.943, rms -23.53 dB
  in peak 0.999 -> out peak 0.794, rms -23.55
  in peak 1.300 -> out peak 0.610, rms -24.06
  in peak 1.600 -> out peak 0.496, rms -24.62
  ```
  Over-full-scale input produces peaks of -3 to -6 dBFS and a progressively quieter master. The loudness-parity guarantee tested by #6320 stops at 0.999.
- **Impact**: 5.1 downmixes and float sources with overs come out 1-2 dB quieter, with distortion from the Stage 1 tanh on the overs, though a linear gain would have sufficed.
- **Suggested Fix**: Derive `file_gain` from the post-Stage-1 peak, or skip Stage 1 when `file_gain < 1` already covers the excess. Extend the #6320 test to input peaks above 1.0.

### D6-05: `phase_coherence` reports 0.0 for any realistic signal level
- **Severity**: LOW
- **Dimension**: Analysis Subsystem
- **Location**: `auralis/analysis/phase_correlation.py:222-262` (`_calculate_phase_coherence`, line 240), `auralis/analysis/fingerprint/metrics/safe_operations.py:30-56`
- **Status**: NEW
- **Description**: The coherence `|Pxy|^2 / (Pxx*Pyy)` is a ratio of power-spectral-density products (~1e-13 for -20 dBFS material) divided with `SafeOperations.safe_divide`, whose guard is the amplitude epsilon `AMPLITUDE_EPS = 1e-10`. Denominators under 1e-10 take the `fallback=0.0`, so the whole spectrum reads 0.
- **Evidence**: `PhaseCorrelationAnalyzer(44100).analyze_correlation` on a perfectly coherent stereo pair (R = 0.9 L): amplitude 3.0 -> 1.0, 1.0 -> 0.998, 0.5 -> 0.671, 0.3 / 0.1 / 0.03 / 0.01 -> overall/low/mid/high coherence all 0.0.
- **Impact**: `phase_coherence` (and the `coherence_spectrum` list) in `QualityMetrics.assess_quality` detailed metrics is always 0 for normal material. No scoring consumer reads it today (`rg coherence` finds none), so the impact is a wrong reported metric on an advisory/offline path.
- **Suggested Fix**: Use `scipy.signal.coherence` (or divide with a relative guard, e.g. `denominator > 1e-12 * max(denominator)`) instead of the amplitude epsilon.

### D6-06: `FingerprintStorage.load()` raises on malformed cache files instead of returning None
- **Severity**: LOW
- **Dimension**: Analysis Subsystem
- **Location**: `auralis/analysis/fingerprint/fingerprint_storage.py:163-225` (`except (json.JSONDecodeError, OSError, KeyError)`)
- **Status**: NEW
- **Description**: The contract is "tuple if valid, None otherwise", and `_is_dead` already treats these files as dead, but `load()` only catches JSON/OS/Key errors. A non-UTF-8 file raises `UnicodeDecodeError` and valid JSON that is not an object (`[1,2]`, `null`, `"x"`) raises `AttributeError` at `content.get`. Unlike the sidecar path (`sidecar_fingerprint_check.py`, #6147/#6175) the dimension values are also not checked for finite/sane numbers.
- **Evidence**: Writing `b'\xff\xfe\x00\x80'`, `b'[1,2]'`, `b'null'` as the entry for a file: `load()` raises UnicodeDecodeError / AttributeError / AttributeError / AttributeError; `_is_dead()` returns True for all four.
- **Impact**: The two production callers wrap it in `except Exception` (`FingerprintService._load_from_file_cache`, backend `load_from_file`) and fall back to re-extraction, so the effect is a WARNING and a missed cache hit; `is_valid()` (public) would raise.
- **Suggested Fix**: Catch `(ValueError, OSError, AttributeError, TypeError)` (UnicodeDecodeError is a ValueError) and reuse `fingerprint_block_is_valid` for the dimension values.

### D6-07: No handshake between the compiled Rust engine and `FINGERPRINT_ALGORITHM_VERSION`
- **Severity**: LOW
- **Dimension**: Analysis Subsystem
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs:22-31` (module exposes only `compute_fingerprint`), `auralis/analysis/fingerprint/rust_fingerprint.py:123-132` (`fingerprint_engine_error` only tests `import auralis_dsp`), `auralis/__version__.py:108`
- **Status**: NEW
- **Description**: The algorithm version lives only in Python; the algorithm itself is compiled. A checkout that bumps the constant (or changes `.rs`) without `maturin develop` stamps rows and sidecars "v16" that were measured by the older binary, and they are never recomputed; `/api/health` still reports `fingerprint_engine_available=true`. The v13-v16 history shows the constant is bumped alongside Rust edits by hand.
- **Evidence**: `dir(auralis_dsp)` is `['compute_fingerprint', 'compute_fingerprint_wrapper']`; no `ALGORITHM_VERSION`/`__version__` binding, no check in `fingerprint_engine_error()`.
- **Impact**: Dev/CI environments with a stale wheel silently write wrongly stamped fingerprints; release builds are unaffected as long as the wheel is built from the tagged tree.
- **Suggested Fix**: Export `ALGORITHM_VERSION` from the crate (single constant in Rust), have `fingerprint_engine_error()` compare it with `FINGERPRINT_ALGORITHM_VERSION` and report a mismatch.

### D6-08: `ContentAnalyzer` swallows `FingerprintUnavailable` at debug level
- **Severity**: LOW
- **Dimension**: Analysis Subsystem
- **Location**: `auralis/core/analysis/content_analyzer.py:145-155`
- **Status**: NEW (sibling of #6107, which fixed `ContinuousMode`)
- **Description**: `except Exception as e: debug(...); content_profile["fingerprint"] = None` turns an engine fault (missing wheel, non-finite result) into "non-critical" and the `AdaptiveMode`/`HybridMode` run proceeds without fingerprint-driven targets, reported as success. #6107 removed exactly this bypass for the default path.
- **Impact**: Adaptive/hybrid jobs silently lose fingerprint enhancement when the engine fails; only a debug log line says so.
- **Suggested Fix**: Let `FingerprintUnavailable` propagate (catch only the documented skip), or log at WARNING and mark the job result.

### D6-09: Duplicated header-duration probes and layout-inconsistent dead parameter in the fingerprint loaders
- **Severity**: LOW
- **Dimension**: Analysis Subsystem
- **Location**: `auralis/analysis/fingerprint/body_window.py:18-30`, `auralis/analysis/fingerprint/track_audio.py:95-110`, `auralis/analysis/fingerprint/windowed_loading.py:94-101,131-137`, `auralis/analysis/fingerprint/fingerprint_service.py:166-181`
- **Status**: NEW
- **Description**: Four copies of "duration from the container header without decoding" (`track_audio.probe_duration_s`, `body_window._probe_duration_s`, and inline copies in `load_ffmpeg_windows` / `load_librosa_windows`) with slightly different failure behaviour (the `body_window` copy returns the raw `.get('duration')`, the librosa one swallows to None). Separately, `FingerprintService.get_or_compute(audio, sr)` computes the sidecar duration as `len(audio) / sr` (samples-first) while `load_track_audio`/`analysis_span_s` treat `audio` as channels-first (`audio.shape[-1]`); no production caller passes `audio`, so the parameter is dead and inconsistent.
- **Impact**: Maintenance risk (a fix to one probe misses the others); a future caller passing a buffer would get a wrong `duration` stamped into the `.25d`.
- **Suggested Fix**: Use `track_audio.probe_duration_s` everywhere (move it next to `windows.py`); drop the `audio`/`sr` parameters from `get_or_compute` or fix the layout in one place.

### D6-10: Misdocumented or miscomputed secondary analysis values (schema range, rolloff percent, loudness window block counts, chroma bin, unused ML features)
- **Severity**: LOW
- **Dimension**: Analysis Subsystem
- **Location**: `auralis/analysis/fingerprint/schema.py:92` (`phase_correlation` declared `NORMALIZED 0.0-1.0`; Rust and the v003 migration use -1..1), `auralis/analysis/mastering_fingerprint.py:15,86-90` (docstring says 95% rolloff, `librosa.feature.spectral_rolloff` default is 0.85; comment says the 90 s cap matches "every other fingerprint path"), `auralis/analysis/loudness_meter.py:36-37,142-170` (`momentary_blocks=4` / `short_term_blocks=30` are commented as 400 ms / 3 s but every caller feeds 400 ms blocks, i.e. 1.6 s / 12 s; no consumer reads them), `auralis/analysis/ml/feature_extractor_mfcc.py:54` (`int(midi_note) % 12` truncates instead of rounding, splitting each pitch class across two chroma bins), `auralis/analysis/ml/feature_extractor.py:131-142` (MFCC/chroma/tonnetz are computed on every classify but only the ones in `_calculate_genre_score` are scored; they are not).
- **Status**: NEW
- **Description**: A set of small inconsistencies between what is documented and what is computed, none on the default mastering path. The `phase_correlation` schema range is consumed only as documentation (the normalizer is percentile fitted), but `target_derivation.py:90` repeats "spans 0-1".
- **Impact**: Misleading comments and wasted work; `momentary_lufs`/`short_term_lufs` are mislabelled windows if anyone starts using them.
- **Suggested Fix**: Correct the schema entry and docstrings, derive block counts from the actual block duration (or drop the two outputs), `round(midi_note)` in chroma, and skip the unused feature groups.

### D6-11: MasteringFingerprint still reads only the 90 s body window
- **Severity**: LOW
- **Dimension**: Analysis Subsystem
- **Location**: `auralis/analysis/mastering_fingerprint.py:80-142`
- **Status**: Existing: #6346
- **Description**: Re-verified: the 7-field fingerprint decodes one 90 s window at `window_offset_s(0.5, ...)` while the 25D fingerprint is whole-track; the #6143/#6323 fixes (body placement, shared `stereo_window`) are in place. Product decision pending in #6346; nothing new to add.
- **Impact**: See #6346.
- **Suggested Fix**: See #6346.

### D7-04: Numeric ID3v1 genre references are stored verbatim ("(17)", "(17)Rock", "17")
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/metadata_extractor.py:133,150-160` (`_raw_values`), `:182-183,134-140` (genre handling)
- **Status**: NEW
- **Description**: For ID3 text frames `_raw_values` returns `frame.text` (the raw strings). A TCON frame written by older taggers/players holds `(17)`, `(17)Rock` or `17`; mutagen's `TCON.genres` resolves those to names but the extractor never uses it. The raw token becomes a `Genre` row.
- **Evidence**: Executed with a real `mutagen.id3.ID3`: `TCON(text=['(17)'])` -> `.genres == ['Rock']` but `extract_metadata(...)['genre'] == '(17)'`; `['(17)Rock','(9)Metal']` -> `['(17)Rock','(9)Metal']`; `['17']` -> `'17'`.
- **Impact**: Old MP3 libraries get genre rows like "(17)" and "(17)Rock" next to "Rock", fragmenting the genre axis (no data loss; fixed by retagging).
- **Suggested Fix**: For a TCON frame read `frame.genres` (which already resolves ID3v1 numbers and the `(n)Name` form) instead of `frame.text`.

### D7-05: Several `tracks`/`albums`/`artists` columns are never written by anything
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/models/track.py:71,74-76,91`; `models/album.py:66-68`; `models/artist.py:40-41`; reader at `auralis/player/integration_library.py:89-103`; `repositories/stats_repository.py:37,57`
- **Status**: NEW (same class as #5755/#6288, which dropped other never-populated columns/fields)
- **Description**: `Track.dr_rating`, `mastering_quality`, `recommended_reference`, `processing_profile`, `skip_count`, `Album.avg_dr_rating/avg_lufs/mastering_consistency` and `Artist.total_plays/avg_mastering_quality` have no writer in `auralis/` or `auralis-web/backend/` (the scanner's track_info never carries `dr_rating`; the only write sites are the allowlist in `update_by_filepath` and `add()`'s `.get('dr_rating')`). They are still serialized by `to_dict()`, `get_library_stats()` reports `average_dr` from an always-NULL column, and the player branch that reads `track.recommended_reference` can never fire.
- **Evidence**: `grep -rn "skip_count|mastering_quality|recommended_reference|processing_profile|total_plays|avg_mastering_quality|mastering_consistency"` over `auralis/` and `auralis-web/backend/` outside `models/` and `tests/` returns only readers/serializers; `dr_rating` has only readers plus pass-through of an absent key.
- **Impact**: Misleading schema/API (always-null "Average DR"), dead branch in the player, extra row width on every track; no runtime failure.
- **Suggested Fix**: Drop them in a forward migration like v26-v28 (or populate them), and remove the dead `recommended_reference` branch.

### D7-06: `get_all_artists()` hydrates every track (with lyrics/comments) for a consumer that needs id/name/artwork_url
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/artist_repository.py:226-253`; sole caller `auralis/cli/fetch_artwork.py:73-100`
- **Status**: NEW
- **Description**: The method eager-loads `Artist.tracks -> Track.album` and `Artist.albums -> Album.tracks` (full Track rows including unbounded `lyrics`/`comments`) for the whole library. `fetch_artwork` reads only `artist.name`, `artist.id`, `artist.artwork_url`. #5084/#5872 fixed the same pattern for the list/page endpoints; this path was left.
- **Evidence**: `fetch_artwork.py:73-100` touches only those three attributes; the repository docstring says "tracks and albums eagerly loaded" because of #2524, not because anyone reads them.
- **Impact**: Memory proportional to library size x lyrics on every run of the CLI (offline tool, hence LOW).
- **Suggested Fix**: Return id/name/artwork_url rows (or the artists with `lazyload`/no relationship options) for this path.

### D7-07: `AlbumArtworkMixin.delete_artwork` unlinks the file before the commit that clears the row
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/album_artwork.py:94-117` (unlink at ~108-112, commit at ~114)
- **Status**: NEW
- **Description**: `update_artwork_path` and `prune_orphans` both unlink the superseded file only after the commit succeeds (the prune adds an `after_commit` hook for exactly that reason). `delete_artwork` does the opposite: `artwork_extractor.delete_artwork(...)` first, then `album.artwork_path = None; session.commit()`. A commit failure (60 s busy timeout on a locked DB) leaves `artwork_path` pointing at a file that is gone.
- **Evidence**: Code order above; the module's own docstring for `prune_orphans` states the rule ("unlinked once the transaction commits, not before").
- **Impact**: Rare dangling `artwork_path` -> artwork route answers with a missing file until re-extraction.
- **Suggested Fix**: Capture the path, commit, then unlink (same order as `update_artwork_path`).

### D7-08: Repository-convention drift: hand-rolled `except: rollback()` and per-item `expunge(obj)` on eager-loading reads remain
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: hand-rolled rollback: `genre_repository.py:142,179,208`; `album_artwork.py:90,115,156`; `track_repository_mutation.py:232,275`; `track_repository_maintenance.py:82,164,233`; `artist_repository.py:287`; `similarity_graph_repository.py:40,60,79,103`; `settings_repository.py:180,224`; `fingerprint_stats_repository.py:107`; `fingerprint_scheduler_repository.py:296`; `factory.py:209` (`reset_library` builds its own session). Per-item expunge on reads that eager-load relationships: `track_repository_lookup.py:52,90`; `track_repository_search.py:86,103,133,164,196,251`; `artist_repository.py:299` (`get_all_artists`); `fingerprint_query_mixin.py:268-272`
- **Status**: NEW (convention only; each item is the shape the checklist says to flag)
- **Description**: #5117 made `_session_scope` roll back on any escaping exception, so these `except ...: session.rollback(); raise` blocks are redundant, and `base._first_detached/_all_detached` exist because `expunge(obj)` does not cascade. No behavioural defect was found in any of them: `session.close()` in the scope's `finally` detaches the related objects anyway, so the loaded attributes stay readable.
- **Evidence**: grep of `rollback()` and `expunge(` in `auralis/library/repositories/`.
- **Impact**: Maintenance only: a future edit can start relying on the per-item form and reintroduce #4236-style detached reads.
- **Suggested Fix**: Opportunistic cleanup: drop the redundant rollbacks, use `_all_detached` for eager-loading list reads, and run `reset_library` through `_session_scope`.


## Relationships

- **Near-silence gain family**: D1-01 (hybrid `normalize`), D5-03 (offline `file_gain`), D5-05 (double attenuation of over-full-scale input in the same `file_gain`), and closed #5551. One shared "gain floor / knee" helper would close all three.
- **Fingerprint v17 bundle**: D6-01 (f32 accumulation), D6-02 (centroid/rolloff window scope), D1-03 (mono-sum `lufs`) all change what a dimension measures, so they should land together with one version bump and one restamp. D6-07 (no engine/version handshake) is the guard that would have caught a stale build.
- **Same defect class as closed fixes, left unfixed in siblings**: D5-02 vs #6327 (true-peak edge zero-pad), D4-01 vs #5566 (RF64), D4-03 vs #4112, D2-02 vs #5721, D6-08 vs #6107, D5-04 vs #3441/#5589.
- **Scope-of-analysis theme**: D5-01, D6-02, D6-11 (#6346) all measure a window of the track and apply it to a track-level decision.
- **Player/dormant path**: D3-10 (#5708), D3-09 (#6106), D2-02, D3-06, D3-07 and D1-02 all live in the real-time chain nothing consumes. Resolving #5708 (wire or delete) would retire most of them at once.
- **Library**: D7-01 is amplified by the v30-to-v31 migration (every compilation re-creates albums on the first rescan), and D7-07 touches the same artwork files.

## Prioritized Fix Order

1. **D7-01, D7-02** - user-visible library damage with no recovery path.
2. **D1-01, D5-03, D5-05** - a shared gain-floor fix; protects against noise being mastered to full scale.
3. **Fingerprint v17 bundle: D6-01, D6-02, D1-03** (+ D6-07 guard) - one algorithm bump; improves every downstream decision.
4. **D4-01, D4-02, D4-03, D4-04** - I/O correctness at container edges; D4-01 is silent data loss on very long output.
5. **D6-03** - memory gate bypass for whole-file jobs (OOM risk when combined with the queue).
6. **D5-01, D2-01** - consistency of mastering between streaming and job exports / loudness window scope.
7. **D7-03, D6-04** - metadata/classifier correctness.
8. **Existing issues** (#6109 gapless zero-pad, #6106, #5708, #3481, #5937, #6082, #6346) - already tracked.
9. **LOW findings** - batch by file; D3-04 (negative `start_index`), D6-06 (`load()` raising), D3-01/D3-02 (player state) first, rest as cleanup.
